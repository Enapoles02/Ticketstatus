# app.py
# -----------------------------------------------------------
# TICKETS DASHBOARD – Streamlit + Firebase
# -----------------------------------------------------------
import streamlit as st
import pandas as pd
import datetime as dt
import json
import firebase_admin
from firebase_admin import credentials, firestore
import io
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="TICKETS DASHBOARD",
    page_icon="📈",
    layout="wide",
)

# -----------------------------------------------------------
# Constants
# -----------------------------------------------------------
ADMIN_CODE = "ADMIN"
COLLECTION_NAME = "aging_dashboard"
DOCUMENT_ID = "latest_upload"
ALLOWED_TOWERS = ["MDM", "P2P", "O2C", "R2R"]

# -----------------------------------------------------------
# Initialize Firebase
# -----------------------------------------------------------
if not firebase_admin._apps:
    firebase_credentials = json.loads(st.secrets["firebase_credentials"])
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# -----------------------------------------------------------
# Functions
# -----------------------------------------------------------
def load_data_from_excel(uploaded_file) -> pd.DataFrame:
    df = pd.read_excel(uploaded_file)
    df["Created"] = pd.to_datetime(df["Created"], errors="coerce")
    today_midnight = pd.Timestamp("today").normalize()
    df["Age"] = (today_midnight - df["Created"].dt.normalize()).dt.days
    if "Client Codes Coding" in df.columns:
        df["Country"] = df["Client Codes Coding"].str[:2]
        df["CompanyCode"] = df["Client Codes Coding"].str[-4:]
    else:
        df["Country"] = ""
        df["CompanyCode"] = ""
    df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()

    df["Today"] = df["Age"] == 0
    df["Yesterday"] = df["Age"] == 1
    df["2 Days"] = df["Age"] == 2
    df["+3 Days"] = df["Age"] >= 3

    pattern = "|".join(["closed", "resolved", "cancel"])
    df["is_open"] = ~df["State"].str.contains(pattern, case=False, na=False)

    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("TowerGroup").agg(
        OPEN_TICKETS=("is_open", "sum"),
        Today=("Today", "sum"),
        Yesterday=("Yesterday", "sum"),
        **{"2 Days": ("2 Days", "sum")},
        **{"+3 Days": ("+3 Days", "sum")},
    ).reset_index()
    agg = agg.rename(columns={
        "TowerGroup": "TOWER",
    })
    return agg.sort_values("TOWER")


def upload_to_firestore(df: pd.DataFrame):
    """Upload DataFrame as JSON to Firestore."""
    df = df.copy()

    # 🔥 Replace NaT with None for datetime fields
    for col in df.select_dtypes(include=["datetime", "datetimetz"]).columns:
        df[col] = df[col].where(df[col].notna(), None)

    data_json = df.to_dict(orient="records")
    db.collection(COLLECTION_NAME).document(DOCUMENT_ID).set({
        "data": data_json,
        "last_update": dt.datetime.utcnow()
    })


def download_from_firestore() -> (pd.DataFrame, dt.datetime):
    """Download DataFrame from Firestore."""
    doc = db.collection(COLLECTION_NAME).document(DOCUMENT_ID).get()
    if doc.exists:
        content = doc.to_dict()
        df = pd.DataFrame(content["data"])
        return df, content.get("last_update")
    else:
        return pd.DataFrame(), None

