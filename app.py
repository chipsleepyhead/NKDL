import os
import json
from pathlib import Path
from datetime import date

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="NYC Taxi Intelligence", page_icon="🚕", layout="wide")

# ---------- Theme ----------
st.markdown("""
<style>
:root {
    --bg: #080D18;
    --panel: #101827;
    --panel-2: #141F31;
    --line: rgba(148, 163, 184, .16);
    --text: #E8EEF8;
    --muted: #91A0B8;
    --cyan: #36D6D0;
    --blue: #5D8BFF;
}
.stApp {
    background:
      radial-gradient(ellipse at 12% 0%, rgba(38, 92, 150, .16), transparent 36%),
      radial-gradient(ellipse at 95% 8%, rgba(25, 183, 174, .09), transparent 28%),
      var(--bg);
    color: var(--text);
}
.block-container {
    padding-top: 1.35rem;
    padding-bottom: 2.2rem;
    max-width: 1650px;
}
[data-testid="stHeader"] { background: rgba(8, 13, 24, .78); }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1524 0%, #0A101C 100%);
    border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] > div { padding-top: 1.2rem; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #AAB7CB;
}
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stMultiSelect label,
[data-testid="stSidebar"] .stDateInput label,
[data-testid="stSidebar"] .stSlider label {
    color: #DCE6F5 !important;
}
h1, h2, h3 { color: #F2F6FC !important; letter-spacing: -.025em; }
p, label, span { }
div[data-testid="stMetric"] {
    background: linear-gradient(145deg, rgba(20,31,49,.96), rgba(14,23,37,.96));
    border: 1px solid var(--line);
    padding: 16px 18px;
    border-radius: 16px;
}
div[data-testid="stMetricLabel"] { color: #A5B4CA !important; }
div[data-testid="stMetricValue"] { color: #F4F8FF !important; }
div[data-testid="stMetricDelta"] { color: var(--cyan) !important; }
div[data-testid="stPlotlyChart"] {
    background: rgba(15, 24, 39, .70);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 8px 8px 2px 8px;
}
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
}
.stButton button[kind="primary"] {
    background: linear-gradient(100deg, #168C91, #3868D8);
    border: 0;
    border-radius: 10px;
    font-weight: 650;
}
.stButton button {
    border-radius: 10px;
}
hr { border-color: var(--line); }
.hero {
    position: relative;
    overflow: hidden;
    padding: 1.45rem 1.6rem;
    border: 1px solid rgba(91, 151, 203, .24);
    border-radius: 20px;
    background: linear-gradient(115deg, rgba(20, 43, 70, .98), rgba(14, 35, 51, .94) 58%, rgba(13, 57, 66, .90));
    color: white;
    margin: .25rem 0 1.25rem 0;
    box-shadow: 0 14px 36px rgba(0, 0, 0, .16);
}
.hero:after {
    content: "NYC";
    position: absolute;
    right: 1.4rem;
    top: -.95rem;
    font-size: 5.4rem;
    font-weight: 850;
    letter-spacing: -.09em;
    color: rgba(219, 245, 255, .055);
    pointer-events: none;
}
.hero h1 { font-size: 1.9rem; margin: 0 0 .45rem 0; }
.hero p { margin: 0; color: #B9D0E5; font-size: .96rem; }
.hero-tag {
    display: inline-block;
    margin-bottom: .7rem;
    padding: .25rem .58rem;
    border-radius: 999px;
    border: 1px solid rgba(90, 220, 215, .25);
    background: rgba(48, 198, 192, .09);
    color: #70E3DC;
    font-size: .70rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
}
.kpi {
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 1.05rem 1.1rem;
    min-height: 118px;
    background: linear-gradient(145deg, rgba(20,31,49,.98), rgba(12,20,33,.98));
    box-shadow: 0 8px 22px rgba(0,0,0,.10);
}
.kpi-label { font-size: .78rem; color: #9DADC3; margin-bottom: .55rem; }
.kpi-value { font-size: 1.58rem; color: #F3F7FE; font-weight: 760; letter-spacing: -.035em; }
.kpi-note { font-size: .73rem; color: #71839D; margin-top: .42rem; }
.section-eyebrow {
    color: #58D8D2;
    text-transform: uppercase;
    font-size: .72rem;
    letter-spacing: .12em;
    font-weight: 750;
    margin-bottom: .3rem;
}
.small-muted { color: #91A0B8; font-size: .82rem; }
</style>
""", unsafe_allow_html=True)

# ---------- Database ----------
# Expected local layout: project folder/data/nyc_taxi_demo.duckdb

import hashlib

PROJECT_DIR = Path(__file__).resolve().parent
DB_FILE = PROJECT_DIR / "data" / "nyc_taxi_demo.duckdb"
PARTS_DIR = PROJECT_DIR / "data" / "db_parts"

