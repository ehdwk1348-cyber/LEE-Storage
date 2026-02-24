import os
import requests
import datetime
from dotenv import load_dotenv
from utils.db_manager import insert_bids

# .env 파일 로드
load_dotenv()

def fetch_recent_bids(days: int = 7) -> int:
    """
    나라장터 API를 호출하여 최근 공고를 가져오고, 타겟 공고만 필터링하여 DB에 저장합니다.
    저장된 신규 공고 수를 반환합니다.
    """
    api_key = os.getenv("KONEPS_API_KEY")
    if not api_key:
        raise ValueError("KONEPS_API_KEY가 존재하지 않습니다. .env 파일을 확인해 주세요.")

    # 조회 기간 설정 (YYYYMMDDHHMM 형식)
    end_dt = datetime.datetime.now()
    start_dt = end_dt - datetime.timedelta(days=days)
    
    inqryBgnDt = start_dt.strftime("%Y%m%d0000")
    inqryEndDt = end_dt.strftime("%Y%m%d2359")
    
    # 조달청 입찰공고정보 신규 API 엔드포인트 (/ad/ 포함 경로)
    url = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"
    
    params = {
        "serviceKey": api_key,
        "numOfRows": "200",  # 한 번에 200개씩 조회
        "pageNo": "1",
        "inqryBgnDt": inqryBgnDt,
        "inqryEndDt": inqryEndDt,
        "inqryDiv": "1",
        "type": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        # 반환 형태 검사 및 에러 처리
        try:
            data = response.json()
        except ValueError:
            raise ValueError("API 응답이 JSON 형식이 아닙니다 (URL 접속 차단, 또는 트래픽 초과일 수 있음).")

        header = data.get('response', {}).get('header', {})
        if header.get('resultCode') != '00':
            error_msg = header.get('resultMsg', '알 수 없는 API 에러')
            raise ValueError(f"API 에러 메세지: {error_msg}")
            
        items = data.get('response', {}).get('body', {}).get('items', [])
        
        # items가 dict 형태로 반환될 수 있음 (항목이 1개일 때 대비)
        if isinstance(items, dict):
            if 'item' in items:
                items = items['item']
            elif 'body' in items:
                pass
            else:
                items = [items]
        elif not items:
            items = []

        # 타겟 조건 필터링 수행
        filtered_bids = filter_target_bids(items)
        
        # DB 저장 및 신규 등록 데이터 개수 반환
        return insert_bids(filtered_bids)

    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"API 요청 중 네트워크 오류가 발생했습니다: {e}")

