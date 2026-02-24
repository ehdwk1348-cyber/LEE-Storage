import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 데이터 포털 API 키
KONEPS_API_KEY = os.getenv("KONEPS_API_KEY", "")

# Google Gemini API 키
try:
    import streamlit as st
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Tavily API 키 (환경 변수 또는 Streamlit Secrets 병행 사용 가능하도록)
try:
    import streamlit as st
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") or st.secrets.get("TAVILY_API_KEY", "")
except Exception:
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
