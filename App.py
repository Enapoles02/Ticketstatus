import streamlit as st
import pandas as pd
import io
import re
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import credentials, firestore

import qrcode
from PIL import Image

# -----------------------
# Configuración general
# -----------------------
st.set_page_config(page_title="Drop24 • Admin Clientes & QR", page_icon="🧺", layout="wide")

ADMIN_CODE = st.secrets.get("admin_code", "ADMIN")

# Firestore (usa tu conexión)
COLLECTION_NAME = "drop24_clients"
META_DOC_ID = "meta"             # guarda metadatos (last_update, total_rows, etc.)
BATCH_PREFIX = "batch_"          # batch_0, batch_1, ...

MEXICO_TZ = ZoneInfo("America/Mexico_City")

# Initialize Firebase only once (MISMA LÓGICA QUE TU CÓDIGO)
if not firebase_admin._apps:
    creds_attr = st.secrets["firebase_credentials"]
    creds = creds_attr.to_dict() if hasattr(creds_attr, "to_dict") else creds_attr
    cred = credentials.Certificate(creds)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -----------------------
# Helpers
# -----------------------
def now_cdmx_str():
    return datetime.now(MEXICO_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

def clean_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"[\r\n]+", "", regex=True)
    )
    return df

def safe_str(x):
    if pd.isna(x):
        return ""
    return str(x).strip()

def normalize_phone(x: str) -> str:
    digits = re.sub(r"\D+", "", safe_str(x))
    return digits

def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Columnas que generamos si faltan
    for c in ["Client ID", "QR Token", "QR Payload", "Updated At"]:
        if c not in df.columns:
            df[c] = ""
    return df

def build_client_id(nombre: str, apellido: str, telefono: str, row_index: int) -> str:
    n = safe_str(nombre).upper()
    a = safe_str(apellido).upper()
    p = normalize_phone(telefono)

    ini = (n[:1] if n else "X") + (a[:1] if a else "X")
    last4 = p[-4:] if len(p) >= 4 else str(row_index).zfill(4)
    return f"C{ini}{last4}{str(row_index).zfill(4)}"

def build_token(client_id: str) -> str:
    ts = datetime.now(MEXICO_TZ).strftime("%Y%m%d%H%M%S")
    return f"T{client_id}-{ts}"

def make_payload(prefix: str, client_id: str, token: str) -> str:
    # Payload simple, robusto y fácil de parsear en Android
    # Ej: DROP24|CNA12340001|TCNA12340001-20260106153000
    return f"{prefix}|{client_id}|{token}"

def make_qr_png_bytes(payload: str) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Clientes")
    return buf.getvalue()

def split_batches(rows: list[dict], batch_size: int = 500) -> list[list[dict]]:
    return [rows[i:i+batch_size] for i in range(0, len(rows), batch_size)]

def firestore_delete_existing_batches():
    # Borra batch_* existentes (si hay)
    docs = db.collection(COLLECTION_NAME).stream()
    for d in docs:
        if d.id.startswith(BATCH_PREFIX) or d.id == META_DOC_ID:
            db.collection(COLLECTION_NAME).document(d.id).delete()

