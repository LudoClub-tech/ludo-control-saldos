import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import os
import random
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Ludo Control Saldos - Gaming Edition",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- ESTILOS CSS PERSONALIZADOS (ESTILO GAMING / GASTOS DIARIOS) ---
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #F0F6FC;
        font-family: 'Segoe UI', Roboto, sans-serif;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .gaming-card {
        background: linear-gradient(135deg, #161B22 0%, #21262D 100%);
        border: 1px solid #30363D;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        text-align: center;
        margin-bottom: 15px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .gaming-card:hover {
        border-color: #58A6FF;
        transform: translateY(-2px);
    }
    
    .saldo-card {
        background: linear-gradient(135deg, #1F293D 0%, #111827 100%);
        border: 2px solid #38BDF8;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.2);
    }
    .saldo-title {
        color: #94A3B8;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 700;
        margin-bottom: 5px;
    }
    .saldo-amount {
        color: #38BDF8;
        font-size: 38px;
        font-weight: 900;
        text-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
    }
    
    .stButton>button {
        width: 100%;
        border-radius: 14px !important;
        height: 3.2em !important;
        font-size: 18px !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px;
        transition: all 0.2s ease-in-out !important;
        border: none !important;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #161B22;
        padding: 8px;
        border-radius: 14px;
        border: 1px solid #30363D;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        border-radius: 10px;
        color: #8B949E;
        font-weight: 700;
        font-size: 15px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #238636 !important;
        color: #FFFFFF !important;
    }
    
    div[data-baseweb="select"] > div, input {
        background-color: #161B22 !important;
        border-radius: 10px !important;
        border-color: #30363D !important;
        color: #FFFFFF !important;
    }
</style>
""", unsafe_allow_html=True)

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
    st.stop()

# --- FUNCIONES DE APOYO ---
def obtener_datos():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=["Fecha", "Hora", "Cliente", "Tipo", "Monto", "Detalle"])
    else:
        df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)
        df["Fecha"] = df["Fecha"].astype(str)
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

# --- INICIALIZACIÓN DE ESTADO DE SESIÓN (SESSION STATE) ---
if "ganador_ruleta_hoy" not in st.session_state:
    st.session_state["ganador_ruleta_hoy"] = None
# 🛡️ CLAVE DE SEGURIDAD: Bloqueo de envío doble
if "bloqueo_envio_admin" not in st.session_state:
    st.session_state["bloqueo_envio_admin"] = False

# Cargar datos
df_movimientos = obtener_datos()
clientes_base = ["Dani", "Mis amores", "Wis", "Wilson"]
clientes_existentes = sorted(list(set(clientes_base + df_movimientos["Cliente"].dropna().unique().tolist())))
fecha_hoy_str = datetime.now().strftime("%Y-%m-%d")

# --- ENCABEZADO GAMING ---
st.markdown("""
    <div style='text-align: center; padding: 10px 0 20px 0;'>
        <h1 style='font-size: 36px; font-weight: 900; color: #58A6FF; margin: 0;'>🎲 LUDO CONTROL</h1>
        <p style='color: #8B949E; font-weight: 600; font-size: 14px;'>SISTEMA DE SALDOS & RANKING DE JUGADORES</p>
    </div>
""", unsafe_allow_html=True)

# --- NAVEGACIÓN PRINCIPAL ---
modo_acceso = st.radio(
    "",
    ["👤 MODO JUGADOR", "🔐 MODO ADMINISTRADOR"],
    horizontal=True,
    label_visibility="collapsed"
)

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# MODO 1: CONSULTA PARA JUGADORES (GAMING UI)
# ==============================================================================
if modo_acceso == "👤 MODO JUGADOR":
    # (El Modo Jugador permanece igual, no necesita bloqueo de envío)
    
    tab_saldo, tab_ranking, tab_ruleta = st.tabs([
        "💰 MI SALDO", 
        "🏆 RANKING Y DESAFÍO", 
        "🎡 RULETA DIARIA"
    ])

    # --- TAB 1: SALDO DE JUGADOR ---
    with tab_saldo:
        if not df_movimientos.empty:
            jugador_seleccionado = st.selectbox(
                "👇 SELECCIONA TU NOMBRE DE JUGADOR:",
                ["-- Seleccionar Jugador --"] + clientes_existentes
            )

            if jugador_seleccionado != "-- Seleccionar Jugador --":
                df_jugador = df_movimientos[df_movimientos["Cliente"] == jugador_seleccionado].copy()

                if not df_jugador.empty:
                    df_jugador["Neto"] = df_jugador.apply(calcular_neto, axis=1)
                    saldo_actual = df_jugador["Neto"].sum()

                    partidas_jugadas_hoy = len(df_jugador[(df_jugador["Fecha"] == fecha_hoy_str) & (df_jugador["Tipo"] == "🔴 Partida jugada (-)")])
                    partidas_ganadas_hoy = len(df_jugador[(df_jugador["Fecha"] == fecha_hoy_str) & (df_jugador["Tipo"] == "🟡 Partida ganada (+)")])

                    st.markdown(f"""
                        <div class="gaming-card saldo-card">
                            <div class="saldo-title">SALDO NETO DISPONIBLE</div>
                            <div class="saldo-amount">${saldo_actual:,.2f}</div>
                            <div style="color: #94A3B8; font-size: 13px; margin-top: 5px;">Jugador: <b>{jugador_seleccionado}</b></div>
                        </div>
                    """, unsafe_allow_html=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"""
                            <div class="gaming-card">
                                <div style="font-size: 24px;">🎮 {partidas_jugadas_hoy} / 3</div>
                                <div style="color: #8B949E; font-size: 12px; font-weight: 700;">JUGADAS HOY</div>
                            </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"""
                            <div class="gaming-card">
                                <div style="font-size: 24px;">🏆 {partidas_ganadas_hoy}</div>
                                <div style="color: #8B949E; font-size: 12px; font-weight: 700;">VICTORIAS HOY</div>
                            </div>
                        """, unsafe_allow_html=True)

                    if partidas_jugadas_hoy >= 3:
                        st.success("🎉 ¡DESAFÍO COMPLETADO! Estás dentro del sorteo de la ruleta hoy.")
                    else:
                        st.info(f"🎯 Juega {3 - partidas_jugadas_hoy} partida(s) más hoy para entrar a la ruleta.")

                    st.markdown("### 📜 HISTORIAL RECIENTE")
                    df_mostrar = df_jugador[["Fecha", "Hora", "Tipo", "Monto", "Detalle"]].iloc[::-1].reset_index(drop=True)
                    st.dataframe(
                        df_mostrar.style.format({"Monto": "${:,.2f}"}),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info(f"Hola {jugador_seleccionado}, aún no registras movimientos.")
        else:
            st.info("Sin registros en la base de datos.")

    # --- TAB 2: RANKING ---
    with tab_ranking:
        st.markdown("### 🥇 PODIO DE CAMPEONES")
        filtro_rango = st.radio("Período:", ["Hoy", "Histórico General"], horizontal=True)

        if not df_movimientos.empty:
            if filtro_rango == "Hoy":
                df_ganadores = df_movimientos[(df_movimientos["Fecha"] == fecha_hoy_str) & (df_movimientos["Tipo"] == "🟡 Partida ganada (+)")]
            else:
                df_ganadores = df_movimientos[df_movimientos["Tipo"] == "🟡 Partida ganada (+)"]

            if not df_ganadores.empty:
                ranking_df = df_ganadores.groupby("Cliente").size().reset_index(name="Victorias")
                ranking_df = ranking_df.sort_values(by="Victorias", ascending=False).reset_index(drop=True)

                col_p1, col_p2, col_p3 = st.columns(3)
                
                if len(ranking_df) >= 1:
                    col_p1.markdown(f"""
                        <div class="gaming-card" style="border-color: #FFD700;">
                            <div style="font-size: 30px;">🥇</div>
                            <div style="font-weight: 800; font-size: 18px; color: #FFD700;">{ranking_df.iloc[0]['Cliente']}</div>
                            <div style="color: #8B949E; font-size: 13px;">{ranking_df.iloc[0]['Victorias']} Victorias</div>
                        </div>
                    """, unsafe_allow_html=True)
                if len(ranking_df) >= 2:
                    col_p2.markdown(f"""
                        <div class="gaming-card" style="border-color: #C0C0C0;">
                            <div style="font-size: 30px;">🥈</div>
                            <div style="font-weight: 800; font-size: 18px; color: #C0C0C0;">{ranking_df.iloc[1]['Cliente']}</div>
                            <div style="color: #8B949E; font-size: 13px;">{ranking_df.iloc[1]['Victorias']} Victorias</div>
                        </div>
                    """, unsafe_allow_html=True)
                if len(ranking_df) >= 3:
                    col_p3.markdown(f"""
                        <div class="gaming-card" style="border-color: #CD7F32;">
                            <div style="font-size: 30px;">🥉</div>
                            <div style="font-weight: 800; font-size: 18px; color: #CD7F32;">{ranking_df.iloc[2]['Cliente']}</div>
                            <div style="color: #8B949E; font-size: 13px;">{ranking_df.iloc[2]['Victorias']} Victorias</div>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("### 📊 TABLA GENERAL DE LÍDERES")
                ranking_df.index += 1
                st.dataframe(ranking_df, use_container_width=True)
            else:
                st.info("Sin partidas ganadas en este lapso de tiempo.")

    # --- TAB 3: RULETA DIARIA (VISTA JUGADOR) ---
    with tab_ruleta:
        st.markdown("### 🎡 SORTEO DE RULETA DIARIA")
        st.caption("Entran automáticamente los jugadores que hayan alcanzado 3 o más partidas hoy.")

        if not df_movimientos.empty:
            df_jugadas_hoy = df_movimientos[(df_movimientos["Fecha"] == fecha_hoy_str) & (df_movimientos["Tipo"] == "🔴 Partida jugada (-)")]
            conteo = df_jugadas_hoy.groupby("Cliente").size().reset_index(name="Cant")
            calificados_list = conteo[conteo["Cant"] >= 3]["Cliente"].tolist()

            if len(calificados_list) > 0:
                st.write(f"👥 **Jugadores Calificados Hoy ({len(calificados_list)}):**")
                cols_cal = st.columns(len(calificados_list))
                for idx, nom in enumerate(calificados_list):
                    cols_cal[idx].markdown(f"<div class='gaming-card' style='padding: 10px; font-weight: bold; color: #238636;'>✅ {nom}</div>", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                if st.session_state["ganador_ruleta_hoy"]:
                    st.markdown(f"""
                        <div class="gaming-card" style="border-color: #238636; background: linear-gradient(135deg, #1C4429 0%, #111827 100%); padding: 35px;">
                            <div style="font-size: 16px; color: #3FB950; font-weight: 800;">🎉 ¡GANADOR OFICIAL DEL SORTEO DE HOY! 🎉</div>
                            <div style="font-size: 42px; font-weight: 900; color: #FFFFFF; text-shadow: 0 0 10px #3FB950;">👑 {st.session_state['ganador_ruleta_hoy']} 👑</div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("⏳ La ruleta aún no ha sido girada el día de hoy. El administrador la girará al final de la jornada.")
            else:
                st.warning("⚠️ Aún no hay jugadores calificados con 3 partidas hoy.")

# ==============================================================================
# MODO 2: ADMINISTRADOR (🔑 CON AUTOLIMPIEZA Y SELECTOR INTERACTIVO)
# ==============================================================================
else:
    st.markdown("### 🔑 ACCESO ADMINISTRADOR")
    CLAVE_ADMIN = "ludo21010227" 
    
    password = st.text_input("Ingresa la contraseña de gestión:", type="password")

    if password == CLAVE_ADMIN:
        st.success("✅ Modo Administrador Activo")
        
        # Inicializar clave del monto en session_state para poder limpiarlo dinámicamente
        if "monto_input" not in st.session_state:
            st.session_state["monto_input"] = 0.0
        if "detalle_input" not in st.session_state:
            st.session_state["detalle_input"] = ""

        # --- SECCIÓN EXCLUSIVA DE GESTIÓN DE RULETA ---
        with st.expander("🎡 CONTROL DE RULETA DIARIA (EXCLUSIVO ADMIN)", expanded=True):
            if not df_movimientos.empty:
                df_jugadas_hoy = df_movimientos[(df_movimientos["Fecha"] == fecha_hoy_str) & (df_movimientos["Tipo"] == "🔴 Partida jugada (-)")]
                conteo = df_jugadas_hoy.groupby("Cliente").size().reset_index(name="Cant")
                calificados_list = conteo[conteo["Cant"] >= 3]["Cliente"].tolist()

                if len(calificados_list) > 0:
                    st.write(f"👥 **Participantes Calificados para Girar:** {', '.join(calificados_list)}")
                    
                    if st.button("🎡 ¡GIRAR RULETA AHORA!", type="primary"):
                        placeholder = st.empty()
                        for i in range(25):
                            seleccionado_temp = random.choice(calificados_list)
                            placeholder.markdown(f"""
                                <div class="gaming-card" style="border-color: #A371F7; padding: 30px;">
                                    <div style="font-size: 14px; color: #A371F7; font-weight: 800;">GIRANDO RULETA EN VIVO...</div>
                                    <div style="font-size: 38px; font-weight: 900; color: #FFFFFF;">🔄 {seleccionado_temp} 🔄</div>
                                </div>
                            """, unsafe_allow_html=True)
                            time.sleep(0.08 + (i * 0.01))
                        
                        ganador_final = random.choice(calificados_list)
                        st.session_state["ganador_ruleta_hoy"] = ganador_final
                        
                        placeholder.markdown(f"""
                            <div class="gaming-card" style="border-color: #238636; background: linear-gradient(135deg, #1C4429 0%, #111827 100%); padding: 35px;">
                                <div style="font-size: 16px; color: #3FB950; font-weight: 800;">🎉 ¡GANADOR DEL PREMIO EXTRA! 🎉</div>
                                <div style="font-size: 42px; font-weight: 900; color: #FFFFFF; text-shadow: 0 0 10px #3FB950;">👑 {ganador_final} 👑</div>
                            </div>
                        """, unsafe_allow_html=True)
                        st.balloons()
                else:
                    st.info("⚠️ Aún no hay jugadores calificados para girar la ruleta hoy.")
        
        # --- REGISTRO DE MOVIMIENTOS ---
        with st.expander("➕ REGISTRAR NUEVO MOVIMIENTO", expanded=True):
            
            # 1. Selector interactivo fuera de st.form para alternar entre Existente y Nuevo en tiempo real
            opcion_cliente = st.radio("Cliente:", ["Existente", "➕ Nuevo"], horizontal=True)

            if opcion_cliente == "Existente":
                cliente_final = st.selectbox("Seleccionar Jugador:", clientes_existentes)
            else:
                cliente_final = st.text_input("Nombre del Nuevo Jugador:").strip()

            opciones_tipo = [
                "🟢 Saldo agregado (+)",
                "🔴 Partida jugada (-)",
                "🟡 Partida ganada (+)",
                "🔵 Reintegro (+)",
                "🟣 Retiro (-)"
            ]
            tipo_movimiento = st.selectbox("Tipo de Movimiento:", opciones_tipo)
            
            # Campo de monto vinculado a session_state
            monto = st.number_input("Monto ($):", min_value=0.0, step=1.0, format="%.2f", key="monto_input")

            fecha_actual = st.date_input("Fecha:", datetime.now().date())
            
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
            detalle = st.text_input("Observaciones:", placeholder="Mesa 1, Nequi, etc.", key="detalle_input")

            submit_registro = st.button("💾 GUARDAR TRANSACCIÓN", type="primary")

            # Lógica que se ejecuta al presionar Guardar
            if submit_registro:
                # 🛑 VALIDACIÓN 1: El usuario no escribió ningún cliente
                if not cliente_final:
                    st.error("❌ Debes indicar el nombre del jugador.")
                
                # 🛑 VALIDACIÓN 2: El monto es 0 o no ingresó nada
                elif monto <= 0:
                    st.warning("⚠️ Debes indicar un monto mayor a $0 para poder guardar la transacción.")
                
                # ✅ SI TODO ESTÁ BIEN: Registra y restablece el monto a 0.0
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
                        st.toast(f"✅ Transacción de ${monto:,.2f} guardada con éxito a {cliente_final}", icon="🎉")
                        
                        # Restablecer el monto y observaciones en el estado
                        st.session_state["monto_input"] = 0.0
                        st.session_state["detalle_input"] = ""
                        time.sleep(0.8)
                    
                    st.rerun()

        st.markdown("### 📊 CONSOLIDADO GENERAL DE SALDOS")
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

        st.markdown("### 📜 HISTORIAL COMPLETO DE REGISTROS")
        if not df_movimientos.empty:
            st.dataframe(
                df_movimientos.iloc[::-1].reset_index(drop=True).style.format({"Monto": "${:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
    elif password != "":
        st.error("🔒 Contraseña incorrecta.")
