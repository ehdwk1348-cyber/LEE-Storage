import os
import re
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def clean_api_key(key: str) -> str:
    """API 키에서 보이지 않는 유니코드 문자, 개행, 공백을 모두 제거하고 순수 영숫자/기호만 반환합니다."""
    if not key:
        return ""
    # 영문자, 숫자, 하이픈(-), 언더바(_) 이외의 모든 문자 제거
    return re.sub(r'[^a-zA-Z0-9_\-]', '', key)

# 데이터 포털 API 키
KONEPS_API_KEY = clean_api_key(os.getenv("KONEPS_API_KEY", ""))

# ==========================================
# [중요] API 키 로드 최적화 (공백/오류 방지)
# 1순위: Streamlit Secrets (클라우드 배포용)
# 2순위: os.getenv (로컬 .env 파일용)
# ==========================================

# 1. Google Gemini API 키
GEMINI_API_KEY = ""
try:
    import streamlit as st
    if "GEMINI_API_KEY" in st.secrets:
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if not GEMINI_API_KEY:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    
GEMINI_API_KEY = clean_api_key(GEMINI_API_KEY)

# 2. Tavily API 키
TAVILY_API_KEY = ""
try:
    import streamlit as st
    if "TAVILY_API_KEY" in st.secrets:
        TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except Exception:
    pass

if not TAVILY_API_KEY:
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

TAVILY_API_KEY = clean_api_key(TAVILY_API_KEY)
