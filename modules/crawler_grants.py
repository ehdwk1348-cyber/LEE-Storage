import os
import requests
from datetime import datetime
import urllib.parse
from bs4 import BeautifulSoup
from utils.db_manager import insert_grants
from dotenv import load_dotenv

load_dotenv()

def clean_html(raw_html):
    """네이버 API 결과에 포함된 <b> 등 HTML 태그를 제거합니다."""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text()

def fetch_grant_news() -> int:
    """
    국고 지원 사업(LINC 3.0, RISE, 혁신지원사업 등) 관련 최신 뉴스 기사를 
    네이버 뉴스 검색 API를 통해 수집하여 Grants 테이블에 저장합니다.
    """
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET_KEY")
    
    if not client_id or not client_secret:
        print("네이버 API 인증 정보가 .env에 존재하지 않습니다.")
        return 0

    # 검색 성능을 높이기위해 더 구체적인 조합으로 쿼리 구성
    queries = [
        '"선정 완료" 대학 사업',
        '"최종 선정" 대학교 사업',
        '"사업비 확보" 대학',
        "글로컬 대학 최종 선정",
        "첨단산업 부트캠프 사업 선정",
        "소프트웨어 중심대학 선정 발표",
        "디지털 혁신공유대학 선정 명단",
        "직업전환교육기관 지정 결과"
    ]
    
    # 2차 필터링용 키워드 (제목이나 내용에 반드시 포함되어야 함)
    must_include = ["선정", "확정", "지정", "발표", "사업비", "축하", "수주", "확보", "명단"]
    # 제외 키워드 (노이즈 제거)
    must_exclude = ["모집", "교육생", "참가자", "인턴", "신입생", "수강생", "특강", "설명회"]
    
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    grants_data = []
    seen_links = set()
    
    for query in queries:
        enc_query = urllib.parse.quote(query)
        # 검색 정확도를 위해 'sort=sim'(유사도순)으로 일부 섞거나 'date' 유지
        url = f"https://openapi.naver.com/v1/search/news.json?query={enc_query}&display=20&sort=sim"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('items', []):
                link = item.get('originallink') or item.get('link', '')
                if link in seen_links: continue
                seen_links.add(link)
                
                title = clean_html(item.get('title', ''))
                description = clean_html(item.get('description', ''))
                full_text = (title + " " + description).lower()
                
                # 핵심 필터 1: 선정/발표 관련 긍정 키워드가 하나라도 있어야 함
                if not any(k in full_text for k in must_include):
                    continue
                
                # 핵심 필터 2: 단순 모집/광고성 기사 제외
                if any(k in full_text for k in must_exclude):
                    continue
                
                school_guess = "확인 필요(제목 참조)"
                if "대학" in title or "학교" in title:
                    words = title.split()
                    for w in words:
                        if "대" in w or "학교" in w:
                            school_guess = clean_html(w)
                            break
                
                grants_data.append({
                    'project_name': title,
                    'agency': '네이버 뉴스',
                    'selected_school': school_guess,
                    'budget_scale': '기사 원문 참조',
                    'notice_url': link,
                    'status': '선정완료(뉴스)',
                    'crawled_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
        except Exception as e:
            print(f"Error fetching {query}: {e}")
            
    try:
        if grants_data:
            return insert_grants(grants_data)
        
    except Exception as e:
        print(f"Error fetching Naver grant news: {e}")
        return 0
