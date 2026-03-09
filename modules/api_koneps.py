"""
나라장터(KONEPS) 입찰공고 수집 모듈
(주)하나티에스 제품군 특화 필터 적용

■ 실제 데이터 분석 결과 (2023~2026년 3년치 검증)
  - 나라장터 용역 API에서 CATIA·SolidWorks 공고는 거의 없음
  - 실제 SW 구매는 조달청 물품 계약(수의계약) 루트로 처리됨
  - 우리가 포착할 수 있는 공고:
      → 실습실 구축 사업 (기자재 + SW 세트 납품)
      → 교육기관 장비·기자재 구매 공고
      → 스마트팩토리 구축 용역 (금오공대 DX혁신 등)
      → 직업교육 혁신 실습환경 구축

■ 필터 전략
  A) 제품명 직접 언급 (CATIA, SolidWorks 등) → 무조건 수집
  B) 교육기관 + 실습실/기자재/장비 구매 공고
  C) 제조업 DX혁신/스마트팩토리 구축 공고 (대학 산학협력단)
  D) 특성화고/마이스터고 실습환경 관련

■ 명확히 제외
  - 정보시스템 개발·구축 (ERP, 홈페이지, 챗봇, 행정SW 등)
  - 설계 용역, 건축, 토목, 건설, 환경조사
  - 청소, 급식, 경비, 차량, 인력 파견
"""
import os
import urllib.parse
import requests
import datetime
from dotenv import load_dotenv
from utils.db_manager import insert_bids

load_dotenv()

# ──────────────────────────────────────────────
# 제품명 키워드 — 이것만 있으면 무조건 수집
# ──────────────────────────────────────────────
PRODUCT_KEYWORDS = [
    # CATIA
    'CATIA', 'catia', '카티아',
    # SolidWorks
    'SOLIDWORKS', 'SolidWorks', 'Solidworks', '솔리드웍스', '솔리드워크',
    # 3DEXPERIENCE
    '3DEXPERIENCE', '3dexperience', '3D EXPERIENCE', '쓰리디익스피리언스',
    # 다쏘시스템즈 계열
    'SIMULIA', 'DELMIA', 'ENOVIA',
    '다쏘시스템', '다쏘 시스템', 'Dassault', 'DASSAULT',
    # CAM/CAE SW
    'CAM 소프트웨어', 'CAM소프트웨어', 'CAE 소프트웨어', 'CAE소프트웨어',
    # 3D CAD 라이선스
    '3D CAD 라이선스', '3DCAD 라이선스', 'CAD 라이선스',
    'CAD 소프트웨어 구매', 'CAD소프트웨어 구매',
    # PLM
    'PLM 구축', 'PLM 도입', 'PDM 구축', 'PDM 도입',
]

# ──────────────────────────────────────────────
# 실습 환경 구축 키워드 — 교육기관 발주일 때 수집
# ──────────────────────────────────────────────
LAB_BUILD_KEYWORDS = [
    # 실습실 구축
    '실습실 구축', '실습실구축', '실습실 조성', '실습실조성',
    '실습실 환경', '실습환경 구축', '실습환경구축',
    '실습 장비', '실습장비', '실습 기자재', '실습기자재',
    '교육 장비', '교육장비', '교육용 장비', '교육용장비',
    # CAD 실습
    'CAD 실습', 'CAD실습', '3D CAD 실습', '설계 실습', '설계실습',
    '기계설계 실습', '기계설계실습',
    # 스마트팩토리 / DX
    '스마트팩토리 구축', '스마트팩토리구축',
    '스마트팩토리 실습', '스마트팩토리실습',
    '스마트 제조', '스마트제조',
    'DX혁신', 'DX 혁신', '디지털혁신 솔루션',
    '디지털트윈 구축', '디지털트윈구축',
    '디지털 전환 솔루션', '디지털전환솔루션',
    # 직업교육 실습
    '직업교육 실습', '직업실습 환경',
    '마이스터고 실습', '특성화고 실습',
    # 메카트로닉스
    '메카트로닉스 실습', '메카트로닉스실습',
    '자동화 실습', '자동화실습',
    # VR/시뮬레이션 (CAD 연계)
    'VR 실습실', 'VR실습실', '가상현실 실습',
    '3D 시뮬레이션 구축', '시뮬레이션 환경 구축',
    # AI·SW 융합 교육 (AISW 교실 등 교육부 사업)
    'AISW', 'AI·SW', 'AI SW', 'AI·DX', 'AI DX',
    'SW교육', 'SW 교육', '소프트웨어교육', '소프트웨어 교육',
    # 기계·제조 솔루션 납품
    '기계설계 솔루션', '제조혁신 솔루션', '스마트공장 솔루션',
    # 산학협력 장비
    '산학협력 장비', '실험실습 장비', '실험실습기자재',
]

