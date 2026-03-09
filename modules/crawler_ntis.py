"""
NTIS (국가과학기술정보서비스) 연구과제 모니터링 모듈

■ 목적
  - CAD/CAM/설계/시뮬레이션 관련 R&D 과제를 수주한 교수를 자동 식별
  - 연구비 내 장비비 보유 = 즉시 구매 가능성 높음

■ 수집 전략
  - 네이버 뉴스 API로 NTIS/연구과제 관련 뉴스 수집 (NTIS OpenAPI는 별도 신청 필요)
  - 학술 키워드 기반 필터링: CAD, CAM, 3D 설계, 디지털트윈, 시뮬레이션 등
  - 대학명 매칭 → target_schools와 교차 분석

■ 향후 확장
  - NTIS OpenAPI 키 확보 시 직접 과제 검색으로 전환
"""
import os
import re
import requests
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from utils.db_manager import insert_ntis_projects, insert_purchase_signal
from dotenv import load_dotenv

load_dotenv()

# 학교명 추출 정규식
_SCHOOL_PATTERN = re.compile(
    r'([가-힣A-Za-z0-9]+(?:대학교|대학|폴리텍|전문대학))'
)

# 연구자명 추출 정규식 (예: "홍길동 교수")
_RESEARCHER_PATTERN = re.compile(
    r'([가-힣]{2,4})\s*(?:교수|연구원|박사|센터장|단장)'
)

# ──────────────────────────────────────────────
# 검색 키워드 (R&D 과제 관련)
# ──────────────────────────────────────────────

NTIS_QUERIES = [
    '"연구과제" "CAD" 대학',
    '"연구과제" "설계 소프트웨어" 대학',
    '"연구장비" "3D" 대학 구매',
    '"장비비" "CAD" 교수',
    '"장비비" "시뮬레이션" 대학',
    '"디지털트윈" 연구과제 대학 선정',
    '"스마트제조" 연구과제 대학',
    '"CATIA" 연구 대학',
    '"SolidWorks" 연구 대학',
    '"유한요소해석" 연구과제',
    '"기계설계" 연구장비 대학',
    '"제조혁신" 연구과제 선정',
]

# 관련성 키워드
RELEVANCE_KW = [
    'CAD', '캐드', 'CATIA', '카티아', 'SolidWorks', '솔리드웍스',
    '3D 설계', '3D설계', '3D 모델링', 'PLM', '디지털트윈', 'digital twin',
    '시뮬레이션', 'SIMULIA', 'FEA', '유한요소', '기계설계', '제조',
    '스마트팩토리', '스마트제조', '메카트로닉스', 'CAM', 'CAE',
]

# 예산/장비비 관련 키워드
BUDGET_KW = [
    '장비비', '연구비', '사업비', '예산', '억원', '천만원', '구매', '도입', '구축',
]


def _clean_html(raw: str) -> str:
    return BeautifulSoup(raw, "html.parser").get_text()


def _extract_school(text: str) -> str:
    matches = _SCHOOL_PATTERN.findall(text)
    return max(matches, key=len) if matches else ''


def _extract_researcher(text: str) -> str:
    match = _RESEARCHER_PATTERN.search(text)
    return match.group(1) if match else ''


def _calc_relevance(title: str, desc: str) -> int:
    """관련성 점수 산정 (0~100)."""
    text = (title + ' ' + desc).upper()
    score = 0

    # 제품명 직접 언급 (+30)
    product_kw = ['CATIA', '카티아', 'SOLIDWORKS', '솔리드웍스', '3DEXPERIENCE', 'SIMULIA']
    if any(k.upper() in text for k in product_kw):
        score += 30

    # CAD/CAM 관련 (+20)
    cad_kw = ['CAD', 'CAM', 'CAE', 'PLM', '3D설계', '3D 설계', '3D 모델링']
    if any(k.upper() in text for k in cad_kw):
        score += 20

    # 연구과제/장비비 관련 (+20)
    if any(k in text for k in ['장비비', '연구장비', '연구과제']):
        score += 20

    # 대학/교수 언급 (+15)
    if _SCHOOL_PATTERN.search(title + ' ' + desc):
        score += 15

    # 설계/시뮬레이션 관련 (+15)
    sim_kw = ['시뮬레이션', '디지털트윈', '유한요소', '기계설계', '스마트제조']
    if any(k in text for k in sim_kw):
        score += 15

    return min(score, 100)


def fetch_ntis_research_news() -> int:
    """
    네이버 뉴스 API로 R&D 과제/연구장비 관련 뉴스를 수집합니다.
    반환값: 신규 저장 건수
    """
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET_KEY")

    if not client_id or not client_secret:
        print("[NTIS 모니터링] 네이버 API 키 없음")
        return 0

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    projects = []
    seen_links = set()

    for query in NTIS_QUERIES:
        enc_query = urllib.parse.quote(query)
        for sort in ("date", "sim"):
            url = (
                f"https://openapi.naver.com/v1/search/news.json"
                f"?query={enc_query}&display=15&sort={sort}"
            )
            try:
                res = requests.get(url, headers=headers, timeout=10)
                res.raise_for_status()
                items = res.json().get('items', [])
            except Exception as e:
                print(f"[NTIS 뉴스 오류] {query}/{sort}: {e}")
                continue

            for item in items:
                link = item.get('originallink') or item.get('link', '')
                if link in seen_links or not link:
                    continue
                seen_links.add(link)

                title = _clean_html(item.get('title', ''))
                description = _clean_html(item.get('description', ''))
                full_text = title + ' ' + description

                # 관련성 점수 산정
                rel_score = _calc_relevance(title, description)
                if rel_score < 20:
                    continue

                school = _extract_school(full_text)
                researcher = _extract_researcher(full_text)

                projects.append({
                    'project_id': '',
                    'project_name': title,
                    'lead_agency': school,
                    'lead_researcher': researcher,
                    'lead_department': '',
                    'total_budget': '',
                    'project_period': '',
                    'keywords': query.replace('"', ''),
                    'relevance_score': rel_score,
                    'source_url': link,
                })

                # 점수 50 이상이고 학교명이 감지되면 구매 신호 생성
                if rel_score >= 50 and school:
                    insert_purchase_signal(
                        school_name=school,
                        signal_type='R&D 과제',
                        signal_title=title,
                        signal_detail=f"연구자: {researcher}" if researcher else description[:100],
                        signal_score=rel_score,
                        source='NTIS 뉴스',
                        source_url=link,
                    )

    if not projects:
        return 0

    return insert_ntis_projects(projects)
