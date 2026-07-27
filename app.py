import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import os

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Control de Saldos - Ludo",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_google_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    archivo_json = "service_account.json"
    
    if os.path.exists(archivo_json):
        creds = ServiceAccountCredentials.from_json_keyfile_name(archivo_json, scope)
    elif len(st.secrets) > 0 and "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        raise FileNotFoundError(f"No se encontró el archivo '{archivo_json}' ni credenciales en Secrets.")
        
    client = gspread.authorize(creds)
    sheet = client.open("Ludo_Control_Saldos").sheet1
    return sheet

try:
    sheet = conectar_google_sheets()
except Exception as e:
    st.error(f"⚠️ Error de conexión con Google Sheets: {e}")
    st.info("💡 Verifica tus credenciales de conexión.")
    st.stop()

# --- FUNCIONES DE APOYO ---
def obtener_datos():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=["Fecha", "Hora", "Cliente", "Tipo", "Monto", "Detalle"])
    else:
        df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)
    return df

def guardar_movimiento(fecha, hora, cliente, tipo, monto, detalle):
    sheet.append_row([str(fecha), str(hora), cliente, tipo, float(monto), detalle])

def calcular_neto(row):
    t = row["Tipo"]
    m = row["Monto"]
    if t in ["🟢 Saldo agregado (+)", "🟡 Partida ganada (+)", "🔵 Reintegro (+)"]:
        return m
    elif t in ["🔴 Partida jugada (-)", "🟣 Retiro (-)"]:
        return -m
    return 0

# Cargar datos
df_movimientos = obtener_datos()
clientes_base = ["Dani", "Mis amores", "Wis", "Wilson"]
clientes_existentes = sorted(list(set(clientes_base + df_movimientos["Cliente"].dropna().unique().tolist())))

# --- CONTROL DE ACCESO / MENU LATERAL ---
st.sidebar.title("🎲 Control de Saldos")
modo_acceso = st.sidebar.radio(
    "Selecciona el modo de uso:",
    ["👤 Consulta Jugadores (Solo Lectura)", "🔐 Modo Administrador"]
)

st.sidebar.divider()

# ==============================================================================
# MODO 1: CONSULTA PARA JUGADORES (SOLO LECTURA)
# ==============================================================================
if modo_acceso == "👤 Consulta Jugadores (Solo Lectura)":
    st.title("📱 Consulta de Saldos - Apuestas Ludo")
    st.caption("Selecciona tu nombre para revisar tu saldo y movimientos en tiempo real.")

    if not df_movimientos.empty:
        jugador_seleccionado = st.selectbox(
            "👇 Busca y selecciona tu nombre de jugador:",
            ["-- Seleccionar Jugador --"] + clientes_existentes
        )

        if jugador_seleccionado != "-- Seleccionar Jugador --":
            df_jugador = df_movimientos[df_movimientos["Cliente"] == jugador_seleccionado].copy()

            if not df_jugador.empty:
                df_jugador["Neto"] = df_jugador.apply(calcular_neto, axis=1)
                saldo_actual = df_jugador["Neto"].sum()

                st.markdown("---")
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric(
                        label=f"Saldo Neto Actual de {jugador_seleccionado}",
                        value=f"${saldo_actual:,.2f}"
                    )
                
                st.subheader("📜 Tu Historial de Movimientos")
                df_mostrar = df_jugador[["Fecha", "Hora", "Tipo", "Monto", "Detalle"]].iloc[::-1].reset_index(drop=True)
                
                st.dataframe(
                    df_mostrar.style.format({"Monto": "${:,.2f}"}),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"Hola {jugador_seleccionado}, aún no tienes partidas ni movimientos registrados.")
        else:
            st.info("👆 Por favor selecciona tu nombre en la lista de arriba para desplegar tus datos.")
    else:
        st.info("No hay movimientos registrados en el sistema todavía.")

