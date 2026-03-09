import streamlit as st
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta

# 사용자 정의 모듈 임포트
from utils.db_manager import (
    init_db, check_db_connection,
    get_all_bids, get_all_grants, get_all_contacts, get_all_references,
    insert_contacts, insert_reference,
    update_contact_pipeline, get_pipeline_summary, get_bid_result_summary,
    get_all_target_schools, get_target_schools_summary,
    update_target_school_status,
    insert_target_schools, insert_target_school_manual, delete_target_school,
    get_all_ntis_projects, get_all_univ_bids,
    get_purchase_signals, mark_signal_acted,
    get_cad_department_stats, get_cad_confirmed_schools,
)
import modules.api_koneps as ak
import modules.crawler_grants as cg
import modules.crawler_contacts as cc
import modules.doc_generator as dg
import modules.api_neis as neis
import modules.crawler_edu_office as edu
import modules.target_school_db as tsdb
import modules.crawler_edu_policy as ep
import modules.crawler_ntis as ntis_crawler
import modules.crawler_univ_bids as univ_bids_crawler
import modules.purchase_signal_engine as pse
import modules.crawler_cad_departments as cad_crawler
from utils.text_processor import build_reference_card_prompt
from modules.scheduler import start_scheduler, get_scheduler_status


# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────
PIPELINE_STAGES = ['미접촉', '접촉완료', '제안서발송', '협의중', '수주', '보류']
STAGE_COLORS = {
    '미접촉': '#4A5568',
    '접촉완료': '#00A3E0',
    '제안서발송': '#F6AD55',
    '협의중': '#68D391',
    '수주': '#38A169',
    '보류': '#FC8181',
}

BUDGET_SEASONS = [
    {"월": "1~2월", "유형": "전반기 예산 편성", "설명": "새 학년도 예산 확정·심의 시기. 제안서 제출 및 스펙인(Spec-in) 활동 최적기.", "icon": "📋"},
    {"월": "3~4월", "유형": "전반기 발주 집중", "설명": "실습실 구축 프로젝트 발주가 집중되는 시기. 사전규격 모니터링 필수.", "icon": "🔥"},
    {"월": "6~7월", "유형": "중간 정산·추경", "설명": "상반기 집행 점검 및 추가경정예산 검토 시기.", "icon": "📊"},
    {"월": "9~10월", "유형": "하반기 발주", "설명": "연말 예산 소진을 위한 발주 시작. 교체 주기 타겟 집중 공략.", "icon": "🎯"},
    {"월": "11~12월", "유형": "연말 예산 소진 집중", "설명": "불용 예산 소진을 위해 수의계약·긴급 발주 가능성 최고조. 기 접촉 고객 follow-up 필수.", "icon": "⚡"},
]