def to_excel(df):
    """Convert DataFrame to Excel in memory."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dashboard")
    processed_data = output.getvalue()
    return processed_data

# -----------------------------------------------------------
# Session state
# -----------------------------------------------------------
if "admin" not in st.session_state:
    st.session_state.admin = False

if "refresh" not in st.session_state:
    st.session_state.refresh = False

# -----------------------------------------------------------
# Main Title
# -----------------------------------------------------------
st.title("📈 Tickets Aging Dashboard")

# -----------------------------------------------------------
# Refresh button
# -----------------------------------------------------------
if st.button("🔄 Refresh Firestore Data"):
    st.session_state.refresh = True

# -----------------------------------------------------------
# Admin access to upload files
# -----------------------------------------------------------
with st.expander("🔐 Administrator Access"):
    if not st.session_state.admin:
        pwd = st.text_input("Enter ADMIN Code to enable uploading", type="password")
        if pwd == ADMIN_CODE:
            st.session_state.admin = True
            st.success("Admin mode enabled ✅")
    else:
        st.info("Admin mode active")
        uploaded = st.file_uploader("Upload a new Excel file", type=["xls", "xlsx"])
        if uploaded:
            df_new = load_data_from_excel(uploaded)
            upload_to_firestore(df_new)
            st.success("Database successfully updated 🔥")
            st.rerun()

# -----------------------------------------------------------
# Load data from Firestore
# -----------------------------------------------------------
df, last_update = download_from_firestore()

# 🔥 Ensure critical columns always exist
if not df.empty:
    if "TowerGroup" not in df.columns:
        df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()
    if "Today" not in df.columns:
        df["Today"] = df["Age"] == 0
    if "Yesterday" not in df.columns:
        df["Yesterday"] = df["Age"] == 1
    if "2 Days" not in df.columns:
        df["2 Days"] = df["Age"] == 2
    if "+3 Days" not in df.columns:
        df["+3 Days"] = df["Age"] >= 3

# -----------------------------------------------------------
# Sidebar filters
# -----------------------------------------------------------
if not df.empty:
    st.sidebar.header("Filters")
    countries = sorted(df["Country"].dropna().unique())
    companies = sorted(df["CompanyCode"].dropna().unique())

    sel_country = st.sidebar.multiselect("Country (CA / US)", countries, default=countries)
    sel_company = st.sidebar.multiselect("Company Code (Last 4 digits)", companies, default=companies)

    df_filtered = df[
        df["Country"].isin(sel_country) &
        df["CompanyCode"].isin(sel_company)
    ]

    # Filter to only allowed Towers
    df_filtered = df_filtered[df_filtered["TowerGroup"].isin(ALLOWED_TOWERS)]

else:
    df_filtered = pd.DataFrame()

# -----------------------------------------------------------
# Main dashboard
# -----------------------------------------------------------
if df_filtered.empty:
    st.warning("No available data. Please upload a file.")
else:
    st.subheader("Dashboard Overview")

    summary = summarize(df_filtered)

    # KPIs
    total_open = int(summary["OPEN_TICKETS"].sum())
    total_plus3 = int(summary["+3 Days"].sum())
    percent_overdue = (total_plus3 / total_open) * 100 if total_open > 0 else 0

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("🎫 Total Open Tickets", total_open)
    kpi2.metric("🕑 Total +3 Days Tickets", total_plus3)
    kpi3.metric("📈 % Overdue", f"{percent_overdue:.1f}%")

    st.subheader("Summary by Tower")
    st.dataframe(summary, use_container_width=True, hide_index=True)

    # Sidebar filter for towers (for graphs)
    st.sidebar.header("Graph Filters")
    sel_towers = st.sidebar.multiselect("Select Towers for Graphs", summary["TOWER"].unique(), default=summary["TOWER"].unique())

    summary_filtered = summary[summary["TOWER"].isin(sel_towers)]

    # 📊 Pie Chart 1: Open Tickets Distribution
    st.subheader("Tickets Distribution by Tower")
    fig1, ax1 = plt.subplots()
    ax1.pie(
        summary_filtered["OPEN_TICKETS"],
        labels=summary_filtered["TOWER"],
        autopct='%1.1f%%',
        startangle=90,
        counterclock=False
    )
    ax1.axis('equal')
    st.pyplot(fig1)

    # 📊 Pie Chart 2: +3 Days Tickets Distribution
    st.subheader("+3 Days Tickets Distribution by Tower")
    fig2, ax2 = plt.subplots()
    ax2.pie(
        summary_filtered["+3 Days"],
        labels=summary_filtered["TOWER"],
        autopct='%1.1f%%',
        startangle=90,
        counterclock=False
    )
    ax2.axis('equal')
    st.pyplot(fig2)

    # 📥 Download button
    excel_data = to_excel(summary)
    st.download_button(
        label="📥 Download Summary in Excel",
        data=excel_data,
        file_name="Tickets_Summary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# -----------------------------------------------------------
# Footer with last update (centered and always visible)
# -----------------------------------------------------------
footer_text = f"Last update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}" if last_update else "Last update: –"

st.markdown(
    f"""
    <div style="
        position:fixed; 
        bottom:0; 
        left:0; 
        width:100%;
        text-align:center;
        padding:6px; 
        font-size:0.75rem; 
        color:#aaa;
        background-color:#f9f9f9;
    ">
        {footer_text}
    </div>
    """,
    unsafe_allow_html=True,
)
