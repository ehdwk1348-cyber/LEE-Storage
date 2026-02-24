import sqlite3
import os
import pandas as pd

# 현재 파일 위치를 기준으로 db 폴더 절대 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'sales_data.db')

def init_db() -> None:
    """
    SQLite 데이터베이스에 연결하고 초기 테이블이 없을 경우 생성합니다.
    """
    # db 디렉토리가 없으면 먼저 생성
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. schools (목표 학교) 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT NOT NULL,
            category TEXT, -- 구분 (특성화고, 전문대, 4년제 등)
            contact TEXT,
            existing_equipments TEXT -- 기존 보유 장비 리스트
        )
    ''')

    # 2. grants (정부 지원 사업) 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            agency TEXT,
            selected_school TEXT,
            budget_scale TEXT,
            notice_url TEXT,
            status TEXT,
            crawled_at TEXT
        )
    ''')
    
    # SQLite ALTER TABLE 로 새 컬럼 추가 (이미 테이블이 있을 경우 대비)
    try:
        cursor.execute("ALTER TABLE grants ADD COLUMN status TEXT")
        cursor.execute("ALTER TABLE grants ADD COLUMN crawled_at TEXT")
        cursor.execute("ALTER TABLE grants ADD COLUMN agency TEXT")
    except sqlite3.OperationalError:
        pass # 컬럼이 이미 존재하면 예외 무시

    # 3. bid_history (과거 입찰 기록) 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bid_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bid_title TEXT NOT NULL,
            demand_agency TEXT,
            successful_bidder TEXT,
            bid_price TEXT, -- 낙찰금액 또는 예산
            introduced_items TEXT,
            contract_date TEXT
        )
    ''')
    
    # SQLite ALTER TABLE 로 새 컬럼 추가 (이미 테이블이 있을 경우 대비)
    try:
        cursor.execute("ALTER TABLE bid_history ADD COLUMN bid_price TEXT")
    except sqlite3.OperationalError:
        pass # 컬럼이 이미 존재하면 예외 발생, 무시함

    # 4. contacts (타겟 교수 목록) 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT NOT NULL,
            name TEXT NOT NULL,
            department TEXT,
            email TEXT,
            phone TEXT,
            research_area TEXT,
            source_url TEXT,
            crawled_at TEXT
        )
    ''')

    conn.commit()
    conn.close()

def insert_bids(bids: list) -> int:
    """
    수집된 공고 리스트를 bid_history 테이블에 삽입합니다.
    새로 삽입된 레코드 수를 반환합니다.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    count = 0
    for bid in bids:
        # 중복 방지를 위한 단순 방어 로직 (공고명과 기관명이 같으면 생략)
        cursor.execute("SELECT id FROM bid_history WHERE bid_title = ? AND demand_agency = ?", 
                       (bid.get('bid_title', ''), bid.get('demand_agency', '')))
        if cursor.fetchone() is None:
            cursor.execute('''
                INSERT INTO bid_history (bid_title, demand_agency, successful_bidder, bid_price, introduced_items, contract_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                bid.get('bid_title', ''),
                bid.get('demand_agency', ''),
                bid.get('successful_bidder', ''),
                bid.get('bid_price', ''),
                bid.get('introduced_items', ''),
                bid.get('contract_date', '')
            ))
            count += 1
    conn.commit()
    conn.close()
    return count

def get_all_bids() -> pd.DataFrame:
    """
    bid_history 테이블의 모든 데이터를 pandas DataFrame으로 반환합니다.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM bid_history ORDER BY id DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def check_db_connection() -> bool:
    """
    데이터베이스 연결 상태를 점검하여 불리언 값을 반환합니다.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.cursor()
        conn.close()
        return True
    except sqlite3.Error:
        # 연결 실패 시 False 반환
        return False

def insert_school(school_name: str, category: str, contact: str, existing_equipments: str) -> bool:
    """
    신규 타겟 학교 정보를 DB에 저장합니다.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO schools (school_name, category, contact, existing_equipments)
            VALUES (?, ?, ?, ?)
        ''', (school_name, category, contact, existing_equipments))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error inserting school: {e}")
        return False

def get_all_schools() -> pd.DataFrame:
    """
    schools 테이블의 모든 학교 데이터를 pandas DataFrame으로 반환합니다.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT id, school_name as '학교명', category as '구분', contact as '연락처', existing_equipments as '보유장비' FROM schools ORDER BY id DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def insert_grants(grants_data: list) -> int:
    """
    수집된 국고 지원 사업 리스트를 grants 테이블에 삽입합니다. 중복은 제외합니다.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    count = 0
    for g in grants_data:
        # 뉴스/공고명이 동일하면 건너뜀 (단순 중복 방지)
        cursor.execute("SELECT id FROM grants WHERE notice_url = ? OR project_name = ?", 
                       (g.get('notice_url', ''), g.get('project_name', '')))
        if cursor.fetchone() is None:
            cursor.execute('''
                INSERT INTO grants (project_name, agency, selected_school, budget_scale, notice_url, status, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                g.get('project_name', ''),
                g.get('agency', ''),
                g.get('selected_school', ''),
                g.get('budget_scale', ''),
                g.get('notice_url', ''),
                g.get('status', ''),
                g.get('crawled_at', '')
            ))
            count += 1
    conn.commit()
    conn.close()
    return count

def get_all_grants() -> pd.DataFrame:
    """
    grants 테이블의 모든 데이터를 반환합니다.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM grants ORDER BY id DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def insert_contacts(contacts_list: list) -> int:
    """
    수집된 교수 연락처 리스트를 contacts 테이블에 삽입합니다. 이메일을 기준으로 단순 중복을 방지합니다.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    count = 0
    from datetime import datetime
    crawled_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for c in contacts_list:
        email = c.get('email', '')
        # 이메일이 있고 중복되면 건너뜀
        if email and email.strip() != "":
            cursor.execute("SELECT id FROM contacts WHERE email = ?", (email,))
            if cursor.fetchone() is not None:
                continue
                
        cursor.execute('''
            INSERT INTO contacts (school_name, name, department, email, phone, research_area, source_url, crawled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            c.get('school_name', ''),
            c.get('name', ''),
            c.get('department', ''),
            email,
            c.get('phone', ''),
            c.get('research_area', ''),
            c.get('source_url', ''),
            crawled_at
        ))
        count += 1
        
    conn.commit()
    conn.close()
    return count

def get_all_contacts() -> pd.DataFrame:
    """
    contacts 테이블의 모든 교수 데이터를 pandas DataFrame으로 반환합니다.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM contacts ORDER BY id DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()