# ──────────────────────────────────────────────
# 타겟 교육기관
# ──────────────────────────────────────────────
TARGET_AGENCIES = [
    '대학교', '대학', '전문대', '산학협력단',
    '마이스터고', '마이스터 고등학교',
    '특성화고', '특성화 고등학교',
    '직업훈련', '폴리텍', '기술고', '공업고', '공고',
    '교육청', '교육원', '인력개발원',
    '직업전문학교', '훈련원', '연수원',
]

# ──────────────────────────────────────────────
# 명확히 제외할 키워드
# ──────────────────────────────────────────────
EXCLUDE_KEYWORDS = [
    # 설계 용역 (건축·토목 등 무관)
    '설계 용역', '설계용역', '건축설계', '토목설계', '설계·감리', '설계감리',
    '건축 설계', '토목 설계',
    # 공사·시공
    '공사', '시공', '건설', '인테리어', '리모델링', '조경',
    '전기공사', '소방공사', '도로공사', '교량',
    # 정보시스템 (SW개발 용역 — 우리 제품 아님)
    '홈페이지', '행정시스템', '민원시스템', '학사관리', '도서관시스템',
    '인사시스템', '급여시스템', '회계시스템', '예약시스템',
    'ERP 구축', 'ERP구축', '그룹웨어',
    # 생활편의 용역
    '청소', '급식', '경비', '차량', '버스', '셔틀',
    '인력파견', '인력 파견', '노무',
    # 자연과학·농업·의료
    '농약', '비료', '방제', '식재료', '급식재료',
    '의료', '간호', '약품', '의약',
    # 기타
    '수학여행', '체험학습', '연수', '해외연수',
    '환경조사', '측량', '지질',
]


def _is_excluded(title: str) -> bool:
    """제외 키워드가 공고명에 포함되면 True."""
    t = title.upper()
    return any(kw.upper() in t for kw in EXCLUDE_KEYWORDS)


def _product_match(title: str) -> bool:
    """제품명 직접 언급."""
    t = title.upper()
    return any(kw.upper() in t for kw in PRODUCT_KEYWORDS)


def _lab_and_edu_match(title: str, agency: str) -> bool:
    """실습실 구축 키워드 + 교육기관 조합."""
    t = title.upper()
    a = agency.upper()
    combined = t + ' ' + a
    lab_hit = any(kw.upper() in t for kw in LAB_BUILD_KEYWORDS)
    edu_hit = any(kw.upper() in combined for kw in TARGET_AGENCIES)
    return lab_hit and edu_hit


def filter_target_bids(raw_data: list) -> list:
    """
    하나티에스 제품군 관련 공고만 필터링합니다.

    통과 조건 (우선 적용 후 OR):
      A) 제품명 직접 언급 (CATIA·SolidWorks 등)
      B) 실습실/기자재 구축 + 교육기관 발주

    제외 조건 (가장 먼저 적용):
      설계 용역, 공사, 정보시스템 개발, 생활편의 용역 등
    """
    results = []

    for item in raw_data:
        agency = (
            item.get('dminsttNm', '') or
            item.get('dmdInsttNm', '') or
            item.get('ntceInsttNm', '') or ''
        )
        title = item.get('bidNtceNm', '') or ''
        date  = item.get('bidNtceDt', '') or ''
        price = item.get('asignBdgtAmt', '') or item.get('presmptPrce', '') or ''

        if not title:
            continue

        # 제외 필터 최우선
        if _is_excluded(title):
            continue

        # 통과 조건
        if _product_match(title) or _lab_and_edu_match(title, agency):
            results.append({
                'bid_title':         title,
                'demand_agency':     agency,
                'successful_bidder': '미상(공고 단계)',
                'bid_price':         str(price),
                'introduced_items':  '',
                'contract_date':     date[:10] if date else '',
            })

    return results


