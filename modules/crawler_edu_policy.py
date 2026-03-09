"""
교육부 보도자료 자동 감시 크롤러

■ 목적
  - LINC 3.0 / RISE / 글로컬대학30 등 선정교 발표 뉴스를 자동 수집
  - 신규 선정교 발견 시 target_schools 테이블에 자동 추가 후보 알림

■ 수집 채널
  1. 네이버 뉴스 API (기존 crawler_grants.py 패턴 재활용)
  2. 교육부 보도자료 RSS (향후 확장 가능)

■ 수집 키워드
  - "LINC 3.0" 선정 / "RISE" 선정 / "글로컬대학" 선정
  - "대학재정지원" 선정 / "산학협력" 선정 / "혁신지원사업" 선정

■ DB 저장
  - edu_policy_news 테이블에 뉴스 기사 저장
  - 선정교 자동 추출 → target_schools 추가 후보로 표시
"""
import os
import re
import requests
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from utils.db_manager import DB_PATH
from dotenv import load_dotenv
import sqlite3

load_dotenv()

# 학교명 추출 정규식
_SCHOOL_PATTERN = re.compile(
    r'([가-힣A-Za-z0-9]+(?:대학교|대학|폴리텍|전문대학))'
)

# ──────────────────────────────────────────────
# 감시 키워드 (선정교 발표 전용)
# ──────────────────────────────────────────────

POLICY_QUERIES = [
    '"LINC 3.0" 선정',
    '"LINC" 대학 선정 발표',
    '"RISE" 대학 선정',
    '"RISE" 사업 선정',
    '"글로컬대학" 선정 발표',
    '"글로컬대학30" 선정',
    '"대학재정지원" 선정',
    '"혁신지원사업" 대학 선정',
    '"산학협력선도대학" 선정',
    '"첨단분야 혁신융합대학" 선정',
]

# 반드시 포함 (선정·발표 맥락)
MUST_INCLUDE = [
    '선정', '확정', '발표', '지정', '선발', '공고',
]

# 제외 키워드
MUST_EXCLUDE = [
    '모집', '접수', '신청', '채용', '인턴', '수강',
    '부동산', '아파트', '주식',
]


def _clean_html(raw: str) -> str:
    """HTML 태그 제거."""
    return BeautifulSoup(raw, "html.parser").get_text()


def _extract_schools(text: str) -> list:
    """텍스트에서 학교명 목록 추출."""
    matches = _SCHOOL_PATTERN.findall(text)
    # 중복 제거, 순서 유지
    seen = set()
    result = []
    for m in matches:
        if m not in seen and len(m) >= 4:  # 최소 4글자 이상
            seen.add(m)
            result.append(m)
    return result


def _init_edu_policy_table():
    """edu_policy_news 테이블 생성 (없으면)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS edu_policy_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            source_url TEXT UNIQUE,
            pub_date TEXT,
            detected_schools TEXT,
            policy_type TEXT,
            is_processed INTEGER DEFAULT 0,
            crawled_at TEXT
        )
    ''')
    conn.commit()
    conn.close()


def fetch_edu_policy_news() -> int:
    """
    네이버 뉴스 API로 교육부 대학 재정지원사업 선정 발표 뉴스를 수집합니다.
    반환값: 신규 저장 건수
    """
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET_KEY")

    if not client_id or not client_secret:
        print("[교육정책 뉴스] 네이버 API 키 없음")
        return 0

    # 테이블 초기화
    _init_edu_policy_table()

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    new_count = 0
    seen_links = set()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for query in POLICY_QUERIES:
        enc_query = urllib.parse.quote(query)
        for sort in ("date", "sim"):
            url = (
                f"https://openapi.naver.com/v1/search/news.json"
                f"?query={enc_query}&display=20&sort={sort}"
            )
            try:
                res = requests.get(url, headers=headers, timeout=10)
                res.raise_for_status()
                items = res.json().get('items', [])
            except Exception as e:
                print(f"[교육정책 뉴스 오류] {query}/{sort}: {e}")
                continue

            for item in items:
                link = item.get('originallink') or item.get('link', '')
                if link in seen_links or not link:
                    continue
                seen_links.add(link)

                title = _clean_html(item.get('title', ''))
                description = _clean_html(item.get('description', ''))
                full_text = title + ' ' + description
                full_lower = full_text.lower()

                # 1차 필터: 선정/발표 맥락 확인
                if not any(k in full_lower for k in MUST_INCLUDE):
                    continue

                # 2차 필터: 무관 기사 제외
                if any(k in full_lower for k in MUST_EXCLUDE):
                    continue

                # 사업 유형 판별
                policy_type = _detect_policy_type(full_text)
                if not policy_type:
                    continue

                # 학교명 추출
                schools = _extract_schools(full_text)
                schools_str = ', '.join(schools) if schools else ''

                pub_date = item.get('pubDate', '')

                # DB 저장 (중복 제거: source_url UNIQUE)
                try:
                    cursor.execute(
                        "INSERT OR IGNORE INTO edu_policy_news "
                        "(title, description, source_url, pub_date, "
                        " detected_schools, policy_type, crawled_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (title, description, link, pub_date,
                         schools_str, policy_type, now)
                    )
                    if cursor.rowcount > 0:
                        new_count += 1
                except Exception:
                    continue

    conn.commit()
    conn.close()
    return new_count


def _detect_policy_type(text: str) -> str:
    """기사 텍스트에서 사업 유형을 판별합니다."""
    text_upper = text.upper()
    if 'LINC' in text_upper or '링크' in text:
        return 'LINC 3.0'
    if 'RISE' in text_upper or '라이즈' in text:
        return 'RISE'
    if '글로컬' in text:
        return '글로컬대학30'
    if '혁신지원' in text or '재정지원' in text:
        return '혁신지원사업'
    if '산학협력' in text or '첨단분야' in text:
        return '산학협력'
    return ''


def get_edu_policy_news() -> list:
    """저장된 교육정책 뉴스 목록을 반환합니다."""
    _init_edu_policy_table()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, description, source_url, pub_date, "
            "       detected_schools, policy_type, is_processed, crawled_at "
            "FROM edu_policy_news "
            "ORDER BY id DESC "
            "LIMIT 50"
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'id': r[0], 'title': r[1], 'description': r[2],
                'source_url': r[3], 'pub_date': r[4],
                'detected_schools': r[5], 'policy_type': r[6],
                'is_processed': r[7], 'crawled_at': r[8],
            }
            for r in rows
        ]
    except Exception:
        return []


def mark_news_processed(news_id: int) -> bool:
    """뉴스 기사를 '처리완료' 로 마킹합니다."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE edu_policy_news SET is_processed = 1 WHERE id = ?",
            (news_id,)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False
