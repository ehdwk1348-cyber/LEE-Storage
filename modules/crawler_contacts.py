import os
import json
import time
import requests
import re
from bs4 import BeautifulSoup
from googlesearch import search
from config import GEMINI_API_KEY

def search_faculty_urls(school_name: str) -> list:
    """
    Google 검색엔진을 사용하여 특정 학교의 타겟 학과 교수진 페이지 URL을 검색합니다.
    """
    query = f'{school_name} "기계공학과" OR "건축공학과" OR "산업공학과" "교수" "이메일"'
    urls = []
    try:
        # googlesearch-python 라이브러리 활용 (봇 차단 우회를 위해 sleep_interval 지정)
        results = search(query, num_results=3, lang="ko", sleep_interval=2)
        for r in results:
            urls.append(r)
    except Exception as e:
        print(f"\n[ERROR] 상세 에러 로그 (search_faculty_urls): {e}\n")
        raise Exception(f"Google 검색 중 오류 발생: {e}")
    return urls

def clean_html_for_llm(raw_html: str) -> str:
    """
    HTML에서 LLM 컨텍스트 한도를 넘지 않도록 불필요한 태그를 제거하고 텍스트만 추출합니다.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    # 불필요한 태그 제거
    for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'img']):
        tag.decompose()
    text = soup.get_text(separator=' ')
    # 공백 정규화
    text = " ".join(text.split())
    # 최대 글자 수 제한 (Gemini 입력 제한 고려)
    return text[:15000] 

def extract_professors_with_llm(url: str, school_name: str) -> list:
    """
    수집된 웹페이지 URL의 텍스트를 읽어와 Gemini 모델을 통해 연락처 정보를 JSON 포맷으로 파싱합니다.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        text_content = clean_html_for_llm(res.text)
    except Exception as e:
        print(f"\n[ERROR] 상세 에러 로그 (웹페이지 수집 실패 - {url}): {e}\n")
        return []

    if not text_content or len(text_content) < 50:
        return []

    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY is missing.")
        return []

    prompt = f"""
다음 텍스트는 '{school_name}'의 대학 학과 홈페이지 내용 중 일부야. 
여기서 3D CAD, 설계, 제조, 디자인, 디지털 트윈, 시뮬레이션, 스마트팩토리와 관련성이 있을 법한 과목을 가르치거나 연구할 가능성이 있는 교수들의 정보를 추출해줘.

추출한 정보는 반드시 아래 형식의 유효한 JSON 배열(Array)로만 응답해야 해. 다른 부가 설명이나 코드블록(```json) 마크다운을 절대 포함하지 말고 순수 JSON만 반환해.

[
  {{
    "school_name": "{school_name}",
    "name": "이름",
    "department": "소속학과",
    "email": "이메일주소",
    "phone": "전화번호",
    "research_area": "연구분야 또는 학과",
    "source_url": "{url}"
  }}
]

텍스트 내에서 해당하는 교수 정보를 찾을 수 없거나 관련 없다고 판단되면 빈 배열 [] 을 반환해.

[홈페이지 내용 시작]
{text_content}
[홈페이지 내용 끝]
"""

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
    }
    
    try:
        response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {}).get("parts", [])
                if content:
                    result_text = content[0].get("text", "")
                    
                    # JSON 배열 부분만 정규식으로 안전하게 추출
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
        else:
            err_msg = f"API Error {response.status_code}: {response.text}"
            print(f"\n[ERROR] 상세 에러 로그 (LLM API 호출 실패): {err_msg}\n")
            raise Exception(err_msg)
    except Exception as e:
        print(f"\n[ERROR] 상세 에러 로그 (LLM 데이터 추출 중 오류): {e}\n")
        raise Exception(f"LLM AI 분석 중 오류: {e}")
    
    return []
