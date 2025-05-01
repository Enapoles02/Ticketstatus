import streamlit as st
import pandas as pd
import datetime as dt
import io
import firebase_admin
from firebase_admin import credentials, firestore
import matplotlib.pyplot as plt
import altair as alt

# ————————————————
# Configuration & Secrets
# ————————————————
st.set_page_config(page_title="Tickets Dashboard", page_icon="📈", layout="wide")
ADMIN_CODE = st.secrets.get("admin_code", "ADMIN")
COLLECTION_NAME = "aging_dashboard"
DOCUMENT_ID = "latest_upload"
ALLOWED_TOWERS = ["MDM", "P2P", "O2C", "R2R"]

# Initialize Firebase only once
if not firebase_admin._apps:
    creds = st.secrets["firebase_credentials"]
    cred = credentials.Certificate(creds)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ————————————————
# Helpers
# ————————————————
def safe_age(created_date):
    try:
        if pd.isna(created_date): return None
        created = pd.to_datetime(created_date).normalize()
        today = pd.Timestamp("today").normalize()
        return (today - created).days
    except:
        return None

REGION_MAPPING = {
    "NAMER": ["US", "CA"],
    "LATAM": ["MX", "AR", "PE"],
    "EUR": ["BE", "GB", "ES", "SE", "IT", "FR", "AT", "SK", "RO", "IE", "CH"],
    "AFRICA": ["AO", "ZA"],
    "ASIA / MIDDLE EAST": ["BH", "QA", "AE"]
}
region_lookup = {code: region for region, codes in REGION_MAPPING.items() for code in codes}

def validate_columns(df, cols):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"❌ Missing columns: {', '.join(missing)}")
        return False
    return True


def load_data_from_excel(uploaded_file):
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip().str.replace(r"[\r\n]+", "", regex=True)
    if not validate_columns(df, ["Assignment group", "State", "Assigned to"]):
        return pd.DataFrame()
    # Created & Age
    created_cols = [c for c in df.columns if "created" in c.lower()]
    df["Created"] = pd.to_datetime(df[created_cols[0]] if created_cols else None, errors="coerce").dt.normalize()
    df["Age"] = df["Created"].apply(safe_age)
    df["Today"] = df["Age"] == 0
    df["Yesterday"] = df["Age"] == 1
    df["2 Days"] = df["Age"] == 2
    df["+3 Days"] = df["Age"] >= 3
    # TowerGroup
    df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()
    df = df.dropna(subset=["TowerGroup"])
    # Country & CompanyCode
    if "Client Codes Coding" in df.columns:
        cc = df["Client Codes Coding"].astype(str)
        df["Country"] = cc.str[:2]
        df["CompanyCode"] = cc.str[-4:]
    else:
        df["Country"] = None
        df["CompanyCode"] = None
        st.warning("⚠️ 'Client Codes Coding' missing.")
    # Status & Unassigned
    df["is_open"] = ~df["State"].str.contains("closed|resolved|cancel", case=False, na=False)
    df["Is_Unassigned"] = df["Assigned to"].isna() | (df["Assigned to"].str.strip() == "")
    df["Unassigned_Age"] = df.apply(lambda r: r["Age"] if r["Is_Unassigned"] else None, axis=1)
    # Region
    df["Region"] = df["Country"].map(region_lookup).fillna("Other")
    return df


def summarize(df):
    return (
        df.groupby("TowerGroup").agg(
            OPEN_TICKETS=("is_open", "sum"),
            Today=("Today", "sum"),
            Yesterday=("Yesterday", "sum"),
            **{"2 Days": ("2 Days", "sum")},
            **{"+3 Days": ("+3 Days", "sum")}    
        )
        .reset_index()
    )