# ==============================================================================
# MODO 2: ADMINISTRADOR (PROTEGIDO POR CLAVE)
# ==============================================================================
else:
    st.sidebar.header("🔑 Acceso Administrador")
    
    CLAVE_ADMIN = "ludo21010227" 
    
    with st.sidebar.form(key="form_login"):
        password = st.text_input("Ingresa la clave de admin:", type="password")
        btn_login = st.form_submit_button("🔓 Entrar", use_container_width=True)

    if password == CLAVE_ADMIN:
        st.sidebar.success("✅ Acceso Concedido")
        st.sidebar.header("➕ Nuevo Movimiento")

        # 1. SELECCIÓN DE TIPO DE JUGADOR
        opcion_cliente = st.sidebar.radio(
            "Tipo de Jugador:", 
            ["Existente", "➕ Nuevo Cliente"], 
            horizontal=True
        )

        if opcion_cliente == "Existente":
            cliente_final = st.sidebar.selectbox("Seleccionar Jugador:", clientes_existentes)
        else:
            cliente_final = st.sidebar.text_input("Escribe el Nombre del Nuevo Jugador:").strip()

        # 2. RESTO DE CAMPOS DENTRO DEL FORMULARIO DE ENVÍO
        with st.sidebar.form(key="form_datos_movimiento", clear_on_submit=True):
            opciones_tipo = [
                "🟢 Saldo agregado (+)",
                "🔴 Partida jugada (-)",
                "🟡 Partida ganada (+)",
                "🔵 Reintegro (+)",
                "🟣 Retiro (-)"
            ]
            tipo_movimiento = st.selectbox("Tipo de Movimiento:", opciones_tipo)
            monto = st.number_input("Monto ($):", min_value=0.0, step=1.0, format="%.2f", value=0.0)

            # SELECTOR DE FECHA Y HORA EN FORMATO 12H (AM/PM) CON NÚMEROS MANUALES
            fecha_actual = st.date_input("Fecha:", datetime.now().date())
            
            st.write("🕒 **Hora del Movimiento:**")
            col_h1, col_h2, col_ampm = st.columns([1, 1, 1])

            hora_now = datetime.now()
            h_12_default = hora_now.hour % 12
            if h_12_default == 0:
                h_12_default = 12
            ampm_default = "PM" if hora_now.hour >= 12 else "AM"

            hora_num = col_h1.number_input("Hora (1-12):", min_value=1, max_value=12, value=h_12_default, step=1)
            min_num = col_h2.number_input("Min (0-59):", min_value=0, max_value=59, value=hora_now.minute, step=1)
            ampm = col_ampm.selectbox("Período:", ["AM", "PM"], index=0 if ampm_default == "AM" else 1)

            hora_formateada = f"{hora_num:02d}:{min_num:02d} {ampm}"

            detalle = st.text_input("Observaciones (Opcional):", placeholder="Ej: Mesa 1, Nequi...")

            boton_guardar = st.form_submit_button("💾 Guardar Transacción", use_container_width=True, type="primary")

        if boton_guardar:
            if not cliente_final:
                st.sidebar.error("❌ Debes seleccionar o escribir el nombre de un jugador.")
            elif monto <= 0:
                st.sidebar.error("❌ El monto debe ser mayor a 0.")
            else:
                with st.spinner("Guardando en Google Sheets..."):
                    guardar_movimiento(
                        fecha_actual.strftime("%Y-%m-%d"),
                        hora_formateada,
                        cliente_final,
                        tipo_movimiento,
                        monto,
                        detalle
                    )
                    st.toast("✅ ¡Movimiento registrado exitosamente!", icon="🎉")
                    st.rerun()

        # PANEL PRINCIPAL DE ADMINISTRACIÓN
        st.title("🎲 Panel de Administración")

        st.subheader("📊 Consolidado General de Saldos")
        if not df_movimientos.empty:
            df_calc = df_movimientos.copy()
            df_calc["Neto"] = df_calc.apply(calcular_neto, axis=1)

            saldos_df = df_calc.groupby("Cliente")["Neto"].sum().reset_index()
            saldos_df.rename(columns={"Neto": "Saldo Actual ($)"}, inplace=True)
            saldos_df = saldos_df.sort_values(by="Saldo Actual ($)", ascending=False)

            st.dataframe(
                saldos_df.style.format({"Saldo Actual ($)": "${:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Sin registros.")

        st.divider()

        st.subheader("📜 Historial Completo (Todas las transacciones)")
        if not df_movimientos.empty:
            st.dataframe(
                df_movimientos.iloc[::-1].reset_index(drop=True).style.format({"Monto": "${:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )

    elif password != "":
        st.sidebar.error("🔒 Contraseña incorrecta.")
    else:
        st.warning("⚠️ Ingresa la clave de administrador en la barra lateral para acceder a la gestión.")
