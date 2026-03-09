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
            crawled_at TEXT,
            contact_status TEXT DEFAULT '미접촉',
            last_contacted_at TEXT,
            next_action_date TEXT,
            memo TEXT
        )
    ''')
    # 기존 테이블에 파이프라인 컬럼 추가 (마이그레이션)
    for col_def in [
        "ALTER TABLE contacts ADD COLUMN contact_status TEXT DEFAULT '미접촉'",
        "ALTER TABLE contacts ADD COLUMN last_contacted_at TEXT",
        "ALTER TABLE contacts ADD COLUMN next_action_date TEXT",
        "ALTER TABLE contacts ADD COLUMN memo TEXT",
    ]:
        try:
            cursor.execute(col_def)
        except Exception:
            pass

    # 5. bid_history 낙찰결과 컬럼 추가 (마이그레이션)
    for col_def in [
        "ALTER TABLE bid_history ADD COLUMN bid_type TEXT DEFAULT '입찰공고'",
        "ALTER TABLE bid_history ADD COLUMN result_status TEXT",
    ]:
        try:
            cursor.execute(col_def)
        except Exception:
            pass

    # 6. references (레퍼런스 카드 원본 데이터) 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS references_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT NOT NULL,
            solution_name TEXT,
            project_name TEXT,
            contract_year TEXT,
            budget TEXT,
            outcome TEXT,
            created_at TEXT
        )
    ''')

    # 7. target_schools (LINC/RISE/글로컬대학 선정교 타겟 DB)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS target_schools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT NOT NULL,
            school_type TEXT,
            region TEXT,
            program_name TEXT NOT NULL,
            program_type TEXT,
            annual_budget TEXT,
            program_period TEXT,
            priority_score INTEGER DEFAULT 0,
            sales_status TEXT DEFAULT '미접촉',
            memo TEXT,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(school_name, program_name)
        )
    ''')

    # 8. ntis_projects (NTIS 국가 R&D 과제 모니터링)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ntis_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            project_name TEXT NOT NULL,
            lead_agency TEXT,
            lead_researcher TEXT,
            lead_department TEXT,
            total_budget TEXT,
            project_period TEXT,
            keywords TEXT,
            relevance_score INTEGER DEFAULT 0,
            source_url TEXT,
            crawled_at TEXT,
            UNIQUE(project_name, lead_agency)
        )
    ''')

    # 9. univ_bids (대학 산학협력단 자체 입찰 공고)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS univ_bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT NOT NULL,
            bid_title TEXT NOT NULL,
            bid_url TEXT,
            pub_date TEXT,
            deadline TEXT,
            budget TEXT,
            bid_type TEXT,
            is_relevant INTEGER DEFAULT 0,
            crawled_at TEXT,
            UNIQUE(school_name, bid_title)
        )
    ''')

    # 10. purchase_signals (구매 신호 통합 테이블)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            signal_title TEXT NOT NULL,
            signal_detail TEXT,
            signal_score INTEGER DEFAULT 0,
            source TEXT,
            source_url TEXT,
            detected_at TEXT,
            is_acted INTEGER DEFAULT 0,
            action_memo TEXT
        )
    ''')

    # 11. target_schools에 CAD 학과 관련 컬럼 추가 (마이그레이션)
    for col_def in [
        "ALTER TABLE target_schools ADD COLUMN has_cad_dept INTEGER DEFAULT 0",
        "ALTER TABLE target_schools ADD COLUMN cad_dept_names TEXT DEFAULT ''",
    ]:
        try:
            cursor.execute(col_def)
        except Exception:
            pass

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
        email = c.get('email', '').strip()
        name = c.get('name', '').strip()
        school = c.get('school_name', '').strip()

        # 이메일이 있으면 이메일 기준 중복 체크
        if email:
            cursor.execute("SELECT id FROM contacts WHERE email = ?", (email,))
            if cursor.fetchone() is not None:
                continue
        else:
            # 이메일 없으면 (학교명 + 이름) 조합으로 중복 체크
            cursor.execute(
                "SELECT id FROM contacts WHERE school_name = ? AND name = ?",
                (school, name)
            )
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


