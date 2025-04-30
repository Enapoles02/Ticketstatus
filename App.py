import streamlit as st
import pandas as pd
import datetime as dt
import json
import firebase_admin
from firebase_admin import credentials, firestore
import io
import matplotlib.pyplot as plt

st.set_page_config(page_title="Tickets Dashboard", page_icon="📈", layout="wide")
ADMIN_CODE = "ADMIN"
COLLECTION_NAME = "aging_dashboard"
ALLOWED_TOWERS = ["MDM", "P2P", "O2C", "R2R"]

REGION_MAP = {
    "US": "NAMER", "CA": "NAMER", "MX": "LATAM", "AR": "LATAM", "PE": "LATAM",
    "BE": "EUR", "GB": "EUR", "ES": "EUR", "SE": "EUR", "IT": "EUR", "FR": "EUR",
    "AT": "EUR", "SK": "EUR", "RO": "EUR", "IE": "EUR", "CH": "EUR",
    "AO": "AFRICA", "ZA": "AFRICA", "BH": "ASIA / MIDDLE EAST",
    "QA": "ASIA / MIDDLE EAST", "AE": "ASIA / MIDDLE EAST"
}

# Firebase Init
if not firebase_admin._apps:
    raw_credentials = st.secrets["firebase_credentials"]
    firebase_credentials = json.loads(json.dumps(dict(raw_credentials)))
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()

def safe_age(created_date):
    try:
        if pd.isna(created_date):
            return None
        created = pd.to_datetime(created_date).tz_localize(None)
        today = pd.Timestamp("today").normalize()
        return (today - created.normalize()).days
    except Exception:
        return None

def load_data_from_excel(uploaded_file):
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()
    if "Client codes coding" in df.columns:
        df["Country"] = df["Client codes coding"].astype(str).str[:2]
        df["CompanyCode"] = df["Client codes coding"].astype(str).str[-4:]
        df["Region"] = df["Country"].map(REGION_MAP).fillna("Other")
    else:
        df["Country"] = "Unknown"
        df["CompanyCode"] = "0000"
        df["Region"] = "Other"

    created_col = [col for col in df.columns if "created" in col.lower()]
    if created_col:
        df["Created"] = pd.to_datetime(df[created_col[0]], errors="coerce").dt.normalize()
    else:
        df["Created"] = pd.NaT
        st.warning("No 'Created' column found.")

    df["Age"] = df["Created"].apply(safe_age)
    df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()
    df["Today"] = df["Age"] == 0
    df["Yesterday"] = df["Age"] == 1
    df["2 Days"] = df["Age"] == 2
    df["+3 Days"] = df["Age"] >= 3
    df["is_open"] = ~df["State"].str.contains("closed|resolved|cancel", case=False, na=False)
    df["Is_Unassigned"] = df["Assigned to"].isna() | (df["Assigned to"].astype(str).str.strip() == "")
    df["Unassigned_Age"] = df.apply(lambda row: row["Age"] if row["Is_Unassigned"] else None, axis=1)
    return df

def summarize(df):
    return df.groupby("TowerGroup").agg(
        OPEN_TICKETS=("is_open", "sum"),
        Today=("Today", "sum"),
        Yesterday=("Yesterday", "sum"),
        **{"2 Days": ("2 Days", "sum")},
        **{"+3 Days": ("+3 Days", "sum")}
    ).reset_index().rename(columns={"TowerGroup": "TOWER"})

def upload_to_firestore(df):
    try:
        for doc in db.collection(COLLECTION_NAME).stream():
            doc.reference.delete()
        for i, row in df.iterrows():
            db.collection(COLLECTION_NAME).document(f"row_{i}").set(row.dropna().to_dict())
        db.collection(COLLECTION_NAME).document("meta_info").set({
            "last_update": dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            "total_rows": len(df)
        })
        st.success("✅ Data uploaded successfully!")
    except Exception as e:
        st.error(f"❌ Firestore upload failed:\n\n{e}")

def download_from_firestore():
    docs = db.collection(COLLECTION_NAME).stream()
    rows = []
    last_update = None
    for doc in docs:
        if doc.id == "meta_info":
            last_update = doc.to_dict().get("last_update")
        else:
            rows.append(doc.to_dict())
    return pd.DataFrame(rows), last_update

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

if "admin" not in st.session_state:
    st.session_state.admin = False

