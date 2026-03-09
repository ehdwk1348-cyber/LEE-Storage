"""
구매 신호 분석 엔진

■ 목적
  - 수집된 모든 데이터를 종합하여 "지금 이 학교에 연락해야 하는가?" 판단
  - 구매 가능성 점수(Purchase Probability Score) 자동 산정
  - 예산 시기 기반 알림 생성

■ 점수 산정 기준
  Tier 1 (즉시 영업): 80~100점
    - 재정지원사업 선정 + 예산 집행기 + 관련 입찰 감지
  Tier 2 (6개월 내): 50~79점
    - R&D 과제 수주 or 선정교 DB에 존재 + 예산 시기
  Tier 3 (파이프라인): 20~49점
    - 타겟 학교 DB에 존재하나 구체적 신호 없음

■ 예산 시기 (대학교 기준)
  - 1~2월: 예산 편성기 → 스펙인 최적기 (+20점)
  - 3~4월: 전반기 발주 집중 (+25점)
  - 5~7월: 중간 집행 (+15점)
  - 9~10월: 하반기 발주 (+20점)
  - 11~12월: 연말 예산 소진 (+25점)
  - 8월: 방학기 (-5점)
"""
from datetime import datetime
from utils.db_manager import (
    get_all_target_schools,
    get_purchase_signals,
    insert_purchase_signal,
    get_all_ntis_projects,
    get_all_univ_bids,
)


# 월별 예산 시기 가중치
BUDGET_MONTH_BONUS = {
    1: 20, 2: 20,      # 예산 편성기
    3: 25, 4: 25,      # 전반기 발주 집중
    5: 15, 6: 15, 7: 15,  # 중간 집행
    8: -5,              # 방학기
    9: 20, 10: 20,      # 하반기 발주
    11: 25, 12: 25,     # 연말 예산 소진
}


def get_budget_season_info() -> dict:
    """현재 월의 예산 시기 정보를 반환합니다."""
    month = datetime.today().month
    bonus = BUDGET_MONTH_BONUS.get(month, 0)

    seasons = {
        (1, 2): {'name': '예산 편성기', 'action': '스펙인(Spec-in) 활동 최적기. 담당자에게 제품 스펙 전달.', 'level': 'high'},
        (3, 4): {'name': '전반기 발주 집중', 'action': '사전규격 공고 모니터링 필수. 즉시 견적 대응.', 'level': 'critical'},
        (5, 7): {'name': '중간 집행기', 'action': '진행 중인 건 follow-up. 추경 예산 파악.', 'level': 'medium'},
        (8, 8): {'name': '하계 방학', 'action': '하반기 대비 자료 준비. 신규 타겟 발굴.', 'level': 'low'},
        (9, 10): {'name': '하반기 발주', 'action': '연말 예산 소진 대비 적극 영업. 제안서 발송.', 'level': 'high'},
        (11, 12): {'name': '연말 예산 소진', 'action': '불용 예산 소진 수의계약 집중. 기 접촉 고객 최종 push.', 'level': 'critical'},
    }

    current_season = {'name': '일반', 'action': '일상 영업 활동', 'level': 'medium'}
    for (s, e), info in seasons.items():
        if s <= month <= e:
            current_season = info
            break

    return {
        'month': month,
        'bonus': bonus,
        'season': current_season,
    }


