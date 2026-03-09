"""
LINC 3.0 / RISE / 글로컬대학30 선정교 + 전국 CAD 관련 학교 타겟 DB 모듈

■ 하나티에스 영업 전략상 핵심 타겟
  - 글로컬대학30: 학교당 최대 1,000억원 (5년) 대형 예산 → 90점
  - LINC 3.0 기술혁신선도형: 80점
  - LINC 3.0 수요맞춤성장형: 70점
  - LINC 3.0 협력기반구축형: 60점
  - RISE 수행 대학: 65점
  - 기계공학 관련 학과 보유: +10점 보너스

■ 추가 타겟 (v5 확충)
  - 일반 4년제 (LINC/글로컬 미선정): 50점 (기계공학 보유 시 +10)
  - 일반 전문대 (LINC 미선정): 45점 (기계설계/CAD 보유 시 +10)
  - 마이스터고: 55점 (정부 지원 예산 보유)
  - 특성화고 (공업계열): 40점
  - ⚠️ 폴리텍 제외 (이미 전체 교 연간계약 체결)
"""
from utils.db_manager import insert_target_schools


# ──────────────────────────────────────────────
# LINC 3.0 선정 대학 (2022~2028)
# ──────────────────────────────────────────────

LINC3_TECH_INNOVATION = {
    # 기술혁신선도형 (교당 약 55억원/년)
    'type': '기술혁신선도형',
    'budget': '약 55억원/년',
    'schools': {
        '수도권': ['고려대학교', '성균관대학교', '한양대학교'],
        '지방': ['강원대학교', '경북대학교', '경상국립대학교', '부경대학교',
                 '부산대학교', '전남대학교', '전북대학교', '충남대학교',
                 '충북대학교', '포항공과대학교'],
    }
}

LINC3_DEMAND_GROWTH = {
    # 수요맞춤성장형 (교당 약 40억원/년)
    'type': '수요맞춤성장형',
    'budget': '약 40억원/년',
    'schools': {
        '수도권': ['가톨릭대학교', '경희대학교', '국민대학교', '단국대학교',
                   '동국대학교', '서강대학교', '서울과학기술대학교', '아주대학교',
                   '인하대학교', '중앙대학교', '한국공학대학교', '한양대학교(ERICA)'],
        '충청': ['건양대학교', '한국교통대학교', '한밭대학교', '한국기술교육대학교',
                 '대전대학교', '선문대학교', '순천향대학교', '한남대학교',
                 '한서대학교', '호서대학교'],
        '호남제주': ['광주대학교', '목포대학교', '우석대학교', '제주대학교',
                    '호남대학교', '동신대학교', '원광대학교', '전주대학교', '조선대학교'],
        '대경강원': ['계명대학교', '대구대학교', '안동대학교', '영남대학교',
                    '경운대학교', '경일대학교', '금오공과대학교', '대구한의대학교',
                    '한동대학교', '한림대학교', '가톨릭관동대학교', '강릉원주대학교'],
        '동남': ['동명대학교', '동서대학교', '울산대학교', '창원대학교',
                 '한국해양대학교', '경남대학교', '경성대학교', '동아대학교',
                 '동의대학교', '인제대학교'],
    }
}

LINC3_COOPERATION = {
    # 협력기반구축형 (교당 약 20억원/년)
    'type': '협력기반구축형',
    'budget': '약 20억원/년',
    'schools': {
        '수도권': ['숙명여자대학교', '인천대학교'],
        '지방': ['고려대학교(세종)', '공주대학교', '국립목포해양대학교',
                 '동국대학교(WISE)', '목원대학교', '신라대학교',
                 '우송대학교', '위덕대학교'],
    }
}

