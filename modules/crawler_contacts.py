"""
교수·담당자 연락처 수집 모듈
(주)하나티에스 영업 타겟에 최적화된 검색 쿼리 적용

■ 학교 유형별 검색 전략
  [대학교 / 전문대]
    - 기계공학과, 기계설계학과, 산업공학과, 메카트로닉스학과
    - 스마트팩토리, 디지털트윈, 정밀기계 전공 교수
    - 산학협력단 담당자, LINC·RISE 사업단 교수

  [특성화고 / 마이스터고]
    - 기계과, 자동화과, 기계설계과, 메카트로닉스과 담당교사
    - 실습부장, 교무부장, 취업지원부 (의사결정자)
    - 교육청 담당 장학사 (예산 흐름 파악용)

■ Tavily → Gemini 파이프라인
  Tavily로 웹 검색 → Gemini가 구조화된 JSON으로 파싱
"""
import json
import re
import requests
from tavily import TavilyClient
from config import GEMINI_API_KEY, TAVILY_API_KEY

# ──────────────────────────────────────────────
# 학교 유형 판별
# ──────────────────────────────────────────────

_VOCATIONAL_KEYWORDS = ['고등학교', '마이스터고', '특성화고', '공업고', '기술고', '공고']
_COLLEGE_KEYWORDS    = ['전문대', '폴리텍', '직업전문학교']


def _school_type(school_name: str) -> str:
    """학교명으로 유형을 판별합니다."""
    for kw in _VOCATIONAL_KEYWORDS:
        if kw in school_name:
            return 'vocational'   # 특성화고·마이스터고
    for kw in _COLLEGE_KEYWORDS:
        if kw in school_name:
            return 'college'      # 전문대·폴리텍
    return 'university'           # 4년제 대학 (기본)


# ──────────────────────────────────────────────
# 학교 유형별 검색 쿼리 생성
# ──────────────────────────────────────────────

def _build_queries(school_name: str) -> list[str]:
    """학교 유형에 따라 최적화된 Tavily 검색 쿼리 목록을 반환합니다."""
    stype = _school_type(school_name)

    if stype == 'vocational':
        # 특성화고·마이스터고: 담당교사·실습부장·교무부장이 키맨
        return [
            f"{school_name} 기계과 기계설계과 담당교사 이메일",
            f"{school_name} 실습부장 메카트로닉스 자동화과 연락처",
            f"{school_name} 교무부장 취업지원부 연락처 이메일",
            f"{school_name} CAD 실습 담당교사",
        ]
    elif stype == 'college':
        # 전문대·폴리텍: 학과장 + 산학협력 담당자
        return [
            f"{school_name} 기계계열 학과장 교수 이메일 연락처",
            f"{school_name} 메카트로닉스 스마트팩토리 교수 연락처",
            f"{school_name} 산학협력처 담당자 이메일",
            f"{school_name} CAD 3D 설계 교수 이메일",
        ]
    else:
        # 4년제 대학: 교수 + 산학협력단 + 사업단 담당자
        return [
            f"{school_name} 기계공학과 기계설계 교수진 이메일 연락처",
            f"{school_name} 산업공학과 스마트팩토리 교수 이메일",
            f"{school_name} 메카트로닉스 정밀기계 교수 연락처",
            f"{school_name} LINC RISE 사업단 담당 교수 연락처",
            f"{school_name} 산학협력단 기계 설계 담당자 이메일",
        ]


# ──────────────────────────────────────────────
# Gemini 파싱 프롬프트 생성
# ──────────────────────────────────────────────