def restore_database():
    if DB_FILE.exists() and DB_FILE.stat().st_size > 0:
        return

    parts = sorted(PARTS_DIR.glob("part_*.bin"))

    if len(parts) != 5:
        raise FileNotFoundError(
            f"Thiếu database: tìm thấy {len(parts)}/5 phần trong {PARTS_DIR}"
        )

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = DB_FILE.with_suffix(".tmp")

    try:
        with temporary_file.open("wb") as output:
            for part in parts:
                with part.open("rb") as source:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)

        temporary_file.replace(DB_FILE)
    finally:
        if temporary_file.exists():
            temporary_file.unlink()

restore_database()
DEFAULT_DB = Path(__file__).resolve().parent / "data" / "nyc_taxi_demo.duckdb"

DB_PATH = Path(os.getenv("NYC_TAXI_DB_PATH", str(DEFAULT_DB))).expanduser()

# ML outputs generated by the modelling pipeline; visualized without refitting.
_PROJECT_DIR = Path(__file__).resolve().parent
_DEFAULT_ML_DIR = _PROJECT_DIR / "ml_results"
if not _DEFAULT_ML_DIR.exists() and (_PROJECT_DIR / "my_results").exists():
    _DEFAULT_ML_DIR = _PROJECT_DIR / "my_results"
ML_DIR = Path(os.getenv("NYC_TAXI_ML_DIR", str(_DEFAULT_ML_DIR))).expanduser()


@st.cache_data(show_spinner=False)
def load_ml_csv(filename: str) -> pd.DataFrame:
    path = ML_DIR / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def load_ml_json(filename: str) -> dict:
    path = ML_DIR / filename
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_zone_lookup(db_path: str) -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    try:
        return con.execute("""
            SELECT DISTINCT zone_id, zone, borough
            FROM mart_zone_hourly
            WHERE zone_id IS NOT NULL
        """).fetchdf()
    finally:
        con.close()


def query_df(sql: str, params=None) -> pd.DataFrame:
    """Run a read-only query against the demo DuckDB file."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Không tìm thấy database: {DB_PATH}. Hãy đặt nyc_taxi_demo.duckdb trong thư mục data."
        )
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(sql, params or []).fetchdf()
    finally:
        con.close()


@st.cache_data(show_spinner="Đang đọc Data Mart...")
def get_metadata(db_path: str):
    con = duckdb.connect(db_path, read_only=True)
    try:
        bounds = con.execute("""
            SELECT MIN(date_key), MAX(date_key)
            FROM mart_zone_hourly
        """).fetchone()
        boroughs = con.execute("""
            SELECT DISTINCT borough
            FROM mart_zone_hourly
            WHERE borough IS NOT NULL
            ORDER BY borough
        """).fetchdf()["borough"].tolist()
        zone_count = con.execute("SELECT COUNT(DISTINCT zone_id) FROM mart_zone_hourly").fetchone()[0]
        return bounds[0], bounds[1], boroughs, int(zone_count)
    finally:
        con.close()


@st.cache_data(show_spinner=False)
def cached_query(db_path: str, sql: str, params: tuple = ()) -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    try:
        return con.execute(sql, list(params)).fetchdf()
    finally:
        con.close()


def sql_filter(start_date, end_date, boroughs, hours=False):
    clauses = ["date_key BETWEEN ? AND ?"]
    params = [start_date, end_date]
    if boroughs:
        placeholders = ",".join(["?"] * len(boroughs))
        clauses.append(f"borough IN ({placeholders})")
        params.extend(boroughs)
    if hours:
        clauses.append("hour_of_day BETWEEN ? AND ?")
        params.extend(hours)
    return " AND ".join(clauses), tuple(params)


def money(value):
    return f"${float(value or 0):,.0f}"


def kpi(label, value, note=""):
    st.markdown(
        f'<div class="kpi"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div><div class="kpi-note">{note}</div></div>',
        unsafe_allow_html=True,
    )


def style_chart(fig):
    """Apply consistent dark styling to Plotly charts."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", color="#DCE6F5", size=12),
        title=dict(font=dict(size=15, color="#F1F5FB"), x=0.02, xanchor="left"),
        margin=dict(l=16, r=16, t=58, b=18),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#AAB7CB")),
        colorway=["#36D6D0", "#5D8BFF", "#B18CFF", "#F4B860", "#F17D9A", "#8BCB88"],
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="rgba(148,163,184,.11)",
        zerolinecolor="rgba(148,163,184,.18)", linecolor="rgba(148,163,184,.18)",
        tickfont=dict(color="#9EADC2")
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="rgba(148,163,184,.11)",
        zerolinecolor="rgba(148,163,184,.18)", linecolor="rgba(148,163,184,.18)",
        tickfont=dict(color="#9EADC2")
    )
    return fig


try:
    min_date, max_date, all_boroughs, total_zones = get_metadata(str(DB_PATH))
except Exception as exc:
    st.error("Chưa mở được database Data Mart.")
    st.code(str(exc))
    st.markdown("""
    **Cách khắc phục**
    1. Tạo thư mục `data` cùng cấp với `app.py`.
    2. Đặt file `nyc_taxi_demo.duckdb` vào thư mục `data`.
    3. Chạy lại `start_demo.bat`.
    """)
    st.stop()

