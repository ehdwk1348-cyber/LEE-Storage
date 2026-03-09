"""
CAD/CAM 학과 탐색 + 교수 정보 수집 크롤러

■ 목적
  - 타겟 학교에 CAD/CAM 관련 교과목이 있는 학과가 있는지 자동 판별
  - 해당 학과의 교수진/학과사무실 연락처를 수집

■ 2단계 파이프라인
  1단계: Tavily 검색 → Gemini가 "이 학교에 CAD 학과가 있는지" 판별
  2단계: CAD 학과 확인 시 → Tavily로 교수진 검색 → Gemini가 구조화 추출

■ 법적 고려
  - 학과 홈페이지 공개 정보만 추출
  - 학과사무실 대표 연락처 우선 수집
  - 이메일 자동 수집 프로그램이 아닌, AI 기반 정보 정리 도구
"""
import json
import re
import time
import os
import requests
from dotenv import load_dotenv
from tavily import TavilyClient
from utils.db_manager import (
    insert_contacts,
    update_target_school_cad_info,
    get_cad_scan_pending_schools,
)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# CAD/CAM 관련 키워드 (학과 판별용)
CAD_KEYWORDS = [
    'CAD', 'CAM', 'CAE', 'CATIA', 'SolidWorks', '솔리드웍스', 'NX',
    'AutoCAD', '3D모델링', '3D 모델링', '기계설계', '기구설계', '금형설계',
    '메카트로닉스', '자동화설계', '디지털트윈', '디지털 트윈',
    '3D프린팅', 'CNC', '컴퓨터응용설계', '컴퓨터응용가공',
    '정밀가공', '스마트팩토리', '스마트 팩토리', 'PLM',
    '유한요소해석', 'FEA', 'CFD', '시뮬레이션',
]


# ──────────────────────────────────────────────
# Gemini API 호출 (공통)
# ──────────────────────────────────────────────