# LINC 3.0 전문대 (수요맞춤성장형)
LINC3_COLLEGE_DEMAND = {
    'type': '수요맞춤성장형(전문대)',
    'budget': '약 20억원/년',
    'schools': {
        '수도권': ['경기과학기술대학교', '경민대학교', '경복대학교', '동서울대학교',
                   '동아방송예술대학교', '동양미래대학교', '연성대학교', '오산대학교',
                   '유한대학교', '인천재능대학교', '인하공업전문대학', '한양여자대학교'],
        '충청강원': ['대전과학기술대학교', '아주자동차대학교', '연암대학교',
                    '우송정보대학', '충북보건과학대학교', '한국영상대학교', '한림성심대학교'],
        '호남제주': ['순천제일대학교', '원광보건대학교', '전남과학대학교',
                    '전주비전대학교', '제주관광대학교', '제주한라대학교', '조선이공대학교'],
        '대구경북': ['경북전문대학교', '계명문화대학교', '구미대학교', '대경대학교',
                    '대구과학대학교', '대구보건대학교', '안동과학대학교',
                    '영남이공대학교', '영진전문대학교'],
        '동남': ['경남도립거창대학', '경남도립남해대학', '경남정보대학교',
                 '동의과학대학교', '동주대학교', '부산과학기술대학교',
                 '부산여자대학교', '연암공과대학교', '울산과학대학교'],
    }
}

LINC3_COLLEGE_COOP = {
    'type': '협력기반구축형(전문대)',
    'budget': '약 11억원/년',
    'schools': {
        '수도권': ['명지전문대학교', '안산대학교', '인덕대학교'],
        '지방': ['가톨릭상지대학교', '강릉영동대학교', '강원도립대학교',
                 '거제대학교', '군장대학교', '대전보건대학교',
                 '동원과학기술대학교', '마산대학교', '목포과학대학교',
                 '전주기전대학교', '창원문성대학교', '춘해보건대학교'],
    }
}


# ──────────────────────────────────────────────
# 글로컬대학30 (2023~2027, 학교당 최대 1,000억원)
# ──────────────────────────────────────────────

GLOCAL30 = {
    '1차(2023)': [
        ('강원대학교', '강원'), ('국립강릉원주대학교', '강원'),
        ('경상국립대학교', '경남'), ('부산대학교', '부산'),
        ('부산교육대학교', '부산'), ('국립순천대학교', '전남'),
        ('국립안동대학교', '경북'), ('경북도립대학교', '경북'),
        ('울산대학교', '경남'), ('전북대학교', '전북'),
        ('충북대학교', '충북'), ('국립한국교통대학교', '충북'),
        ('포항공과대학교', '경북'), ('한림대학교', '강원'),
    ],
    '2차(2024)': [
        ('건양대학교', '충남'), ('경북대학교', '경북'),
        ('국립목포대학교', '전남'), ('국립창원대학교', '경남'),
        ('경남도립거창대학', '경남'), ('경남도립남해대학', '경남'),
        ('한국승강기대학교', '경남'), ('동아대학교', '부산'),
        ('동서대학교', '부산'), ('대구보건대학교', '대구'),
        ('광주보건대학교', '광주'), ('대전보건대학교', '대전'),
        ('대구한의대학교', '경북'), ('원광대학교', '전북'),
        ('원광보건대학교', '전북'), ('인제대학교', '경남'),
        ('한동대학교', '경북'),
    ],
    '3차(2025)': [
        ('경성대학교', '부산'), ('순천향대학교', '충남'),
        ('전남대학교', '전남'), ('제주대학교', '제주'),
        ('조선대학교', '광주'), ('조선간호대학교', '광주'),
        ('충남대학교', '충남'), ('국립공주대학교', '충남'),
        ('한서대학교', '충남'),
    ],
}


# ──────────────────────────────────────────────
# 기계공학 관련 학과 보유 대학 (우선순위 +10)
# CAD/CAM 실습 도입 가능성이 높은 대학
# ──────────────────────────────────────────────