# ---------- Navigation & filters ----------
st.sidebar.markdown("# 🚕 NYC Taxi")
st.sidebar.markdown("**INTELLIGENCE PLATFORM**")
st.sidebar.caption("Data Warehouse · Analytics")
page = st.sidebar.radio(
    "Điều hướng",
    ["Executive Overview", "Demand Analytics", "Spatial Zone Analysis",
     "Revenue & Congestion", "Demand Forecast", "Zone Segmentation", "AI Assistant"],
    label_visibility="visible",
)
st.sidebar.divider()
st.sidebar.markdown("**Bộ lọc dữ liệu**")
date_range = st.sidebar.date_input(
    "Khoảng ngày", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
selected_boroughs = st.sidebar.multiselect(
    "Borough", all_boroughs, default=all_boroughs
)
selected_hours = st.sidebar.slider("Khung giờ", 0, 23, (0, 23))
st.sidebar.divider()
st.sidebar.caption("LIVE SOURCE · DuckDB / 5 Data Marts")
st.sidebar.caption(f"Database: {DB_PATH.name} · {DB_PATH.stat().st_size / (1024**2):.1f} MB")

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range
if start_date > end_date:
    start_date, end_date = end_date, start_date
if not selected_boroughs:
    st.warning("Hãy chọn ít nhất một Borough ở thanh bên để hiển thị dữ liệu.")
    st.stop()

# SQL predicates and data mart queries
where_hour, params_hour = sql_filter(start_date, end_date, selected_boroughs, selected_hours)
where_all_hours, params_all_hours = sql_filter(start_date, end_date, selected_boroughs)
where_revenue, params_revenue = sql_filter(start_date, end_date, selected_boroughs)

hourly_sql = f"""
    SELECT hour_of_day AS hour, zone_id, zone, borough,
           SUM(trip_count) AS trip_count,
           SUM(total_revenue) AS total_revenue,
           AVG(avg_trip_distance) AS avg_trip_distance
    FROM mart_zone_hourly
    WHERE {where_hour}
    GROUP BY hour_of_day, zone_id, zone, borough
"""
h = cached_query(str(DB_PATH), hourly_sql, params_hour)

revenue_sql = f"""
    SELECT date_key AS date, borough, SUM(trip_count) AS trip_count,
           SUM(total_revenue) AS total_revenue,
           SUM(fare_revenue) AS fare_revenue,
           SUM(tip_revenue) AS tip_revenue,
           AVG(avg_revenue_per_trip) AS avg_revenue_per_trip,
           AVG(avg_trip_distance) AS avg_trip_distance
    FROM mart_revenue_borough
    WHERE {where_revenue}
    GROUP BY date_key, borough
"""
r = cached_query(str(DB_PATH), revenue_sql, params_revenue)

# Data mart hourly zone table includes daily/hourly aggregates, not individual trip/payment records.
trip_total = int(h["trip_count"].sum()) if not h.empty else 0
revenue_total = float(r["total_revenue"].sum()) if not r.empty else 0.0
avg_revenue_trip = float(r["avg_revenue_per_trip"].mean()) if not r.empty else 0.0
avg_distance = float(h["avg_trip_distance"].mean()) if not h.empty else 0.0

st.markdown(f"""
<div class="hero">
<div class="hero-tag">NYC TAXI · DATA WAREHOUSE</div>
<h1>{page}</h1>
<p>Khám phá nhu cầu di chuyển, hiệu quả doanh thu và mô hình hoạt động theo thời gian và khu vực.</p>
</div>
""", unsafe_allow_html=True)

if page == "Executive Overview":
    c = st.columns(4)
    with c[0]: kpi("Tổng lượt chuyến", f"{trip_total:,}", "Từ mart_zone_hourly theo bộ lọc")
    with c[1]: kpi("Tổng doanh thu", money(revenue_total), "Từ mart_revenue_borough")
    with c[2]: kpi("Doanh thu TB / chuyến", f"${avg_revenue_trip:,.2f}", "Trung bình theo ngày/khu vực")
    with c[3]: kpi("Quãng đường TB", f"{avg_distance:.2f} mi", "Từ số liệu tổng hợp theo zone/giờ")

    daily = r.groupby("date", as_index=False).agg(
        trip_count=("trip_count", "sum"), revenue=("total_revenue", "sum")
    ).sort_values("date") if not r.empty else pd.DataFrame(columns=["date", "trip_count", "revenue"])
    borough = h.groupby("borough", as_index=False)["trip_count"].sum().sort_values("trip_count", ascending=False) if not h.empty else pd.DataFrame(columns=["borough", "trip_count"])
    left, right = st.columns([1.5, 1])
    with left:
        fig = px.line(daily, x="date", y="trip_count", title="Xu hướng số chuyến theo ngày", markers=False)
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), xaxis_title="", yaxis_title="Trips")
        st.plotly_chart(style_chart(fig), width="stretch")
    with right:
        fig = px.bar(borough, x="trip_count", y="borough", orientation="h", title="Nhu cầu theo Borough")
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), xaxis_title="Trips", yaxis_title="")
        st.plotly_chart(style_chart(fig), width="stretch")
    st.caption("Các số liệu là kết quả tổng hợp trong Data Mart; không phải dữ liệu từng chuyến riêng lẻ.")

