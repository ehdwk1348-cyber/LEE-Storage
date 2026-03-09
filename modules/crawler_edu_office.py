"""
교육청 입찰공고 크롤러 모듈
특성화고는 교육청 예산 → 학교 납품 구조이므로
나라장터에서 교육청 공고를 별도로 집중 수집합니다.

■ 수집 대상
  - 17개 시도교육청 나라장터 공고
  - (주)하나티에스 제품군 관련 키워드로 필터

■ 필터 전략
  - 제품명 직접 언급 (CATIA, SolidWorks 등) → 무조건 수집
  - CAD·실습·설계 키워드 + 교육청 기관 → 수집
  - 설계 용역·공사·인테리어 등 → 제외
"""
import os
import requests
import datetime
from utils.db_manager import insert_bids
from dotenv import load_dotenv

load_dotenv()

# 17개 시도교육청
EDU_OFFICES = [
    "서울특별시교육청", "부산광역시교육청", "대구광역시교육청", "인천광역시교육청",
    "광주광역시교육청", "대전광역시교육청", "울산광역시교육청", "세종특별자치시교육청",
    "경기도교육청", "강원특별자치도교육청", "충청북도교육청", "충청남도교육청",
    "전북특별자치도교육청", "전라남도교육청", "경상북도교육청", "경상남도교육청",
    "제주특별자치도교육청",
]

# ──────────────────────────────────────────────
# 하나티에스 제품군 키워드 (한글/영문/혼합/약어)
# ──────────────────────────────────────────────

# 제품명 직접 언급 → 교육청 여부 무관하게 수집
PRODUCT_KEYWORDS = [
    'CATIA', 'catia', '카티아',
    '3DEXPERIENCE', '3dexperience', '3D EXPERIENCE',
    'SOLIDWORKS', 'SolidWorks', 'Solidworks', '솔리드웍스', '솔리드워크',
    'SIMULIA', 'DELMIA', 'ENOVIA',
    '다쏘시스템', 'Dassault', 'DASSAULT',
    'CAM 소프트웨어', 'CAE 소프트웨어',
]

# 일반 CAD·실습 키워드 → 교육청 기관일 때 수집
CAD_KEYWORDS = [
    # 3D CAD
    '3D CAD', '3DCAD', '3D캐드', '3d cad',
    'CAD 소프트웨어', 'CAD소프트웨어', 'CAD 라이선스', 'CAD라이선스',
    '캐드 소프트웨어', '캐드소프트웨어',
    '3차원 설계', '3차원설계', '3D 설계', '3D설계',
    # 실습 환경
    'CAD 실습', 'CAD실습', '설계 실습', '설계실습',
    'CAD 실습실', 'CAD실습실', '3D 실습', '3D실습',
    '기계설계 실습', '기계설계실습',
    # 스마트팩토리 / 디지털트윈
    '스마트팩토리', '스마트 팩토리', 'Smart Factory',
    '디지털트윈', '디지털 트윈', 'Digital Twin',
    'PLM', 'PDM',
    # 메카트로닉스
    '메카트로닉스', 'Mechatronics',
    # SW 라이선스
    'SW 라이선스', 'SW라이선스', '소프트웨어 라이선스',
    # 기자재
    'CAD 기자재', '실습 기자재', '실습기자재',
    # VR / 시뮬레이션
    '3D 시뮬레이션', '3D시뮬레이션',
    'VR 실습', 'VR실습', '가상현실 실습',
]

# 교육청 공고에서 구매·납품 맥락일 때 추가 수집
EDU_PURCHASE_KEYWORDS = [
    '소프트웨어 구매', '소프트웨어구매',
    'SW 구매', 'SW구매',
    '라이선스 구매', '라이선스구매',
    '실습 장비 구매', '실습장비구매',
    '기자재 구매', '기자재구매',
    '교육용 소프트웨어', '교육용소프트웨어',
]

# 제외 키워드 (용역·공사 등)
EXCLUDE_KEYWORDS = [
    '설계 용역', '설계용역', '설계·감리', '설계감리',
    '건축 설계', '건축설계', '토목 설계', '토목설계',
    '인테리어', '리모델링', '공사', '시공', '건설',
    '조경', '전기공사', '소방공사', '도로', '교량',
    '청소 용역', '청소용역', '급식', '경비 용역',
    '인력 파견', '인력파견',
]