# ──────────────────────────────────────────────
# 전역 CSS 인젝션
# ──────────────────────────────────────────────
def inject_global_css():
    st.markdown("""
    <style>
    /* ── 기본 레이아웃 ── */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Noto Sans KR', sans-serif;
    }

    /* ── 메인 배경 ── */
    .stApp {
        background-color: #0D1117;
    }

    /* ── 사이드바 ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0D1B2A 0%, #112240 100%);
        border-right: 1px solid #1E3A5F;
    }
    section[data-testid="stSidebar"] .stRadio label {
        color: #A8B8C8 !important;
        font-size: 0.88rem;
        padding: 6px 0;
        transition: color 0.2s;
    }
    section[data-testid="stSidebar"] .stRadio label:hover {
        color: #00A3E0 !important;
    }
    /* 선택된 라디오 강조 */
    section[data-testid="stSidebar"] .stRadio [data-checked="true"] + label {
        color: #00A3E0 !important;
        font-weight: 600;
    }

    /* ── 헤더 배너 ── */
    .hana-header {
        background: linear-gradient(135deg, #0A2342 0%, #1A3A5C 50%, #0D2137 100%);
        border-bottom: 2px solid #00A3E0;
        padding: 16px 28px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: -1rem -1rem 1.5rem -1rem;
        border-radius: 0 0 8px 8px;
    }
    .hana-logo-block {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .hana-logo-icon {
        width: 42px;
        height: 42px;
        background: linear-gradient(135deg, #00A3E0, #0077B6);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.4rem;
        font-weight: 900;
        color: white;
        letter-spacing: -1px;
    }
    .hana-logo-text {
        line-height: 1.2;
    }
    .hana-logo-text .company {
        font-size: 1.1rem;
        font-weight: 700;
        color: #FFFFFF;
        letter-spacing: 0.3px;
    }
    .hana-logo-text .tagline {
        font-size: 0.72rem;
        color: #00A3E0;
        font-weight: 500;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .hana-header-right {
        text-align: right;
    }
    .hana-header-right .sys-title {
        font-size: 0.78rem;
        color: #6B8CAE;
        font-weight: 400;
    }
    .hana-header-right .sys-name {
        font-size: 0.92rem;
        color: #A8CCEA;
        font-weight: 600;
    }

    /* ── 사이드바 브랜드 블록 ── */
    .sidebar-brand {
        background: linear-gradient(135deg, #00A3E0 0%, #0077B6 100%);
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 20px;
        text-align: center;
    }
    .sidebar-brand .sb-company {
        font-size: 1.05rem;
        font-weight: 700;
        color: #fff;
        letter-spacing: 0.3px;
    }
    .sidebar-brand .sb-tagline {
        font-size: 0.7rem;
        color: rgba(255,255,255,0.8);
        margin-top: 2px;
    }
    .sidebar-info {
        background: rgba(0,163,224,0.08);
        border: 1px solid rgba(0,163,224,0.2);
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 16px;
        font-size: 0.75rem;
        color: #7A9AB5;
        line-height: 1.7;
    }
    .sidebar-info .info-row {
        display: flex;
        gap: 6px;
        align-items: flex-start;
    }
    .sidebar-menu-label {
        font-size: 0.68rem;
        font-weight: 600;
        color: #4A6A8A;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        padding: 0 0 6px 0;
        border-bottom: 1px solid #1E3A5F;
        margin-bottom: 8px;
    }

    /* ── KPI 카드 ── */
    .kpi-card {
        background: linear-gradient(135deg, #161B22 0%, #1C2433 100%);
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 20px 22px;
        position: relative;
        overflow: hidden;
        transition: border-color 0.2s, transform 0.2s;
    }
    .kpi-card:hover {
        border-color: #00A3E0;
        transform: translateY(-2px);
    }
    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        border-radius: 12px 12px 0 0;
    }
    .kpi-card.blue::before { background: linear-gradient(90deg, #00A3E0, #0077B6); }
    .kpi-card.green::before { background: linear-gradient(90deg, #38A169, #2D7A56); }
    .kpi-card.orange::before { background: linear-gradient(90deg, #F6AD55, #E58C1A); }
    .kpi-card.purple::before { background: linear-gradient(90deg, #805AD5, #6B46C1); }
    .kpi-card.teal::before { background: linear-gradient(90deg, #319795, #2C7A7B); }

    .kpi-icon {
        font-size: 1.8rem;
        margin-bottom: 8px;
        display: block;
    }
    .kpi-label {
        font-size: 0.75rem;
        color: #6B8CAE;
        font-weight: 500;
        letter-spacing: 0.3px;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #E6EDF3;
        line-height: 1;
    }
    .kpi-sub {
        font-size: 0.72rem;
        color: #4A6A8A;
        margin-top: 4px;
    }

    /* ── 섹션 헤더 ── */
    .section-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 10px;
        border-bottom: 1px solid #21262D;
    }
    .section-header .sh-icon {
        width: 32px;
        height: 32px;
        background: linear-gradient(135deg, #00A3E0, #0077B6);
        border-radius: 7px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.9rem;
    }
    .section-header h3 {
        font-size: 1.05rem;
        font-weight: 600;
        color: #E6EDF3;
        margin: 0;
    }

    /* ── 정보 박스 ── */
    .info-box {
        background: rgba(0,163,224,0.07);
        border: 1px solid rgba(0,163,224,0.25);
        border-left: 3px solid #00A3E0;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 0.82rem;
        color: #8BBEDC;
        margin-bottom: 1rem;
        line-height: 1.6;
    }
    .warn-box {
        background: rgba(246,173,85,0.07);
        border: 1px solid rgba(246,173,85,0.25);
        border-left: 3px solid #F6AD55;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 0.82rem;
        color: #D4A843;
        margin-bottom: 1rem;
    }
    .success-box {
        background: rgba(56,161,105,0.07);
        border: 1px solid rgba(56,161,105,0.25);
        border-left: 3px solid #38A169;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 0.82rem;
        color: #68C48A;
        margin-bottom: 1rem;
    }

    /* ── 파이프라인 퍼널 ── */
    .funnel-bar {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 14px;
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 8px;
        margin-bottom: 8px;
        transition: border-color 0.2s;
    }
    .funnel-bar:hover { border-color: #30363D; }
    .funnel-stage {
        font-size: 0.8rem;
        font-weight: 600;
        min-width: 80px;
        color: #A8B8C8;
    }
    .funnel-track {
        flex: 1;
        background: #21262D;
        border-radius: 4px;
        height: 10px;
        overflow: hidden;
    }
    .funnel-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.6s ease;
    }
    .funnel-count {
        font-size: 0.85rem;
        font-weight: 700;
        min-width: 30px;
        text-align: right;
        color: #E6EDF3;
    }

    /* ── 예산 시즌 카드 ── */
    .season-card {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 10px;
        display: flex;
        gap: 14px;
        align-items: flex-start;
        transition: border-color 0.2s;
    }
    .season-card.active {
        background: linear-gradient(135deg, rgba(0,163,224,0.12) 0%, rgba(0,119,182,0.08) 100%);
        border-color: #00A3E0;
        box-shadow: 0 0 0 1px rgba(0,163,224,0.3);
    }
    .season-icon {
        font-size: 1.5rem;
        min-width: 36px;
        text-align: center;
    }
    .season-body {}
    .season-month {
        font-size: 0.78rem;
        color: #4A6A8A;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .season-type {
        font-size: 0.95rem;
        font-weight: 700;
        color: #E6EDF3;
        margin: 2px 0 4px 0;
    }
    .season-card.active .season-type { color: #00A3E0; }
    .season-desc {
        font-size: 0.78rem;
        color: #6B8CAE;
        line-height: 1.6;
    }
    .season-badge {
        display: inline-block;
        background: linear-gradient(135deg, #00A3E0, #0077B6);
        color: white;
        font-size: 0.65rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 10px;
        margin-left: 8px;
        vertical-align: middle;
        letter-spacing: 0.5px;
    }

    /* ── 버튼 스타일 ── */
    .stButton > button {
        background: linear-gradient(135deg, #00A3E0 0%, #0077B6 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 0.45rem 1.2rem !important;
        transition: all 0.2s !important;
        box-shadow: 0 2px 8px rgba(0,163,224,0.25) !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #0077B6 0%, #005A8E 100%) !important;
        box-shadow: 0 4px 14px rgba(0,163,224,0.4) !important;
        transform: translateY(-1px) !important;
    }

    /* ── 데이터프레임 ── */
    .stDataFrame {
        border: 1px solid #21262D !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }

    /* ── 입력 필드 ── */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        background-color: #161B22 !important;
        border-color: #30363D !important;
        color: #E6EDF3 !important;
        border-radius: 8px !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #00A3E0 !important;
        box-shadow: 0 0 0 1px rgba(0,163,224,0.3) !important;
    }

    /* ── 탭 스타일 제거 (사이드바 메뉴로 대체) ── */

    /* ── 구분선 ── */
    hr {
        border-color: #21262D !important;
        margin: 1.5rem 0 !important;
    }

    /* ── 스케줄러 상태 뱃지 ── */
    .sched-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(56,161,105,0.15);
        border: 1px solid rgba(56,161,105,0.3);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.75rem;
        color: #68C48A;
        font-weight: 500;
    }
    .sched-dot {
        width: 6px; height: 6px;
        background: #38A169;
        border-radius: 50%;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    /* ── 경쟁사 카드 ── */
    .comp-card {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .comp-name { font-size: 0.88rem; font-weight: 600; color: #E6EDF3; }
    .comp-count {
        font-size: 1.1rem;
        font-weight: 700;
        color: #00A3E0;
    }

    /* ── 빈 상태 ── */
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        color: #4A6A8A;
    }
    .empty-state .empty-icon { font-size: 2.5rem; margin-bottom: 12px; }
    .empty-state .empty-msg { font-size: 0.88rem; }

    /* ── 스크롤바 ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0D1117; }
    ::-webkit-scrollbar-thumb { background: #30363D; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #484F58; }

    /* ── Streamlit 기본 요소 커스텀 ── */
    .stAlert { border-radius: 8px !important; }
    .stSuccess { background: rgba(56,161,105,0.1) !important; border-color: rgba(56,161,105,0.3) !important; }
    .stWarning { background: rgba(246,173,85,0.1) !important; border-color: rgba(246,173,85,0.3) !important; }
    .stError { background: rgba(252,129,129,0.1) !important; border-color: rgba(252,129,129,0.3) !important; }
    .stInfo { background: rgba(0,163,224,0.08) !important; border-color: rgba(0,163,224,0.25) !important; }

    /* 메트릭 카드 */
    [data-testid="stMetric"] {
        background: #161B22 !important;
        border: 1px solid #21262D !important;
        border-radius: 10px !important;
        padding: 14px !important;
    }
    [data-testid="stMetricLabel"] { color: #6B8CAE !important; font-size: 0.78rem !important; }
    [data-testid="stMetricValue"] { color: #E6EDF3 !important; }

    /* 제목 스타일 */
    h1 { color: #E6EDF3 !important; font-weight: 700 !important; font-size: 1.6rem !important; }
    h2 { color: #C9D1D9 !important; font-weight: 600 !important; font-size: 1.3rem !important; }
    h3 { color: #C9D1D9 !important; font-weight: 600 !important; }

    /* 익스팬더 */
    .streamlit-expanderHeader {
        background: #161B22 !important;
        border: 1px solid #21262D !important;
        border-radius: 8px !important;
        color: #A8B8C8 !important;
    }
    </style>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 공통 헬퍼
# ──────────────────────────────────────────────
@st.cache_data
def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode('utf-8-sig')


def call_gemini(prompt: str) -> str:
    import requests
    from config import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        return "⚠️ GEMINI_API_KEY가 설정되지 않았습니다."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 2048},
    }
    try:
        res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
        if res.status_code == 200:
            parts = res.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return parts[0].get("text", "결과 없음") if parts else "결과 없음"
        return f"⚠️ API 에러 [{res.status_code}]: {res.text}"
    except Exception as e:
        return f"⚠️ 오류: {e}"


def section_header(icon: str, title: str):
    """공통 섹션 헤더 컴포넌트."""
    st.markdown(f"""
    <div class="section-header">
        <div class="sh-icon">{icon}</div>
        <h3>{title}</h3>
    </div>
    """, unsafe_allow_html=True)


def info_box(msg: str):
    st.markdown(f'<div class="info-box">ℹ️ &nbsp;{msg}</div>', unsafe_allow_html=True)


def empty_state(icon: str, msg: str):
    st.markdown(f"""
    <div class="empty-state">
        <div class="empty-icon">{icon}</div>
        <div class="empty-msg">{msg}</div>
    </div>
    """, unsafe_allow_html=True)


def render_kpi_card(icon: str, label: str, value, sub: str = "", color: str = "blue"):
    st.markdown(f"""
    <div class="kpi-card {color}">
        <span class="kpi-icon">{icon}</span>
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 사이드바
# ──────────────────────────────────────────────
def render_sidebar() -> str:
    with st.sidebar:
        # 브랜드 블록
        st.markdown("""
        <div class="sidebar-brand">
            <div class="sb-company">(주)하나티에스</div>
            <div class="sb-tagline">CATIA · SolidWorks · 3DEXPERIENCE</div>
        </div>
        """, unsafe_allow_html=True)

        # 회사 정보
        st.markdown("""
        <div class="sidebar-info">
            <div class="info-row">📍 부산 사상구 모라로 22<br>&nbsp;&nbsp;&nbsp;&nbsp;부산벤처타워 905호</div>
            <div class="info-row">📞 02-6957-1855</div>
            <div class="info-row">🌐 <a href="https://1ts.kr" target="_blank" style="color:#00A3E0;">1ts.kr</a></div>
        </div>
        """, unsafe_allow_html=True)

        # 메뉴
        st.markdown('<div class="sidebar-menu-label">NAVIGATION</div>', unsafe_allow_html=True)

        menu_items = {
            "대시보드": "홈",
            "구매 신호 분석": "영업",
            "타겟 학교 DB": "영업",
            "타겟 발굴 및 공략": "영업",
            "영업 파이프라인": "영업",
            "공고 수집/분석": "정보수집",
            "경쟁사 분석": "분석",
            "학교알리미 조회": "분석",
            "Spec-in 문서 생성": "문서",
            "레퍼런스 카드 생성": "문서",
        }
        menu_icons = {
            "대시보드": "🏠",
            "구매 신호 분석": "📡",
            "타겟 학교 DB": "🗂️",
            "타겟 발굴 및 공략": "🎯",
            "영업 파이프라인": "📋",
            "공고 수집/분석": "📊",
            "경쟁사 분석": "🔍",
            "학교알리미 조회": "🔎",
            "Spec-in 문서 생성": "📝",
            "레퍼런스 카드 생성": "🏆",
        }

        labels = [f"{menu_icons[k]}  {k}" for k in menu_items.keys()]
        keys = list(menu_items.keys())

        selected_label = st.radio("", labels, label_visibility="collapsed")
        selected = keys[labels.index(selected_label)]

        # 하단 구분 & API 진단
        st.markdown("---")
        st.markdown('<div class="sidebar-menu-label">SYSTEM</div>', unsafe_allow_html=True)
        with st.expander("🛠️ API 상태 진단"):
            from config import GEMINI_API_KEY, TAVILY_API_KEY
            def mask(k):
                if not k: return "❌ 미설정"
                if len(k) < 10: return "⚠️ 짧음"
                return f"✅ {k[:4]}···{k[-4:]}"
            st.markdown(f"""
            <div style="font-size:0.75rem; color:#6B8CAE; line-height:2;">
            GEMINI &nbsp;{mask(GEMINI_API_KEY)}<br>
            TAVILY &nbsp;{mask(TAVILY_API_KEY)}<br>
            KONEPS &nbsp;✅ 설정됨
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="font-size:0.68rem; color:#2D4A62; text-align:center; margin-top:12px;">
            PSIS v2.0 · {datetime.today().strftime('%Y.%m.%d')}
        </div>
        """, unsafe_allow_html=True)

    return selected


# ──────────────────────────────────────────────
# 공통 헤더 배너
# ──────────────────────────────────────────────
def render_page_header(title: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="hana-header">
        <div class="hana-logo-block">
            <div class="hana-logo-icon">H</div>
            <div class="hana-logo-text">
                <div class="company">(주)하나티에스</div>
                <div class="tagline">Public Sales Intelligence System</div>
            </div>
        </div>
        <div class="hana-header-right">
            <div class="sys-title">{subtitle if subtitle else 'PSIS Dashboard'}</div>
            <div class="sys-name">{title}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 탭 렌더 함수
# ──────────────────────────────────────────────

def render_dashboard():
    render_page_header("대시보드", "현황 요약")

    if not check_db_connection():
        st.error("❌ 데이터베이스 연결 실패 — 경로와 권한을 확인하세요.")
        return

    pipeline = get_pipeline_summary()
    bids_df = get_all_bids()
    grants_df = get_all_grants()
    contacts_df = get_all_contacts()

    # 타겟 학교 통계
    target_df = get_all_target_schools()
    target_count = len(target_df)
    target_contacted = len(target_df[target_df['sales_status'] != '미접촉']) if not target_df.empty else 0

    # KPI 카드 행
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        render_kpi_card("🗂️", "타겟 학교", target_count, f"접촉 {target_contacted}교", "cyan")
    with c2:
        render_kpi_card("👥", "타겟 담당자", len(contacts_df), "발굴된 교수·담당자", "blue")
    with c3:
        render_kpi_card("🏆", "수주 완료", pipeline.get('수주', 0), "누적 수주 건수", "green")
    with c4:
        render_kpi_card("🤝", "협의 진행 중", pipeline.get('협의중', 0), "현재 협의 중인 건", "orange")
    with c5:
        render_kpi_card("📄", "수집 공고", len(bids_df), "나라장터 공고 건수", "purple")
    with c6:
        render_kpi_card("💰", "국고 사업", len(grants_df), "감지된 지원사업", "teal")

    # 구매 신호 요약
    sig_summary = pse.get_signal_summary()
    if sig_summary['total'] > 0:
        st.markdown("---")
        section_header("📡", "구매 신호 현황")
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            render_kpi_card("📡", "구매 신호", sig_summary['total'], f"미조치 {sig_summary['unacted']}건", "red")
        with sc2:
            budget_info = pse.get_budget_season_info()
            render_kpi_card("📅", "예산 시기", budget_info['season']['name'], f"+{budget_info['bonus']}점 보너스", "orange")
        with sc3:
            top5 = sig_summary.get('by_school_top5', [])
            render_kpi_card("🎯", "최우선 대상", top5[0]['school'] if top5 else "-", f"{top5[0]['max_score']}점" if top5 else "수집 필요", "green")
        with sc4:
            ntis_df = get_all_ntis_projects()
            render_kpi_card("🔬", "R&D 과제", len(ntis_df), "연구과제 뉴스", "blue")

    # 이번 주 할 일 (Top 5)
    weekly_top5 = pse.get_weekly_action_list(top_n=5)
    if weekly_top5:
        st.markdown("---")
        section_header("🎯", "이번 주 접근 대상 TOP 5")
        for i, s in enumerate(weekly_top5):
            score_color = "#FF6B6B" if s['total_score'] >= 80 else "#F6AD55" if s['total_score'] >= 50 else "#4A6A8A"
            st.markdown(f"""
            <div style="background:#161B22; border:1px solid #21262D; border-radius:8px;
                         padding:10px 14px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-weight:700; color:#E8EDF2; font-size:0.88rem;">{i+1}. {s['school_name']}</span>
                    <span style="font-size:0.7rem; color:#4A6A8A; margin-left:8px;">{s['program_name']} · {s['sales_status']}</span>
                </div>
                <div style="background:{score_color}22; color:{score_color}; padding:2px 10px;
                            border-radius:12px; font-size:0.75rem; font-weight:600;">{s['total_score']}점</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    col_left, col_right = st.columns([1.4, 1])

    with col_left:
        section_header("📊", "영업 파이프라인 퍼널")
        max_val = max((pipeline.get(s, 0) for s in PIPELINE_STAGES), default=1) or 1

        for stage in PIPELINE_STAGES:
            cnt = pipeline.get(stage, 0)
            pct = int(cnt / max_val * 100)
            color = STAGE_COLORS.get(stage, '#00A3E0')
            st.markdown(f"""
            <div class="funnel-bar">
                <div class="funnel-stage">{stage}</div>
                <div class="funnel-track">
                    <div class="funnel-fill" style="width:{pct}%; background:{color};"></div>
                </div>
                <div class="funnel-count" style="color:{color};">{cnt}</div>
            </div>
            """, unsafe_allow_html=True)

    with col_right:
        section_header("⚡", "자동 수집 스케줄러")
        sched_jobs = get_scheduler_status()
        if sched_jobs:
            st.markdown('<div class="sched-badge"><div class="sched-dot"></div>AUTO 수집 활성</div>',
                        unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            for job in sched_jobs:
                next_run = job.get('next_run', '-')
                st.markdown(f"""
                <div style="background:#161B22; border:1px solid #21262D; border-radius:8px;
                             padding:10px 14px; margin-bottom:8px; font-size:0.8rem;">
                    <div style="color:#A8B8C8; font-weight:600;">{job.get('id','')}</div>
                    <div style="color:#4A6A8A; font-size:0.72rem; margin-top:3px;">
                        다음 실행: {next_run}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:#161B22; border:1px dashed #2D4A62; border-radius:8px;
                         padding:20px; text-align:center; color:#4A6A8A; font-size:0.8rem;">
                스케줄러 비활성 상태<br>
                <span style="font-size:0.72rem;">apscheduler 설치 후 재시작 시 자동 활성화</span>
            </div>
            """, unsafe_allow_html=True)

        # 이번 달 예산 시즌 알림
        st.markdown("<br>", unsafe_allow_html=True)
        section_header("📅", "이번 달 영업 포인트")
        now_month = datetime.today().month
        active_season = None
        for season in BUDGET_SEASONS:
            try:
                parts = season["월"].replace("월", "").split("~")
                s, e = int(parts[0].strip()), int(parts[-1].strip())
                if s <= now_month <= e:
                    active_season = season
                    break
            except Exception:
                pass
        if active_season:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,rgba(0,163,224,0.12),rgba(0,119,182,0.06));
                         border:1px solid rgba(0,163,224,0.3); border-radius:10px; padding:14px 16px;">
                <div style="font-size:1.4rem; margin-bottom:6px;">{active_season['icon']}</div>
                <div style="font-size:0.88rem; font-weight:700; color:#00A3E0;">{active_season['유형']}</div>
                <div style="font-size:0.75rem; color:#6B8CAE; margin-top:4px; line-height:1.6;">
                    {active_season['설명']}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="info-box">현재 특별한 예산 집행 시즌이 아닙니다.</div>',
                        unsafe_allow_html=True)


def render_target_discovery():
    render_page_header("타겟 발굴 및 공략", "AI 자동 교수·담당자 탐색")

    tab_individual, tab_cad_scan = st.tabs(["🎯 개별 교수 발굴", "🔬 CAD 학과 일괄 스캔"])

    # ── 탭1: 기존 개별 교수 발굴 ──
    with tab_individual:
        info_box("학교명만 입력하면 AI가 3D CAD·디지털 트윈 관련 교수진 연락처를 자동 수집합니다.")

        col1, col2 = st.columns([1, 2])

        with col1:
            section_header("🎯", "타겟 자동 발굴")
            school_name = st.text_input("타겟 학교명", placeholder="예) 인하대학교", label_visibility="collapsed")
            st.caption("학교명을 입력하고 발굴 버튼을 누르세요")
            if st.button("🔍  교수 자동 발굴 시작", use_container_width=True):
                if not school_name.strip():
                    st.error("학교명을 입력해주세요.")
                else:
                    with st.spinner(f"'{school_name}' 교수진 탐색 중… (최대 1분)"):
                        try:
                            professors = cc.search_and_extract_professors(school_name)
                            if not professors:
                                st.warning("유효한 교수 정보를 찾지 못했습니다.")
                            else:
                                inserted = insert_contacts(professors)
                                st.success(f"✅ {len(professors)}명 발굴 / {inserted}건 신규 저장")
                        except Exception as e:
                            st.error(f"오류: {e}")

        with col2:
            section_header("📋", "발굴된 타겟 현황")
            df = get_all_contacts()
            if not df.empty:
                display_cols = [c for c in ['school_name', 'name', 'department', 'email', 'phone', 'contact_status']
                                if c in df.columns]
                st.dataframe(
                    df[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "school_name": "학교명",
                        "name": "담당자명",
                        "department": "학과/부서",
                        "email": "이메일",
                        "phone": "전화번호",
                        "contact_status": "영업 상태",
                    }
                )
                st.download_button(
                    "📥 연락처 CSV 다운로드",
                    convert_df_to_csv(df),
                    "target_contacts.csv", "text/csv",
                )
            else:
                empty_state("👤", "아직 발굴된 담당자가 없습니다.\n좌측에서 학교명을 입력하고 발굴을 시작하세요.")

    # ── 탭2: CAD 학과 일괄 스캔 ──
    with tab_cad_scan:
        info_box(
            "타겟 학교 DB의 학교를 순회하며 CAD/CAM 교과목이 있는 학과를 자동 탐색합니다. "
            "발견되면 해당 학과 교수진 정보까지 자동 수집합니다. "
            "(Tavily 웹검색 + Gemini AI 추출)"
        )
        st.caption("⚠️ 수집된 정보는 학교 공개 웹페이지 기반이며, 영업 활용 시 정보통신망법을 준수하세요.")

        # KPI 카드
        stats = get_cad_department_stats()
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_kpi_card("🏫", "전체 학교", stats['total'], "타겟 학교 DB", "cyan")
        with c2:
            render_kpi_card("✅", "CAD 학과 보유", stats['has_cad'], "확인 완료", "green")
        with c3:
            render_kpi_card("❌", "CAD 학과 없음", stats['no_cad'], "확인 완료", "red")
        with c4:
            render_kpi_card("⏳", "미확인", stats['pending'], "스캔 대기", "orange")

        st.markdown("---")

        # 스캔 실행
        col_ctrl, col_result = st.columns([1, 2])

        with col_ctrl:
            section_header("⚙️", "스캔 설정")
            max_schools = st.number_input(
                "한 번에 스캔할 학교 수", min_value=1, max_value=30, value=5, step=1,
                key="cad_max_schools"
            )
            collect_prof = st.checkbox("교수 정보도 함께 수집", value=True, key="cad_collect_prof")

            if st.button("🔬 CAD 학과 일괄 스캔 시작", use_container_width=True, key="cad_batch_btn"):
                with st.spinner(f"상위 {max_schools}교 CAD 학과 스캔 중… (학교당 약 30초)"):
                    try:
                        result = cad_crawler.batch_scan_cad_departments(
                            max_schools=max_schools,
                            collect_professors=collect_prof,
                        )
                        st.success(
                            f"✅ {result['scanned']}교 스캔 완료 | "
                            f"CAD 학과 {result['cad_found']}교 발견 | "
                            f"교수 {result['professors_saved']}명 저장"
                        )
                        # 결과 상세를 session_state에 저장
                        st.session_state['cad_scan_results'] = result.get('results', [])
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류: {e}")

            # 개별 학교 스캔
            st.markdown("---")
            section_header("🔍", "개별 학교 스캔")
            single_school = st.text_input("학교명", placeholder="예) 서울대학교", key="cad_single")
            if st.button("이 학교만 스캔", use_container_width=True, key="cad_single_btn"):
                if single_school.strip():
                    with st.spinner(f"'{single_school}' CAD 학과 탐색 중…"):
                        try:
                            res = cad_crawler.scan_cad_department(single_school.strip())
                            if res['has_cad_dept']:
                                dept_str = ', '.join(res['dept_names'])
                                st.success(f"✅ CAD 관련 학과 발견: {dept_str}")
                                # 교수 수집
                                if collect_prof:
                                    with st.spinner("교수진 정보 수집 중…"):
                                        profs = cad_crawler.scan_and_collect_professors(
                                            single_school.strip(), res['dept_names']
                                        )
                                        if profs:
                                            saved = insert_contacts(profs)
                                            st.success(f"✅ 교수 {len(profs)}명 발굴 / {saved}건 신규 저장")
                                        else:
                                            st.info("교수 정보를 찾지 못했습니다.")

                                # 상세 결과 표시
                                for dept in res.get('details', []):
                                    with st.expander(f"📚 {dept.get('dept_name', '')} (신뢰도: {dept.get('confidence', '-')})"):
                                        subjects = dept.get('cad_subjects', [])
                                        if subjects:
                                            st.markdown("**CAD 관련 교과목:** " + ', '.join(subjects))
                            else:
                                st.warning(f"'{single_school}'에서 CAD 관련 학과를 찾지 못했습니다.")
                        except Exception as e:
                            st.error(f"오류: {e}")

        with col_result:
            # 최근 스캔 결과
            scan_results = st.session_state.get('cad_scan_results', [])
            if scan_results:
                section_header("📊", "최근 스캔 결과")
                for r in scan_results:
                    icon = "✅" if r.get('has_cad') else ("❌" if r.get('has_cad') is False else "⚠️")
                    dept_str = ', '.join(r.get('dept_names', [])) if r.get('dept_names') else '-'
                    prof_cnt = r.get('professors_count', 0)
                    st.markdown(f"""
                    <div style="background:#161B22; border:1px solid #21262D; border-radius:8px;
                                 padding:10px 14px; margin-bottom:6px; font-size:0.85rem;">
                        <span style="margin-right:6px;">{icon}</span>
                        <strong style="color:#E8EDF2;">{r.get('school_name','')}</strong>
                        <span style="color:#4A6A8A; margin-left:8px;">학과: {dept_str}</span>
                        {f'<span style="color:#68D391; margin-left:8px;">교수 {prof_cnt}명 저장</span>' if prof_cnt else ''}
                        {f'<span style="color:#FC8181; margin-left:8px;">오류: {r.get("error","")[:30]}</span>' if r.get("error") else ''}
                    </div>
                    """, unsafe_allow_html=True)

            # CAD 학과 확인된 학교 목록
            st.markdown("---")
            section_header("🏫", "CAD 학과 보유 확인 학교")
            cad_df = get_cad_confirmed_schools()
            if not cad_df.empty:
                st.dataframe(
                    cad_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "school_name": "학교명",
                        "school_type": "유형",
                        "cad_dept_names": "CAD 관련 학과",
                        "program_name": "사업명",
                        "priority_score": "우선순위",
                        "sales_status": "영업상태",
                    }
                )

                # 선택한 학교 교수 발굴
                sel = st.selectbox(
                    "교수 발굴할 학교 선택", cad_df['school_name'].tolist(), key="cad_prof_sel"
                )
                if st.button("🎯 이 학교 교수 발굴", key="cad_prof_btn"):
                    row = cad_df[cad_df['school_name'] == sel].iloc[0]
                    depts = [d.strip() for d in str(row.get('cad_dept_names', '')).split(',') if d.strip()]
                    if depts:
                        with st.spinner(f"'{sel}' 교수진 수집 중…"):
                            profs = cad_crawler.scan_and_collect_professors(sel, depts)
                            if profs:
                                saved = insert_contacts(profs)
                                st.success(f"✅ {len(profs)}명 발굴 / {saved}건 신규 저장")
                            else:
                                st.info("교수 정보를 찾지 못했습니다.")
                    else:
                        st.warning("학과 정보가 없습니다. 먼저 스캔을 실행하세요.")
            else:
                empty_state("🔬", "아직 스캔된 학교가 없습니다.\n좌측에서 스캔을 시작하세요.")


def render_pipeline():
    render_page_header("영업 파이프라인", "단계별 진행 관리")

    df = get_all_contacts()
    if df.empty:
        empty_state("📋", "'타겟 발굴' 탭에서 먼저 담당자를 발굴하세요.")
        return

    # 단계별 요약 바
    pipeline = get_pipeline_summary()
    cols = st.columns(len(PIPELINE_STAGES))
    for i, stage in enumerate(PIPELINE_STAGES):
        cnt = pipeline.get(stage, 0)
        color = STAGE_COLORS.get(stage, '#00A3E0')
        cols[i].markdown(f"""
        <div style="background:#161B22; border:1px solid {color}30; border-top:3px solid {color};
                     border-radius:8px; padding:10px; text-align:center;">
            <div style="font-size:1.4rem; font-weight:700; color:{color};">{cnt}</div>
            <div style="font-size:0.72rem; color:#6B8CAE; margin-top:2px;">{stage}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        section_header("📊", "연락처 목록")
        filter_stage = st.selectbox("단계 필터", ["전체"] + PIPELINE_STAGES, label_visibility="collapsed")
        if filter_stage != "전체" and 'contact_status' in df.columns:
            view_df = df[df['contact_status'] == filter_stage]
        else:
            view_df = df

        display_cols = [c for c in ['id', 'school_name', 'name', 'department', 'email',
                                     'contact_status', 'next_action_date', 'memo'] if c in view_df.columns]
        st.dataframe(view_df[display_cols], use_container_width=True, hide_index=True,
                     column_config={
                         "id": st.column_config.NumberColumn("ID", width="small"),
                         "school_name": "학교명",
                         "name": "담당자",
                         "department": "학과",
                         "email": "이메일",
                         "contact_status": "상태",
                         "next_action_date": "다음 액션일",
                         "memo": "메모",
                     })

    with col_right:
        section_header("✏️", "상태 업데이트")
        target_id = st.number_input("연락처 ID", min_value=1, step=1)
        new_status = st.selectbox("변경 상태", PIPELINE_STAGES)
        next_date = st.date_input("다음 액션 예정일", value=datetime.today() + timedelta(days=7))
        memo = st.text_area("메모", height=100, placeholder="미팅 내용, 다음 액션 등")

        if st.button("💾  상태 저장", use_container_width=True):
            ok = update_contact_pipeline(int(target_id), new_status, memo, str(next_date))
            if ok:
                st.success(f"ID {target_id} → '{new_status}' 업데이트 완료")
                st.rerun()
            else:
                st.error("업데이트 실패. ID를 확인해주세요.")

        st.markdown("---")
        st.download_button(
            "📥 파이프라인 CSV",
            convert_df_to_csv(df[display_cols] if display_cols else df),
            "pipeline_status.csv", "text/csv",
            use_container_width=True,
        )




def render_bid_analysis():
    render_page_header("공고 수집/분석", "나라장터 + 교육청 공고 통합")

    tab_koneps, tab_edu, tab_replace = st.tabs(["📊 나라장터 공고", "🏛️ 교육청 공고", "⚠️ 교체 주기 타겟"])

    # ── 탭1: 나라장터 공고 ──
    with tab_koneps:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("최근 공고 수집\n(7일)", use_container_width=True):
                with st.spinner("최근 7일 공고 수집 중…"):
                    try:
                        count = ak.fetch_recent_bids(days=7)
                        st.success(f"✅ {count}건")
                    except Exception as e:
                        st.error(f"❌ {e}")
        with col2:
            if st.button("과거 공고 수집\n(5년)", use_container_width=True):
                ph = st.empty()
                with st.spinner("5년치 수집 중… (1~2분)"):
                    try:
                        count = ak.fetch_past_bids(years=5, st_placeholder=ph)
                        ph.empty()
                        st.success(f"✅ {count}건")
                    except Exception as e:
                        ph.empty()
                        st.error(f"❌ {e}")
        with col3:
            if st.button("사전규격 탐색\n(30일)", use_container_width=True):
                with st.spinner("사전규격 탐색 중…"):
                    try:
                        count = ak.fetch_pre_spec_bids(30)
                        st.success(f"✅ {count}건" if count > 0 else "새 건 없음")
                    except Exception as e:
                        st.error(f"❌ {e}")
        with col4:
            if st.button("낙찰결과\n업데이트", use_container_width=True):
                with st.spinner("낙찰 결과 조회 중…"):
                    try:
                        count = ak.fetch_bid_results_for_history()
                        st.success(f"✅ {count}건")
                    except Exception as e:
                        st.error(f"❌ {e}")

        st.markdown("---")
        df_bids = get_all_bids()
        if not df_bids.empty:
            df_bids_view = df_bids.copy()
            df_bids_view['contract_date'] = pd.to_datetime(df_bids_view['contract_date'], errors='coerce').dt.strftime('%Y-%m-%d')
            section_header("📋", f"전체 입찰 이력 ({len(df_bids_view)}건)")
            st.dataframe(df_bids_view, use_container_width=True, hide_index=True)
            st.download_button("📥 전체 이력 CSV", convert_df_to_csv(df_bids_view), "all_bids.csv", "text/csv")
        else:
            empty_state("📂", "저장된 데이터가 없습니다. 위 버튼으로 데이터를 수집하세요.")

    # ── 탭2: 교육청 공고 ──
    with tab_edu:
        col1, col2 = st.columns([1, 2])
        with col1:
            section_header("⚙️", "수집 설정")
            days = st.slider("수집 기간 (일)", min_value=7, max_value=90, value=30, step=7, key="edu_days")
            if st.button("🏛️  교육청 공고 수집", use_container_width=True, key="edu_fetch"):
                with st.spinner(f"최근 {days}일 교육청 공고 수집 중…"):
                    try:
                        count = edu.fetch_edu_office_bids(days=days)
                        st.success(f"✅ {count}건 신규 저장")
                    except Exception as e:
                        st.error(f"❌ {e}")

            st.markdown("---")
            section_header("📊", "교육청별 현황")
            summary = edu.get_edu_office_summary()
            if summary:
                for agency, cnt in list(summary.items())[:10]:
                    short = agency.replace("교육청", "").replace("특별시", "").replace("광역시", "").replace("특별자치시", "").replace("특별자치도", "").replace("도", "")
                    st.markdown(f"""
                    <div class="comp-card">
                        <div class="comp-name">{short} 교육청</div>
                        <div class="comp-count">{cnt}건</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                empty_state("📭", "수집된 공고가 없습니다.")

        with col2:
            section_header("📋", "수집된 교육청 공고 목록")
            df_bids_all = get_all_bids()
            if not df_bids_all.empty and "bid_type" in df_bids_all.columns:
                edu_df = df_bids_all[df_bids_all["bid_type"] == "교육청공고"].copy()
                if not edu_df.empty:
                    edu_df["contract_date"] = pd.to_datetime(
                        edu_df["contract_date"], errors="coerce"
                    ).dt.strftime("%Y-%m-%d")
                    show = [c for c in ["bid_title", "demand_agency", "contract_date", "bid_price"]
                            if c in edu_df.columns]
                    st.dataframe(edu_df[show], use_container_width=True, hide_index=True,
                                 column_config={
                                     "bid_title": "공고명",
                                     "demand_agency": "발주기관",
                                     "contract_date": "공고일",
                                     "bid_price": "추정가격",
                                 })
                    st.download_button("📥 교육청 공고 CSV", convert_df_to_csv(edu_df[show]),
                                       "edu_office_bids.csv", "text/csv", key="edu_csv")
                else:
                    empty_state("📭", "수집된 교육청 공고가 없습니다.\n좌측 버튼으로 수집을 시작하세요.")
            else:
                empty_state("📭", "수집된 교육청 공고가 없습니다.\n좌측 버튼으로 수집을 시작하세요.")

    # ── 탭3: 교체 주기 타겟 ──
    with tab_replace:
        df_bids_raw = get_all_bids()
        if not df_bids_raw.empty:
            df_bids_raw['contract_date'] = pd.to_datetime(df_bids_raw['contract_date'], errors='coerce')
            today = pd.Timestamp.today()
            target_replace = df_bids_raw[
                (df_bids_raw['contract_date'] >= today - pd.DateOffset(years=5)) &
                (df_bids_raw['contract_date'] <= today - pd.DateOffset(years=3))
            ].copy()

            section_header("⚠️", "교체 주기 도래 타겟 (3~5년 경과)")
            if not target_replace.empty:
                st.markdown(f'<div class="warn-box">⚠️ {len(target_replace)}건의 교체·유지보수 타겟 이력 발견 — 선제 접촉을 권장합니다.</div>',
                            unsafe_allow_html=True)
                target_replace['contract_date'] = target_replace['contract_date'].dt.strftime('%Y-%m-%d')
                st.dataframe(target_replace, use_container_width=True, hide_index=True)
                st.download_button("📥 교체 타겟 CSV", convert_df_to_csv(target_replace), "target_bids.csv", "text/csv", key="replace_csv")
            else:
                st.markdown('<div class="info-box">현재 3~5년 차 교체 주기 해당 기관이 없습니다.</div>',
                            unsafe_allow_html=True)
        else:
            empty_state("📂", "입찰 데이터가 없습니다. '나라장터 공고' 탭에서 먼저 수집하세요.")




def render_spec_in():
    render_page_header("Spec-in 문서 생성", "맞춤형 도입 품의서·시방서 자동 작성")

    info_box("타겟 학교와 예산 정보를 입력하면 AI가 내부 기안용 Spec-in 문서 초안을 자동 작성합니다.")

    df_grants = get_all_grants()
    school_options = ["직접 입력"]
    if not df_grants.empty:
        school_options += (df_grants['selected_school'] + " (" + df_grants['project_name'] + ")").tolist()

    col1, col2 = st.columns([1, 1.5])
    with col1:
        section_header("📝", "제안 조건 입력")
        selected = st.selectbox("수집된 국고사업 리스트", school_options)

        auto_school = auto_project = auto_budget = ""
        if selected != "직접 입력":
            idx = school_options.index(selected) - 1
            auto_school = df_grants.iloc[idx]['selected_school']
            auto_project = df_grants.iloc[idx]['project_name']
            auto_budget = df_grants.iloc[idx]['budget_scale']

        with st.form("doc_gen_form"):
            school = st.text_input("타겟 학교명 *", value=auto_school, placeholder="한국대학교")
            project = st.text_input("정부 지원 사업명 *", value=auto_project, placeholder="LINC 3.0")
            budget = st.text_input("확보/추정 예산", value=auto_budget, placeholder="약 10억 원")
            solution = st.text_input("제안 솔루션명 *", placeholder="3DEXPERIENCE / 스마트팩토리 통합")
            extra = st.text_area("추가 강조 소구점", placeholder="유지보수 3년 무상 등", height=80)
            submitted = st.form_submit_button("✨  문서 초안 생성", use_container_width=True)

    with col2:
        section_header("📄", "생성된 문서")
        if submitted:
            if not school or not project or not solution:
                st.error("학교명, 사업명, 솔루션명은 필수입니다.")
            else:
                with st.spinner("Gemini AI가 맞춤형 문서를 작성 중…"):
                    result = dg.generate_spec_in_document(school, project, budget, solution, extra)
                    st.markdown(result)
        else:
            st.markdown("""
            <div style="background:#161B22; border:1px dashed #2D4A62; border-radius:10px;
                         padding:3rem; text-align:center; color:#4A6A8A;">
                <div style="font-size:2rem; margin-bottom:10px;">📄</div>
                <div style="font-size:0.85rem;">좌측 폼을 작성하고<br>생성 버튼을 누르세요</div>
            </div>
            """, unsafe_allow_html=True)


def render_reference_card():
    render_page_header("레퍼런스 카드 생성", "납품 실적 1페이지 레퍼런스")

    info_box("납품 실적을 입력하면 잠재 고객에게 공유 가능한 1장짜리 레퍼런스 카드를 자동 생성합니다.")

    col1, col2 = st.columns([1, 1.5])
    with col1:
        section_header("✏️", "납품 실적 입력")
        with st.form("ref_form"):
            r_school = st.text_input("납품 기관명 *", placeholder="○○대학교")
            r_solution = st.text_input("도입 솔루션 *", placeholder="CATIA V5 / 3DEXPERIENCE")
            r_project = st.text_input("연계 사업명", placeholder="LINC+ 사회맞춤형학과")
            r_year = st.text_input("납품 연도", placeholder="2024")
            r_budget = st.text_input("사업 규모", placeholder="약 5억 원")
            r_outcome = st.text_area("도입 성과", placeholder="실습실 30석 구축, 취업률 15% 향상 등", height=80)
            save_ref = st.checkbox("DB에 실적 저장")
            submitted = st.form_submit_button("✨  레퍼런스 카드 생성", use_container_width=True)

    with col2:
        section_header("🏆", "생성된 레퍼런스 카드")
        if submitted:
            if not r_school or not r_solution:
                st.error("납품 기관명과 솔루션명은 필수입니다.")
            else:
                if save_ref:
                    insert_reference(r_school, r_solution, r_project, r_year, r_budget, r_outcome)
                    st.success("✅ 실적이 DB에 저장되었습니다.")
                with st.spinner("AI가 레퍼런스 카드를 작성 중…"):
                    prompt = build_reference_card_prompt(r_school, r_solution, r_project, r_year, r_budget, r_outcome)
                    result = call_gemini(prompt)
                    st.markdown(result)
        else:
            st.markdown("""
            <div style="background:#161B22; border:1px dashed #2D4A62; border-radius:10px;
                         padding:3rem; text-align:center; color:#4A6A8A;">
                <div style="font-size:2rem; margin-bottom:10px;">🏆</div>
                <div style="font-size:0.85rem;">좌측 폼을 작성하고<br>생성 버튼을 누르세요</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    section_header("📋", "저장된 납품 레퍼런스 목록")
    ref_df = get_all_references()
    if not ref_df.empty:
        st.dataframe(ref_df, use_container_width=True, hide_index=True)
        st.download_button("📥 레퍼런스 목록 CSV", convert_df_to_csv(ref_df), "references.csv", "text/csv")
    else:
        empty_state("📂", "저장된 레퍼런스 실적이 없습니다.")


def render_school_info():
    render_page_header("학교알리미 조회", "NEIS 학교 기본정보·학과·취업률")

    info_box("학교명을 검색하면 기본정보·학과·취업률을 자동 조회합니다. Spec-in 문서 작성 시 데이터를 활용하세요.")

    col1, col2 = st.columns([1, 2])
    with col1:
        section_header("🔎", "학교 검색")
        school_type = st.selectbox(
            "학교 유형",
            ["전체", "특성화고등학교", "마이스터고등학교", "전문대학", "대학교"],
        )
        search_nm = st.text_input("학교명", placeholder="인하대학교")

        if st.button("조회", use_container_width=True):
            if not search_nm.strip() and school_type == "전체":
                st.error("학교명 또는 유형을 선택해주세요.")
            else:
                with st.spinner("NEIS에서 조회 중…"):
                    results = neis.search_schools(
                        school_name=search_nm.strip(),
                        school_type="" if school_type == "전체" else school_type,
                    )
                    if results:
                        st.session_state["neis_results"] = results
                        st.success(f"✅ {len(results)}개 학교 발견")
                    else:
                        st.warning("검색 결과가 없습니다.")

    with col2:
        section_header("📋", "검색 결과")
        results = st.session_state.get("neis_results", [])
        if results:
            df = pd.DataFrame(results)
            display_cols = [c for c in ["school_name", "school_type", "region", "edu_office",
                                         "address", "phone", "homepage", "found_type"] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True,
                         column_config={
                             "school_name": "학교명",
                             "school_type": "학교 유형",
                             "region": "지역",
                             "edu_office": "교육청",
                             "address": "주소",
                             "phone": "전화",
                             "homepage": "홈페이지",
                             "found_type": "설립유형",
                         })
            st.download_button("📥 학교 목록 CSV", convert_df_to_csv(df[display_cols]),
                               "school_list.csv", "text/csv")
        else:
            empty_state("🏫", "좌측에서 학교명 또는 유형을 선택하고 조회하세요.")

    st.markdown("---")
    section_header("🔍", "개별 학교 상세 프로파일")
    detail_nm = st.text_input("상세 조회할 학교명", placeholder="인하대학교", key="neis_detail")
    if st.button("상세 조회", use_container_width=False):
        with st.spinner("학교 상세 정보 조회 중…"):
            profile = neis.get_school_full_profile(detail_nm.strip())
            if "error" in profile:
                st.error(profile["error"])
            else:
                basic = profile.get("basic", {})
                depts = profile.get("departments", [])
                employ = profile.get("employment")

                c1, c2, c3 = st.columns(3)
                c1.metric("학교 유형", basic.get("school_type", "-"))
                c2.metric("설립 유형", basic.get("found_type", "-"))
                c3.metric("지역", basic.get("region", "-"))

                st.markdown(f"""
                <div style="background:#161B22; border:1px solid #21262D; border-radius:8px;
                             padding:12px 16px; font-size:0.82rem; color:#8BBEDC; margin:12px 0;">
                    📍 {basic.get('address', '-')} &nbsp;|&nbsp;
                    📞 {basic.get('phone', '-')} &nbsp;|&nbsp;
                    🌐 <a href="{basic.get('homepage','#')}" target="_blank" style="color:#00A3E0;">
                    {basic.get('homepage','-')}</a>
                </div>
                """, unsafe_allow_html=True)

                if depts:
                    st.markdown("**학과/학급 목록:**")
                    st.dataframe(pd.DataFrame(depts), use_container_width=True, hide_index=True)

                if employ:
                    e1, e2, e3 = st.columns(3)
                    e1.metric("졸업자 수", employ.get("grad_count", "-"))
                    e2.metric("취업자 수", employ.get("employ_count", "-"))
                    e3.metric("취업률", employ.get("employ_rate", "-"))




def render_target_school_db():
    render_page_header("타겟 학교 DB", "전국 CAD 관련 학교 통합 DB")

    info_box(
        "LINC 3.0, 글로컬대학30 선정교 + 전국 기계공학 보유 대학/전문대/마이스터고/특성화고 "
        "통합 데이터베이스입니다. 기계공학 관련 학과 보유 학교는 우선순위가 높습니다. "
        "예산 집행 시기(5~7월, 10~12월)에 맞춰 공략하세요."
    )

    # 데이터 로드/초기화
    col_load1, col_load2 = st.columns(2)
    with col_load1:
        if st.button("🗂️  LINC/글로컬 선정교 적재", use_container_width=True):
            with st.spinner("선정교 데이터 적재 중…"):
                count = tsdb.load_all_target_schools()
                st.success(f"✅ LINC/글로컬 {count}건 신규 적재 완료")

    with col_load2:
        if st.button("🏫  전국 학교 DB 확충 (대학+고교)", use_container_width=True,
                      type="primary"):
            with st.spinner("전국 CAD 관련 학교 데이터 적재 중…"):
                result = tsdb.load_nationwide_schools()
                msg_parts = []
                if result['linc_glocal'] > 0:
                    msg_parts.append(f"LINC/글로컬 {result['linc_glocal']}교")
                if result['universities'] > 0:
                    msg_parts.append(f"일반대학 {result['universities']}교")
                if result['colleges'] > 0:
                    msg_parts.append(f"전문대 {result['colleges']}교")
                if result['meister'] > 0:
                    msg_parts.append(f"마이스터고 {result['meister']}교")
                if result['specialized'] > 0:
                    msg_parts.append(f"특성화고 {result['specialized']}교")
                if msg_parts:
                    st.success(f"✅ 총 {result['total']}건 신규 적재: {', '.join(msg_parts)}")
                else:
                    st.info("이미 모든 학교가 적재되어 있습니다.")
                st.rerun()

    # 통계 KPI
    summary_df = get_target_schools_summary()
    if not summary_df.empty:
        # 최대 6개까지 표시
        display_rows = summary_df.head(6)
        cols = st.columns(len(display_rows))
        for i, (_, row) in enumerate(display_rows.iterrows()):
            with cols[i]:
                render_kpi_card(
                    row['사업명'],
                    f"{row['학교수']}교",
                    f"접촉 {row['접촉학교수']}교" if row['접촉학교수'] > 0 else "미접촉"
                )

    st.markdown("---")

    # 필터링 UI
    df = get_all_target_schools()
    if df.empty:
        empty_state("🗂️", "타겟 학교 데이터가 없습니다.\n상단 'DB 초기화/갱신' 버튼을 클릭하세요.")
        return

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        prog_filter = st.selectbox(
            "사업명",
            ["전체"] + sorted(df['program_name'].unique().tolist())
        )
    with col_f2:
        type_filter = st.selectbox(
            "학교 유형",
            ["전체"] + sorted(df['school_type'].dropna().unique().tolist())
        )
    with col_f3:
        min_score = st.slider("최소 우선순위", 0, 100, 60, step=5)

    filtered = df.copy()
    if prog_filter != "전체":
        filtered = filtered[filtered['program_name'] == prog_filter]
    if type_filter != "전체":
        filtered = filtered[filtered['school_type'] == type_filter]
    filtered = filtered[filtered['priority_score'] >= min_score]

    section_header("🏫", f"타겟 학교 목록 ({len(filtered)}교)")

    if not filtered.empty:
        show_cols = ['school_name', 'program_name', 'program_type',
                     'region', 'annual_budget', 'priority_score', 'sales_status']
        display_cols = {
            'school_name': '학교명',
            'program_name': '사업명',
            'program_type': '유형',
            'region': '지역',
            'annual_budget': '연간예산',
            'priority_score': '우선순위',
            'sales_status': '영업상태',
        }
        existing = [c for c in show_cols if c in filtered.columns]
        st.dataframe(
            filtered[existing],
            use_container_width=True,
            hide_index=True,
            column_config=display_cols,
        )

        st.download_button(
            "📥 타겟 학교 CSV 다운로드",
            convert_df_to_csv(filtered[existing]),
            "target_schools.csv", "text/csv",
        )

        # 영업 상태 업데이트
        st.markdown("---")
        section_header("✏️", "영업 상태 업데이트")
        col_u1, col_u2, col_u3 = st.columns([2, 1, 2])
        with col_u1:
            school_options = filtered['school_name'].tolist()
            sel_school = st.selectbox("학교 선택", school_options, key="ts_school")
        with col_u2:
            new_status = st.selectbox(
                "상태",
                ['미접촉', '접촉완료', '제안서발송', '협의중', '수주', '보류'],
                key="ts_status"
            )
        with col_u3:
            memo = st.text_input("메모", key="ts_memo")

        if st.button("상태 업데이트", key="ts_update"):
            row_match = filtered[filtered['school_name'] == sel_school]
            if not row_match.empty:
                sid = int(row_match.iloc[0]['id'])
                if update_target_school_status(sid, new_status, memo):
                    st.success(f"✅ {sel_school} → {new_status}")
                    st.rerun()
    else:
        empty_state("🔍", "필터 조건에 맞는 학교가 없습니다.")

    # ── 학교 데이터 관리 (CSV 업로드 / 수동 추가 / 삭제) ──
    st.markdown("---")
    section_header("📋", "학교 데이터 관리")

    tab_csv, tab_manual, tab_delete = st.tabs(["📄 CSV 업로드", "✍️ 수동 추가", "🗑️ 학교 삭제"])

    with tab_csv:
        st.markdown(
            "**CSV 파일 형식**: `학교명, 학교유형(4년제/전문대), 지역, 사업명, 유형, 연간예산, 사업기간, 우선순위점수`"
        )
        st.caption("첫 번째 행은 헤더로 인식됩니다. 인코딩은 UTF-8 또는 CP949(엑셀 기본)를 지원합니다.")
        uploaded = st.file_uploader("CSV 파일 선택", type=["csv"], key="ts_csv_upload")
        if uploaded is not None:
            try:
                # UTF-8 먼저 시도, 실패하면 CP949
                try:
                    csv_df = pd.read_csv(uploaded, encoding='utf-8')
                except UnicodeDecodeError:
                    uploaded.seek(0)
                    csv_df = pd.read_csv(uploaded, encoding='cp949')

                # 컬럼 매핑 (한글 → 영문)
                col_map = {
                    '학교명': 'school_name', '학교유형': 'school_type',
                    '지역': 'region', '사업명': 'program_name',
                    '유형': 'program_type', '연간예산': 'annual_budget',
                    '사업기간': 'program_period', '우선순위': 'priority_score',
                    '우선순위점수': 'priority_score',
                }
                csv_df.rename(columns=col_map, inplace=True)

                st.dataframe(csv_df.head(10), use_container_width=True, hide_index=True)
                st.info(f"총 {len(csv_df)}행 감지됨")

                if st.button("📥 DB에 적재", key="ts_csv_load"):
                    required = ['school_name', 'program_name']
                    missing = [c for c in required if c not in csv_df.columns]
                    if missing:
                        st.error(f"필수 컬럼 누락: {', '.join(missing)}")
                    else:
                        records = []
                        for _, row in csv_df.iterrows():
                            records.append({
                                'school_name': str(row.get('school_name', '')).strip(),
                                'school_type': str(row.get('school_type', '')).strip(),
                                'region': str(row.get('region', '')).strip(),
                                'program_name': str(row.get('program_name', '')).strip(),
                                'program_type': str(row.get('program_type', '')).strip(),
                                'annual_budget': str(row.get('annual_budget', '')).strip(),
                                'program_period': str(row.get('program_period', '')).strip(),
                                'priority_score': int(row.get('priority_score', 50)),
                            })
                        count = insert_target_schools(records)
                        st.success(f"✅ {count}건 신규 적재 완료 (중복 제외)")
                        st.rerun()
            except Exception as e:
                st.error(f"CSV 파싱 오류: {e}")

    with tab_manual:
        with st.form("manual_school_form", clear_on_submit=True):
            mc1, mc2 = st.columns(2)
            with mc1:
                m_name = st.text_input("학교명 *", placeholder="예: 서울대학교")
                m_type = st.selectbox("학교 유형", ["4년제", "전문대"])
                m_region = st.text_input("지역", placeholder="예: 수도권")
                m_score = st.number_input("우선순위 점수", 0, 100, 70, step=5)
            with mc2:
                m_prog = st.text_input("사업명 *", placeholder="예: LINC 3.0")
                m_ptype = st.text_input("사업 유형", placeholder="예: 기술혁신선도형")
                m_budget = st.text_input("연간 예산", placeholder="예: 약 55억원/년")
                m_period = st.text_input("사업 기간", placeholder="예: 2022~2028")

            submitted = st.form_submit_button("➕ 학교 추가", use_container_width=True)
            if submitted:
                if not m_name or not m_prog:
                    st.error("학교명과 사업명은 필수입니다.")
                else:
                    ok = insert_target_school_manual(
                        m_name, m_type, m_region, m_prog, m_ptype,
                        m_budget, m_period, m_score
                    )
                    if ok:
                        st.success(f"✅ {m_name} ({m_prog}) 추가 완료")
                        st.rerun()
                    else:
                        st.warning("이미 등록된 학교+사업명 조합입니다.")

    with tab_delete:
        if not df.empty:
            del_options = [
                f"{row['school_name']} ({row['program_name']})"
                for _, row in df.iterrows()
            ]
            del_sel = st.selectbox("삭제할 학교 선택", del_options, key="ts_del_sel")
            if st.button("🗑️ 삭제", key="ts_del_btn"):
                idx = del_options.index(del_sel)
                sid = int(df.iloc[idx]['id'])
                if delete_target_school(sid):
                    st.success(f"✅ {del_sel} 삭제 완료")
                    st.rerun()

    # ── 교육정책 뉴스 자동 감시 ──
    st.markdown("---")
    section_header("📰", "교육정책 선정교 뉴스 감시")
    st.caption(
        "LINC·RISE·글로컬대학 선정 발표 뉴스를 자동 수집합니다. "
        "매주 수요일 08:30 자동 실행되며, 수동으로도 즉시 수집할 수 있습니다."
    )

    if st.button("🔍 선정교 뉴스 즉시 수집", key="ts_policy_fetch"):
        with st.spinner("교육정책 뉴스 수집 중…"):
            news_count = ep.fetch_edu_policy_news()
            if news_count > 0:
                st.success(f"✅ {news_count}건 신규 뉴스 수집 완료")
            else:
                st.info("신규 뉴스가 없습니다.")

    news_list = ep.get_edu_policy_news()
    if news_list:
        for news in news_list:
            icon = "✅" if news['is_processed'] else "🆕"
            with st.expander(f"{icon} [{news['policy_type']}] {news['title']}", expanded=False):
                st.markdown(f"**발행일**: {news['pub_date']}")
                if news['detected_schools']:
                    st.markdown(f"**감지된 학교**: {news['detected_schools']}")
                st.markdown(f"**내용**: {news['description']}")
                st.markdown(f"[🔗 기사 원문 보기]({news['source_url']})")

                if not news['is_processed']:
                    col_act1, col_act2 = st.columns(2)
                    with col_act1:
                        if st.button("✅ 처리 완료", key=f"ep_done_{news['id']}"):
                            ep.mark_news_processed(news['id'])
                            st.rerun()
                    with col_act2:
                        # 감지된 학교를 바로 타겟 DB에 추가
                        if news['detected_schools']:
                            if st.button("➕ 학교 일괄 추가", key=f"ep_add_{news['id']}"):
                                schools = [s.strip() for s in news['detected_schools'].split(',') if s.strip()]
                                added = 0
                                for sch in schools:
                                    ok = insert_target_school_manual(
                                        sch, '4년제', '', news['policy_type'],
                                        '뉴스 감지', '', '', 70
                                    )
                                    if ok:
                                        added += 1
                                ep.mark_news_processed(news['id'])
                                st.success(f"✅ {added}교 추가, {len(schools)-added}교 중복 제외")
                                st.rerun()
    else:
        st.info("수집된 교육정책 뉴스가 없습니다. '선정교 뉴스 즉시 수집' 버튼을 클릭하세요.")


# ──────────────────────────────────────────────
# 구매 신호 분석 (핵심 신규 기능)
# ──────────────────────────────────────────────

def render_purchase_signals():
    render_page_header("구매 신호 분석", "누가 지금 살 돈이 있는가?")

    info_box(
        "R&D 과제·국고사업·대학 입찰·예산 시기를 종합하여 구매 가능성을 점수화합니다. "
        "'지금 연락해야 할 학교' 순위를 확인하세요."
    )

    # 예산 시기 알림
    budget_info = pse.get_budget_season_info()
    season = budget_info['season']
    level_color = {'critical': '#FF6B6B', 'high': '#F6AD55', 'medium': '#68D391', 'low': '#4A6A8A'}
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(0,163,224,0.12),rgba(0,119,182,0.06));
                 border:1px solid {level_color.get(season['level'], '#4A6A8A')}; border-radius:10px; padding:14px 16px; margin-bottom:16px;">
        <div style="font-size:0.75rem; color:#6B8CAE;">현재 {budget_info['month']}월 · 예산 보너스 +{budget_info['bonus']}점</div>
        <div style="font-size:1rem; font-weight:700; color:{level_color.get(season['level'], '#00A3E0')}; margin-top:4px;">
            {season['name']}
        </div>
        <div style="font-size:0.8rem; color:#A8B8C8; margin-top:6px; line-height:1.6;">
            {season['action']}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 탭 구성: 종합 | R&D 과제 | 대학 입찰 | 국고 사업
    tab_main, tab_ntis, tab_univ, tab_grant = st.tabs([
        "📡 종합 분석", "🔬 R&D 과제", "🏗️ 대학 입찰", "💰 국고 사업"
    ])

    # ── 탭1: 종합 분석 ──
    with tab_main:
        # 데이터 수집 버튼
        col_b1, col_b2, col_b3, col_b4 = st.columns(4)
        with col_b1:
            if st.button("🔬 R&D 과제 수집", use_container_width=True):
                with st.spinner("NTIS 연구과제 뉴스 수집 중…"):
                    cnt = ntis_crawler.fetch_ntis_research_news()
                    st.success(f"✅ {cnt}건 수집") if cnt else st.info("신규 건 없음")
        with col_b2:
            if st.button("🏗️ 대학 입찰 수집", use_container_width=True):
                with st.spinner("산학협력단 입찰 뉴스 수집 중…"):
                    cnt = univ_bids_crawler.fetch_univ_bid_news(top_n=20)
                    st.success(f"✅ {cnt}건 수집") if cnt else st.info("신규 건 없음")
        with col_b3:
            if st.button("💰 국고사업 수집", use_container_width=True):
                with st.spinner("지원사업 뉴스 수집 중…"):
                    try:
                        cnt = cg.fetch_grant_news()
                        st.success(f"✅ {cnt}건 감지") if cnt > 0 else st.info("신규 건 없음")
                    except Exception as e:
                        st.error(f"❌ {e}")
        with col_b4:
            if st.button("📡 신호 재분석", use_container_width=True):
                st.rerun()

        st.markdown("---")

        # 구매 신호 요약
        sig_summary = pse.get_signal_summary()
        c1, c2, c3 = st.columns(3)
        with c1:
            render_kpi_card("📡", "총 구매 신호", sig_summary['total'], f"미조치 {sig_summary['unacted']}건", "cyan")
        with c2:
            by_type = sig_summary.get('by_type', {})
            type_str = ', '.join(f"{k}({v})" for k, v in list(by_type.items())[:3]) if by_type else "수집 필요"
            render_kpi_card("📊", "신호 유형", len(by_type), type_str, "blue")
        with c3:
            top5 = sig_summary.get('by_school_top5', [])
            top_str = top5[0]['school'] if top5 else "수집 필요"
            render_kpi_card("🎯", "최우선 학교", top_str if top5 else "-", f"점수 {top5[0]['max_score']}점" if top5 else "", "green")

        st.markdown("---")

        # 이번 주 액션 리스트
        section_header("🎯", "이번 주 접근 대상 (상위 15교)")
        weekly = pse.get_weekly_action_list(top_n=15)

        if weekly:
            for i, school in enumerate(weekly):
                score = school['total_score']
                tier = school['tier']
                if score >= 80:
                    bar_color = "#FF6B6B"
                elif score >= 50:
                    bar_color = "#F6AD55"
                else:
                    bar_color = "#4A6A8A"

                signals_text = ""
                if school['signals']:
                    sig_items = [f"{s['type']}: {s['title'][:30]}" for s in school['signals'][:2]]
                    signals_text = " | ".join(sig_items)

                st.markdown(f"""
                <div style="background:#161B22; border:1px solid #21262D; border-radius:10px;
                             padding:12px 16px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="font-size:0.95rem; font-weight:700; color:#E8EDF2;">
                                {i+1}. {school['school_name']}
                            </span>
                            <span style="font-size:0.72rem; color:#4A6A8A; margin-left:8px;">
                                {school['program_name']} · {school['sales_status']}
                            </span>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px;">
                            <div style="background:{bar_color}22; color:{bar_color}; padding:3px 10px;
                                        border-radius:12px; font-size:0.75rem; font-weight:600;">
                                {score}점
                            </div>
                            <div style="font-size:0.68rem; color:#6B8CAE;">{tier}</div>
                        </div>
                    </div>
                    <div style="font-size:0.72rem; color:#6B8CAE; margin-top:6px;">
                        기본 {school['base_score']} + 신호 {school['signal_bonus']} + 시기 {school['budget_bonus']}
                        {f" + 상태 {school['status_bonus']}" if school['status_bonus'] else ""}
                    </div>
                    {"<div style='font-size:0.7rem; color:#00A3E0; margin-top:4px;'>" + signals_text + "</div>" if signals_text else ""}
                    <div style="font-size:0.72rem; color:#68D391; margin-top:4px;">
                        → {school['recommended_action']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            empty_state("📡", "타겟 학교 DB를 먼저 초기화하세요.")

        # 미조치 구매 신호 목록
        st.markdown("---")
        section_header("🔔", "미조치 구매 신호")
        signals_df = get_purchase_signals(min_score=0, limit=30)
        if not signals_df.empty:
            unacted = signals_df[signals_df['is_acted'] == 0]
            if not unacted.empty:
                for _, sig in unacted.iterrows():
                    with st.expander(f"[{sig['signal_type']}] {sig['school_name']} — {sig['signal_title'][:50]}", expanded=False):
                        st.markdown(f"**점수**: {sig['signal_score']}점 | **출처**: {sig['source']}")
                        st.markdown(f"**상세**: {sig['signal_detail']}")
                        if sig.get('source_url'):
                            st.markdown(f"[🔗 원문 보기]({sig['source_url']})")
                        if st.button("✅ 조치 완료", key=f"sig_act_{sig['id']}"):
                            mark_signal_acted(int(sig['id']), "조치 완료")
                            st.rerun()
            else:
                st.info("모든 구매 신호가 조치 완료되었습니다.")
        else:
            st.info("구매 신호가 없습니다. 상단 수집 버튼을 클릭하세요.")

    # ── 탭2: R&D 과제 ──
    with tab_ntis:
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔬 R&D 과제 뉴스 수집", use_container_width=True, key="ntis_fetch"):
                with st.spinner("NTIS 연구과제 관련 뉴스 수집 중…"):
                    count = ntis_crawler.fetch_ntis_research_news()
                    if count > 0:
                        st.success(f"✅ {count}건 신규 수집 완료")
                    else:
                        st.info("신규 뉴스가 없습니다.")

        ntis_df = get_all_ntis_projects()

        with col2:
            if not ntis_df.empty:
                c1, c2, c3 = st.columns(3)
                with c1:
                    render_kpi_card("🔬", "수집 과제", len(ntis_df), "연구과제 뉴스", "blue")
                with c2:
                    high_rel = len(ntis_df[ntis_df['relevance_score'] >= 50]) if 'relevance_score' in ntis_df.columns else 0
                    render_kpi_card("🎯", "고관련성", high_rel, "50점 이상", "green")
                with c3:
                    schools = ntis_df['lead_agency'].dropna().nunique() if 'lead_agency' in ntis_df.columns else 0
                    render_kpi_card("🏫", "관련 대학", schools, "학교 수", "cyan")

        st.markdown("---")

        if not ntis_df.empty:
            min_rel = st.slider("최소 관련성 점수", 0, 100, 30, step=10, key="ntis_rel")
            filtered = ntis_df[ntis_df['relevance_score'] >= min_rel]
            section_header("📋", f"연구과제 뉴스 ({len(filtered)}건)")
            if not filtered.empty:
                show_cols = ['project_name', 'lead_agency', 'lead_researcher', 'relevance_score', 'keywords']
                display_names = {
                    'project_name': '과제/기사명', 'lead_agency': '대학',
                    'lead_researcher': '연구자', 'relevance_score': '관련성',
                    'keywords': '키워드',
                }
                existing = [c for c in show_cols if c in filtered.columns]
                st.dataframe(filtered[existing].head(30), use_container_width=True, hide_index=True, column_config=display_names)
            else:
                empty_state("🔬", "필터 조건에 맞는 과제가 없습니다.")
        else:
            empty_state("🔬", "수집된 R&D 과제 뉴스가 없습니다.\n수집 버튼을 클릭하세요.")

    # ── 탭3: 대학 자체 입찰 ──
    with tab_univ:
        col1, col2 = st.columns([1, 3])
        with col1:
            top_n = st.number_input("검색 학교 수", 10, 50, 20, step=5, key="univ_top_n")
            if st.button("🏗️ 대학 입찰 뉴스 수집", use_container_width=True, key="univ_fetch"):
                with st.spinner(f"상위 {top_n}교 산학협력단 입찰 뉴스 수집 중…"):
                    count = univ_bids_crawler.fetch_univ_bid_news(top_n=top_n)
                    if count > 0:
                        st.success(f"✅ {count}건 신규 수집 완료")
                    else:
                        st.info("신규 입찰 뉴스가 없습니다.")

        bids_df = get_all_univ_bids()

        with col2:
            if not bids_df.empty:
                c1, c2, c3 = st.columns(3)
                with c1:
                    render_kpi_card("🏗️", "감지 입찰", len(bids_df), "대학 자체 입찰", "orange")
                with c2:
                    relevant = len(bids_df[bids_df['is_relevant'] == 1]) if 'is_relevant' in bids_df.columns else 0
                    render_kpi_card("🎯", "CAD 관련", relevant, "관련 입찰", "green")
                with c3:
                    schools = bids_df['school_name'].nunique() if 'school_name' in bids_df.columns else 0
                    render_kpi_card("🏫", "감지 학교", schools, "학교 수", "cyan")

        st.markdown("---")

        if not bids_df.empty:
            section_header("📋", f"감지된 대학 입찰 ({len(bids_df)}건)")
            show_cols = ['school_name', 'bid_title', 'pub_date', 'bid_type']
            display_names = {
                'school_name': '학교명', 'bid_title': '입찰/공고명',
                'pub_date': '발행일', 'bid_type': '유형',
            }
            existing = [c for c in show_cols if c in bids_df.columns]
            st.dataframe(bids_df[existing].head(30), use_container_width=True, hide_index=True, column_config=display_names)

            for _, bid in bids_df.head(10).iterrows():
                with st.expander(f"[{bid.get('school_name','')}] {bid.get('bid_title','')[:50]}", expanded=False):
                    st.markdown(f"**발행일**: {bid.get('pub_date', '-')}")
                    if bid.get('bid_url'):
                        st.markdown(f"[🔗 원문 보기]({bid['bid_url']})")
        else:
            empty_state("🏗️", "수집된 대학 자체 입찰이 없습니다.\n수집 버튼을 클릭하세요.")

    # ── 탭4: 국고 사업 (기존 예산 흐름 모니터링) ──
    with tab_grant:
        col1, col2 = st.columns([1, 3])
        with col1:
            section_header("🔄", "뉴스 수집")
            if st.button("최신 뉴스 크롤링", use_container_width=True, key="grant_fetch"):
                with st.spinner("최신 지원사업 뉴스 갱신 중…"):
                    try:
                        import sqlite3, os
                        DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'sales_data.db')
                        conn = sqlite3.connect(DB_PATH)
                        conn.execute('DELETE FROM grants')
                        conn.commit()
                        conn.close()
                        count = cg.fetch_grant_news()
                        if count > 0:
                            st.success(f"✅ {count}건 감지")
                        else:
                            st.info("새로운 선정 뉴스가 없습니다.")
                    except Exception as e:
                        st.error(f"❌ {e}")

        with col2:
            df_grants = get_all_grants()
            if not df_grants.empty:
                section_header("📰", "감지된 지원사업 목록")
                st.dataframe(
                    df_grants,
                    use_container_width=True, hide_index=True,
                    column_config={
                        "project_name": "사업명/기사제목",
                        "agency": "출처",
                        "selected_school": "선정학교(추정)",
                        "budget_scale": "예산규모",
                        "notice_url": st.column_config.LinkColumn("기사 바로가기", display_text="🔗 보기"),
                        "status": "상태",
                        "crawled_at": "수집일시",
                    },
                )
                st.download_button("📥 CSV 다운로드", convert_df_to_csv(df_grants),
                                   "grant_news.csv", "text/csv", key="grant_csv")

                # 메일 템플릿
                st.markdown("---")
                section_header("✉️", "선정 학교 축하 메일 템플릿")
                latest = df_grants.iloc[0]
                school = latest.get('selected_school', '귀교')
                project = str(latest.get('project_name', ''))[:30]
                st.text_area(
                    "복사하여 사용하세요",
                    f"제목: [{school}] {project}… 선정 축하드립니다!\n\n"
                    f"안녕하세요, 교수님.\n"
                    f"이번에 귀교가 국고 지원 사업에 선정되셨다는 반가운 소식을 접했습니다.\n"
                    f"예산 집행 계획 관련하여, (주)하나티에스가 타 대학 사업단에 성공적으로 구축한\n"
                    f"3D CAD 및 디지털 트윈 실습실 레퍼런스를 공유해 드릴까 합니다.\n"
                    f"편하신 시간에 연락 주십시오.\n\n"
                    f"(주)하나티에스 영업팀 | 02-6957-1855 | www.1ts.kr",
                    height=180,
                    label_visibility="collapsed",
                    key="grant_mail",
                )
            else:
                empty_state("📭", "수집된 지원사업 이력이 없습니다.\n크롤링 버튼으로 데이터를 수집하세요.")


def render_competitor_analysis():
    render_page_header("경쟁사 분석", "낙찰 이력 기반 경쟁 패턴")

    info_box("과거 낙찰 이력에서 경쟁사별 수주 패턴을 분석합니다. '낙찰결과 업데이트' 후 데이터가 쌓여야 분석이 가능합니다.")

    col1, col2 = st.columns([1, 2])
    with col1:
        section_header("🔄", "데이터 업데이트")
        if st.button("낙찰결과 업데이트", use_container_width=True):
            with st.spinner("낙찰업체/금액 조회 중…"):
                try:
                    count = ak.fetch_bid_results_for_history()
                    st.success(f"✅ {count}건 업데이트")
                except Exception as e:
                    st.error(f"❌ {e}")

        st.markdown("---")
        section_header("🏢", "경쟁사 순위")
        competitor_df = get_bid_result_summary()
        if not competitor_df.empty:
            for _, row in competitor_df.iterrows():
                name = row.get("낙찰업체", "-")
                cnt = row.get("낙찰건수", 0)
                st.markdown(f"""
                <div class="comp-card">
                    <div class="comp-name">{name}</div>
                    <div class="comp-count">{cnt}건</div>
                </div>
                """, unsafe_allow_html=True)

    with col2:
        competitor_df = get_bid_result_summary()
        if not competitor_df.empty:
            section_header("📊", "경쟁사별 낙찰 건수")
            st.bar_chart(competitor_df.set_index("낙찰업체")["낙찰건수"])

            st.markdown("---")
            section_header("🔍", "경쟁사 수주 기관 상세")
            competitors = competitor_df["낙찰업체"].tolist()
            selected_comp = st.selectbox("경쟁사 선택", competitors)
            if selected_comp:
                df_bids = get_all_bids()
                if not df_bids.empty:
                    comp_bids = df_bids[df_bids["successful_bidder"] == selected_comp].copy()
                    if not comp_bids.empty:
                        comp_bids["contract_date"] = pd.to_datetime(
                            comp_bids["contract_date"], errors="coerce"
                        ).dt.strftime("%Y-%m-%d")
                        st.dataframe(
                            comp_bids[["bid_title", "demand_agency", "contract_date", "bid_price"]],
                            use_container_width=True, hide_index=True,
                        )
                        st.markdown(f"""
                        <div class="success-box">
                            💡 <strong>전략 제안:</strong> {selected_comp}가 수주한 기관에
                            교체 주기 도래 시점에 맞춰 선제 접촉하세요.
                        </div>
                        """, unsafe_allow_html=True)
        else:
            empty_state("📊", "낙찰업체 데이터가 없습니다.\n과거 입찰 분석에서 데이터 수집 후 낙찰결과를 업데이트하세요.")


# ──────────────────────────────────────────────
# 메인 진입점
# ──────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="PSIS | 하나티에스 영업 지능 시스템",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_dotenv()
    init_db()
    start_scheduler()

    inject_global_css()

    selected = render_sidebar()

    # 탭 라우팅
    if selected == "대시보드":
        render_dashboard()
    elif selected == "구매 신호 분석":
        render_purchase_signals()
    elif selected == "타겟 학교 DB":
        render_target_school_db()
    elif selected == "타겟 발굴 및 공략":
        render_target_discovery()
    elif selected == "영업 파이프라인":
        render_pipeline()
    elif selected == "공고 수집/분석":
        render_bid_analysis()
    elif selected == "경쟁사 분석":
        render_competitor_analysis()
    elif selected == "학교알리미 조회":
        render_school_info()
    elif selected == "Spec-in 문서 생성":
        render_spec_in()
    elif selected == "레퍼런스 카드 생성":
        render_reference_card()


if __name__ == "__main__":
    main()