elif page == "Demand Analytics":
    c = st.columns(3)
    with c[0]: kpi("Trips trong bộ lọc", f"{trip_total:,}")
    with c[1]: kpi("Số zone xuất hiện", f"{h.zone_id.nunique():,}" if not h.empty else "0")
    with c[2]: kpi("Giờ được chọn", f"{selected_hours[0]:02d}:00–{selected_hours[1]:02d}:00")
    by_hour = h.groupby("hour", as_index=False)["trip_count"].sum() if not h.empty else pd.DataFrame(columns=["hour", "trip_count"])
    left, right = st.columns(2)
    with left:
        fig = px.bar(by_hour, x="hour", y="trip_count", title="Nhu cầu theo giờ", labels={"hour": "Giờ", "trip_count": "Số chuyến"})
        st.plotly_chart(style_chart(fig), width="stretch")
    with right:
        heat = cached_query(str(DB_PATH), f"""
            SELECT dayofweek(date_key) AS weekday, hour_of_day AS hour,
                   SUM(trip_count) AS trip_count
            FROM mart_zone_hourly
            WHERE {where_all_hours}
            GROUP BY weekday, hour ORDER BY weekday, hour
        """, params_all_hours)
        if not heat.empty:
            day_map = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}
            heat["day_name"] = heat["weekday"].map(day_map)
            pivot = heat.pivot(index="day_name", columns="hour", values="trip_count")
            order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            pivot = pivot.reindex([d for d in order if d in pivot.index])
            fig = px.imshow(pivot, aspect="auto", color_continuous_scale=["#14243A", "#1E5A77", "#27A9AD", "#79F0D7"], title="Heatmap: thứ × giờ", labels=dict(x="Giờ", y="Thứ", color="Trips"))
            st.plotly_chart(style_chart(fig), width="stretch")
        else:
            st.info("Không có dữ liệu trong bộ lọc.")
    top = h.groupby(["zone", "borough"], as_index=False)["trip_count"].sum().nlargest(12, "trip_count") if not h.empty else pd.DataFrame(columns=["zone", "borough", "trip_count"])
    fig = px.bar(top.sort_values("trip_count"), x="trip_count", y="zone", color="borough", orientation="h", title="Top zone theo nhu cầu")
    st.plotly_chart(style_chart(fig), width="stretch")