_BID_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"


def _is_excluded(title: str) -> bool:
    t = title.upper()
    return any(kw.upper() in t for kw in EXCLUDE_KEYWORDS)


def _filter_edu_office_bids(raw_data: list) -> list:
    """
    교육청 발주 공고 중 하나티에스 제품군 관련 항목만 필터링합니다.

    통과 조건:
      A) 제품명 직접 언급 (기관 무관)
      B) 교육청/특성화고 기관 + CAD 키워드
      C) 교육청 기관 + 소프트웨어 구매 키워드
    """
    result = []

    for item in raw_data:
        agency = (
            item.get("dminsttNm", "") or
            item.get("dmdInsttNm", "") or
            item.get("ntceInsttNm", "") or ""
        )
        title = item.get("bidNtceNm", "") or ""
        date  = item.get("bidNtceDt", "") or ""
        price = item.get("asignBdgtAmt", "") or item.get("presmptPrce", "") or ""

        if not title:
            continue

        # 제외 필터 우선
        if _is_excluded(title):
            continue

        title_up  = title.upper()
        agency_up = agency.upper()
        combined  = title_up + " " + agency_up

        # 교육청·특성화고 기관 여부
        is_edu = (
            "교육청" in agency or
            any(eo in agency for eo in EDU_OFFICES) or
            any(kw in agency for kw in ["고등학교", "마이스터", "특성화", "직업", "폴리텍"])
        )

        # A: 제품명 직접 언급
        product_hit  = any(kw.upper() in combined for kw in PRODUCT_KEYWORDS)
        # B: 교육청 + CAD 키워드
        cad_hit      = is_edu and any(kw.upper() in title_up for kw in CAD_KEYWORDS)
        # C: 교육청 + 구매 키워드
        purchase_hit = is_edu and any(kw.upper() in title_up for kw in EDU_PURCHASE_KEYWORDS)

        if product_hit or cad_hit or purchase_hit:
            result.append({
                "bid_title":         title,
                "demand_agency":     agency,
                "successful_bidder": "미상(공고 단계)",
                "bid_price":         str(price),
                "introduced_items":  "",
                "contract_date":     date[:10] if date else "",
                "bid_type":          "교육청공고",
            })

    return result


def fetch_edu_office_bids(days: int = 28) -> int:
    """
    나라장터 API에서 교육청 발주 공고를 집중 수집합니다.
    나라장터 API 최대 조회 범위 제한: 28일 이하
    반환값: 신규 저장 건수
    """
    api_key = os.getenv("KONEPS_API_KEY")
    if not api_key:
        raise ValueError("KONEPS_API_KEY가 없습니다. .env 파일을 확인하세요.")

    end_dt   = datetime.datetime.now()
    start_dt = end_dt - datetime.timedelta(days=days)

    all_filtered = []

    for page in range(1, 11):   # 최대 200×10 = 2,000건
        bgnDt = start_dt.strftime("%Y%m%d0000")
        endDt = end_dt.strftime("%Y%m%d2359")
        url = (
            f"{_BID_URL}?serviceKey={api_key}"
            f"&numOfRows=200&pageNo={page}"
            f"&inqryBgnDt={bgnDt}&inqryEndDt={endDt}"
            f"&inqryDiv=1&type=json"
        )
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                break
            data   = r.json()
            header = data.get("response", {}).get("header", {})
            if header.get("resultCode") != "00":
                break
            body  = data.get("response", {}).get("body", {})
            total = int(body.get("totalCount", 0) or 0)
            items = body.get("items", {})
            if isinstance(items, dict):
                items = items.get("item", [])
            if isinstance(items, dict):
                items = [items]
            if not items:
                break

            all_filtered.extend(_filter_edu_office_bids(items))

            if page * 200 >= total:
                break

        except Exception as e:
            print(f"[교육청 크롤러] 페이지 {page} 오류: {e}")
            break

    return insert_bids(all_filtered)


def get_edu_office_summary() -> dict:
    """수집된 교육청 공고를 기관별로 집계합니다."""
    import sqlite3
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'db', 'sales_data.db'
    )
    try:
        conn   = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT demand_agency, COUNT(*) as cnt
            FROM bid_history
            WHERE bid_type = '교육청공고'
            GROUP BY demand_agency
            ORDER BY cnt DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}