def _call_gemini(prompt: str, max_tokens: int = 4096) -> str:
    """Gemini REST API를 호출하고 응답 텍스트를 반환합니다."""
    if not GEMINI_API_KEY or len(GEMINI_API_KEY) < 20:
        raise ValueError("GEMINI_API_KEY가 누락되었거나 유효하지 않습니다.")

    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta"
        f"/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens},
    }
    res = requests.post(
        api_url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Gemini API 에러 [{res.status_code}]: {res.text[:200]}")

    parts = (
        res.json()
        .get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    return parts[0].get("text", "") if parts else ""


def _parse_json_response(raw_text: str) -> dict | list:
    """Gemini 응답에서 JSON을 추출합니다."""
    cleaned = re.sub(r'```(?:json)?\s*', '', raw_text).replace('```', '').strip()

    # dict 또는 list 시작 위치 찾기
    start_brace = cleaned.find('{')
    start_bracket = cleaned.find('[')

    if start_brace == -1 and start_bracket == -1:
        return {}

    # 먼저 나오는 것 기준
    if start_bracket == -1:
        start = start_brace
    elif start_brace == -1:
        start = start_bracket
    else:
        start = min(start_brace, start_bracket)

    json_str = cleaned[start:]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # 잘린 JSON 복구 시도
        if json_str.startswith('['):
            last = json_str.rfind('}')
            if last != -1:
                try:
                    return json.loads(json_str[:last + 1] + ']')
                except json.JSONDecodeError:
                    pass
        elif json_str.startswith('{'):
            last = json_str.rfind('}')
            if last != -1:
                try:
                    return json.loads(json_str[:last + 1])
                except json.JSONDecodeError:
                    pass
        return {}


# ──────────────────────────────────────────────
# Tavily 검색 (공통)
# ──────────────────────────────────────────────

def _tavily_search(queries: list, max_results: int = 3) -> str:
    """여러 쿼리로 Tavily 검색을 실행하고 결과를 합칩니다."""
    if not TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY가 누락되었습니다.")

    client = TavilyClient(api_key=TAVILY_API_KEY)
    all_parts = []

    for query in queries:
        try:
            res = client.search(
                query=query,
                search_depth="advanced",
                include_raw_content=False,
                max_results=max_results,
            )
            for r in res.get("results", []):
                text = r.get("content", "").strip()
                if text:
                    all_parts.append(f"[출처: {r.get('url', '')}]\n{text}")
        except Exception as e:
            print(f"[Tavily 오류] {query}: {e}")
            continue

    # 최대 8개 결과 사용 (Gemini 토큰 절약)
    return "\n\n".join(all_parts[:8])


# ──────────────────────────────────────────────
# 1단계: CAD 학과 판별
# ──────────────────────────────────────────────

def _build_curriculum_queries(school_name: str, school_type: str = '4년제') -> list:
    """학교 유형별 교육과정 검색 쿼리를 생성합니다."""
    if school_type in ('4년제', '전문대'):
        return [
            f'"{school_name}" 기계공학과 교육과정 CAD',
            f'"{school_name}" 학과 교과목 기계설계 3D모델링 시뮬레이션',
            f'"{school_name}" 메카트로닉스 자동화 디지털트윈 교육과정',
        ]
    else:
        # 특성화고/마이스터고
        return [
            f'"{school_name}" 기계과 교육과정 CAD 실습',
            f'"{school_name}" 기계설계과 자동화과 교과목',
        ]


def _build_cad_detect_prompt(school_name: str, content: str) -> str:
    """CAD 학과 존재 여부 판별용 Gemini 프롬프트를 생성합니다."""
    return f"""다음은 '{school_name}'의 학과 및 교육과정 관련 웹 검색 결과야.

이 학교에서 아래 키워드와 관련된 교과목이나 실습 과정이 있는 학과를 찾아줘.

[관련 키워드]
CAD, CAM, CAE, CATIA, SolidWorks, NX, AutoCAD, 3D모델링, 기계설계,
기구설계, 금형설계, 메카트로닉스, 자동화설계, 디지털트윈,
3D프린팅, CNC, 컴퓨터응용설계, 컴퓨터응용가공, 스마트팩토리

반드시 아래 형식의 유효한 JSON만 반환해. 마크다운이나 설명은 절대 포함하지 마.

{{
  "has_cad_dept": true 또는 false,
  "departments": [
    {{
      "dept_name": "학과명",
      "cad_subjects": ["발견된 CAD 관련 교과목명"],
      "confidence": "high 또는 medium 또는 low"
    }}
  ]
}}

관련 학과가 하나도 없으면:
{{"has_cad_dept": false, "departments": []}}

주의사항:
- 실제 검색 결과에 나온 정보만 사용할 것 (추측 금지)
- 학과명은 정확히 기재 (예: "기계공학과", "스마트기계공학과")
- confidence: 검색 결과에 교과목명이 명확히 나오면 "high", 학과명만 있으면 "medium", 불확실하면 "low"

[검색 결과]
{content}
[끝]"""


def scan_cad_department(school_name: str, school_type: str = '4년제') -> dict:
    """
    단일 학교에 대해 CAD/CAM 학과 보유 여부를 판별합니다.

    반환값:
        {
            "has_cad_dept": True/False,
            "dept_names": ["기계공학과", ...],
            "details": [{"dept_name": "...", "cad_subjects": [...], "confidence": "high"}]
        }
    """
    queries = _build_curriculum_queries(school_name, school_type)
    content = _tavily_search(queries)

    if not content:
        return {"has_cad_dept": False, "dept_names": [], "details": []}

    prompt = _build_cad_detect_prompt(school_name, content)
    raw = _call_gemini(prompt)
    result = _parse_json_response(raw)

    if not isinstance(result, dict):
        return {"has_cad_dept": False, "dept_names": [], "details": []}

    has_cad = result.get("has_cad_dept", False)
    departments = result.get("departments", [])

    dept_names = [d.get("dept_name", "") for d in departments if d.get("dept_name")]

    # DB 업데이트
    update_target_school_cad_info(
        school_name=school_name,
        has_cad=1 if has_cad else -1,
        dept_names=','.join(dept_names),
    )

    return {
        "has_cad_dept": has_cad,
        "dept_names": dept_names,
        "details": departments,
    }


# ──────────────────────────────────────────────
# 2단계: 교수진 정보 수집
# ──────────────────────────────────────────────

def _build_professor_prompt(school_name: str, dept_name: str, content: str) -> str:
    """교수진 정보 추출용 Gemini 프롬프트를 생성합니다."""
    return f"""다음은 '{school_name}' {dept_name}의 교수진 관련 웹 검색 결과야.

이 학과에서 CAD/CAM, 기계설계, 3D모델링, 디지털트윈, 스마트팩토리 관련
소프트웨어 도입에 관여할 가능성이 높은 교수 및 학과사무실 정보를 추출해줘.

⚠️ 중요: 학과 공식 웹페이지에 공개된 정보만 추출할 것.
학과사무실 대표 이메일/전화번호도 별도 항목으로 포함.

반드시 아래 형식의 유효한 JSON 배열만 반환해. 마크다운이나 설명은 절대 포함하지 마.

[
  {{
    "name": "교수명 또는 '학과사무실'",
    "department": "{dept_name}",
    "email": "공개된 이메일 (없으면 빈 문자열)",
    "phone": "전화번호 (없으면 빈 문자열)",
    "research_area": "연구분야 또는 담당과목",
    "source_url": "출처 URL"
  }}
]

관련 정보가 없으면 빈 배열 [] 을 반환해.

[검색 결과]
{content}
[끝]"""


def scan_and_collect_professors(school_name: str, dept_names: list) -> list:
    """
    CAD 학과가 확인된 학교에 대해 교수진 정보를 수집합니다.

    반환값: [{"school_name", "name", "department", "email", "phone",
             "research_area", "source_url"}, ...]
    """
    all_professors = []

    for dept in dept_names:
        queries = [
            f'"{school_name}" "{dept}" 교수진 연락처 이메일',
            f'"{school_name}" "{dept}" 학과사무실 전화번호',
        ]
        content = _tavily_search(queries, max_results=3)

        if not content:
            continue

        prompt = _build_professor_prompt(school_name, dept, content)
        raw = _call_gemini(prompt)
        result = _parse_json_response(raw)

        if not isinstance(result, list):
            continue

        for prof in result:
            if not prof.get("name"):
                continue
            prof["school_name"] = school_name
            # department가 없으면 현재 학과명으로 채움
            if not prof.get("department"):
                prof["department"] = dept
            all_professors.append(prof)

        # 학과 간 API 호출 간격
        time.sleep(1)

    return all_professors


# ──────────────────────────────────────────────
# 배치 실행
# ──────────────────────────────────────────────

def batch_scan_cad_departments(max_schools: int = 10,
                                collect_professors: bool = True) -> dict:
    """
    미확인(has_cad_dept=0) 학교를 배치 스캔합니다.

    파라미터:
        max_schools: 한 번에 처리할 최대 학교 수
        collect_professors: True이면 CAD 학과 발견 시 교수 정보도 수집

    반환값:
        {"scanned": int, "cad_found": int, "professors_saved": int, "results": list}
    """
    pending = get_cad_scan_pending_schools(limit=max_schools)
    if not pending:
        return {"scanned": 0, "cad_found": 0, "professors_saved": 0, "results": []}

    scanned = 0
    cad_found = 0
    professors_saved = 0
    results = []

    for school in pending[:max_schools]:
        school_name = school['school_name']
        school_type = school.get('school_type', '4년제')

        try:
            # 1단계: CAD 학과 판별
            scan_result = scan_cad_department(school_name, school_type)
            scanned += 1

            result_entry = {
                'school_name': school_name,
                'has_cad': scan_result['has_cad_dept'],
                'dept_names': scan_result['dept_names'],
                'professors_count': 0,
            }

            if scan_result['has_cad_dept'] and collect_professors:
                cad_found += 1

                # 2단계: 교수 정보 수집
                professors = scan_and_collect_professors(
                    school_name, scan_result['dept_names']
                )
                if professors:
                    saved = insert_contacts(professors)
                    professors_saved += saved
                    result_entry['professors_count'] = saved

            results.append(result_entry)

        except Exception as e:
            print(f"[CAD 스캔 오류] {school_name}: {e}")
            results.append({
                'school_name': school_name,
                'has_cad': None,
                'dept_names': [],
                'professors_count': 0,
                'error': str(e),
            })

        # 학교 간 API 호출 간격 (rate limit 방지)
        time.sleep(2)

    return {
        "scanned": scanned,
        "cad_found": cad_found,
        "professors_saved": professors_saved,
        "results": results,
    }