elif page == "Spatial Zone Analysis":
    st.caption("Bản đồ vùng taxi NYC theo ranh giới Taxi Zone chính thức. Màu sắc thể hiện nhu cầu hoặc doanh thu trong dữ liệu Data Mart của dự án.")
    zone_summary = (
        h.groupby(["zone_id", "zone", "borough"], as_index=False)
        .agg(trips=("trip_count", "sum"), revenue=("total_revenue", "sum"))
        if not h.empty else pd.DataFrame(columns=["zone_id", "zone", "borough", "trips", "revenue"])
    )

    if zone_summary.empty:
        st.info("Không có dữ liệu zone trong bộ lọc hiện tại.")
    else:
        metric_choice = st.radio(
            "Tô màu khu vực theo",
            ["Mức độ đông · số chuyến", "Doanh thu"],
            horizontal=True,
            key="zone_polygon_metric",
        )
        metric_col = "trips" if metric_choice.startswith("Mức") else "revenue"
        metric_title = "Số chuyến" if metric_col == "trips" else "Doanh thu tổng hợp"

        # Prefer a local official GeoJSON; if absent, try the NYC Open Data public endpoint.
        geojson_path = Path(__file__).resolve().parent / "data" / "taxi_zones.geojson"
        if not geojson_path.exists():
            geojson_path = Path(__file__).resolve().parent / "taxi_zones.geojson"

        geojson = None
        if geojson_path.exists():
            try:
                with open(geojson_path, "r", encoding="utf-8") as geo_file:
                    geojson = json.load(geo_file)
            except Exception:
                geojson = None

        if geojson is None:
            try:
                import urllib.request
                geo_url = "https://data.cityofnewyork.us/api/geospatial/8meu-9t5y?method=export&format=GeoJSON"
                with urllib.request.urlopen(geo_url, timeout=8) as response:
                    geojson = json.loads(response.read().decode("utf-8"))
                try:
                    geojson_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(geojson_path, "w", encoding="utf-8") as geo_file:
                        json.dump(geojson, geo_file)
                except Exception:
                    pass
            except Exception:
                st.error("Chưa có file ranh giới Taxi Zone GeoJSON và không tải được từ NYC Open Data. Đặt file `taxi_zones.geojson` trong thư mục `data` để bật bản đồ.")
                st.markdown("Nguồn ranh giới chính thức: [NYC Open Data – NYC Taxi Zones](https://data.cityofnewyork.us/Transportation/NYC-Taxi-Zones/8meu-9t5y)")

        if geojson is not None:
            features = geojson.get("features", [])
            id_property = None
            if features:
                props = features[0].get("properties", {})
                for candidate in ["locationid", "LocationID", "location_id", "OBJECTID", "objectid"]:
                    if candidate in props:
                        id_property = candidate
                        break
            if id_property is None:
                st.error("GeoJSON đã tải nhưng không tìm thấy trường ID của Taxi Zone.")
            else:
                map_data = zone_summary.copy()
                map_data["zone_id"] = pd.to_numeric(map_data["zone_id"], errors="coerce")
                map_data = map_data.dropna(subset=["zone_id"])
                map_data["zone_id"] = map_data["zone_id"].astype(int)
                # Use a string key so it joins reliably to GeoJSON feature IDs.
                value_lookup = {
                    str(int(row["zone_id"])): {
                        "zone": str(row["zone"]),
                        "borough": str(row["borough"]),
                        "trips": int(row["trips"]),
                        "revenue": float(row["revenue"]),
                    }
                    for _, row in map_data.iterrows()
                }
                for feature in features:
                    props = feature.get("properties", {})
                    zone_key = str(props.get(id_property, ""))
                    metric = value_lookup.get(zone_key)
                    props["project_zone_id"] = zone_key
                    props["project_zone_name"] = metric["zone"] if metric else str(props.get("zone", "Unknown"))
                    props["project_borough"] = metric["borough"] if metric else str(props.get("borough", "Unknown"))
                    props["project_trips"] = metric["trips"] if metric else None
                    props["project_revenue"] = metric["revenue"] if metric else None

                map_df = pd.DataFrame([
                    {
                        "zone_key": str(int(row["zone_id"])),
                        "zone": str(row["zone"]),
                        "borough": str(row["borough"]),
                        "trips": int(row["trips"]),
                        "revenue": float(row["revenue"]),
                    }
                    for _, row in map_data.iterrows()
                ])
                # Use choropleth (GeoJSON + lat/lon) rather than choropleth_mapbox.
                # This works with newer Plotly versions where choropleth_mapbox was removed.
                fig_map = px.choropleth(
                    map_df,
                    geojson=geojson,
                    locations="zone_key",
                    featureidkey=f"properties.{id_property}",
                    color=metric_col,
                    hover_name="zone",
                    hover_data={"borough": True, "trips": ":,", "revenue": ":,.2f", "zone_key": False},
                    projection="mercator",
                    title=f"NYC Taxi Zones · {metric_title}",
                    labels={"trips": "Số chuyến", "revenue": "Doanh thu"},
                )
                fig_map.update_geos(
                    center={"lat": 40.72, "lon": -73.92},
                    lataxis_range=[40.48, 40.95],
                    lonaxis_range=[-74.28, -73.68],
                    fitbounds="locations",
                    showcountries=False,
                    showland=True,
                    landcolor="#0A1422",
                    showocean=True,
                    oceancolor="#0A1422",
                    showlakes=True,
                    lakecolor="#0A1422",
                    bgcolor="#0A1422",
                )
                fig_map.update_traces(marker_line_color="#263449", marker_line_width=0.35)
                fig_map.update_layout(
                    height=680,
                    margin={"r": 0, "t": 55, "l": 0, "b": 0},
                    paper_bgcolor="#0A1422",
                    geo_bgcolor="#0A1422",
                )
                st.plotly_chart(style_chart(fig_map), width="stretch")
                st.caption("Di chuột lên từng vùng để xem tên zone, borough, số chuyến và doanh thu. Các chỉ số được tổng hợp theo dữ liệu và bộ lọc hiện tại.")

elif page == "Revenue & Congestion":
    c = st.columns(4)
    with c[0]: kpi("Tổng doanh thu", money(revenue_total))
    with c[1]: kpi("Fare revenue", money(r.fare_revenue.sum() if not r.empty else 0))
    with c[2]: kpi("Tip revenue", money(r.tip_revenue.sum() if not r.empty else 0))
    with c[3]: kpi("Số chuyến", f"{int(r.trip_count.sum()):,}" if not r.empty else "0")
    left, right = st.columns(2)
    with left:
        rev_daily = cached_query(str(DB_PATH), """
            SELECT date_key AS date, SUM(trip_count) AS trip_count,
                   SUM(total_revenue) AS total_revenue,
                   SUM(fare_revenue) AS fare_revenue,
                   SUM(tip_revenue) AS tip_revenue
            FROM mart_revenue_daily WHERE date_key BETWEEN ? AND ?
            GROUP BY date_key ORDER BY date_key
        """, (start_date, end_date))
        fig = px.line(rev_daily, x="date", y="total_revenue", title="Doanh thu tổng hợp theo ngày")
        st.plotly_chart(style_chart(fig), width="stretch")
    with right:
        borough_rev = r.groupby("borough", as_index=False)["total_revenue"].sum().sort_values("total_revenue", ascending=False) if not r.empty else pd.DataFrame(columns=["borough", "total_revenue"])
        fig = px.bar(borough_rev, x="borough", y="total_revenue", title="Doanh thu theo Borough")
        st.plotly_chart(style_chart(fig), width="stretch")
    st.caption("Data Mart hiện không chứa phương thức thanh toán hoặc phí congestion riêng; không hiển thị biểu đồ giả cho các trường này.")