def upload_to_firestore(df):
    df_clean = df.copy()
    for col in df_clean.columns:
        if df_clean[col].apply(lambda x: isinstance(x, (dict, list, set))).any():
            df_clean.drop(col, axis=1, inplace=True)
            st.warning(f"⚠️ Dropped '{col}' (non-serializable)")
    for c in df_clean.select_dtypes(include=["datetime", "datetimetz"]):
        df_clean[c] = df_clean[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_clean = df_clean.where(pd.notnull(df_clean), None)
    db.collection(COLLECTION_NAME).document(DOCUMENT_ID).set({
        "data": df_clean.to_dict(orient="records"),
        "last_update": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    })


def download_from_firestore():
    doc = db.collection(COLLECTION_NAME).document(DOCUMENT_ID).get()
    if doc.exists:
        c = doc.to_dict()
        return pd.DataFrame(c.get("data", [])), c.get("last_update")
    return pd.DataFrame(), None


def to_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Data")
    return buf.getvalue()

# ————————————————
# UI
# ————————————————
if "admin" not in st.session_state:
    st.session_state.admin = False

st.title("📈 Tickets Aging Dashboard")
if st.button("🔄 Refresh"):
    st.experimental_rerun()

with st.expander("🔐 Administrator Access"):
    if not st.session_state.admin:
        pwd = st.text_input("Enter ADMIN Code", type="password")
        if pwd == ADMIN_CODE:
            st.session_state.admin = True
            st.success("Admin mode enabled ✅")
    else:
        up = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
        if up:
            df_new = load_data_from_excel(up)
            if not df_new.empty:
                upload_to_firestore(df_new)
                st.success("Database updated ✅")
                st.experimental_rerun()

# Load & recalc
df, last_update = download_from_firestore()
if df.empty:
    st.warning("No data loaded.")
    st.stop()

# Dynamic flags recalculation
df["Created"] = pd.to_datetime(df["Created"], errors="coerce")
df["Age"] = df["Created"].apply(safe_age)
df["Today"] = df["Age"] == 0
df["Yesterday"] = df["Age"] == 1
df["2 Days"] = df["Age"] == 2
df["+3 Days"] = df["Age"] >= 3
df["is_open"] = ~df["State"].str.contains("closed|resolved|cancel", case=False, na=False)
df["Is_Unassigned"] = df["Assigned to"].isna() | (df["Assigned to"].str.strip() == "")
df["Unassigned_Age"] = df.apply(lambda r: r["Age"] if r["Is_Unassigned"] else None, axis=1)
# Ensure Region exists after reload
if "Region" not in df.columns:
    df["Region"] = df["Country"].map(region_lookup).fillna("Other")

# Sidebar Filters
st.sidebar.header("Filters")

# 1) Region filter
regions = sorted(df["Region"].dropna().unique())
sel_region = st.sidebar.multiselect("Region", regions, default=regions)

# 2) Filter by selected regions
df_reg = df[df["Region"].isin(sel_region)]

# 3) Country based on region
countries = sorted(df_reg["Country"].dropna().unique())
sel_country = st.sidebar.multiselect("Country", countries, default=countries)

# 4) Company Code based on selected countries
df_country = df_reg[df_reg["Country"].isin(sel_country)]
companies = sorted(df_country["CompanyCode"].dropna().unique())
sel_company = st.sidebar.multiselect("Company Code", companies, default=companies)

# 5) Apply filters
df_filtered = df[
    df["Region"].isin(sel_region) &
    df["Country"].isin(sel_country) &
    df["CompanyCode"].isin(sel_company) &
    df["TowerGroup"].isin(ALLOWED_TOWERS)
]

# Summary by Tower
t_summary = summarize(df_filtered)
st.sidebar.header("Graph Filters")
sel_towers = st.sidebar.multiselect("Select Towers", t_summary["TowerGroup"], default=t_summary["TowerGroup"])
df_graph = df_filtered[df_filtered["TowerGroup"].isin(sel_towers)]
t_summary = t_summary[t_summary["TowerGroup"].isin(t_summary["TowerGroup"])]

# KPIs
st.subheader("📊 KPIs")
total_open = int(df_graph["is_open"].sum())
total_plus3 = int(df_graph["+3 Days"].sum())
pct_overdue = (total_plus3 / total_open * 100) if total_open else 0
c1, c2, c3 = st.columns(3)
c1.metric("🎫 Open Tickets", total_open)
c2.metric("🕑 +3 Days", total_plus3)
c3.metric("📈 % Overdue", f"{pct_overdue:.1f}%")

# Summary by Tower Table
st.subheader("📋 Summary by Tower")
st.dataframe(t_summary, use_container_width=True, hide_index=True)

# Status Overview by SGBS & Local grouped by Tower
sgbs_df = df_graph[df_graph["Assignment group"].str.contains("SGBS|GBS|banking", case=False, na=False)]
local_df = df_graph[~df_graph["Assignment group"].str.contains("SGBS|GBS|banking", case=False, na=False) & df_graph["Assignment group"].notna()]
if not sgbs_df.empty:
    summary_sgbs = summarize(sgbs_df)
    st.subheader("📋 Status Overview by SGBS")
    st.dataframe(summary_sgbs, use_container_width=True, hide_index=True)
if not local_df.empty:
    summary_local = summarize(local_df)
    st.subheader("📋 Status Overview by Local")
    st.dataframe(summary_local, use_container_width=True, hide_index=True)

# Pie Charts
col1, col2 = st.columns(2)
with col1:
    st.markdown("**🔵 Open Tickets by Tower**")
    fig1, ax1 = plt.subplots()
    ax1.pie(t_summary["OPEN_TICKETS"], labels=t_summary["TowerGroup"], autopct='%1.1f%%')
    ax1.axis('equal')
    st.pyplot(fig1)
with col2:
    st.markdown("**🟠 Tickets +3 Days by Tower**")
    fig2, ax2 = plt.subplots()
    ax2.pie(t_summary["+3 Days"], labels=t_summary["TowerGroup"], autopct='%1.1f%%')
    ax2.axis('equal')
    st.pyplot(fig2)

# Status Overview by Tower
st.subheader("📋 Status Overview by Tower")
pivot_status = df_graph.pivot_table(
    index="State", columns="TowerGroup", values="Created", aggfunc="count", fill_value=0
).astype(int)
st.dataframe(pivot_status, use_container_width=True)

# Download Filtered DB
st.subheader("📥 Download Filtered DB")
st.download_button(
    "Download Excel", data=to_excel(df_graph), file_name="Filtered_Tickets.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Ticket Drilldown
st.subheader("👁️ Ticket Drilldown")
sel = st.selectbox("Select Tower", df_graph["TowerGroup"].unique())
df_tower = df_graph[df_graph["TowerGroup"] == sel]
state_filt = st.multiselect("Filter by State", df_tower["State"].unique())
if state_filt:
    df_tower = df_tower[df_tower["State"].isin(state_filt)]
st.dataframe(df_tower, use_container_width=True)
st.download_button(
    f"Download Tickets {sel}", data=to_excel(df_tower), file_name=f"Tickets_{sel}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Unassigned Tickets
st.subheader("📋 Unassigned Tickets")
df_un = df_graph[df_graph["Is_Unassigned"]].sort_values("Unassigned_Age", ascending=False)
if not df_un.empty:
    st.dataframe(
        df_un[["Number", "Short description", "Created", "Age", "Unassigned_Age"]],
        use_container_width=True, hide_index=True
    )
    overdue = df_un[df_un["Unassigned_Age"] > 3].shape[0]
    if overdue:
        st.error(f"⚠️ {overdue} tickets unassigned >3 days")
    st.subheader("👁️ Unassigned Drilldown")
    st.dataframe(df_un, use_container_width=True)
    st.download_button(
        "Download Unassigned", data=to_excel(df_un), file_name="Unassigned_Tickets.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Footer with last update
footer = f"""
<div style="position:fixed; bottom:0; left:0; width:100%; text-align:center;
        padding:6px; font-size:0.75rem; color:#888; background:#f8f8f8;">
    Last update: {last_update or "–"}
</div>
"""
st.markdown(footer, unsafe_allow_html=True)

# Interactive Region Chart
st.subheader("🌍 Tickets by Region and Country (Interactive)")
if "Region" not in df_graph.columns:
    df_graph["Region"] = df_graph["Country"].map(region_lookup).fillna("Other")
alt_data = df_graph.groupby(["Region", "Country"]).size().reset_index(name="Ticket Count")
chart = alt.Chart(alt_data).mark_bar().encode(
    x=alt.X("Country:N", sort="-y"),
    y="Ticket Count:Q",
    color="Region:N",
    tooltip=["Region", "Country", "Ticket Count"]
)
st.altair_chart(chart, use_container_width=True)

# Map Visualization
st.subheader("🗺️ Tickets by Country (Map)")

# Cargar GeoJSON mundial directamente
def_world_json = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'
world = alt.topo_feature(def_world_json, 'countries')

map_chart = alt.Chart(world).mark_geoshape().encode(
    color=alt.Color('Ticket Count:Q', title='Tickets'),
    tooltip=[
        alt.Tooltip('properties.name:N', title='Country'),
        alt.Tooltip('Ticket Count:Q')
    ]
).transform_lookup(
    lookup='properties.iso_a2',
    from_=alt.LookupData(alt_data, 'Country', ['Ticket Count'])
).project(
    type='equalEarth'
).properties(
    width=800,
    height=400
)

st.altair_chart(map_chart, use_container_width=True)