st.title("📈 Tickets Aging Dashboard")
refresh = st.button("🔄 Refresh Database")

with st.expander("🔐 Administrator Access"):
    if not st.session_state.admin:
        pwd = st.text_input("Enter ADMIN Code", type="password")
        if pwd == ADMIN_CODE:
            st.session_state.admin = True
            st.success("Admin mode enabled ✅")
    else:
        uploaded = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
        if uploaded:
            df_new = load_data_from_excel(uploaded)
            upload_to_firestore(df_new)
            st.rerun()

if refresh:
    st.rerun()

df, last_update = download_from_firestore()

if not df.empty:
    df["Created"] = pd.to_datetime(df["Created"], errors="coerce")
    df["Age"] = df["Created"].apply(safe_age)
    df["Today"] = df["Age"] == 0
    df["Yesterday"] = df["Age"] == 1
    df["2 Days"] = df["Age"] == 2
    df["+3 Days"] = df["Age"] >= 3
    df["is_open"] = ~df["State"].str.contains("closed|resolved|cancel", case=False, na=False)
    df["Is_Unassigned"] = df["Assigned to"].isna() | (df["Assigned to"].astype(str).str.strip() == "")
    df["Unassigned_Age"] = df.apply(lambda row: row["Age"] if row["Is_Unassigned"] else None, axis=1)

    st.sidebar.header("Filters")
    countries = sorted(df["Country"].dropna().unique())
    companies = sorted(df["CompanyCode"].dropna().unique())
    regions = sorted(df["Region"].dropna().unique())
    sel_region = st.sidebar.multiselect("🌍 Region", regions, default=regions)
    sel_country = st.sidebar.multiselect("Country", countries, default=countries)
    sel_company = st.sidebar.multiselect("Company Code", companies, default=companies)

    df_filtered = df[
        df["Region"].isin(sel_region) &
        df["Country"].isin(sel_country) &
        df["CompanyCode"].isin(sel_company) &
        df["TowerGroup"].isin(ALLOWED_TOWERS)
    ]

    # Subfiltro: mostrar solo CompanyCodes compatibles con Country
    if not df_filtered.empty:
        combos_validos = df_filtered.groupby("Country")["CompanyCode"].unique().to_dict()
        df_filtered = df_filtered[df_filtered.apply(lambda row: row["CompanyCode"] in combos_validos.get(row["Country"], []), axis=1)]

    summary = summarize(df_filtered)
    sel_towers = st.sidebar.multiselect("Select Towers", summary["TOWER"].unique(), default=summary["TOWER"].unique())
    df_graph = df_filtered[df_filtered["TowerGroup"].isin(sel_towers)]
    summary_filtered = summary[summary["TOWER"].isin(sel_towers)]

    if not df_graph.empty:
        st.subheader("📊 KPIs")
        total_open = int(df_graph["is_open"].sum())
        total_plus3 = int(df_graph["+3 Days"].sum())
        percent_overdue = (total_plus3 / total_open) * 100 if total_open > 0 else 0
        k1, k2, k3 = st.columns(3)
        k1.metric("🎫 Open Tickets", total_open)
        k2.metric("🕑 +3 Days", total_plus3)
        k3.metric("📈 % Overdue", f"{percent_overdue:.1f}%")

        st.subheader("📋 Summary by Tower")
        st.dataframe(summary_filtered, use_container_width=True)

        st.subheader("📊 Unassigned Tickets by Tower and Aging")
        chart_df = df_graph[df_graph["Is_Unassigned"]].copy()
        chart_df["Age Bucket"] = pd.cut(chart_df["Age"], bins=[-1, 0, 1, 2, float("inf")], labels=["0", "1", "2", "3+"])
        if not chart_df.empty:
            chart_summary = chart_df.groupby(["TowerGroup", "Age Bucket"]).size().unstack().fillna(0)
            st.bar_chart(chart_summary)

        st.subheader("📥 Download Filtered Data")
        st.download_button("Download DB", data=to_excel(df_graph), file_name="Tickets.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("No data available for selected filters.")

    st.markdown(f"""
    <div style="position:fixed; bottom:0; left:0; width:100%; text-align:center;
    padding:6px; font-size:0.75rem; color:#888; background-color:#f8f8f8;">
    Last update: {last_update if last_update else "–"}
    </div>
    """, unsafe_allow_html=True)