elif page == "Demand Forecast":
    st.subheader("Demand Forecast · kết quả mô hình ML")
    forecast_meta = load_ml_json("forecast_result.json")
    predictions = load_ml_csv("forecast_predictions_TEST.csv")
    ranking = load_ml_csv("forecast_model_ranking_SELECTION.csv")
    importance = load_ml_csv("forecast_feature_importance.csv")

    if predictions.empty or not forecast_meta:
        st.warning("Chưa tìm thấy output ML. Kiểm tra thư mục ml_results cạnh app.py.")
    else:
        metrics = forecast_meta.get("test_metrics", {})
        st.caption("Đây là kết quả dự báo trên tập TEST holdout đã chạy trước đó, không phải dự báo tương lai trực tiếp.")
        m1, m2, m3, m4 = st.columns(4)
        with m1: kpi("Mô hình được chọn", str(forecast_meta.get("selection_winner", "N/A")), "Theo model-selection window")
        with m2: kpi("TEST MAE", f"{metrics.get('mae', float('nan')):.3f}", "Sai số tuyệt đối trung bình")
        with m3: kpi("TEST RMSE", f"{metrics.get('rmse', float('nan')):.3f}", "Sai số lớn bị phạt mạnh hơn")
        with m4: kpi("TEST R²", f"{metrics.get('r2', float('nan')):.3f}", "Đánh giá trên holdout")

        predictions["event_hour"] = pd.to_datetime(predictions["event_hour"], errors="coerce")
        predictions["event_date"] = predictions["event_hour"].dt.date
        filtered = predictions[predictions["event_date"].between(start_date, end_date)].copy()
        zones = load_zone_lookup(str(DB_PATH))
        if not zones.empty:
            zone_options = zones[["zone_id", "zone", "borough"]].drop_duplicates().sort_values("zone")
            zone_labels = {f"{int(row.zone_id)} · {row.zone} ({row.borough})": int(row.zone_id)
                           for row in zone_options.itertuples()}
            choices = ["All test zones"] + list(zone_labels.keys())
            choice = st.selectbox("Zone để xem dự báo", choices, key="ml_forecast_zone")
            if choice != "All test zones":
                filtered = filtered[filtered["zone_id"] == zone_labels[choice]]

        if filtered.empty:
            st.info("Không có dòng dự báo TEST trong khoảng ngày/zone đã chọn. Thử mở rộng bộ lọc ngày.")
        else:
            hourly = filtered.groupby("event_hour", as_index=False).agg(
                actual=("trip_count", "sum"), prediction=("prediction", "sum")
            ).sort_values("event_hour")
            left, right = st.columns([1.6, 1])
            with left:
                long = hourly.melt(id_vars="event_hour", value_vars=["actual", "prediction"],
                                   var_name="series", value_name="trips")
                fig = px.line(long, x="event_hour", y="trips", color="series",
                              title="Thực tế và dự báo · tập TEST",
                              labels={"event_hour": "Thời điểm", "trips": "Số chuyến", "series": "Chuỗi"})
                st.plotly_chart(style_chart(fig), width="stretch")
            with right:
                st.markdown("#### Chất lượng trên TEST")
                st.write(f"**Số dòng TEST:** {int(metrics.get('n_rows', len(predictions))):,}")
                st.write(f"**WAPE:** {metrics.get('wape_pct', float('nan')):.2f}%")
                st.write(f"**Khoảng hiển thị:** {start_date} → {end_date}")
                st.caption("Metric là kết quả toàn TEST; biểu đồ được lọc theo ngày và zone.")
            st.dataframe(filtered[["zone_id", "event_hour", "trip_count", "prediction"]].head(500),
                         width="stretch", hide_index=True)
            st.download_button("Tải CSV dự báo đang hiển thị",
                               data=filtered.to_csv(index=False).encode("utf-8"),
                               file_name="nyc_taxi_forecast_test_filtered.csv", mime="text/csv")

        if not ranking.empty:
            st.markdown("#### Xếp hạng mô hình trên selection window")
            st.caption("Bảng này dùng để chọn mô hình; metric TEST phía trên là đánh giá holdout cuối.")
            fig = px.bar(ranking.sort_values("mae", ascending=True), x="mae", y="model",
                         orientation="h", color="mae", title="Model ranking · MAE thấp hơn tốt hơn",
                         labels={"mae": "MAE", "model": "Mô hình"})
            st.plotly_chart(style_chart(fig), width="stretch")
            st.dataframe(ranking, width="stretch", hide_index=True)

        if not importance.empty:
            model_names = sorted(importance["model"].dropna().unique().tolist())
            model_pick = st.selectbox("Mô hình xem feature importance", model_names, key="ml_feature_model")
            imp = importance[importance["model"] == model_pick].nlargest(15, "importance").sort_values("importance")
            fig = px.bar(imp, x="importance", y="feature", orientation="h",
                         title=f"Top feature importance · {model_pick}",
                         labels={"importance": "Importance", "feature": "Feature"})
            st.plotly_chart(style_chart(fig), width="stretch")

        st.warning("Giới hạn: đây là one-hour-ahead backtesting với trip counts đã quan sát trong quá khứ. Không diễn giải thành dự báo 24 giờ tương lai. Missing zone-hours được xem là UNKNOWN, không tự coi là 0.")