def upload_clients_to_firestore(df: pd.DataFrame):
    # Limpiar NaNs
    df_clean = df.copy()
    df_clean = df_clean.where(pd.notnull(df_clean), None)

    # Convertir datetimes a string (por si acaso)
    for c in df_clean.columns:
        if pd.api.types.is_datetime64_any_dtype(df_clean[c]):
            df_clean[c] = pd.to_datetime(df_clean[c], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

    rows = df_clean.to_dict(orient="records")
    batches = split_batches(rows, batch_size=500)

    firestore_delete_existing_batches()

    # Guardar batches
    for i, b in enumerate(batches):
        db.collection(COLLECTION_NAME).document(f"{BATCH_PREFIX}{i}").set({
            "rows": b
        })

    # Guardar meta
    db.collection(COLLECTION_NAME).document(META_DOC_ID).set({
        "last_update": now_cdmx_str(),
        "total_rows": len(rows),
        "batch_count": len(batches),
        "schema": list(df_clean.columns)
    })

def download_clients_from_firestore() -> tuple[pd.DataFrame, str | None]:
    meta = db.collection(COLLECTION_NAME).document(META_DOC_ID).get()
    if not meta.exists:
        return pd.DataFrame(), None

    meta_dict = meta.to_dict()
    batch_count = int(meta_dict.get("batch_count", 0))
    last_update = meta_dict.get("last_update")

    all_rows = []
    for i in range(batch_count):
        doc = db.collection(COLLECTION_NAME).document(f"{BATCH_PREFIX}{i}").get()
        if doc.exists:
            all_rows.extend(doc.to_dict().get("rows", []))

    df = pd.DataFrame(all_rows)
    return df, last_update

def guess_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    # intenta encontrar columna por coincidencia aproximada
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    # match parcial
    for c in df.columns:
        cl = c.lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c
    return None

# -----------------------
# UI
# -----------------------
if "admin" not in st.session_state:
    st.session_state.admin = False

st.title("🧺 Drop24 • Admin Clientes & QR")
st.caption("Carga tu Excel (el mismo que tú actualizas), genera Client ID + QR y sincroniza a Firebase.")

top_left, top_right = st.columns([2, 1])
with top_right:
    if st.button("🔄 Refresh"):
        st.rerun()

with st.expander("🔐 Administrator Access", expanded=not st.session_state.admin):
    if not st.session_state.admin:
        pwd = st.text_input("Enter ADMIN Code", type="password")
        if pwd and pwd == ADMIN_CODE:
            st.session_state.admin = True
            st.success("Admin mode enabled ✅")
            st.rerun()
    else:
        st.success("Admin mode ON ✅")

# --- Mostrar DB actual desde Firestore ---
df_db, last_update = download_clients_from_firestore()

c1, c2, c3 = st.columns(3)
c1.metric("👥 Clientes en DB", int(df_db.shape[0]) if not df_db.empty else 0)
c2.metric("🕒 Última actualización", last_update or "—")
c3.metric("☁️ Fuente", "Firestore")

st.divider()

# -----------------------
# Cargar Excel y generar QRs
# -----------------------
if not st.session_state.admin:
    st.info("Entra como ADMIN para cargar Excel y actualizar la base.")
    if not df_db.empty:
        st.subheader("Vista de la base actual (Firestore)")
        st.dataframe(df_db, use_container_width=True, hide_index=True)
    st.stop()

st.subheader("1) Cargar tu Excel (base de datos)")

uploaded = st.file_uploader("Sube tu Excel de clientes", type=["xlsx", "xls"])
prefix = st.text_input("Prefijo del QR Payload", value="DROP24")
force_regen = st.checkbox("Regenerar Client ID / QR aunque ya existan", value=False)

if uploaded:
    df = pd.read_excel(uploaded, engine="openpyxl")
    df = clean_cols(df)
    df = ensure_columns(df)

    # Intento de detección automática de columnas "base"
    col_nombre   = guess_column(df, ["Nombre", "Name", "First Name", "firstname", "nombre"])
    col_apellido = guess_column(df, ["Apellido", "Last Name", "lastname", "apellidos", "apellido"])
    col_tel      = guess_column(df, ["Telefono", "Teléfono", "Phone", "Celular", "WhatsApp", "Movil", "Móvil"])
    col_email    = guess_column(df, ["Email", "Correo", "Mail", "E-mail"])

    st.markdown("### 2) Mapear columnas (solo si aplica)")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        col_nombre = st.selectbox("Columna Nombre", df.columns, index=(list(df.columns).index(col_nombre) if col_nombre in df.columns else 0))
    with m2:
        col_apellido = st.selectbox("Columna Apellido", df.columns, index=(list(df.columns).index(col_apellido) if col_apellido in df.columns else 0))
    with m3:
        col_tel = st.selectbox("Columna Teléfono", df.columns, index=(list(df.columns).index(col_tel) if col_tel in df.columns else 0))
    with m4:
        col_email = st.selectbox("Columna Email (opcional)", ["(no usar)"] + list(df.columns), index=(1 + list(df.columns).index(col_email) if col_email in df.columns else 0))

    # Generación
    st.subheader("3) Generar / completar Client ID + QR")
    run = st.button("⚙️ Generar IDs + QRs")

    if run:
        updated_at = now_cdmx_str()
        created = 0
        regenerated = 0

        for i in range(len(df)):
            has_id = bool(safe_str(df.at[i, "Client ID"]))
            has_token = bool(safe_str(df.at[i, "QR Token"]))
            has_payload = bool(safe_str(df.at[i, "QR Payload"]))

            if force_regen or (not has_id) or (not has_token) or (not has_payload):
                nombre = safe_str(df.at[i, col_nombre])
                apellido = safe_str(df.at[i, col_apellido])
                telefono = safe_str(df.at[i, col_tel])

                client_id = safe_str(df.at[i, "Client ID"])
                if force_regen or not client_id:
                    client_id = build_client_id(nombre, apellido, telefono, i + 1)

                token = build_token(client_id)
                payload = make_payload(prefix, client_id, token)

                df.at[i, "Client ID"] = client_id
                df.at[i, "QR Token"] = token
                df.at[i, "QR Payload"] = payload
                df.at[i, "Updated At"] = updated_at

                if has_id or has_token or has_payload:
                    regenerated += 1
                else:
                    created += 1

        st.success(f"Listo ✅ Nuevos: {created} | Actualizados/Regenerados: {regenerated}")

        # Crear ZIP de QRs
        st.subheader("4) Descargas")
        # Excel actualizado
        excel_bytes = df_to_excel_bytes(df)
        st.download_button(
            "⬇️ Descargar Excel actualizado",
            data=excel_bytes,
            file_name="Drop24_Clientes_Actualizado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # ZIP QRs
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for i in range(len(df)):
                cid = safe_str(df.at[i, "Client ID"]) or f"CLIENT_{i+1}"
                payload = safe_str(df.at[i, "QR Payload"])
                if payload:
                    png = make_qr_png_bytes(payload)
                    z.writestr(f"QR_{cid}.png", png)

        st.download_button(
            "⬇️ Descargar ZIP de QRs (PNG)",
            data=zip_buf.getvalue(),
            file_name="Drop24_QRs.zip",
            mime="application/zip"
        )

        st.divider()

        # Sync a Firestore
        st.subheader("5) Sincronizar a Firebase (Firestore)")
        if st.button("☁️ Subir base a Firestore"):
            upload_clients_to_firestore(df)
            st.success("Base subida a Firestore ✅")
            st.rerun()

        st.subheader("Vista previa")
        st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.info("Sube tu Excel para generar/actualizar IDs y QRs.")

st.divider()

# -----------------------
# Mostrar DB actual (Firestore)
# -----------------------
st.subheader("Base actual en Firestore (lectura)")
df_db2, last_update2 = download_clients_from_firestore()
if df_db2.empty:
    st.warning("Aún no hay datos guardados en Firestore para Drop24.")
else:
    st.caption(f"Last update: {last_update2}")
    st.dataframe(df_db2, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Descargar Excel (Firestore)",
        data=df_to_excel_bytes(df_db2),
        file_name="Drop24_Clientes_Firestore.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
