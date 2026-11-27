# 영업팀 매출 현황 대시보드
# 영업팀장이 지역·카테고리·기간을 고르면 매출 지표, 월별 추이, 지역별 비교, 상세 표를 볼 수 있는 화면
from pathlib import Path

import pandas as pd
import streamlit as st

# ── 기본 설정 ───────────────────────────────────────────
st.set_page_config(page_title="영업팀 매출 현황", page_icon="📊", layout="wide")

# 데이터 파일 위치: app.py와 같은 폴더 기준(상대경로) → 배포 서버에서도 그대로 동작
DATA_FILE = Path(__file__).parent / "sales_sample.csv"
# 화면에 꼭 필요한 열 목록
REQUIRED_COLUMNS = ["date", "region", "category", "sales", "quantity"]


@st.cache_data  # 조건을 바꿔 화면이 다시 실행돼도 파일은 한 번만 읽도록 결과를 기억
def load_data(path: Path) -> pd.DataFrame:
    # utf-8-sig: 엑셀에서 저장한 CSV 맨 앞의 보이지 않는 표시(BOM)까지 처리
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        # 엑셀(CP949)로 저장된 한글 CSV도 읽을 수 있게 한 번 더 시도
        df = pd.read_csv(path, encoding="cp949")
    df.columns = df.columns.str.strip()  # 열 이름 앞뒤 공백 제거
    return df


# ── 제목 ────────────────────────────────────────────────
st.title("📊 영업팀 매출 현황")
st.caption("데이터 기준: 2026년 1~10월 · 출처: sales_sample.csv (수업용 가상 매출 데이터)")

# ── 방어 코드 1) 데이터 파일이 없을 때 ──────────────────
if not DATA_FILE.exists():
    st.error(
        f"데이터 파일 '{DATA_FILE.name}'을(를) 찾을 수 없습니다. "
        "파일 이름이 맞는지, app.py와 같은 폴더에 있는지 확인해 주세요."
    )
    st.stop()  # 여기서 화면 그리기를 멈춤

df = load_data(DATA_FILE)

# ── 방어 코드 2) 필요한 열이 없을 때 ────────────────────
missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
if missing:
    st.error(
        f"데이터에 필요한 열이 없습니다: {', '.join(missing)}. "
        "CSV 첫 줄(머리글)의 열 이름을 확인해 주세요."
    )
    st.stop()

# 자료형 정리: 날짜는 날짜로, 매출·수량은 숫자로 (읽을 수 없는 값은 빈칸 처리 후 제외)
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
df = df.dropna(subset=["date", "sales"])

if df.empty:
    st.error("데이터 파일에 읽을 수 있는 행이 없습니다. CSV 내용을 확인해 주세요.")
    st.stop()

# ── 사이드바: 조건 선택 ─────────────────────────────────
st.sidebar.header("조건 선택")

# 지역: 여러 개 선택, 기본은 전체
region_options = sorted(df["region"].dropna().unique())
regions = st.sidebar.multiselect("지역", region_options, default=region_options)

# 카테고리: 드롭다운, '전체' 포함
category_options = ["전체"] + sorted(df["category"].dropna().unique())
category = st.sidebar.selectbox("카테고리", category_options)

# 기간: 슬라이더로 시작~끝 날짜 범위 선택
min_day = df["date"].min().date()
max_day = df["date"].max().date()
start_day, end_day = st.sidebar.slider(
    "기간",
    min_value=min_day,
    max_value=max_day,
    value=(min_day, max_day),
    format="YYYY-MM-DD",
)

# ── 필터: 고른 조건으로 걸러낸 데이터 = filtered ────────
cond = df["region"].isin(regions)  # 지역: 고른 값 중 하나
if category != "전체":
    cond &= df["category"] == category  # 카테고리: 고른 값과 같음
cond &= df["date"].dt.date.between(start_day, end_day)  # 기간: 범위 안
filtered = df[cond]

st.sidebar.markdown(f"**선택 조건: {len(filtered):,}건 / 전체 {len(df):,}건**")

# ── 방어 코드 3) 조건에 맞는 데이터가 0건일 때 ──────────
# 필터 바로 아래, 지표·그래프·표보다 위에서 검사
if filtered.empty:
    st.info(
        "선택한 조건에 맞는 데이터가 없습니다(0건). "
        "왼쪽 사이드바에서 지역을 하나 이상 고르거나, 카테고리를 '전체'로 바꾸거나, "
        "기간을 넓혀 보세요."
    )
    st.stop()  # 0건이면 지표·그래프·표를 그리지 않음

# ── 본문: 탭 두 개 ──────────────────────────────────────
tab_summary, tab_detail = st.tabs(["요약", "상세 데이터"])

with tab_summary:
    # 지표 카드 3개 (모두 filtered 기준)
    total_sales = filtered["sales"].sum()
    order_count = len(filtered)
    avg_order = total_sales / order_count  # 0건은 위에서 막았으므로 0으로 나눌 일 없음

    c1, c2, c3 = st.columns(3)
    c1.metric("총 매출", f"{total_sales:,.0f}원")
    c2.metric("주문 건수", f"{order_count:,}건")
    c3.metric("평균 주문액", f"{avg_order:,.0f}원")

    left, right = st.columns(2)

    with left:
        # 월별 매출 추이 → 선 그래프 (월 순서대로)
        st.subheader("월별 매출 추이")
        monthly = (
            filtered.groupby(filtered["date"].dt.to_period("M"))["sales"].sum()
        )
        monthly.index = monthly.index.strftime("%Y-%m")  # '2026-01' 형태로 표시
        monthly.index.name = "월"
        st.line_chart(monthly, y_label="매출(원)")

    with right:
        # 지역별 매출 → 막대 그래프 (큰 순서대로)
        st.subheader("지역별 매출 (큰 순서)")
        by_region = (
            filtered.groupby("region")["sales"].sum().sort_values(ascending=False)
        )
        by_region.index.name = "지역"
        # sort=False: 위에서 정한 '큰 순서'를 그래프가 그대로 따르게 함
        st.bar_chart(by_region, y_label="매출(원)", sort=False)

    # 경영 판단 문장 (현재 조건의 1위 지역 기준으로 자동 작성)
    top_region = by_region.index[0]
    top_share = by_region.iloc[0] / total_sales * 100
    st.markdown("---")
    st.markdown(
        f"**이 화면으로 내릴 수 있는 경영 판단:** 현재 조건에서 매출 1위 지역은 "
        f"**{top_region}**(전체의 {top_share:.0f}%)입니다. 매출이 낮은 지역과 월을 확인해 "
        "판촉 예산과 재고 배분을 조정하는 근거로 쓸 수 있습니다."
    )

with tab_detail:
    st.subheader("상세 데이터")
    # 보기 좋은 한글 열 이름으로 바꿔 표로 표시 (열 제목을 누르면 정렬됨)
    table = filtered.sort_values("date").rename(
        columns={
            "date": "날짜",
            "region": "지역",
            "category": "카테고리",
            "sales": "매출(원)",
            "quantity": "수량",
        }
    )
    st.dataframe(
        table,
        width="stretch",  # 화면 폭에 맞춤
        hide_index=True,  # 행 번호 숨김
        column_config={
            "날짜": st.column_config.DateColumn(format="YYYY-MM-DD"),
            "매출(원)": st.column_config.NumberColumn(format="%d"),
        },
    )