elif page == "Zone Segmentation":
    st.subheader("Zone Segmentation · K-Means")
    cluster_meta = load_ml_json("clustering_result.json")
    assignments = load_ml_csv("zone_cluster_assignments.csv")
    cluster_profile = load_ml_csv("cluster_profile.csv")

    if assignments.empty or not cluster_meta:
        st.warning("Chưa tìm thấy output clustering. Kiểm tra thư mục ml_results cạnh app.py.")
    else:
        winner = cluster_meta.get("winner", {})
        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi("Thuật toán", str(winner.get("algorithm", "N/A")), "Mô hình được chọn")
        with c2: kpi("Số cụm", str(winner.get("k_found", "N/A")), "K tìm được")
        with c3: kpi("Silhouette", f"{winner.get('silhouette', float('nan')):.3f}", "Chỉ số cấu trúc cụm")
        with c4: kpi("Số zone", f"{winner.get('n_zones', len(assignments)):,}", "Zone được phân cụm")

        zones = load_zone_lookup(str(DB_PATH))
        if not zones.empty:
            assignments = assignments.merge(zones.drop_duplicates("zone_id"), on="zone_id", how="left")
        else:
            assignments["zone"] = assignments["zone_id"].astype(str)
            assignments["borough"] = "Unknown"

        st.caption("Cluster labels là mã số. Model được fit trên TRAIN period; cần diễn giải profile trước khi gán tên nghiệp vụ.")
        if not cluster_profile.empty:
            st.markdown("#### Hồ sơ các cụm")
            st.dataframe(cluster_profile, width="stretch", hide_index=True)
            fig = px.scatter(
                cluster_profile, x="pickup_per_recorded_hour", y="revenue_per_trip",
                size="n_zones", color=cluster_profile["cluster_id"].astype(str),
                hover_data=["cluster_id", "n_zones", "weekend_ratio", "night_ratio", "peak_ratio"],
                title="Cluster profile · nhu cầu và doanh thu/chuyến",
                labels={"pickup_per_recorded_hour": "Trips / recorded hour",
                        "revenue_per_trip": "Revenue / trip", "color": "Cluster"}
            )
            st.plotly_chart(style_chart(fig), width="stretch")

        st.markdown("#### Tra cứu zone theo cụm")
        cluster_ids = sorted(assignments["cluster_id"].dropna().unique().tolist())
        selected_clusters = st.multiselect("Lọc cluster", cluster_ids, default=cluster_ids, key="ml_cluster_filter")
        visible = assignments[assignments["cluster_id"].isin(selected_clusters)].copy()
        borough_options = sorted(visible["borough"].dropna().astype(str).unique().tolist())
        borough_filter = st.multiselect("Lọc Borough", borough_options, default=borough_options, key="ml_cluster_borough")
        visible = visible[visible["borough"].astype(str).isin(borough_filter)]
        cols = [c for c in ["zone_id", "zone", "borough", "cluster_id", "trips",
                            "pickup_per_recorded_hour", "observation_coverage", "weekend_ratio",
                            "night_ratio", "peak_ratio", "revenue_per_trip", "distance_per_trip"]
                if c in visible.columns]
        st.dataframe(visible[cols].sort_values(["cluster_id", "trips"], ascending=[True, False]),
                     width="stretch", hide_index=True)
        st.download_button("Tải CSV zone và cluster",
                           data=visible.to_csv(index=False).encode("utf-8"),
                           file_name="nyc_taxi_zone_clusters.csv", mime="text/csv")
        st.warning("Không tự gán nhãn như tourist/business zone. Cluster IDs là kết quả thuật toán; cần diễn giải và xác thực trước khi đặt tên.")