def fetch_past_bids(years: int = 5, st_placeholder=None) -> int:
    """
    과거 N년 치의 데이터를 수집합니다.
    공공데이터포털 API 조회 기간 제한(보통 1~6개월)을 우회하기 위해 
    한 달(30일) 단위로 쪼개서 과거 데이터를 호출합니다.
    """
    api_key = os.getenv("KONEPS_API_KEY")
    if not api_key:
        raise ValueError("KONEPS_API_KEY가 존재하지 않습니다. .env 파일을 확인해 주세요.")
        
    url = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"
    
    total_added = 0
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365 * years)
    
    current_end = end_date
    
    # 루프 방어: 60회 (5년 * 12개월)
    max_loops = years * 12
    loop_count = 0
    
    while current_end > start_date and loop_count < max_loops:
        loop_count += 1
        current_start = current_end - datetime.timedelta(days=30) # 30일 간격
        if current_start < start_date:
            current_start = start_date
            
        inqryBgnDt = current_start.strftime("%Y%m%d0000")
        inqryEndDt = current_end.strftime("%Y%m%d2359")
        
        if st_placeholder:
            st_placeholder.text(f"데이터 수집 중... ({current_start.strftime('%Y-%m-%d')} ~ {current_end.strftime('%Y-%m-%d')})")
            
        params = {
            "serviceKey": api_key,
            "numOfRows": "200", 
            "pageNo": "1",
            "inqryBgnDt": inqryBgnDt,
            "inqryEndDt": inqryEndDt,
            "inqryDiv": "1",
            "type": "json"
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                header = data.get('response', {}).get('header', {})
                if header.get('resultCode') == '00':
                    items = data.get('response', {}).get('body', {}).get('items', [])
                    if isinstance(items, dict) and 'item' in items:
                        items = items['item']
                    elif not isinstance(items, list):
                        items = [items] if items else []
                        
                    filtered_bids = filter_target_bids(items)
                    added = insert_bids(filtered_bids)
                    total_added += added
        except Exception as e:
            # 부분 실패 시 다음 루프로 넘어감
            pass
            
        current_end = current_start - datetime.timedelta(days=1)
        
    return total_added

def fetch_pre_spec_bids(days: int = 7) -> int:
    """
    조달청 사전규격정보 API를 호출하여 정식 입찰 전 단계의 공고를 수집합니다.
    (실제 입찰공고보다 한발 먼저 수요를 파악하기 위함)
    """
    api_key = os.getenv("KONEPS_API_KEY")
    if not api_key:
        return 0

    end_dt = datetime.datetime.now()
    start_dt = end_dt - datetime.timedelta(days=days)
    
    inqryBgnDt = start_dt.strftime("%Y%m%d0000")
    inqryEndDt = end_dt.strftime("%Y%m%d2359")
    
    # 조달청 사전규격 API 엔드포인트
    url = "https://apis.data.go.kr/1230000/ao/HrcspsSstndrdInfoService/getOpnSstndrdInfoListServc"
    
    params = {
        "serviceKey": api_key,
        "numOfRows": "100", 
        "pageNo": "1",
        "inqryBgnDt": inqryBgnDt,
        "inqryEndDt": inqryEndDt,
        "type": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', [])
            if isinstance(items, dict) and 'item' in items:
                items = items['item']
            elif not isinstance(items, list):
                items = [items] if items else []
                
            filtered_bids = filter_target_bids(items)
            return insert_bids(filtered_bids)
    except Exception as e:
        print(f"사전규격 API 로드 에러: {e}")
        
    return 0

def filter_target_bids(raw_data: list) -> list:
    """
    수집된 원본 데이터 중 교육기관 및 3D/디지털 트윈 관련 공고만 필터링합니다.
    """
    target_agencies = [
        '고등학교', '대학교', '대학', '산학협력단', '직업훈련', '폴리텍', 
        '마이스터', '과학고', '영재학교', '정보고', '기술고', '특성화', 
        '교육청', '교육원', '인력개발', '직업전문'
    ]
    target_keywords = [
        '3D', 'CAD', '캐드', '설계', '디지털 트윈', '디지털트윈', '실습실', '소프트웨어', 'SW',
        '3D프린터', '메타버스', '기계', '역설계', '엔지니어링', '스마트팩토리',
        '카티아', 'CATIA', '솔리드웍스', 'SOLIDWORKS', '설계소프트웨어'
    ]
    
    filtered_results = []
    
    for item in raw_data:
        dmdInsttNm = item.get('dmdInsttNm', '') or ''
        bidNtceNm = item.get('bidNtceNm', '') or ''
        bidNtceDt = item.get('bidNtceDt', '') or ''
        
        # 금액 추출 (배정예산 또는 기초금액)
        bid_price = item.get('asignBdgtAmt', '') or item.get('presmptPrce', '') or ''
        
        # 수요기관명 필터
        agency_match = any(agency in dmdInsttNm for agency in target_agencies)
        
        # 공고명 필터 (대소문자 구분 없이 비교하기 위해 upper() 사용)
        name_match = any(keyword in bidNtceNm.upper() for keyword in target_keywords)
        
        if agency_match and name_match:
            filtered_results.append({
                'bid_title': bidNtceNm,
                'demand_agency': dmdInsttNm,
                'successful_bidder': '미상(공고 단계)', 
                'bid_price': str(bid_price),
                'introduced_items': '',
                'contract_date': bidNtceDt[:10] if bidNtceDt else '' # YYYY-MM-DD 형식으로 슬라이싱
            })
            
    return filtered_results