MECH_ENG_SCHOOLS = [
    '고려대학교', '성균관대학교', '한양대학교', '서울과학기술대학교',
    '아주대학교', '인하대학교', '한국공학대학교', '한양대학교(ERICA)',
    '한밭대학교', '한국기술교육대학교', '한국교통대학교',
    '금오공과대학교', '영남대학교', '경북대학교', '경상국립대학교',
    '부경대학교', '부산대학교', '울산대학교', '창원대학교',
    '한국해양대학교', '동명대학교', '동의대학교', '동아대학교',
    '전남대학교', '전북대학교', '충남대학교', '충북대학교',
    '강원대학교', '포항공과대학교', '국민대학교', '단국대학교',
    '경희대학교', '중앙대학교', '계명대학교', '대구대학교',
    '영남이공대학교', '인하공업전문대학', '동양미래대학교',
    '경남정보대학교', '구미대학교', '동의과학대학교',
    # v5 추가: 기존 목록에 없던 기계공학 보유 대학
    '서울대학교', '연세대학교', 'KAIST', 'UNIST', 'GIST', 'DGIST',
    '건국대학교', '세종대학교', '홍익대학교', '한국항공대학교',
    '숭실대학교', '명지대학교', '광운대학교', '한경국립대학교',
    '가천대학교', '서울시립대학교', '이화여자대학교',
    '국립군산대학교', '대구가톨릭대학교',
    '서일대학교', '대림대학교', '두원공과대학교', '대덕대학교',
    '대구공업대학교',
]


# ──────────────────────────────────────────────
# 추가 타겟: LINC/글로컬 미선정 4년제 대학 (기계공학 관련 학과 보유)
# 폴리텍 제외
# ──────────────────────────────────────────────

ADDITIONAL_UNIVERSITIES = {
    '수도권': [
        ('서울대학교', '기계공학부, 항공우주공학과'),
        ('연세대학교', '기계공학부'),
        ('서울시립대학교', '기계정보공학과'),
        ('가천대학교', '기계공학과, 미래자동차학과'),
        ('건국대학교', '기계로봇자동차공학부, 항공우주공학과'),
        ('경기대학교', '기계공학과'),
        ('대진대학교', '기계공학과'),
        ('명지대학교', '기계공학과, 로봇공학과'),
        ('세종대학교', '기계공학과, 항공시스템공학과'),
        ('수원대학교', '기계공학과'),
        ('숭실대학교', '기계공학부'),
        ('이화여자대학교', '기계공학과'),
        ('한국항공대학교', '항공우주공학과, 기계공학과'),
        ('한성대학교', '기계공학과'),
        ('홍익대학교', '기계시스템디자인공학과'),
        ('광운대학교', '로봇학부'),
        ('한경국립대학교', '기계공학과, 로봇공학과'),
    ],
    '충청': [
        ('KAIST', '기계공학과, 항공우주공학과'),
        ('배재대학교', '로봇공학과'),
        ('상명대학교', '로봇공학과'),
    ],
    '호남제주': [
        ('GIST', '기계공학부'),
        ('국립군산대학교', '기계공학과, 자동차공학전공'),
    ],
    '대경강원': [
        ('DGIST', '로봇및기계전자공학전공'),
        ('대구가톨릭대학교', '기계자동차공학부'),
    ],
    '동남': [
        ('UNIST', '기계공학과'),
    ],
}

# ──────────────────────────────────────────────
# 추가 타겟: LINC 미선정 전문대 (기계/설계/CAD 관련 학과 보유)
# 폴리텍 제외
# ──────────────────────────────────────────────

ADDITIONAL_COLLEGES = {
    '수도권': [
        ('서일대학교', '기계설계과, 스마트기계과'),
        ('두원공과대학교', '기계과, 자동차과, 스마트기계과'),
        ('수원과학대학교', '기계공학과'),
        ('대림대학교', '메카트로닉스과, 기계설계과'),
    ],
    '충청': [
        ('대덕대학교', '기계설계과, 자동차과'),
        ('신성대학교', '자동차과, 기계과'),
    ],
    '호남제주': [
        ('전남도립대학교', '자동차과'),
    ],
    '대경강원': [
        ('대구공업대학교', '기계자동차과, 기계설계과'),
        ('강동대학교', '자동차과'),
    ],
    '동남': [
        ('김해대학교', '기계자동차공학과'),
    ],
}

# ──────────────────────────────────────────────
# 마이스터고등학교 (기계/자동차/자동화 관련)
# 정부 지원 예산이 있어 구매력이 높음
# ──────────────────────────────────────────────

