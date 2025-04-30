import streamlit as st
import pandas as pd
import datetime as dt
import json
import firebase_admin
from firebase_admin import credentials, firestore
import io
import matplotlib.pyplot as plt
import altair as alt
import plotly.express as px

st.set_page_config(page_title="Tickets Dashboard", page_icon="📈", layout="wide")

ADMIN_CODE = "ADMIN"
COLLECTION_NAME = "aging_dashboard"
DOCUMENT_ID = "latest_upload"
ALLOWED_TOWERS = ["MDM", "P2P", "O2C", "R2R"]

if not firebase_admin._apps:
    raw_secrets = st.secrets["firebase_credentials"]
    firebase_credentials = {k: v for k, v in raw_secrets.items()}
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()

REGION_MAPPING = {
    "NAMER": ["US", "CA"],
    "LATAM": ["MX", "AR", "PE"],
    "EUR": ["BE", "GB", "ES", "SE", "IT", "FR", "AT", "SK", "RO", "IE", "CH"],
    "AFRICA": ["AO", "ZA"],
    "ASIA / MIDDLE EAST": ["BH", "QA", "AE"]
}
region_lookup = {code: region for region, codes in REGION_MAPPING.items() for code in codes}

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
    df.columns = df.columns.str.strip().str.replace(r"[\r\n]+", "", regex=True)
    created_col = [col for col in df.columns if "created" in col.lower()]
    df["Created"] = pd.to_datetime(df[created_col[0]], errors="coerce").dt.normalize() if created_col else pd.NaT
    df["Age"] = df["Created"].apply(safe_age)
    df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()

    if "Client Codes Coding" in df.columns:
        df["Country"] = df["Client Codes Coding"].astype(str).str[:2]
        df["CompanyCode"] = df["Client Codes Coding"].astype(str).str[-4:]
        df["Region"] = df["Country"].map(region_lookup).fillna("Other")
        df = df[df["Region"].isin(["NAMER", "LATAM"])]
    else:
        df["Country"] = None
        df["CompanyCode"] = None
        df["Region"] = None
        st.warning("⚠️ 'Client Codes Coding' column is missing. 'Country', 'CompanyCode' and 'Region' not derived.")

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
    df_clean = df.copy()
    for col in df_clean.select_dtypes(include=["datetime", "datetimetz", "datetime64"]).columns:
        df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d %H:%M:%S')
    df_clean = df_clean.where(pd.notnull(df_clean), None)
    for col in df_clean.columns:
        if df_clean[col].apply(lambda x: isinstance(x, (dict, list, set))).any():
            df_clean.drop(columns=[col], inplace=True)
            st.warning(f"⚠️ Dropped column '{col}' (not serializable).")
    data_json = df_clean.to_dict(orient="records")
    db.collection(COLLECTION_NAME).document(DOCUMENT_ID).set({
        "data": data_json,
        "last_update": dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    })

def download_from_firestore():
    doc = db.collection(COLLECTION_NAME).document(DOCUMENT_ID).get()
    if doc.exists:
        content = doc.to_dict()
        return pd.DataFrame(content["data"]), content.get("last_update")
    return pd.DataFrame(), None

def to_excel(df):
    df_safe = df.copy()
    for col in df_safe.select_dtypes(include=["datetimetz"]).columns:
        df_safe[col] = df_safe[col].dt.tz_localize(None)
    for col in df_safe.columns:
        df_safe[col] = df_safe[col].apply(lambda x: str(x) if isinstance(x, (dict, list, set)) else x)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_safe.to_excel(writer, index=False, sheet_name="Data")
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
            st.success("Database updated successfully ✅")
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
    if "TowerGroup" not in df.columns:
        df["TowerGroup"] = df["Assignment group"].str.split().str[1].str.upper()
    if "Country" not in df.columns and "Client Codes Coding" in df.columns:
        df["Country"] = df["Client Codes Coding"].astype(str).str[:2]
        df["CompanyCode"] = df["Client Codes Coding"].astype(str).str[-4:]
    if "Region" not in df.columns:
        df["Region"] = df["Country"].map(region_lookup).fillna("Other")

    df["is_open"] = ~df["State"].str.contains("closed|resolved|cancel", case=False, na=False)
    df["Is_Unassigned"] = df["Assigned to"].isna() | (df["Assigned to"].astype(str).str.strip() == "")
    df["Unassigned_Age"] = df.apply(lambda row: row["Age"] if row["Is_Unassigned"] else None, axis=1)

    st.sidebar.header("Filters")
    region_options = sorted(df["Region"].dropna().unique())
    sel_region = st.sidebar.multiselect("Region", region_options, default=region_options)
    sel_country = st.sidebar.multiselect("Country", sorted(df["Country"].dropna().unique()))
    sel_company = st.sidebar.multiselect("Company Code", sorted(df["CompanyCode"].dropna().unique()))

    df_filtered = df[
        df["Region"].isin(sel_region) &
        df["Country"].isin(sel_country) &
        df["CompanyCode"].isin(sel_company) &
        df["TowerGroup"].isin(ALLOWED_TOWERS)
    ]
