import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 데이터 포털 API 키
KONEPS_API_KEY = os.getenv("KONEPS_API_KEY", "")

# Google Gemini API 키
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
