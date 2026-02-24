# Python 3.10 슬림 버전 이미지 사용 (경량화 목적)
FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 업데이트 및 필수 패키지 설치 (필요시)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 패키지 의존성 파일 복사
COPY requirements.txt .

# 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스코드 복사
COPY . .

# Streamlit 구동 포트 노출 (기본 8501)
EXPOSE 8501

# 컨테이너 실행 명령 (비동기 Health Check 및 서버 설정 포함)
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
