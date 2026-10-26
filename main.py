import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 및 제목 표시
# ==========================================
st.set_page_config(
    page_title="일별 박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스 조회")

# ==========================================
# 2. 날짜 선택 달력 (최대 선택 가능일: KST 기준 어제)
# 배포 서버 시계(UTC)와 상관없이 KST 기준으로 어제를 계산합니다.
# ==========================================
kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.datetime.now(kst)
max_selectable_date = (now_kst - datetime.timedelta(days=1)).date()

selected_date = st.date_input(
    label="📅 조회할 날짜를 선택하세요 (최대 어제까지 선택 가능)",
    value=max_selectable_date,
    max_value=max_selectable_date
)

target_dt = selected_date.strftime('%Y%m%d')        # API 요청용 (예: 20261025)
display_date = selected_date.strftime('%Y년 %m월 %d일') # 화면 표시용

st.caption(f"📅 **현재 조회 날짜:** {display_date}")

# ==========================================
# 3. KOBIS API 인증키 불러오기
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
    response.raise_for_status()
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

if not movie_list:
    st.warning("⚠️ 그날은 아직 집계 전입니다.")
    st.info("""
    **확인 및 해결 방법:**
    - KOBIS의 일별 박스오피스는 매일 오전에 최종 집계됩니다.
    - 다른 날짜를 선택하시거나, 잠시 후 다시 시도해 주세요.
    """)
    st.stop()

# ==========================================
# 6. 데이터 전처리 (문자열 -> 정수 변환 및 오름차순 정렬)
# ==========================================
df = pd.DataFrame(movie_list)

# 숫자로 쓰이는 컬럼들을 명시적으로 정수(int) 변환
numeric_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# ⚠️ 핵심: 정수형 rank를 기준으로 데이터프레임을 명시적으로 오름차순(1 -> 10) 정렬
df = df.sort_values(by="rank", ascending=True).reset_index(drop=True)

# ==========================================
# 7. 1위 영화 지표 카드 (Metrics)
# ==========================================
# 명시적으로 정렬된 df에서 1위(rank == 1) 행 추출
top_movie = df.iloc[0]

top_title = top_movie['movieNm']
if top_movie['audiAcc'] >= 1000000:
    top_title += " 🏆"

st.markdown("---")
st.subheader(f"🥇 1위: {top_title}")

col1, col2, col3 = st.columns(3)

rank_inten = top_movie['rankInten']
if rank_inten > 0:
    rank_delta = f"🔺 {rank_inten}"
elif rank_inten < 0:
    rank_delta = f"🔹 {abs(rank_inten)}"
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

col