else:
    st.subheader("AI Assistant · hỏi đáp từ Data Mart")
    st.caption("Trợ lý hỏi đáp theo quy tắc trên Data Mart, có thể hiểu nhiều cách diễn đạt phổ biến nhưng chưa kết nối mô hình ngôn ngữ lớn.")
    st.markdown("Bạn có thể hỏi tự nhiên, chẳng hạn: **Giờ nào có doanh thu cao nhất?**, **Khu vực nào đông nhất?**, **Borough nào kiếm được nhiều tiền nhất?**")

    with st.form("assistant_question_form", clear_on_submit=False):
        question = st.text_input(
            "Nhập câu hỏi",
            placeholder="Ví dụ: Giờ nào có doanh thu nhiều nhất?",
            key="assistant_question_input",
        )
        submitted = st.form_submit_button("Phân tích câu hỏi", type="primary")

    if submitted:
        st.session_state["assistant_question"] = question.strip()

    question_to_answer = st.session_state.get("assistant_question", "")
    if question_to_answer:
        q = question_to_answer.casefold()
        revenue_words = ["doanh thu", "revenue", "kiếm được", "thu nhập", "tiền nhiều", "tiền cao", "gross"]
        hour_words = ["giờ", "hour", "khung giờ", "thời điểm", "mấy giờ", "theo giờ"]
        zone_words = ["zone", "khu vực", "vùng", "borough", "quận", "địa điểm"]
        top_words = ["cao nhất", "nhiều nhất", "lớn nhất", "đông nhất", "tốt nhất", "top", "nào cao", "nào nhiều"]
        is_revenue = any(word in q for word in revenue_words)
        is_hour = any(word in q for word in hour_words)
        is_zone = any(word in q for word in zone_words)
        is_top = any(word in q for word in top_words)

        if h.empty:
            st.info("Không có dữ liệu trong bộ lọc hiện tại để trả lời câu hỏi.")
        elif is_revenue and is_hour:
            hourly_revenue = h.groupby("hour", as_index=False)["total_revenue"].sum().sort_values("total_revenue", ascending=False)
            if hourly_revenue.empty:
                st.info("Không có dữ liệu doanh thu theo giờ trong bộ lọc hiện tại.")
            else:
                top_row = hourly_revenue.iloc[0]
                st.success(f"Giờ có doanh thu tổng hợp cao nhất là **{int(top_row['hour']):02d}:00**, đạt **{money(top_row['total_revenue'])}**.")
                display_df = hourly_revenue.copy()
                display_df["hour"] = display_df["hour"].map(lambda value: f"{int(value):02d}:00")
                st.dataframe(display_df.rename(columns={"hour": "Giờ", "total_revenue": "Doanh thu"}), width="stretch", hide_index=True)
                fig = px.bar(hourly_revenue.sort_values("hour"), x="hour", y="total_revenue", title="Doanh thu theo giờ", labels={"hour": "Giờ", "total_revenue": "Doanh thu"})
                st.plotly_chart(style_chart(fig), width="stretch")
        elif is_hour:
            value_col = "total_revenue" if is_revenue else "trip_count"
            hourly = h.groupby("hour", as_index=False)[value_col].sum().sort_values(value_col, ascending=False)
            if hourly.empty:
                st.info("Không có dữ liệu theo giờ trong bộ lọc hiện tại.")
            else:
                top_row = hourly.iloc[0]
                if is_revenue:
                    st.success(f"Giờ có doanh thu cao nhất là **{int(top_row['hour']):02d}:00**, đạt **{money(top_row[value_col])}**.")
                else:
                    st.success(f"Giờ đông nhất là **{int(top_row['hour']):02d}:00**, với **{int(top_row[value_col]):,} chuyến**.")
                st.dataframe(hourly, width="stretch", hide_index=True)
        elif is_revenue and is_zone:
            by_zone = h.groupby(["zone", "borough"], as_index=False)["total_revenue"].sum().sort_values("total_revenue", ascending=False)
            if not by_zone.empty:
                top_row = by_zone.iloc[0]
                st.success(f"Khu vực có doanh thu cao nhất là **{top_row['zone']} ({top_row['borough']})**, đạt **{money(top_row['total_revenue'])}**.")
                st.dataframe(by_zone.head(15), width="stretch", hide_index=True)
        elif is_revenue:
            by_borough = r.groupby("borough", as_index=False)["total_revenue"].sum().sort_values("total_revenue", ascending=False)
            if not by_borough.empty:
                top_row = by_borough.iloc[0]
                st.success(f"Borough có doanh thu cao nhất là **{top_row['borough']}**, đạt **{money(top_row['total_revenue'])}**.")
                st.dataframe(by_borough, width="stretch", hide_index=True)
        elif is_zone or any(word in q for word in ["nhu cầu", "chuyến", "pickup", "đông", "bận rộn"]):
            value_col = "total_revenue" if is_revenue else "trip_count"
            by_zone = h.groupby(["zone", "borough"], as_index=False)[value_col].sum().sort_values(value_col, ascending=False)
            if not by_zone.empty:
                top_row = by_zone.iloc[0]
                if is_revenue:
                    st.success(f"Khu vực có doanh thu cao nhất là **{top_row['zone']} ({top_row['borough']})**, đạt **{money(top_row[value_col])}**.")
                else:
                    st.success(f"Khu vực đông nhất là **{top_row['zone']} ({top_row['borough']})**, với **{int(top_row[value_col]):,} chuyến**.")
                st.dataframe(by_zone.head(15), width="stretch", hide_index=True)
        else:
            st.info("Mình chưa phân loại được ý câu hỏi này. Hiện có thể trả lời câu hỏi về doanh thu theo giờ/khu vực/Borough, số chuyến theo giờ và khu vực. Hãy diễn đạt theo một trong các chỉ số đó.")

st.divider()
st.caption("NYC TAXI INTELLIGENCE  /  DATA SOURCE: DuckDB · 5 Data Marts  /  Số liệu lấy từ database dự án; không sinh dữ liệu giả.")