# ──────────────────────────────────────────────
# API 호출 함수
# ──────────────────────────────────────────────

_BID_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"
_PRE_SPEC_URL = "https://apis.data.go.kr/1230000/ao/HrcspsSstndrdInfoService/getPublshedStdrdInfoServc"


def _build_url(base: str, api_key: str, extra_params: dict) -> str:
    """
    serviceKey 이중 인코딩 방지를 위해 URL을 직접 구성합니다.
    공공데이터포털 API는 serviceKey를 URL에 직접 붙여야 정상 동작합니다.
    한글 등 특수문자가 포함된 파라미터 값은 URL 인코딩합니다.
    """
    parts = []
    for k, v in extra_params.items():
        encoded = urllib.parse.quote(str(v), safe="")
        parts.append(f"{k}={encoded}")
    qs = "&".join(parts)
    return f"{base}?serviceKey={api_key}&{qs}"


def _call_bid_api(api_key: str, start_dt: datetime.datetime,
                  end_dt: datetime.datetime, page: int = 1) -> list:
    """나라장터 입찰공고 API 단일 페이지 호출."""
    extra = {
        "numOfRows":  "200",
        "pageNo":     str(page),
        "inqryBgnDt": start_dt.strftime("%Y%m%d0000"),
        "inqryEndDt": end_dt.strftime("%Y%m%d2359"),
        "inqryDiv":   "1",
        "type":       "json",
    }
    try:
        url = _build_url(_BID_URL, api_key, extra)
        res = requests.get(url, timeout=20)
        if res.status_code != 200:
            return []
        data = res.json()
        if data.get('response', {}).get('header', {}).get('resultCode') != '00':
            return []
        body  = data.get('response', {}).get('body', {})
        items = body.get('items', [])
        if isinstance(items, dict):
            items = items.get('item', [])
            if isinstance(items, dict):
                items = [items]
        return items if isinstance(items, list) else []
    except Exception:
        return []


def fetch_recent_bids(days: int = 7) -> int:
    """
    최근 N일 나라장터 공고를 수집하여 DB에 저장합니다.
    나라장터 API 최대 조회 범위 제한(28일)으로 인해 28일 단위로 자동 분할합니다.
    """
    api_key = os.getenv("KONEPS_API_KEY")
    if not api_key:
        raise ValueError("KONEPS_API_KEY가 없습니다. .env 파일을 확인하세요.")

    end_dt     = datetime.datetime.now()
    start_dt   = end_dt - datetime.timedelta(days=days)
    chunk_days = 28   # API 최대 허용 범위

    total        = 0
    chunk_end    = end_dt
    while chunk_end > start_dt:
        chunk_start = max(chunk_end - datetime.timedelta(days=chunk_days), start_dt)
        for page in range(1, 26):
            items = _call_bid_api(api_key, chunk_start, chunk_end, page)
            if not items:
                break
            total += insert_bids(filter_target_bids(items))
            if len(items) < 200:
                break
        chunk_end = chunk_start - datetime.timedelta(days=1)

    return total


def fetch_past_bids(years: int = 5, st_placeholder=None) -> int:
    """
    과거 N년치 데이터를 28일 단위로 쪼개 수집합니다.
    나라장터 API 최대 조회 범위 제한: 28일 이하
    """
    api_key = os.getenv("KONEPS_API_KEY")
    if not api_key:
        raise ValueError("KONEPS_API_KEY가 없습니다. .env 파일을 확인하세요.")

    total_added = 0
    end_date    = datetime.datetime.now()
    start_date  = end_date - datetime.timedelta(days=365 * years)
    current_end = end_date

    for _ in range(years * 14):   # 28일 단위이므로 연간 ~13구간
        if current_end <= start_date:
            break
        current_start = max(current_end - datetime.timedelta(days=28), start_date)

        if st_placeholder:
            st_placeholder.text(
                f"수집 중… {current_start.strftime('%Y-%m-%d')} ~ {current_end.strftime('%Y-%m-%d')}"
            )

        # 30일 구간도 전 페이지 스캔
        for page in range(1, 26):
            items = _call_bid_api(api_key, current_start, current_end, page)
            if not items:
                break
            total_added += insert_bids(filter_target_bids(items))
            if len(items) < 200:
                break

        current_end = current_start - datetime.timedelta(days=1)

    return total_added


