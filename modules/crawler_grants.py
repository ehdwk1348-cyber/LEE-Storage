"""
국고 지원사업 뉴스 크롤러 모듈
(주)하나티에스 타겟 사업에 특화된 쿼리로 수집

■ 타겟 사업 유형
  - LINC 3.0, RISE, 혁신지원사업 (대학·전문대)
  - 직업교육 혁신지원사업 (특성화고·마이스터고)
  - 스마트팩토리 구축 지원, 디지털 트윈 사업
  - SW·CAD 실습실 구축 관련 예산 확보 소식

■ 수집 전략
  - 1차: 사업 선정/확정 뉴스 쿼리 (선정학교 파악)
  - 2차: 제품군 직접 언급 뉴스 (도입 수요 포착)
  - 필터: CAD·3D·실습·설계 관련 콘텐츠만 통과
"""
import os
import re
import requests
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from utils.db_manager import insert_grants
from dotenv import load_dotenv

load_dotenv()

# 학교명 추출 정규식
_SCHOOL_PATTERN = re.compile(
    r'([가-힣A-Za-z0-9]+(?:대학교|대학|고등학교|마이스터고|폴리텍|전문대학|직업전문학교))'
)

# ──────────────────────────────────────────────
# 쿼리 정의 (하나티에스 타겟 사업 특화)
# ──────────────────────────────────────────────

# 1그룹: 대학/전문대 대형 국고사업 선정 뉴스
GRANT_QUERIES = [
    '"LINC" 대학 선정',
    '"RISE" 대학 선정',
    '"혁신지원사업" 대학 선정',
    '"글로컬대학" 선정',
    '"첨단산업" 대학 선정',
    '"산학협력" 사업비 확보',
    '"디지털 혁신" 대학 선정',
]

# 2그룹: 특성화고·마이스터고 관련 예산 사업
VOCATIONAL_QUERIES = [
    '"직업교육 혁신" 특성화고 선정',
    '"마이스터고" 사업 선정',
    '"특성화고" 실습 장비 예산',
    '"직업교육" 스마트 실습실',
    '"교육청" CAD 실습 예산',
]

# 3그룹: 제품군 직접 언급 도입 뉴스 (도입 수요 직접 포착)
PRODUCT_QUERIES = [
    '"CATIA" 대학 도입',
    '"SolidWorks" 실습실',
    '"솔리드웍스" 학교',
    '"3D CAD" 실습실 구축',
    '"스마트팩토리" 실습 구축',
    '"디지털트윈" 실습실 구축',
    '"3DEXPERIENCE" 교육',
    '"CAD" 특성화고 실습',
]

ALL_QUERIES = GRANT_QUERIES + VOCATIONAL_QUERIES + PRODUCT_QUERIES

# ──────────────────────────────────────────────
# 필터 키워드
# ──────────────────────────────────────────────

# 반드시 포함 (선정·확정 or 제품 도입 맥락)
MUST_INCLUDE = [
    '선정', '확정', '지정', '발표', '사업비', '확보', '수주',
    '도입', '구축', '납품', '계약', '체결', '착수',
    '실습실', 'CAD', '카티아', '솔리드', '3D',
]

# 제외 키워드 (무관 기사)
MUST_EXCLUDE = [
    '모집', '교육생 모집', '참가자 모집', '신입생', '수강생',
    '특강', '설명회', '채용', '인턴', '알바', '봉사',
    '부동산', '아파트', '분양', '주식', '코인',
]

# 하나티에스 관련 콘텐츠 확인 (2차 필터)
RELEVANCE_KEYWORDS = [
    'CAD', '캐드', '3D', 'CATIA', '카티아', 'SolidWorks', '솔리드웍스',
    '설계', '실습', '스마트팩토리', '디지털트윈', '메카트로닉스',
    '기계', '제조', '엔지니어링', '직업교육', '특성화', '마이스터',
    '산학협력', 'PLM', 'PDM', '시뮬레이션',
]


def clean_html(raw: str) -> str:
    return BeautifulSoup(raw, "html.parser").get_text()


def extract_school_name(text: str) -> str:
    matches = _SCHOOL_PATTERN.findall(text)
    if not matches:
        return "확인 필요(기사 원문 참조)"
    return max(matches, key=len)


def _is_relevant(title: str, description: str) -> bool:
    """하나티에스 제품군·타겟 시장과 관련 있는 기사인지 확인."""
    full = (title + ' ' + description).upper()
    return any(kw.upper() in full for kw in RELEVANCE_KEYWORDS)


def fetch_grant_news() -> int:
    """
    네이버 뉴스 API로 하나티에스 타겟 사업 선정 뉴스를 수집합니다.
    반환값: 신규 저장 건수
    """
    client_id     = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET_KEY")

    if not client_id or not client_secret:
        print("[네이버 뉴스] API 키 없음")
        return 0

    headers = {
        "X-Naver-Client-Id":     client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    grants_data = []
    seen_links  = set()

    for query in ALL_QUERIES:
        enc_query = urllib.parse.quote(query)
        # sim(유사도순) + date(최신순) 두 가지로 수집
        for sort in ("date", "sim"):
            url = (
                f"https://openapi.naver.com/v1/search/news.json"
                f"?query={enc_query}&display=10&sort={sort}"
            )
            try:
                res = requests.get(url, headers=headers, timeout=10)
                res.raise_for_status()
                items = res.json().get('items', [])
            except Exception as e:
                print(f"[네이버 뉴스 오류] {query}/{sort}: {e}")
                continue

            for item in items:
                link = item.get('originallink') or item.get('link', '')
                if link in seen_links:
                    continue
                seen_links.add(link)

                title       = clean_html(item.get('title', ''))
                description = clean_html(item.get('description', ''))
                full_lower  = (title + ' ' + description).lower()

                # 1차 필터: 선정·확정·도입 맥락
                if not any(k in full_lower for k in MUST_INCLUDE):
                    continue

                # 2차 필터: 광고·모집·무관 기사 제외
                if any(k in full_lower for k in MUST_EXCLUDE):
                    continue

                # 3차 필터: 하나티에스 제품군·타겟 시장 관련 여부
                if not _is_relevant(title, description):
                    continue

                school = extract_school_name(title + ' ' + description)

                grants_data.append({
                    'project_name':   title,
                    'agency':         '네이버 뉴스',
                    'selected_school': school,
                    'budget_scale':   '기사 원문 참조',
                    'notice_url':     link,
                    'status':         '선정완료(뉴스)',
                    'crawled_at':     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

    if not grants_data:
        return 0

    try:
        return insert_grants(grants_data)
    except Exception as e:
        print(f"[grants 저장 오류] {e}")
        return 0
