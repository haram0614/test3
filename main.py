import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 및 제목 표시
# ==========================================
st.set_page_config(
    page_title="어제 박스오피스 순위",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제 일별 박스오피스 순위")

# ==========================================
# 2. 한국 시간(KST) 기준 어제 날짜 구하기
# 배포 서버의 시계가 UTC(세계 표준시)일 수 있으므로 KST로 명시적 변환
# ==========================================
kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(kst)
yesterday = now_kst - datetime.timedelta(days=1)
target_dt = yesterday.strftime('%Y%m%d')        # API 요청용 (예: 20261021)
display_date = yesterday.strftime('%Y년 %m월 %d일') # 화면 표시용

st.caption(f"📅 **조회 기준일:** {display_date} (한국 시간 기준 어제)")

# ==========================================
# 3. KOBIS API 인증키 불러오기
# secrets.toml 또는 Streamlit Cloud Secrets의 KOBIS_KEY 사용
# ==========================================
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.info("""
    **확인 및 해결 방법:**
    1. 로컬 환경: `.streamlit/secrets.toml` 파일에 `KOBIS_KEY = "발급받은_키"`를 추가해 주세요.
    2. Streamlit Cloud: 앱 설정의 **Secrets** 항목에 `KOBIS_KEY = "발급받은_키"`를 등록해 주세요.
    """)
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# ==========================================
# 4. KOBIS API 데이터 요청
# ==========================================
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_dt
}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()  # HTTP status가 200이 아닐 경우 예외 발생
    data = response.json()
except requests.exceptions.RequestException as e:
    st.error("📡 API 서버와의 통신에 실패했습니다.")
    st.info("""
    **확인 및 해결 방법:**
    - 인터넷 연결 상태를 확인해 주세요.
    - KOBIS API 서버 점검 중일 수 있으니 잠시 후 다시 시도해 주세요.
    """)
    st.stop()

# ==========================================
# 5. 응답 예외 처리 (오류 상자 또는 데이터 누락)
# ==========================================
# 인증키가 틀렸거나 오류 발생 시 KOBIS는 faultInfo 상자를 반환함
if "faultInfo" in data:
    st.error(f"❌ KOBIS API 오류가 발생했습니다: {data['faultInfo'].get('message', '알 수 없는 오류')}")
    st.info("""
    **확인 및 해결 방법:**
    - 등록된 `KOBIS_KEY`가 올바른지 확인해 주세요.
    - 영화진흥위원회 통합전산망(KOBIS)에서 키가 활성화되었는지 확인해 주세요.
    """)
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
movie_list = box_office_result.get("dailyBoxOfficeList", [])

# 데이터 목록이 비어있는 경우
if not movie_list:
    st.warning("⚠️ 어제 박스오피스 데이터가 아직 집계되지 않았거나 존재하지 않습니다.")
    st.info("""
    **확인 및 해결 방법:**
    - KOBIS의 일별 박스오피스는 보통 매일 오전에 최종 집계됩니다.
    - 잠시 후 페이지를 새로고침(F5)하여 다시 확인해 보세요.
    """)
    st.stop()

# ==========================================
# 6. 데이터 전처리 (문자열 -> 숫자 변환)
# ==========================================
df = pd.DataFrame(movie_list)

# 숫자로 사용되는 컬럼들을 정수형으로 변환
numeric_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# ==========================================
# 7. 1위 영화 지표 카드 (Metrics)
# ==========================================
top_movie = df.iloc[0]

st.markdown("---")
st.subheader(f"🥇 1위: {top_movie['movieNm']}")

col1, col2, col3 = st.columns(3)

# 전일 대비 순위 변환 (+2, -1, 변동없음)
rank_inten = top_movie['rankInten']
if rank_inten > 0:
    rank_delta = f"▲ {rank_inten}"
elif rank_inten < 0:
    rank_delta = f"▼ {abs(rank_inten)}"
else:
    rank_delta = "변동없음"

col1.metric(
    label="일일 관객수",
    value=f"{top_movie['audiCnt']:,} 명",
    delta=rank_delta
)

col2.metric(
    label="누적 관객수",
    value=f"{top_movie['audiAcc']:,} 명"
)

col3.metric(
    label="스크린 수",
    value=f"{top_movie['scrnCnt']:,} 개"
)

# ==========================================
# 8. 관객수 상위 5편 막대그래프
# ==========================================
st.markdown("---")
st.subheader("📊 관객수 상위 5편")

top5_df = df.head(5)[["movieNm", "audiCnt"]].copy()
# 차트 범례 이름 깔끔하게 변경
top5_df.columns = ["영화명", "일일 관객수"]

st.bar_chart(
    data=top5_df,
    x="영화명",
    y="일일 관객수",
    use_container_width=True
)

# ==========================================
# 9. 전체 순위 표 (Table)
# ==========================================
st.markdown("---")
st.subheader("📋 전체 박스오피스 순위")

# 요청하신 출력용 컬럼만 선택 및 한글 표제어로 변경
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "일일 관객수", "누적 관객수", "스크린수"]

# 천 단위 쉼표(,) 포맷팅 적용
display_df["일일 관객수"] = display_df["일일 관객수"].apply(lambda x: f"{x:,}")
display_df["누적 관객수"] = display_df["누적 관객수"].apply(lambda x: f"{x:,}")
display_df["스크린수"] = display_df["스크린수"].apply(lambda x: f"{x:,}")

st.dataframe(
    display_df,
    hide_index=True,
    use_container_width=True
)
