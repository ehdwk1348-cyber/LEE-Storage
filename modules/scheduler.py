"""
자동 수집 스케줄러 모듈
APScheduler를 사용해 Streamlit 앱 실행 중 백그라운드로 주기적 데이터 수집을 수행합니다.
- 매일 오전 7시: 사전규격 공고 수집 (30일치)
- 매일 오전 7시 30분: 최근 7일 입찰 공고 수집
- 매주 월요일 오전 8시: 국고 지원사업 뉴스 수집
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _run_pre_spec_job():
    """사전규격 공고 자동 수집 작업."""
    try:
        import modules.api_koneps as ak
        count = ak.fetch_pre_spec_bids(30)
        logger.info(f"[스케줄러] 사전규격 수집 완료: {count}건 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    except Exception as e:
        logger.error(f"[스케줄러] 사전규격 수집 실패: {e}")


def _run_recent_bids_job():
    """최근 입찰 공고 자동 수집 작업."""
    try:
        import modules.api_koneps as ak
        count = ak.fetch_recent_bids(7)
        logger.info(f"[스케줄러] 최근 공고 수집 완료: {count}건 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    except Exception as e:
        logger.error(f"[스케줄러] 최근 공고 수집 실패: {e}")


def _run_grant_news_job():
    """국고 지원사업 뉴스 자동 수집 작업."""
    try:
        import modules.crawler_grants as cg
        count = cg.fetch_grant_news()
        logger.info(f"[스케줄러] 지원사업 뉴스 수집 완료: {count}건 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    except Exception as e:
        logger.error(f"[스케줄러] 지원사업 뉴스 수집 실패: {e}")


def _run_edu_office_job():
    """교육청 공고 자동 수집 작업."""
    try:
        import modules.crawler_edu_office as edu
        count = edu.fetch_edu_office_bids(28)
        logger.info(f"[스케줄러] 교육청 공고 수집 완료: {count}건 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    except Exception as e:
        logger.error(f"[스케줄러] 교육청 공고 수집 실패: {e}")


def _run_edu_policy_job():
    """교육부 보도자료/선정교 뉴스 자동 감시 작업."""
    try:
        import modules.crawler_edu_policy as ep
        count = ep.fetch_edu_policy_news()
        logger.info(f"[스케줄러] 교육정책 뉴스 수집 완료: {count}건 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    except Exception as e:
        logger.error(f"[스케줄러] 교육정책 뉴스 수집 실패: {e}")


def _run_ntis_job():
    """NTIS R&D 과제 뉴스 자동 수집 작업."""
    try:
        import modules.crawler_ntis as ntis_c
        count = ntis_c.fetch_ntis_research_news()
        logger.info(f"[스케줄러] R&D 과제 뉴스 수집 완료: {count}건 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    except Exception as e:
        logger.error(f"[스케줄러] R&D 과제 뉴스 수집 실패: {e}")


def _run_univ_bids_job():
    """대학 산학협력단 자체 입찰 뉴스 자동 수집 작업."""
    try:
        import modules.crawler_univ_bids as ub
        count = ub.fetch_univ_bid_news(top_n=20)
        logger.info(f"[스케줄러] 대학 입찰 뉴스 수집 완료: {count}건 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    except Exception as e:
        logger.error(f"[스케줄러] 대학 입찰 뉴스 수집 실패: {e}")


def _run_cad_dept_scan_job():
    """CAD 학과 보유 여부 자동 스캔 작업 (5교씩)."""
    try:
        import modules.crawler_cad_departments as cad
        result = cad.batch_scan_cad_departments(max_schools=5)
        logger.info(
            f"[스케줄러] CAD 학과 스캔 완료: "
            f"{result['scanned']}교 스캔, {result['cad_found']}교 발견, "
            f"{result['professors_saved']}명 교수 저장 "
            f"({datetime.now().strftime('%Y-%m-%d %H:%M')})"
        )
    except Exception as e:
        logger.error(f"[스케줄러] CAD 학과 스캔 실패: {e}")


def start_scheduler():
    """
    APScheduler BackgroundScheduler를 시작합니다.
    Streamlit의 st.session_state를 활용해 앱 재실행 시 중복 시작을 방지합니다.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        import streamlit as st

        # 이미 실행 중이면 재시작하지 않음
        if st.session_state.get("_scheduler_started"):
            return

        scheduler = BackgroundScheduler(timezone="Asia/Seoul")

        # 매일 오전 7:00 - 사전규격 수집
        scheduler.add_job(
            _run_pre_spec_job,
            CronTrigger(hour=7, minute=0),
            id="pre_spec_daily",
            replace_existing=True,
        )
        # 매일 오전 7:30 - 최근 공고 수집
        scheduler.add_job(
            _run_recent_bids_job,
            CronTrigger(hour=7, minute=30),
            id="recent_bids_daily",
            replace_existing=True,
        )
        # 매주 월요일 오전 8:00 - 국고 뉴스 수집
        scheduler.add_job(
            _run_grant_news_job,
            CronTrigger(day_of_week="mon", hour=8, minute=0),
            id="grant_news_weekly",
            replace_existing=True,
        )
        # 매주 화요일 오전 8:00 - 교육청 공고 수집
        scheduler.add_job(
            _run_edu_office_job,
            CronTrigger(day_of_week="tue", hour=8, minute=0),
            id="edu_office_weekly",
            replace_existing=True,
        )
        # 매주 수요일 오전 8:30 - 교육정책/선정교 뉴스 감시
        scheduler.add_job(
            _run_edu_policy_job,
            CronTrigger(day_of_week="wed", hour=8, minute=30),
            id="edu_policy_weekly",
            replace_existing=True,
        )
        # 매주 목요일 오전 8:00 - R&D 과제 뉴스 수집
        scheduler.add_job(
            _run_ntis_job,
            CronTrigger(day_of_week="thu", hour=8, minute=0),
            id="ntis_weekly",
            replace_existing=True,
        )
        # 매주 금요일 오전 8:00 - 대학 산학협력단 입찰 뉴스 수집
        scheduler.add_job(
            _run_univ_bids_job,
            CronTrigger(day_of_week="fri", hour=8, minute=0),
            id="univ_bids_weekly",
            replace_existing=True,
        )
        # 매주 토요일 오전 6:00 - CAD 학과 스캔 (5교씩)
        scheduler.add_job(
            _run_cad_dept_scan_job,
            CronTrigger(day_of_week="sat", hour=6, minute=0),
            id="cad_dept_scan_weekly",
            replace_existing=True,
        )

        scheduler.start()
        st.session_state["_scheduler_started"] = True
        st.session_state["_scheduler"] = scheduler
        logger.info("[스케줄러] 백그라운드 자동 수집 스케줄러 시작됨.")

    except ImportError:
        logger.warning("[스케줄러] apscheduler 패키지가 설치되지 않아 자동 수집이 비활성화됩니다.")
    except Exception as e:
        logger.error(f"[스케줄러] 시작 실패: {e}")


def get_scheduler_status() -> list:
    """
    현재 등록된 스케줄 작업 목록과 다음 실행 시각을 반환합니다.
    """
    import streamlit as st
    scheduler = st.session_state.get("_scheduler")
    if not scheduler:
        return []
    result = []
    for job in scheduler.get_jobs():
        result.append({
            "작업명": job.id,
            "다음실행": job.next_run_time.strftime("%Y-%m-%d %H:%M") if job.next_run_time else "비활성",
        })
    return result