def calculate_school_scores() -> list:
    """
    모든 타겟 학교의 구매 가능성 점수를 종합 산정합니다.
    반환값: [{'school_name', 'base_score', 'signal_bonus', 'budget_bonus',
              'total_score', 'signals', 'tier', 'recommended_action'}, ...]
    """
    target_df = get_all_target_schools()
    if target_df.empty:
        return []

    signals_df = get_purchase_signals(min_score=0, limit=500)
    ntis_df = get_all_ntis_projects()
    univ_bids_df = get_all_univ_bids()

    budget_info = get_budget_season_info()
    budget_bonus = budget_info['bonus']

    results = []
    # 학교별로 집계
    seen_schools = set()

    for _, row in target_df.iterrows():
        school = row['school_name']
        if school in seen_schools:
            continue
        seen_schools.add(school)

        base_score = int(row.get('priority_score', 0))
        sales_status = row.get('sales_status', '미접촉')

        # 구매 신호 보너스
        signal_bonus = 0
        signal_list = []

        if not signals_df.empty:
            school_signals = signals_df[signals_df['school_name'] == school]
            if not school_signals.empty:
                signal_bonus += min(int(school_signals['signal_score'].max()), 30)
                for _, sig in school_signals.iterrows():
                    signal_list.append({
                        'type': sig.get('signal_type', ''),
                        'title': sig.get('signal_title', ''),
                        'score': sig.get('signal_score', 0),
                    })

        # NTIS 과제 보너스
        ntis_bonus = 0
        if not ntis_df.empty:
            school_ntis = ntis_df[ntis_df['lead_agency'] == school]
            if not school_ntis.empty:
                ntis_bonus = min(int(school_ntis['relevance_score'].max()), 20)
                signal_list.append({
                    'type': 'R&D 과제',
                    'title': f"NTIS 과제 {len(school_ntis)}건 감지",
                    'score': ntis_bonus,
                })

        # 대학 자체 입찰 보너스
        bid_bonus = 0
        if not univ_bids_df.empty:
            school_bids = univ_bids_df[univ_bids_df['school_name'] == school]
            if not school_bids.empty:
                bid_bonus = 25
                signal_list.append({
                    'type': '대학 입찰',
                    'title': f"산학협력단 입찰 {len(school_bids)}건 감지",
                    'score': bid_bonus,
                })

        # 영업 상태 보너스
        status_bonus = {
            '접촉완료': 10, '제안서발송': 15, '협의중': 20, '수주': 0, '보류': -10,
        }.get(sales_status, 0)

        total = min(base_score + signal_bonus + ntis_bonus + bid_bonus + budget_bonus + status_bonus, 100)

        # 등급 판정
        if total >= 80:
            tier = 'Tier 1 (즉시 영업)'
            action = '즉시 담당자 연락. 견적/제안서 준비.'
        elif total >= 50:
            tier = 'Tier 2 (단기 기회)'
            action = '이번 달 내 접촉. 교수 연구 분야 파악 후 맞춤 제안.'
        else:
            tier = 'Tier 3 (파이프라인)'
            action = '분기 1회 접촉. 예산 시기에 재평가.'

        results.append({
            'school_name': school,
            'program_name': row.get('program_name', ''),
            'base_score': base_score,
            'signal_bonus': signal_bonus + ntis_bonus + bid_bonus,
            'budget_bonus': budget_bonus,
            'status_bonus': status_bonus,
            'total_score': total,
            'signals': signal_list,
            'tier': tier,
            'sales_status': sales_status,
            'recommended_action': action,
        })

    # 점수 내림차순 정렬
    results.sort(key=lambda x: x['total_score'], reverse=True)
    return results


def get_weekly_action_list(top_n: int = 15) -> list:
    """이번 주 접근해야 할 학교 목록 (상위 N개)."""
    all_scores = calculate_school_scores()
    # 수주/보류 제외
    actionable = [s for s in all_scores if s['sales_status'] not in ('수주', '보류')]
    return actionable[:top_n]


def get_signal_summary() -> dict:
    """구매 신호 요약 통계."""
    signals_df = get_purchase_signals(min_score=0, limit=500)
    if signals_df.empty:
        return {'total': 0, 'unacted': 0, 'by_type': {}, 'by_school_top5': []}

    unacted = signals_df[signals_df['is_acted'] == 0]

    by_type = {}
    if 'signal_type' in signals_df.columns:
        by_type = signals_df['signal_type'].value_counts().to_dict()

    by_school = []
    if 'school_name' in unacted.columns and not unacted.empty:
        top_schools = unacted.groupby('school_name').agg(
            count=('id', 'count'),
            max_score=('signal_score', 'max')
        ).sort_values('max_score', ascending=False).head(5)
        for name, row in top_schools.iterrows():
            by_school.append({
                'school': name,
                'count': int(row['count']),
                'max_score': int(row['max_score']),
            })

    return {
        'total': len(signals_df),
        'unacted': len(unacted),
        'by_type': by_type,
        'by_school_top5': by_school,
    }