def update_contact_pipeline(contact_id: int, status: str, memo: str, next_action_date: str) -> bool:
    """
    교수 연락처의 영업 파이프라인 상태를 업데이트합니다.
    """
    from datetime import datetime
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE contacts
            SET contact_status = ?, memo = ?, next_action_date = ?, last_contacted_at = ?
            WHERE id = ?
        ''', (status, memo, next_action_date, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), contact_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"파이프라인 업데이트 오류: {e}")
        return False


def get_pipeline_summary() -> dict:
    """
    영업 파이프라인 단계별 건수를 딕셔너리로 반환합니다.
    """
    stages = ['미접촉', '접촉완료', '제안서발송', '협의중', '수주', '보류']
    result = {s: 0 for s in stages}
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for stage in stages:
            cursor.execute("SELECT COUNT(*) FROM contacts WHERE contact_status = ?", (stage,))
            result[stage] = cursor.fetchone()[0]
        conn.close()
    except Exception:
        pass
    return result


def insert_reference(school_name: str, solution_name: str, project_name: str,
                     contract_year: str, budget: str, outcome: str) -> bool:
    """
    납품 레퍼런스 데이터를 저장합니다.
    """
    from datetime import datetime
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO references_data (school_name, solution_name, project_name, contract_year, budget, outcome, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (school_name, solution_name, project_name, contract_year, budget, outcome,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"레퍼런스 저장 오류: {e}")
        return False


def get_all_references() -> pd.DataFrame:
    """
    레퍼런스 데이터 전체를 반환합니다.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM references_data ORDER BY id DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def fetch_bid_result(bid_title: str) -> dict:
    """
    낙찰결과 API를 호출하여 낙찰업체 및 낙찰금액을 조회합니다.
    공공데이터포털 계약정보 API 사용.
    """
    import requests
    api_key = os.getenv("KONEPS_API_KEY", "")
    if not api_key:
        return {}

    url = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrvcPPSstemIndstrytyPe"
    params = {
        "serviceKey": api_key,
        "numOfRows": "10",
        "pageNo": "1",
        "type": "json",
        "bidNtceNm": bid_title[:20] if bid_title else "",
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = data.get('response', {}).get('body', {}).get('items', [])
            if isinstance(items, dict) and 'item' in items:
                items = [items['item']] if isinstance(items['item'], dict) else items['item']
            if items:
                item = items[0]
                return {
                    'successful_bidder': item.get('sucsfbidCorpNm', ''),
                    'bid_price': item.get('sucsfbidAmt', ''),
                }
    except Exception:
        pass
    return {}


def insert_target_schools(schools_data: list) -> int:
    """
    LINC/RISE/글로컬대학 선정교 데이터를 target_schools에 삽입합니다.
    school_name + program_name 조합으로 중복 방지.
    반환값: 신규 삽입 건수
    """
    from datetime import datetime
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    count = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for s in schools_data:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO target_schools "
                "(school_name, school_type, region, program_name, program_type, "
                " annual_budget, program_period, priority_score, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    s.get('school_name', ''),
                    s.get('school_type', ''),
                    s.get('region', ''),
                    s.get('program_name', ''),
                    s.get('program_type', ''),
                    s.get('annual_budget', ''),
                    s.get('program_period', ''),
                    s.get('priority_score', 0),
                    now, now,
                )
            )
            if cursor.rowcount > 0:
                count += 1
        except Exception:
            continue

    conn.commit()
    conn.close()
    return count


def get_all_target_schools() -> pd.DataFrame:
    """target_schools 전체 조회."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT * FROM target_schools ORDER BY priority_score DESC, id DESC",
            conn
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def get_target_schools_summary() -> pd.DataFrame:
    """사업별 선정교 통계."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query('''
            SELECT program_name as 사업명,
                   COUNT(*) as 학교수,
                   COUNT(CASE WHEN sales_status != '미접촉' THEN 1 END) as 접촉학교수
            FROM target_schools
            GROUP BY program_name
            ORDER BY 학교수 DESC
        ''', conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def update_target_school_status(school_id: int, status: str, memo: str) -> bool:
    """타겟 학교의 영업 상태를 업데이트."""
    from datetime import datetime
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE target_schools SET sales_status=?, memo=?, updated_at=? WHERE id=?",
            (status, memo, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), school_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def insert_target_school_manual(school_name: str, school_type: str, region: str,
                                program_name: str, program_type: str,
                                annual_budget: str, program_period: str,
                                priority_score: int) -> bool:
    """수동으로 타겟 학교 1건을 추가합니다."""
    from datetime import datetime
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT OR IGNORE INTO target_schools "
            "(school_name, school_type, region, program_name, program_type, "
            " annual_budget, program_period, priority_score, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (school_name, school_type, region, program_name, program_type,
             annual_budget, program_period, priority_score, now, now)
        )
        inserted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return inserted
    except Exception:
        return False


def delete_target_school(school_id: int) -> bool:
    """타겟 학교 1건을 삭제합니다."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM target_schools WHERE id = ?", (school_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_bid_result_summary() -> pd.DataFrame:
    """
    bid_history에서 낙찰업체별 건수/금액 합계를 반환합니다 (경쟁사 분석).
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query('''
            SELECT successful_bidder as 낙찰업체,
                   COUNT(*) as 낙찰건수,
                   demand_agency as 수요기관
            FROM bid_history
            WHERE successful_bidder != '' AND successful_bidder != '미상(공고 단계)'
            GROUP BY successful_bidder
            ORDER BY 낙찰건수 DESC
        ''', conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def get_competitor_analysis() -> dict:
    """
    경쟁사 낙찰 이력을 종합 분석합니다.
    반환값: {
        'competitor_ranking': DataFrame (업체별 낙찰건수/수요기관),
        'agency_competitors': DataFrame (수요기관별 낙찰업체),
        'recent_wins': DataFrame (최근 낙찰 건),
        'total_bids': int,
        'identified_bidders': int,
    }
    """
    result = {
        'competitor_ranking': pd.DataFrame(),
        'agency_competitors': pd.DataFrame(),
        'recent_wins': pd.DataFrame(),
        'total_bids': 0,
        'identified_bidders': 0,
    }
    try:
        conn = sqlite3.connect(DB_PATH)

        # 전체 공고 수
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bid_history")
        result['total_bids'] = cursor.fetchone()[0]

        # 낙찰업체가 확인된 건수
        cursor.execute(
            "SELECT COUNT(*) FROM bid_history "
            "WHERE successful_bidder != '' AND successful_bidder != '미상(공고 단계)'"
        )
        result['identified_bidders'] = cursor.fetchone()[0]

        # 경쟁사 랭킹 (업체별 건수·수요기관 수)
        result['competitor_ranking'] = pd.read_sql_query('''
            SELECT successful_bidder as 낙찰업체,
                   COUNT(*) as 낙찰건수,
                   COUNT(DISTINCT demand_agency) as 거래기관수
            FROM bid_history
            WHERE successful_bidder != '' AND successful_bidder != '미상(공고 단계)'
            GROUP BY successful_bidder
            ORDER BY 낙찰건수 DESC
            LIMIT 20
        ''', conn)

        # 수요기관별 어떤 업체가 낙찰했는지
        result['agency_competitors'] = pd.read_sql_query('''
            SELECT demand_agency as 수요기관,
                   successful_bidder as 낙찰업체,
                   bid_title as 공고명,
                   bid_price as 낙찰금액,
                   contract_date as 계약일
            FROM bid_history
            WHERE successful_bidder != '' AND successful_bidder != '미상(공고 단계)'
            ORDER BY contract_date DESC
            LIMIT 50
        ''', conn)

        # 최근 낙찰 건
        result['recent_wins'] = pd.read_sql_query('''
            SELECT bid_title as 공고명,
                   demand_agency as 수요기관,
                   successful_bidder as 낙찰업체,
                   bid_price as 금액,
                   contract_date as 일자
            FROM bid_history
            WHERE successful_bidder != '' AND successful_bidder != '미상(공고 단계)'
            ORDER BY contract_date DESC
            LIMIT 20
        ''', conn)

        conn.close()
    except Exception:
        pass
    return result


# ──────────────────────────────────────────────
# NTIS 연구과제
# ──────────────────────────────────────────────

def insert_ntis_projects(projects: list) -> int:
    """NTIS 연구과제 목록을 DB에 삽입합니다."""
    from datetime import datetime
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    count = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for p in projects:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO ntis_projects "
                "(project_id, project_name, lead_agency, lead_researcher, "
                " lead_department, total_budget, project_period, keywords, "
                " relevance_score, source_url, crawled_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (p.get('project_id', ''), p.get('project_name', ''),
                 p.get('lead_agency', ''), p.get('lead_researcher', ''),
                 p.get('lead_department', ''), p.get('total_budget', ''),
                 p.get('project_period', ''), p.get('keywords', ''),
                 p.get('relevance_score', 0), p.get('source_url', ''), now)
            )
            if cursor.rowcount > 0:
                count += 1
        except Exception:
            continue
    conn.commit()
    conn.close()
    return count


def get_all_ntis_projects() -> pd.DataFrame:
    """NTIS 연구과제 전체 조회."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT * FROM ntis_projects ORDER BY relevance_score DESC, id DESC", conn
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


# ──────────────────────────────────────────────
# 대학 산학협력단 자체 입찰
# ──────────────────────────────────────────────

def insert_univ_bids(bids: list) -> int:
    """대학 자체 입찰 공고를 DB에 삽입합니다."""
    from datetime import datetime
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    count = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for b in bids:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO univ_bids "
                "(school_name, bid_title, bid_url, pub_date, deadline, "
                " budget, bid_type, is_relevant, crawled_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (b.get('school_name', ''), b.get('bid_title', ''),
                 b.get('bid_url', ''), b.get('pub_date', ''),
                 b.get('deadline', ''), b.get('budget', ''),
                 b.get('bid_type', ''), b.get('is_relevant', 0), now)
            )
            if cursor.rowcount > 0:
                count += 1
        except Exception:
            continue
    conn.commit()
    conn.close()
    return count


def get_all_univ_bids() -> pd.DataFrame:
    """대학 자체 입찰 공고 전체 조회."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT * FROM univ_bids ORDER BY id DESC", conn
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


# ──────────────────────────────────────────────
# 구매 신호 통합
# ──────────────────────────────────────────────

def insert_purchase_signal(school_name: str, signal_type: str, signal_title: str,
                           signal_detail: str, signal_score: int,
                           source: str, source_url: str) -> bool:
    """구매 신호 1건을 추가합니다."""
    from datetime import datetime
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO purchase_signals "
            "(school_name, signal_type, signal_title, signal_detail, "
            " signal_score, source, source_url, detected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (school_name, signal_type, signal_title, signal_detail,
             signal_score, source, source_url,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_purchase_signals(min_score: int = 0, limit: int = 50) -> pd.DataFrame:
    """구매 신호 조회 (점수순 정렬)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT * FROM purchase_signals "
            "WHERE signal_score >= ? "
            "ORDER BY signal_score DESC, id DESC "
            "LIMIT ?",
            conn, params=(min_score, limit)
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def mark_signal_acted(signal_id: int, memo: str) -> bool:
    """구매 신호를 '조치 완료'로 마킹합니다."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE purchase_signals SET is_acted=1, action_memo=? WHERE id=?",
            (memo, signal_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def update_target_school_cad_info(school_name: str, has_cad: int, dept_names: str) -> bool:
    """target_schools의 CAD 학과 보유 여부를 업데이트합니다.
    has_cad: 1=있음, -1=없음, 0=미확인
    dept_names: 쉼표 구분 학과명 (예: '기계공학과,메카트로닉스공학과')
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE target_schools SET has_cad_dept=?, cad_dept_names=? WHERE school_name=?",
            (has_cad, dept_names, school_name)
        )
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    except Exception:
        return False


def get_cad_scan_pending_schools(limit: int = 50) -> list:
    """has_cad_dept=0 (미확인)인 학교 목록을 반환합니다."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT school_name, school_type, priority_score
            FROM target_schools
            WHERE has_cad_dept = 0
            ORDER BY priority_score DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [{'school_name': r[0], 'school_type': r[1] or '4년제', 'priority_score': r[2]}
                for r in rows]
    except Exception:
        return []


def get_cad_department_stats() -> dict:
    """CAD 학과 스캔 통계를 반환합니다."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT school_name) FROM target_schools")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT school_name) FROM target_schools WHERE has_cad_dept = 1")
        has_cad = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT school_name) FROM target_schools WHERE has_cad_dept = -1")
        no_cad = cursor.fetchone()[0]
        pending = total - has_cad - no_cad
        conn.close()
        return {'total': total, 'has_cad': has_cad, 'no_cad': no_cad, 'pending': pending}
    except Exception:
        return {'total': 0, 'has_cad': 0, 'no_cad': 0, 'pending': 0}


def get_cad_confirmed_schools() -> pd.DataFrame:
    """CAD 학과가 확인된 학교 목록을 반환합니다."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query('''
            SELECT DISTINCT school_name, school_type, cad_dept_names,
                   program_name, priority_score, sales_status
            FROM target_schools
            WHERE has_cad_dept = 1
            ORDER BY priority_score DESC
        ''', conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def get_action_required_schools(limit: int = 20) -> pd.DataFrame:
    """이번 주 접근해야 할 학교 목록 (구매 신호 점수 + 영업 상태 종합)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query('''
            SELECT ts.school_name, ts.program_name, ts.priority_score,
                   ts.sales_status, ts.memo,
                   COALESCE(ps.total_signals, 0) as signal_count,
                   COALESCE(ps.max_score, 0) as max_signal_score,
                   (ts.priority_score + COALESCE(ps.max_score, 0)) as action_score
            FROM target_schools ts
            LEFT JOIN (
                SELECT school_name,
                       COUNT(*) as total_signals,
                       MAX(signal_score) as max_score
                FROM purchase_signals
                WHERE is_acted = 0
                GROUP BY school_name
            ) ps ON ts.school_name = ps.school_name
            ORDER BY action_score DESC
            LIMIT ?
        ''', conn, params=(limit,))
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()
