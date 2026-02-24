import streamlit as st
from dotenv import load_dotenv

# 사용자 정의 모듈 임포트
from utils.db_manager import init_db, check_db_connection, get_all_bids, get_all_grants
import modules.api_koneps as ak
import modules.crawler_grants as cg
import modules.doc_generator as dg
from datetime import datetime, timedelta
import pandas as pd

@st.cache_data
def convert_df_to_csv(df):
    """데이터프레임을 한글 깨짐 없는 CSV(Excel 호환) 바이트로 변환합니다."""
    return df.to_csv(index=False).encode('utf-8-sig')

def main() -> None:
    """
    Streamlit 대시보드의 메인 진입점 함수입니다.
    기본 설정, DB 초기화 및 레이아웃을 구성합니다.
    """
    # 1. 페이지 기본 설정 (와이드 모드 적용)
    st.set_page_config(
        page_title="공공 영업 지능형 대시보드 (PSIS)",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 환경 변수 로드 (.env 활용을 위함)
    load_dotenv()

    # 2. 시스템 초기화 및 DB 테이블 점검
    init_db()

    # 3. 사이드바 구성
    st.sidebar.title("📌 PSIS 메뉴")
    menu_options = ["대시보드", "타겟 학교 관리", "예산 흐름 모니터링", "과거 입찰 분석", "Spec-in 문서 자동 생성"]
    selected_menu = st.sidebar.radio("원하시는 작업을 선택하세요:", menu_options)

    # 4. 메인 콘텐츠 렌더링
    st.title("🏛️ 공공 영업 지능형 대시보드 (PSIS)")
    st.markdown("---")

    if selected_menu == "대시보드":
        st.subheader("PSIS 대시보드 초기화 완료 🎉")
        st.write("환영합니다. B2B 공공 교육기관 영업 지원을 위한 지능형 시스템입니다.")
        
        # 상태 검증을 통한 안정성 피드백 표시
        if check_db_connection():
            st.success("✅ 시스템 상태: 데이터베이스(SQLite3) 연결이 정상적으로 완료되었습니다.")
        else:
            st.error("❌ 시스템 상태: 데이터베이스 연결에 실패했습니다. 경로와 권한을 확인하세요.")

    elif selected_menu == "타겟 학교 관리":
        st.subheader("🎯 타겟 학교 관리")
        st.info("💡 3D CAD/디지털 트윈 영업의 타겟이 되는 학교들의 현황을 등록하고 관리합니다.")

        # 레이아웃을 두 단으로 나눔 (입력 폼과 리스트뷰)
        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown("#### ✨ 신규 학교 등록")
            with st.form("add_school_form", clear_on_submit=True):
                school_name = st.text_input("학교명 (필수)", placeholder="예: 미래직업고등학교")
                category = st.selectbox("구분", ["특성화고", "전문대", "4년제 대학", "직업전문학교", "기타"])
                contact = st.text_input("담당자 / 연락처", placeholder="예: 김선생님, 010-1234-5678")
                equipments = st.text_area("보유 장비 현황 (선택)", placeholder="예: AutoCAD 50카피, 3D 프린터 2대")
                
                submitted = st.form_submit_button("등록 완료")

                if submitted:
                    if school_name.strip() == "":
                        st.error("🚫 학교명은 필수 입력 항목입니다.")
                    else:
                        from utils.db_manager import insert_school
                        # DB 삽입 로직
                        if insert_school(school_name, category, contact, equipments):
                            st.success(f"✅ '{school_name}' 데이터가 등록되었습니다!")
                        else:
                            st.error("❌ 저장에 실패했습니다.")

        with col2:
            st.markdown("#### 📋 타겟 학교 현황 목록")
            from utils.db_manager import get_all_schools
            df_schools = get_all_schools()
            
            if not df_schools.empty:
                st.dataframe(df_schools, use_container_width=True, hide_index=True)
                csv_data = convert_df_to_csv(df_schools)
                st.download_button(label="📥 엑셀(CSV) 다운로드", data=csv_data, file_name="target_schools.csv", mime="text/csv")
            else:
                st.warning("등록된 학교 데이터가 없습니다. 좌측에서 정보를 추가해주세요.")

    elif selected_menu == "예산 흐름 모니터링":
        st.subheader("💰 정부 지원 사업 수주 모니터링 (Money Trail)")
        st.info("💡 주요 정부 지원 사업 검색어를 통해 최신 뉴스를 수집합니다. 새로운 필터 기준을 적용하려면 초기화 후 다시 검색하세요.")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🌐 최신 지원사업 뉴스 크롤링", use_container_width=True):
                with st.spinner("기존 데이터를 비우고 최신 뉴스를 새로 갱신 중입니다..."):
                    try:
                        import sqlite3, os
                        DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'sales_data.db')
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('DELETE FROM grants')
                        conn.commit()
                        conn.close()
                        
                        news_count = cg.fetch_grant_news()
                        if news_count > 0:
                            st.success(f"✅ 웹 크롤링 완료! {news_count}건의 새로운 사업 선정 소식이 감지되었습니다.")
                        else:
                            st.info("포착된 유효한 최신 선정 뉴스가 없습니다.")
                    except Exception as e:
                        st.error(f"❌ 크롤링 중 오류가 발생했습니다: {str(e)}")
        
        with col2:
             st.markdown("🎯 **영업 팁:** 사업명/선정학교가 확인되면 담당 부서에 메일 제안을 띄워보세요.")
        
        st.markdown("---")
        st.markdown("### 📰 실시간 정부 지원 사업 감지 보드")
        df_grants = get_all_grants()
        
        if not df_grants.empty:
            # 컬럼명 보기 좋게 변경 및 링크 컬럼 설정
            st.dataframe(
                df_grants, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "project_name": "사업명/기사제목",
                    "agency": "출처",
                    "selected_school": "선정학교(추정)",
                    "budget_scale": "예산규모",
                    "notice_url": st.column_config.LinkColumn("기사 바로가기", display_text="🔗 보기"),
                    "status": "상태",
                    "crawled_at": "수집일시"
                }
            )
            
            # 다운로드 버튼 추가
            csv_data = convert_df_to_csv(df_grants)
            st.download_button(label="📥 수집 목록 엑셀(CSV) 다운로드", data=csv_data, file_name="grant_news.csv", mime="text/csv")

            # 액션 제안
            st.markdown("#### ⚡ 신규 수주 대학 대상 메일 캠페인")
            latest_school = df_grants.iloc[0]['selected_school']
            latest_project = df_grants.iloc[0]['project_name']
            
            st.text_area("자동 생성 메일 템플릿(복사용)", 
                         f"제목: [{latest_school}] {latest_project[:20]}... 선정을 진심으로 축하드립니다!\n\n안녕하세요, 교수님.\n이번에 귀교가 대규모 국고 지원 사업에 선정되셨다는 반가운 소식을 뉴스({df_grants.iloc[0]['notice_url']})를 통해 접했습니다.\n예산 집행 계획과 관련하여, 저희가 타 대학 사업단에 성공적으로 구축한 3D CAD 및 디지털 트윈 실습실 레퍼런스를 공유해 드릴까 합니다.\n편하신 시간에 연락 주십시오.", 
                         height=150)
            
        else:
            st.warning("수집된 사업 이력이 없습니다. 좌측에서 크롤링 버튼을 눌러 데이터를 확인하세요.")

    elif selected_menu == "과거 입찰 분석":
        st.subheader("📊 과거 입찰 분석 & 교체 주기 예측")
        st.info("💡 나라장터(조달청) 입찰 공고 중, 목표 기관(교육기관)과 3D/디지털 트윈 관련 데이터만 필터링하여 수집합니다.")
        
        # 데이터 수집 버튼부
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 최근 공고 수집 (7일)", use_container_width=True):
                with st.spinner("최근 7일 조달청 API를 호출 중입니다..."):
                    try:
                        added_count = ak.fetch_recent_bids(days=7)
                        st.success(f"✅ 수집 완료! {added_count}건의 새 공고가 추가되었습니다.")
                    except Exception as e:
                        st.error(f"❌ 데이터 수집 중 오류: {str(e)}")

        with col2:
            if st.button("⏪ 과거 공고 수집 (5년)", use_container_width=True):
                st_placeholder = st.empty()
                with st.spinner("과거 5년 치 조달청 API를 호출 중입니다... (최대 1~2분 소요)"):
                    try:
                        added_count = ak.fetch_past_bids(years=5, st_placeholder=st_placeholder)
                        st_placeholder.empty()
                        st.success(f"✅ 수집 완료! 5년간 데이터 중 {added_count}건의 타겟 공고가 추가되었습니다.")
                    except Exception as e:
                        st_placeholder.empty()
                        st.error(f"❌ 과거 데이터 수집 중 오류: {str(e)}")
                        
        with col3:
            if st.button("🚀 사전규격 탐색 (초기영업)", use_container_width=True):
                with st.spinner("정식 입찰 전 단계(사전규격)의 타겟 학교를 찾고 있습니다..."):
                    try:
                        added_count = ak.fetch_pre_spec_bids(30)
                        if added_count > 0:
                            st.success(f"✅ 경쟁사보다 빨리! {added_count}건의 사전규격 단계 영업 기회가 포착되었습니다.")
                        else:
                            st.info("현재 새롭게 포착된 3D/캐드 관련 사전규격이 없거나, API 서버 지연이 있습니다.")
                    except Exception as e:
                        st.error(f"❌ 사전규격 연동 오류: {str(e)}")

        st.markdown("---")
        
        # 교체 주기 예측 알림판
        st.markdown("### 🚨 교체 주기 도래 타겟 (3~5년 경과)")
        df_bids = get_all_bids()
        
        if not df_bids.empty:
            # 계약일자(contract_date/입찰공고일) 기준 필터링
            df_bids['contract_date'] = pd.to_datetime(df_bids['contract_date'], errors='coerce')
            
            # 3~5년 전 기준 날짜 계산
            today = pd.to_datetime('today')
            years_3_ago = today - pd.DateOffset(years=3)
            years_5_ago = today - pd.DateOffset(years=5)
            
            # 교체 대상: 5년 전 ~ 3년 전 사이 공고
            target_df = df_bids[(df_bids['contract_date'] >= years_5_ago) & (df_bids['contract_date'] <= years_3_ago)]
            
            if not target_df.empty:
                st.warning(f"⚠️ 총 {len(target_df)}건의 교체/유지보수 타겟 이력이 발견되었습니다. 적극적인 선제 영업을 권장합니다.")
                # 표시를 위해 날짜 형식을 문자열로 복원
                target_df['contract_date'] = target_df['contract_date'].dt.strftime('%Y-%m-%d')
                st.dataframe(target_df, use_container_width=True, hide_index=True)
                
                csv_target = convert_df_to_csv(target_df)
                st.download_button(label="📥 교체 타겟 엑셀(CSV) 다운로드", data=csv_target, file_name="target_bids.csv", mime="text/csv")
            else:
                st.info("현재 3~5년 차 교체 주기에 해당하는 타겟 기관이 데이터에 없습니다.")
                
            st.markdown("### 📝 전체 수집된 입찰 이력 데이터 백업")
            df_bids['contract_date'] = df_bids['contract_date'].dt.strftime('%Y-%m-%d')
            st.dataframe(df_bids, use_container_width=True, hide_index=True)
            
            csv_all_bids = convert_df_to_csv(df_bids)
            st.download_button(label="📥 전체 입찰 이력 엑셀(CSV) 다운로드", data=csv_all_bids, file_name="all_bids_history.csv", mime="text/csv")
            
        else:
            st.warning("현재 저장된 데이터가 없습니다. 상단의 수집기 버튼을 눌러 데이터를 불러오세요.")

    elif selected_menu == "Spec-in 문서 자동 생성":
        st.subheader("📝 Spec-in 문서 자동 생성기 (Helper)")
        st.info("💡 타겟 학교와 예산 정보를 넣으면, 교수님과 행정실이 복사해서 기안으로 쓸 수 있는 '도입 품의서/시방서'가 1분 만에 완성됩니다.")
        
        # DB 연동: 최근 사업 수주 내역 가져오기
        df_grants = get_all_grants()
        school_options = ["직접 입력"]
        if not df_grants.empty:
            grants_list = df_grants['selected_school'] + " (" + df_grants['project_name'] + ")"
            school_options.extend(grants_list.tolist())

        col1, col2 = st.columns([1, 1.5])
        
        with col1:
            st.markdown("#### ⚙️ 제안 조건 입력")
            
            # DB 기반 드롭다운 선택
            selected_target = st.selectbox("📂 수집된 국고 사업 리스트에서 선택 (자동 입력)", school_options)
            
            auto_school = ""
            auto_project = ""
            auto_budget = ""
            
            if selected_target != "직접 입력":
                idx = school_options.index(selected_target) - 1
                auto_school = df_grants.iloc[idx]['selected_school']
                auto_project = df_grants.iloc[idx]['project_name']
                auto_budget = df_grants.iloc[idx]['budget_scale']
                
            with st.form("doc_gen_form"):
                school = st.text_input("타겟 학교명", value=auto_school, placeholder="한국대학교")
                project = st.text_input("정부 지원 사업명", value=auto_project, placeholder="LINC 3.0 산학연협력 선도대학 육성사업")
                budget = st.text_input("확보/추정 예산", value=auto_budget, placeholder="약 10억 원")
                solution = st.text_input("당사 제안 솔루션명", placeholder="3DEXPERIENCE / 스마트팩토리 통합 솔루션")
                extra = st.text_area("추가 강조 소구점 (선택)", placeholder="유지보수 3년 무상, 취업 연계 프로그램 제공 등")
                
                generate_btn = st.form_submit_button("문서 초안 생성하기 ✨")
                
        with col2:
            st.markdown("#### 📄 생성된 문서 결과 (복사 가능)")
            if generate_btn:
                if not school or not project or not solution:
                    st.error("학교명, 사업명, 제안 솔루션명은 필수 입력입니다.")
                else:
                    with st.spinner("AI(Gemini) 모델이 학교 맞춤형 문서를 작성 중입니다..."):
                        result_doc = dg.generate_spec_in_document(school, project, budget, solution, extra)
                        st.markdown(result_doc)
            else:
                st.write("좌측 폼에 정보를 입력하고 생성 버튼을 누르시면, 여기에 결과가 나타납니다.")

if __name__ == "__main__":
    main()
