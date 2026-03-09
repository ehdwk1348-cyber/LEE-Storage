"""
NEIS(교육행정정보시스템) 학교알리미 API 연동 모듈
- 학교 기본 정보 조회 (학교명, 주소, 전화번호, 설립유형 등)
- 학과 정보 조회 (전문대/특성화고 학과 목록)
- 취업 현황 조회
- 인증키 없이 무료 사용 가능 (공개 데이터)
NEIS API 문서: https://open.neis.go.kr/portal/guide/apiIntroPage.do
"""
import requests
from typing import Optional

NEIS_BASE = "https://open.neis.go.kr/hub"


def _neis_get(endpoint: str, params: dict) -> list:
    """NEIS API 공통 호출 함수. 결과 row 리스트를 반환합니다."""
    params.setdefault("Type", "json")
    params.setdefault("pIndex", "1")
    params.setdefault("pSize", "100")
    try:
        r = requests.get(f"{NEIS_BASE}/{endpoint}", params=params, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        # NEIS는 서비스명 키 아래 [head, row] 구조
        for key, val in data.items():
            if key == "RESULT":
                return []
            if isinstance(val, list) and len(val) >= 2:
                rows = val[1].get("row", [])
                return rows if isinstance(rows, list) else []
    except Exception as e:
        print(f"[NEIS API 오류] {endpoint}: {e}")
    return []


def search_schools(school_name: str = "", school_type: str = "") -> list:
    """
    학교명 또는 학교 유형으로 학교 기본 정보를 검색합니다.
    school_type: '특성화고등학교', '마이스터고등학교', '전문대학', '대학교' 등
    반환: [{학교명, 교육청, 주소, 전화번호, 설립유형, 학교종류}, ...]
    """
    params = {}
    if school_name:
        params["SCHUL_NM"] = school_name
    if school_type:
        params["SCHUL_KND_SC_NM"] = school_type

    rows = _neis_get("schoolInfo", params)
    result = []
    for r in rows:
        result.append({
            "school_name": r.get("SCHUL_NM", ""),
            "edu_office": r.get("ATPT_OFCDC_SC_NM", ""),       # 교육청
            "region": r.get("LCTN_SC_NM", ""),                   # 지역
            "address": r.get("ORG_RDNMA", ""),                   # 도로명 주소
            "phone": r.get("ORG_TELNO", ""),                     # 대표 전화
            "homepage": r.get("HMPG_ADRES", ""),                 # 홈페이지
            "school_type": r.get("SCHUL_KND_SC_NM", ""),        # 학교 종류
            "found_type": r.get("FOND_SC_NM", ""),               # 설립 유형 (공립/사립)
            "school_code": r.get("SD_SCHUL_CODE", ""),           # 학교 코드
            "edu_office_code": r.get("ATPT_OFCDC_SC_CODE", ""), # 교육청 코드
        })
    return result


def get_school_departments(school_code: str, edu_office_code: str) -> list:
    """
    특정 학교의 학과(계열) 정보를 조회합니다.
    반환: [{학과명, 계열명, 학년수}, ...]
    """
    rows = _neis_get("classInfo", {
        "SD_SCHUL_CODE": school_code,
        "ATPT_OFCDC_SC_CODE": edu_office_code,
    })
    seen = set()
    result = []
    for r in rows:
        dept = r.get("DDDEP_NM", "") or r.get("CLRM_NM", "")
        if dept and dept not in seen:
            seen.add(dept)
            result.append({
                "department": dept,
                "grade": r.get("GRADE", ""),
                "class_nm": r.get("CLASS_NM", ""),
            })
    return result


def get_employment_stats(school_name: str) -> Optional[dict]:
    """
    학교명으로 취업 현황을 조회합니다 (전문대/대학 대상).
    반환: {졸업자수, 취업자수, 취업률} 또는 None
    """
    rows = _neis_get("empSttDtaInfo", {"SCHUL_NM": school_name})
    if not rows:
        return None
    r = rows[0]
    return {
        "grad_count": r.get("GRAD_THSCLSF_STDCNT", ""),     # 졸업자 수
        "employ_count": r.get("EMPLOY_THSCLSF_STDCNT", ""), # 취업자 수
        "employ_rate": r.get("EMPLOY_RATE", ""),             # 취업률
        "year": r.get("AY", ""),                              # 학년도
    }


def get_school_full_profile(school_name: str) -> dict:
    """
    학교명으로 기본정보 + 학과정보 + 취업현황을 통합 조회합니다.
    Spec-in 문서 자동 작성 시 학교 데이터 자동 채우기에 활용.
    """
    # 1. 기본 정보 조회
    schools = search_schools(school_name=school_name)
    if not schools:
        return {"error": f"'{school_name}' 학교 정보를 찾을 수 없습니다."}

    school = schools[0]
    result = {"basic": school, "departments": [], "employment": None}

    # 2. 학과 정보 조회
    if school.get("school_code") and school.get("edu_office_code"):
        result["departments"] = get_school_departments(
            school["school_code"], school["edu_office_code"]
        )

    # 3. 취업 현황 (전문대/대학 한정)
    if school.get("school_type") in ["전문대학", "대학교", "대학원"]:
        result["employment"] = get_employment_stats(school_name)

    return result