def fetch_pre_spec_bids(days: int = 30) -> int:
    """
    조달청 사전규격정보 API로 정식 입찰 전 단계 공고를 수집합니다.
    """
    api_key = os.getenv("KONEPS_API_KEY")
    if not api_key:
        return 0

    end_dt   = datetime.datetime.now()
    start_dt = end_dt - datetime.timedelta(days=days)

    extra = {
        "numOfRows":  "100",
        "pageNo":     "1",
        "inqryBgnDt": start_dt.strftime("%Y%m%d0000"),
        "inqryEndDt": end_dt.strftime("%Y%m%d2359"),
        "type":       "json",
    }

    try:
        res = requests.get(_build_url(_PRE_SPEC_URL, api_key, extra), timeout=20)
        if res.status_code != 200:
            return 0
        data  = res.json()
        body  = data.get('response', {}).get('body', {})
        items = body.get('items', [])
        if isinstance(items, dict):
            items = items.get('item', [])
            if isinstance(items, dict):
                items = [items]
        if not isinstance(items, list):
            return 0

        # 사전규격 필드 → 공통 포맷으로 변환
        normalized = []
        for item in items:
            normalized.append({
                'bidNtceNm':    (item.get('stdrdNm', '') or item.get('prdctNm', '') or ''),
                'dminsttNm':    (item.get('dminsttNm', '') or item.get('dmdInsttNm', '') or ''),
                'bidNtceDt':    (item.get('opnDt', '') or item.get('bidNtceDt', '') or ''),
                'asignBdgtAmt': (item.get('asignBdgtAmt', '') or item.get('presmptPrce', '') or ''),
            })

        filtered = filter_target_bids(normalized)
        for f in filtered:
            f['bid_type'] = '사전규격'
        return insert_bids(filtered)

    except Exception as e:
        print(f"[사전규격 API 오류] {e}")
        return 0


def fetch_bid_results_for_history() -> int:
    """
    bid_history에서 낙찰업체 미확인 건을 대상으로
    나라장터 공고 API(inqryDiv=2 낙찰결과)를 호출하여 업데이트합니다.
    """
    import sqlite3

    api_key = os.getenv("KONEPS_API_KEY")
    if not api_key:
        return 0

    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'db', 'sales_data.db'
    )
    conn   = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, bid_title, demand_agency, contract_date "
        "FROM bid_history "
        "WHERE successful_bidder = '미상(공고 단계)' "
        "ORDER BY id DESC LIMIT 50"
    )
    rows    = cursor.fetchall()
    updated = 0

    for row_id, bid_title, demand_agency, contract_date in rows:
        try:
            base = datetime.datetime.strptime(contract_date[:10], "%Y-%m-%d")
        except Exception:
            base = datetime.datetime.now() - datetime.timedelta(days=180)

        extra = {
            "numOfRows":  "10",
            "pageNo":     "1",
            "inqryBgnDt": (base - datetime.timedelta(days=7)).strftime("%Y%m%d0000"),
            "inqryEndDt": (base + datetime.timedelta(days=60)).strftime("%Y%m%d2359"),
            "inqryDiv":   "2",   # 낙찰결과 조회
            "type":       "json",
        }
        if demand_agency:
            extra["dminsttNm"] = demand_agency[:20]

        try:
            res = requests.get(_build_url(_BID_URL, api_key, extra), timeout=15)
            if res.status_code != 200:
                continue
            data  = res.json()
            items = data.get('response', {}).get('body', {}).get('items', [])
            if isinstance(items, dict):
                items = items.get('item', [])
                if isinstance(items, dict):
                    items = [items]
            if not isinstance(items, list) or not items:
                continue

            title_kw = bid_title[:15] if bid_title else ""
            for item in items:
                if title_kw and title_kw not in (item.get('bidNtceNm', '') or ''):
                    continue
                bidder = item.get('sucsfbidCorpNm', '') or item.get('prcbdrCrpNm', '') or ''
                price  = item.get('sucsfbidAmt', '') or item.get('presmptPrce', '') or ''
                if bidder:
                    cursor.execute(
                        "UPDATE bid_history "
                        "SET successful_bidder=?, bid_price=?, result_status='낙찰확인' "
                        "WHERE id=?",
                        (bidder, str(price), row_id)
                    )
                    updated += 1
                    break
        except Exception:
            continue

    conn.commit()
    conn.close()
    return updated