MEISTER_HIGH_SCHOOLS = [
    # (학교명, 지역, 관련분야)
    ('경북기계공업고등학교', '대구', '기계'),
    ('군산기계공업고등학교', '전북', '기계'),
    ('부산자동차고등학교', '부산', '자동차'),
    ('거제공업고등학교', '경남', '기계/조선'),
    ('광주자동화설비마이스터고등학교', '광주', '자동화설비'),
    ('금오공업고등학교', '경북', '기계'),
    ('동아마이스터고등학교', '대전', '기계'),
    ('부산기계공업고등학교', '부산', '기계'),
    ('수원하이텍고등학교', '경기', '기계'),
    ('전북기계공업고등학교', '전북', '기계'),
    ('평택마이스터고등학교', '경기', '자동차'),
    ('공군항공과학고등학교', '경남', '항공기계'),
    ('연무마이스터고등학교', '충남', '자동차'),
    ('서울로봇고등학교', '서울', '로봇기계'),
    ('포항제철공업고등학교', '경북', '기계/제철'),
    ('현대공업고등학교', '울산', '기계'),
    ('대구일마이스터고등학교', '대구', '자동차'),
    ('아산스마트팩토리마이스터고등학교', '충남', '스마트팩토리'),
]

# ──────────────────────────────────────────────
# 특성화고등학교 (공업계열 기계/자동차 학과 보유)
# ──────────────────────────────────────────────

SPECIALIZED_HIGH_SCHOOLS = {
    '서울': [
        '경기기계공업고등학교', '서울공업고등학교',
        '영등포공업고등학교', '성동공업고등학교',
    ],
    '인천': [
        '계산공업고등학교', '부평공업고등학교', '인천기계공업고등학교',
    ],
    '경기': [
        '부천공업고등학교', '안산공업고등학교', '안양공업고등학교',
        '동일공업고등학교', '두원공업고등학교', '수원공업고등학교',
    ],
    '부산': [
        '부산공업고등학교', '부산전자공업고등학교',
        '동명공업고등학교', '동아공업고등학교',
    ],
    '대구': [
        '대구공업고등학교', '경북공업고등학교', '영남공업고등학교',
    ],
    '강원': [
        '춘천기계공업고등학교', '강릉정보공업고등학교',
    ],
    '충북': [
        '청주공업고등학교', '충북공업고등학교', '충주공업고등학교',
    ],
    '충남': [
        '천안공업고등학교', '서산공업고등학교',
    ],
    '전북': [
        '전주공업고등학교', '이리공업고등학교',
    ],
    '전남': [
        '목포공업고등학교', '순천공업고등학교', '나주공업고등학교',
    ],
    '경북': [
        '상주공업고등학교', '포항흥해공업고등학교',
    ],
    '경남': [
        '마산공업고등학교', '창원공업고등학교', '진주기계공업고등학교',
    ],
}


def _build_linc3_records(linc_data: dict, score: int) -> list:
    """LINC 3.0 데이터를 DB 삽입용 레코드로 변환."""
    records = []
    prog_type = linc_data['type']
    budget = linc_data['budget']

    for region, schools in linc_data['schools'].items():
        for name in schools:
            bonus = 10 if name in MECH_ENG_SCHOOLS else 0
            records.append({
                'school_name': name,
                'school_type': '전문대' if '전문대' in prog_type else '4년제',
                'region': region,
                'program_name': 'LINC 3.0',
                'program_type': prog_type,
                'annual_budget': budget,
                'program_period': '2022.03~2028.02',
                'priority_score': score + bonus,
            })
    return records


def _build_additional_univ_records() -> list:
    """LINC/글로컬 미선정 4년제 대학을 DB 삽입용 레코드로 변환."""
    records = []
    for region, schools in ADDITIONAL_UNIVERSITIES.items():
        for name, depts in schools:
            bonus = 10 if name in MECH_ENG_SCHOOLS else 0
            records.append({
                'school_name': name,
                'school_type': '4년제',
                'region': region,
                'program_name': '일반대학(공학)',
                'program_type': depts,
                'annual_budget': '-',
                'program_period': '-',
                'priority_score': 50 + bonus,
            })
    return records


