import os
import json
import re
import requests
from tavily import TavilyClient
from config import GEMINI_API_KEY, TAVILY_API_KEY

def search_and_extract_professors(school_name: str) -> list:
    """
    Tavily API를 사용하여 검색 결과를 요약/추출한 뒤, Gemini LLM을 통해 교수 정보를 파싱합니다.
    """
    if not TAVILY_API_KEY:
        print("[ERROR] TAVILY_API_KEY가 설정되지 않았습니다.")
        raise Exception("시스템 설정 에러: Tavily API 키가 누락되었습니다.")
        
    query = f"{school_name} 기계공학과 OR 건축공학과 교수진 이름 이메일 연락처 연구분야"
    
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        # HTML 스크래핑 대신 Tavily의 본문 추출(content) 기능을 바로 사용
        response = client.search(query=query, search_depth="advanced", include_raw_content=False, max_results=3)
        
        results = response.get("results", [])
        if not results:
            print("[INFO] Tavily 검색 결과가 없습니다.")
            return []
            
        # Tavily가 반환한 양질의 웹페이지 요약/본문(content)을 하나로 합침
        combined_content = "\n\n".join([r.get("content", "") for r in results])
        
    except Exception as e:
        print(f"\n[ERROR] 상세 에러 로그 (Tavily 검색 실패): {e}\n")
        raise Exception(f"Tavily API 검색 중 오류 발생: {e}")
        
    if not combined_content.strip():
        return []

    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY is missing.")
        raise Exception("시스템 설정 에러: Gemini API 키가 누락되었습니다.")

    prompt = f"""
다음 텍스트는 '{school_name}'의 3D CAD, 설계, 제조, 디자인, 디지털 트윈, 시뮬레이션, 스마트팩토리 등과 관련된 학과의 홈페이지 및 교수진 정보 검색 결과야.
여기서 해당 분야와 관련성이 있을 법한 과목을 가르치거나 연구할 가능성이 있는 교수들의 정보를 추출해줘.

추출한 정보는 반드시 아래 형식의 유효한 JSON 배열(Array)로만 응답해야 해. 다른 부가 설명이나 코드블록(```json) 마크다운을 절대 포함하지 말고 순수 JSON만 반환해.

[
  {{
    "school_name": "{school_name}",
    "name": "이름",
    "department": "소속학과",
    "email": "이메일주소",
    "phone": "전화번호",
    "research_area": "연구분야 또는 학과",
    "source_url": "Tavily Search 결과"
  }}
]

텍스트 내에서 해당하는 교수 정보를 찾을 수 없거나 관련 없다고 판단되면 빈 배열 [] 을 반환해.

[검색 결과 내용 시작]
{combined_content}
[검색 결과 내용 끝]
"""

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
    }
    
    try:
        res = requests.post(api_url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
        if res.status_code == 200:
            data = res.json()
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {}).get("parts", [])
                if content:
                    result_text = content[0].get("text", "")
                    
                    # JSON 배열 부분 정규식 추출
                    match = re.search(r'\[.*\]', result_text, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                        try:
                            parsed_list = json.loads(json_str)
                            return parsed_list
                        except json.JSONDecodeError as je:
                            print(f"\n[ERROR] 상세 에러 로그 (JSON 파싱 에러): {je}\nResult: {json_str}\n")
                            raise Exception(f"AI 응답 JSON 처리 중 오류: {je}")
                    else:
                        print(f"\n[ERROR] 상세 에러 로그 (JSON 배열 패턴 찾기 못함): {result_text}\n")
                        return []
        else:
            err_msg = f"API Error {res.status_code}: {res.text}"
            print(f"\n[ERROR] 상세 에러 로그 (LLM API 호출 실패): {err_msg}\n")
            raise Exception(err_msg)
    except Exception as e:
        print(f"\n[ERROR] 상세 에러 로그 (LLM 데이터 추출 중 오류): {e}\n")
        raise Exception(f"LLM AI 분석 중 오류: {e}")
    
    return []