def _build_prompt(school_name: str, content: str) -> str:
    stype = _school_type(school_name)

    if stype == 'vocational':
        target_desc = (
            "기계과·기계설계과·메카트로닉스과·자동화과 담당교사, 실습부장, "
            "교무부장, 취업지원부 담당자"
        )
    elif stype == 'college':
        target_desc = (
            "기계계열 학과장, 스마트팩토리·CAD 담당 교수, 산학협력처 담당자"
        )
    else:
        target_desc = (
            "기계공학과·산업공학과·메카트로닉스학과 교수, "
            "스마트팩토리·디지털트윈·3D CAD 관련 연구 교수, "
            "LINC·RISE 사업단 담당 교수, 산학협력단 담당자"
        )

    return f"""
다음은 '{school_name}' 관련 웹 검색 결과야.

이 학교에서 3D CAD(CATIA, SolidWorks), 스마트팩토리, 디지털트윈, 기계설계 소프트웨어 도입에
관여할 가능성이 높은 담당자 정보를 추출해줘.

추출 대상: {target_desc}

반드시 아래 형식의 유효한 JSON 배열만 반환해. 마크다운(```json)이나 부가 설명은 절대 포함하지 마.

[
  {{
    "school_name": "{school_name}",
    "name": "이름 (없으면 빈 문자열)",
    "department": "소속 학과·부서",
    "email": "이메일 (없으면 빈 문자열)",
    "phone": "전화번호 (없으면 빈 문자열)",
    "research_area": "연구분야 또는 담당업무",
    "source_url": "출처 URL"
  }}
]

관련 정보가 없으면 빈 배열 [] 을 반환해.

[검색 결과]
{content}
[끝]
"""


# ──────────────────────────────────────────────
# 메인 함수
# ──────────────────────────────────────────────

def search_and_extract_professors(school_name: str) -> list:
    """
    Tavily 검색 + Gemini 파싱으로 학교 유형에 맞는 담당자 정보를 수집합니다.
    반환값: [{"school_name", "name", "department", "email", ...}, ...]
    """
    if not TAVILY_API_KEY:
        raise Exception("TAVILY_API_KEY가 누락되었습니다.")
    if not GEMINI_API_KEY or len(GEMINI_API_KEY) < 20:
        raise Exception("GEMINI_API_KEY가 누락되었거나 유효하지 않습니다.")

    queries = _build_queries(school_name)

    # ── Tavily 검색 ──
    client = TavilyClient(api_key=TAVILY_API_KEY)
    all_content_parts = []

    for query in queries:
        try:
            res = client.search(
                query=query,
                search_depth="advanced",
                include_raw_content=False,
                max_results=3,
            )
            for r in res.get("results", []):
                text = r.get("content", "").strip()
                if text:
                    all_content_parts.append(f"[출처: {r.get('url','')}]\n{text}")
        except Exception as e:
            print(f"[Tavily 오류] {query}: {e}")
            continue

    if not all_content_parts:
        return []

    # 중복 제거 후 합치기 (Gemini 토큰 절약)
    combined = "\n\n".join(all_content_parts[:6])   # 최대 6개 결과 사용

    # ── Gemini 파싱 ──
    prompt  = _build_prompt(school_name, combined)
    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta"
        f"/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents":       [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
    }

    try:
        res = requests.post(
            api_url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
    except Exception as e:
        raise Exception(f"Gemini API 호출 오류: {e}")

    if res.status_code != 200:
        raise Exception(f"Gemini API 에러 [{res.status_code}]: {res.text[:200]}")

    parts = (
        res.json()
        .get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    if not parts:
        return []

    raw_text = parts[0].get("text", "")

    # 마크다운 코드블록 제거
    cleaned = re.sub(r'```(?:json)?\s*', '', raw_text).replace('```', '').strip()

    start = cleaned.find('[')
    if start == -1:
        return []

    json_str = cleaned[start:]

    # 완전한 JSON 파싱 시도
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # 잘린 경우 마지막 완전한 객체까지 복구
        last = json_str.rfind('}')
        if last == -1:
            return []
        try:
            return json.loads(json_str[:last + 1] + ']')
        except json.JSONDecodeError as e:
            raise Exception(f"AI 응답 JSON 파싱 실패: {e}")