def _build_additional_college_records() -> list:
    """LINC 미선정 전문대를 DB 삽입용 레코드로 변환."""
    records = []
    for region, schools in ADDITIONAL_COLLEGES.items():
        for name, depts in schools:
            bonus = 10 if name in MECH_ENG_SCHOOLS else 0
            records.append({
                'school_name': name,
                'school_type': '전문대',
                'region': region,
                'program_name': '일반전문대(기계)',
                'program_type': depts,
                'annual_budget': '-',
                'program_period': '-',
                'priority_score': 45 + bonus,
            })
    return records


def _build_meister_records() -> list:
    """마이스터고를 DB 삽입용 레코드로 변환."""
    records = []
    for name, region, field in MEISTER_HIGH_SCHOOLS:
        records.append({
            'school_name': name,
            'school_type': '마이스터고',
            'region': region,
            'program_name': '마이스터고',
            'program_type': field,
            'annual_budget': '정부지원',
            'program_period': '-',
            'priority_score': 55,
        })
    return records


def _build_specialized_hs_records() -> list:
    """특성화고를 DB 삽입용 레코드로 변환."""
    records = []
    for region, schools in SPECIALIZED_HIGH_SCHOOLS.items():
        for name in schools:
            records.append({
                'school_name': name,
                'school_type': '특성화고',
                'region': region,
                'program_name': '특성화고(공업)',
                'program_type': '기계/자동차',
                'annual_budget': '-',
                'program_period': '-',
                'priority_score': 40,
            })
    return records


def load_all_target_schools() -> int:
    """
    LINC 3.0, 글로컬대학30 선정교를 모두 DB에 적재합니다.
    반환값: 신규 삽입 건수
    """
    all_records = []

    # LINC 3.0
    all_records.extend(_build_linc3_records(LINC3_TECH_INNOVATION, 80))
    all_records.extend(_build_linc3_records(LINC3_DEMAND_GROWTH, 70))
    all_records.extend(_build_linc3_records(LINC3_COOPERATION, 60))
    all_records.extend(_build_linc3_records(LINC3_COLLEGE_DEMAND, 65))
    all_records.extend(_build_linc3_records(LINC3_COLLEGE_COOP, 55))

    # 글로컬대학30
    for batch, schools in GLOCAL30.items():
        for name, region in schools:
            bonus = 10 if name in MECH_ENG_SCHOOLS else 0
            all_records.append({
                'school_name': name,
                'school_type': '전문대' if '대학교' not in name else '4년제',
                'region': region,
                'program_name': '글로컬대학30',
                'program_type': batch,
                'annual_budget': '최대 200억원/년',
                'program_period': '2023~2027 (5년)',
                'priority_score': 90 + bonus,
            })

    return insert_target_schools(all_records)


def load_nationwide_schools() -> dict:
    """
    전국 CAD 관련 학교를 DB에 추가 적재합니다.
    (LINC/글로컬 + 일반대학 + 전문대 + 마이스터고 + 특성화고)

    반환값: {'linc_glocal': int, 'universities': int,
             'colleges': int, 'meister': int, 'specialized': int, 'total': int}
    """
    result = {}

    # 1) LINC/글로컬 (기존)
    result['linc_glocal'] = load_all_target_schools()

    # 2) 일반 4년제
    result['universities'] = insert_target_schools(_build_additional_univ_records())

    # 3) 일반 전문대
    result['colleges'] = insert_target_schools(_build_additional_college_records())

    # 4) 마이스터고
    result['meister'] = insert_target_schools(_build_meister_records())

    # 5) 특성화고
    result['specialized'] = insert_target_schools(_build_specialized_hs_records())

    result['total'] = sum(result.values())
    return result


def get_priority_targets(min_score: int = 70) -> list:
    """
    우선순위 점수 이상인 학교만 반환합니다.
    영업팀이 즉시 공략할 대상입니다.
    """
    import sqlite3
    from utils.db_manager import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT school_name, program_name, program_type, annual_budget, "
        "       priority_score, sales_status "
        "FROM target_schools "
        "WHERE priority_score >= ? "
        "ORDER BY priority_score DESC",
        (min_score,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'school_name': r[0], 'program_name': r[1],
            'program_type': r[2], 'annual_budget': r[3],
            'priority_score': r[4], 'sales_status': r[5],
        }
        for r in rows
    ]
