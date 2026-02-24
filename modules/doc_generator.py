import requests
from config import GEMINI_API_KEY
from utils.text_processor import build_spec_in_prompt

def generate_spec_in_document(school_name: str, project_name: str, budget: str, solution_name: str, extra_points: str) -> str:
    """
    구성된 프롬프트를 Google Gemini API로 전송하고 결과를 반환합니다.
    (추가 라이브러리 설치 방지용 REST API 직접 호출 통신)
    """
    if not GEMINI_API_KEY:
        return "⚠️ 오류: GEMINI_API_KEY가 등록되지 않았습니다. .env 파일이나 config 설정을 확인하고 다시 실행해 주세요."
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    prompt_text = build_spec_in_prompt(school_name, project_name, budget, solution_name, extra_points)
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 2048
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {}).get("parts", [])
                if content:
                    return content[0].get("text", "텍스트가 생성되지 않았습니다.")
            return "API 응답에서 텍스트를 찾을 수 없습니다."
        else:
            return f"⚠️ API 에러 [{response.status_code}]: {response.text}"
            
    except requests.exceptions.RequestException as e:
        return f"⚠️ 네트워크 문제로 문서 생성에 실패했습니다: {str(e)}"
