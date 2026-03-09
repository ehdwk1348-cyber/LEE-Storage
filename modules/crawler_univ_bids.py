"""
대학 산학협력단 자체 입찰 공고 크롤러

■ 목적
  - 나라장터에 올라가지 않는 대학 자체 입찰을 포착
  - CAD/CAM SW는 수의계약으로 거래되므로, 대학 자체 공고가 핵심 채널

■ 수집 전략
  1. 네이버 뉴스/블로그 API로 "OO대학교 입찰" 키워드 검색
  2. 타겟 학교 DB에 등록된 학교만 대상으로 검색 (효율성)
  3. CAD/실습실/장비 관련 키워드 필터링

■ 확장 계획
  - 주요 대학 산학협력단 홈페이지 직접 크롤링 (구조가 학교마다 다름)
  - RSS 피드 제공 대학은 RSS로 수집
"""
import os
import re
import requests
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from utils.db_manager import (
    insert_univ_bids, insert_purchase_signal,
    get_all_target_schools,
)
from dotenv import load_dotenv

load_dotenv()

# 학교명 추출
_SCHOOL_PATTERN = re.compile(
    r'([가-힣A-Za-z0-9]+(?:대학교|대학|폴리텍|전문대학))'
)

# 입찰/구매 관련 키워드
BID_KEYWORDS = [
    '입찰', '공고', '구매', '조달', '납품', '용역', '발주',
    '제안요청', 'RFP', '견적', '계약',
]

# CAD/실습 관련 키워드
RELEVANCE_KW = [
    'CAD', 'CAM', 'CAE', 'CATIA', 'SolidWorks', '솔리드웍스', '카티아',
    '3D', 'PLM', '소프트웨어', 'SW', '실습', '장비', '시뮬레이션',
    '디지털트윈', '스마트팩토리', '메카트로닉스', '기계', '설계',
    '라이선스', '교육용', '실습실',
]


def _clean_html(raw: str) -> str:
    return BeautifulSoup(raw, "html.parser").get_text()


def _is_bid_relevant(title: str, desc: str) -> bool:
    """입찰 + CAD/실습 관련 여부 확인."""
    text = (title + ' ' + desc).upper()
    has_bid = any(k in text for k in BID_KEYWORDS)
    has_rel = any(k.upper() in text for k in RELEVANCE_KW)
    return has_bid and has_rel


def fetch_univ_bid_news(top_n: int = 30) -> int:
    """
    타겟 학교 상위 N교의 자체 입찰/구매 공고를 뉴스에서 수집합니다.
    반환값: 신규 저장 건수
    """
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET_KEY")

    if not client_id or not client_secret:
        print("[산학협력단 입찰] 네이버 API 키 없음")
        return 0

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    # 타겟 학교 상위 N교만 검색 (효율성)
    target_df = get_all_target_schools()
    if target_df.empty:
        print("[산학협력단 입찰] 타겟 학교 DB 비어있음")
        return 0

    # 우선순위 상위 학교 선택 (중복 제거)
    schools = target_df.sort_values('priority_score', ascending=False)
    unique_schools = schools['school_name'].drop_duplicates().head(top_n).tolist()

    bids_data = []
    seen_links = set()

    for school in unique_schools:
        # 학교명 + 입찰/구매 키워드 조합
        queries = [
            f'"{school}" 입찰 소프트웨어',
            f'"{school}" 구매 CAD',
            f'"{school}" 산학협력단 장비',
        ]

        for query in queries:
            enc_query = urllib.parse.quote(query)
            url = (
                f"https://openapi.naver.com/v1/search/news.json"
                f"?query={enc_query}&display=5&sort=date"
            )
            try:
                res = requests.get(url, headers=headers, timeout=10)
                res.raise_for_status()
                items = res.json().get('items', [])
            except Exception:
                continue

            for item in items:
                link = item.get('originallink') or item.get('link', '')
                if link in seen_links or not link:
                    continue
                seen_links.add(link)

                title = _clean_html(item.get('title', ''))
                desc = _clean_html(item.get('description', ''))

                if not _is_bid_relevant(title, desc):
                    continue

                pub_date = item.get('pubDate', '')

                bids_data.append({
                    'school_name': school,
                    'bid_title': title,
                    'bid_url': link,
                    'pub_date': pub_date,
                    'deadline': '',
                    'budget': '',
                    'bid_type': '뉴스 감지',
                    'is_relevant': 1,
                })

                # 구매 신호 생성
                insert_purchase_signal(
                    school_name=school,
                    signal_type='대학 입찰',
                    signal_title=title,
                    signal_detail=desc[:150],
                    signal_score=70,
                    source='산학협력단 뉴스',
                    source_url=link,
                )

    if not bids_data:
        return 0

    return insert_univ_bids(bids_data)
