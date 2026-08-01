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
    page_title="Ludo Control Saldos",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- ESTILOS CSS PERSONALIZADOS ---
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

def verificar_y_crear_columnas():
    """Verifica que todas las columnas existan y las crea si faltan"""
    try:
        headers = sheet.row_values(1)
        
        columnas_esperadas = ["Fecha", "Hora", "Cliente", "Tipo", "Monto", "Detalle", "Saldo_Anterior", "Saldo_Nuevo"]
        
        columnas_faltantes = []
        for col in columnas_esperadas:
            if col not in headers:
                columnas_faltantes.append(col)
        
        if columnas_faltantes:
            for col in columnas_faltantes:
                ultima_columna = len(headers) + 1
                sheet.add_cols(1)
                sheet.update_cell(1, ultima_columna, col)
                headers.append(col)
            
            st.success(f"✅ Columnas agregadas: {', '.join(columnas_faltantes)}")
            st.info("🔄 La página se recargará para aplicar los cambios...")
            time.sleep(2)
            st.rerun()
        
        return True
    except Exception as e:
        st.error(f"⚠️ Error al verificar columnas: {e}")
        return False

try:
    sheet = conectar_google_sheets()
    verificar_y_crear_columnas()
except Exception as e:
    st.error(f"⚠️ Error de conexión con Google Sheets: {e}")
    st.stop()

# --- FUNCIONES DE APOYO ---
def obtener_datos():
    """Obtiene todos los datos de Google Sheets"""
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    if df.empty:
        df = pd.DataFrame(columns=["Fecha", "Hora", "Cliente", "Tipo", "Monto", "Detalle", "Saldo_Anterior", "Saldo_Nuevo"])
    else:
        for col in ["Monto", "Saldo_Anterior", "Saldo_Nuevo"]:
            if col not in df.columns:
                df[col] = 0.0
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        df["Fecha"] = df["Fecha"].astype(str)
    
    return df

def guardar_movimiento(fecha, hora, cliente, tipo, monto, detalle):
    """Guarda un movimiento con saldo anterior y nuevo"""
    df = obtener_datos()
    
    df_cliente = df[df["Cliente"] == cliente].copy()
    
    saldo_anterior = 0.0
    if not df_cliente.empty:
        for _, row in df_cliente.iterrows():
            saldo_anterior += calcular_neto(row)
    
    neto = 0
    if tipo in ["🟢 Saldo agregado (+)", "🟡 Partida ganada (+)", "🔵 Reintegro (+)"]:
        neto = monto
    elif tipo in ["🔴 Partida jugada (-)", "🟣 Retiro (-)"]:
        neto = -monto
    
    saldo_nuevo = saldo_anterior + neto
    
    sheet.append_row([
        str(fecha), 
        str(hora), 
        cliente, 
        tipo, 
        float(monto), 
        detalle,
        float(saldo_anterior),
        float(saldo_nuevo)
    ])

def actualizar_movimiento(fila_sheets, fecha, hora, cliente, tipo, monto, detalle):
    """Actualiza un movimiento recalculando saldos anteriores y nuevos"""
    df = obtener_datos()
    idx_real = fila_sheets - 2
    
    df_cliente = df[df["Cliente"] == cliente].copy()
    
    saldo_anterior = 0.0
    for i, row in df_cliente.iterrows():
        if i < idx_real:
            saldo_anterior += calcular_neto(row)
    
    neto = 0
    if tipo in ["🟢 Saldo agregado (+)", "🟡 Partida ganada (+)", "🔵 Reintegro (+)"]:
        neto = monto
    elif tipo in ["🔴 Partida jugada (-)", "🟣 Retiro (-)"]:
        neto = -monto
    
    saldo_nuevo = saldo_anterior + neto
    
    rango = f"A{fila_sheets}:H{fila_sheets}"
    valores = [[
        str(fecha), 
        str(hora), 
        cliente, 
        tipo, 
        float(monto), 
        detalle,
        float(saldo_anterior),
        float(saldo_nuevo)
    ]]
    sheet.update(rango, valores)

def calcular_neto(row):
    t = row["Tipo"]
    m = row["Monto"]
    if t in ["🟢 Saldo agregado (+)", "🟡 Partida ganada (+)", "🔵 Reintegro (+)"]:
        return m
    elif t in ["🔴 Partida jugada (-)", "🟣 Retiro (-)"]:
        return -m
    return 0

# --- INICIALIZACIÓN DE ESTADO DE SESIÓN ---
if "ganador_ruleta_hoy" not in st.session_state:
    st.session_state["ganador_ruleta_hoy"] = None
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
# MODO 1: CONSULTA PARA JUGADORES
# ==============================================================================
if modo_acceso == "👤 MODO JUGADOR":
    
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
                    
                    saldo_anterior = saldo_actual
                    if not df_jugador.empty:
                        ultimo_neto = calcular_neto(df_jugador.iloc[-1])
                        saldo_anterior = saldo_actual - ultimo_neto

                    partidas_jugadas_hoy = len(df_jugador[(df_jugador["Fecha"] == fecha_hoy_str) & (df_jugador["Tipo"] == "🔴 Partida jugada (-)")])
                    partidas_ganadas_hoy = len(df_jugador[(df_jugador["Fecha"] == fecha_hoy_str) & (df_jugador["Tipo"] == "🟡 Partida ganada (+)")])

                    st.markdown(f"""
                        <div class="gaming-card saldo-card">
                            <div class="saldo-title">SALDO NETO DISPONIBLE</div>
                            <div class="saldo-amount">${saldo_actual:,.2f}</div>
                            <div style="color: #94A3B8; font-size: 13px; margin-top: 5px;">Jugador: <b>{jugador_seleccionado}</b></div>
                            <div style="color: #8B949E; font-size: 12px; margin-top: 5px;">
                                📊 Saldo anterior: <b>${saldo_anterior:,.2f}</b> | Último movimiento: <b>${df_jugador.iloc[-1]['Monto']:,.2f}</b>
                            </div>
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
                    df_mostrar = df_jugador[["Fecha", "Hora", "Tipo", "Monto", "Detalle", "Saldo_Anterior", "Saldo_Nuevo"]].iloc[::-1].reset_index(drop=True)
                    
                    df_mostrar_formateado = df_mostrar.copy()
                    for col in ["Monto", "Saldo_Anterior", "Saldo_Nuevo"]:
                        if col in df_mostrar_formateado.columns:
                            df_mostrar_formateado[col] = df_mostrar_formateado[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
                    
                    st.dataframe(
                        df_mostrar_formateado,
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info(f"Hola {jugador_seleccionado}, aún no registras movimientos.")
        else:
            st.info("Sin registros en la base de datos.")

    # --- TAB 2: RANKING ---
    with tab_ranking:
        st.markdown("### 🏆 RANKING DE JUGADORES")
        st.caption("📊 Las victorias se suman automáticamente al registrar '🟡 Partida ganada (+)'")
        
        filtro_rango = st.radio(
            "📅 Período:", 
            ["🏆 Ranking del Día", "👑 Ranking General"], 
            horizontal=True,
            index=0
        )

        if not df_movimientos.empty:
            if filtro_rango == "🏆 Ranking del Día":
                df_victorias = df_movimientos[
                    (df_movimientos["Fecha"] == fecha_hoy_str) & 
                    (df_movimientos["Tipo"] == "🟡 Partida ganada (+)")
                ]
                titulo = f"🏆 VICTORIAS DE HOY ({fecha_hoy_str})"
            else:
                df_victorias = df_movimientos[df_movimientos["Tipo"] == "🟡 Partida ganada (+)"]
                titulo = "👑 RANKING GENERAL HISTÓRICO"

            if not df_victorias.empty:
                ranking_df = df_victorias.groupby("Cliente").size().reset_index(name="Victorias")
                ranking_df = ranking_df.sort_values(by="Victorias", ascending=False).reset_index(drop=True)
                
                st.markdown(f"### {titulo}")
                st.write(f"Total de partidas ganadas registradas: {len(df_victorias)}")
                
                st.markdown("### 🥇 PODIO DE CAMPEONES")
                
                col_p1, col_p2, col_p3 = st.columns(3)
                
                if len(ranking_df) >= 1:
                    with col_p1:
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #FFD700; border-width: 3px;">
                                <div style="font-size: 40px;">🥇</div>
                                <div style="font-weight: 900; font-size: 20px; color: #FFD700;">{ranking_df.iloc[0]['Cliente']}</div>
                                <div style="color: #FFD700; font-size: 24px; font-weight: 800;">{ranking_df.iloc[0]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                if len(ranking_df) >= 2:
                    with col_p2:
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #C0C0C0; border-width: 3px;">
                                <div style="font-size: 40px;">🥈</div>
                                <div style="font-weight: 900; font-size: 20px; color: #C0C0C0;">{ranking_df.iloc[1]['Cliente']}</div>
                                <div style="color: #C0C0C0; font-size: 24px; font-weight: 800;">{ranking_df.iloc[1]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                if len(ranking_df) >= 3:
                    with col_p3:
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #CD7F32; border-width: 3px;">
                                <div style="font-size: 40px;">🥉</div>
                                <div style="font-weight: 900; font-size: 20px; color: #CD7F32;">{ranking_df.iloc[2]['Cliente']}</div>
                                <div style="color: #CD7F32; font-size: 24px; font-weight: 800;">{ranking_df.iloc[2]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                            </div>
                        """, unsafe_allow_html=True)

                st.markdown("### 📊 TABLA DE POSICIONES")
                
                ranking_df.insert(0, "Posición", range(1, len(ranking_df) + 1))
                
                def color_posicion(val):
                    if val == 1:
                        return 'background-color: #FFD700; color: #000000; font-weight: bold;'
                    elif val == 2:
                        return 'background-color: #C0C0C0; color: #000000; font-weight: bold;'
                    elif val == 3:
                        return 'background-color: #CD7F32; color: #000000; font-weight: bold;'
                    return ''
                
                st.dataframe(
                    ranking_df.style
                    .format({"Victorias": "{:,.0f}"})
                    .map(color_posicion, subset=['Posición']),
                    use_container_width=True,
                    hide_index=True
                )
                
                with st.expander("📊 ESTADÍSTICAS ADICIONALES", expanded=False):
                    col_est1, col_est2, col_est3, col_est4 = st.columns(4)
                    
                    with col_est1:
                        st.metric("Total Jugadores", len(ranking_df))
                    
                    with col_est2:
                        total_victorias = ranking_df["Victorias"].sum()
                        st.metric("Total Victorias", total_victorias)
                    
                    with col_est3:
                        promedio = round(total_victorias / len(ranking_df) if len(ranking_df) > 0 else 0, 1)
                        st.metric("Promedio/Jugador", promedio)
                    
                    with col_est4:
                        max_victorias = ranking_df["Victorias"].max() if not ranking_df.empty else 0
                        st.metric("Máximo Victorias", max_victorias)
                    
                    todos_jugadores = set(clientes_existentes)
                    jugadores_con_victorias = set(ranking_df["Cliente"].tolist())
                    jugadores_sin_victorias = todos_jugadores - jugadores_con_victorias
                    
                    if jugadores_sin_victorias:
                        st.warning(f"⚠️ Jugadores sin victorias: {', '.join(jugadores_sin_victorias)}")
                
            else:
                st.info("📭 No hay victorias registradas en este período.")
                
                if filtro_rango == "🏆 Ranking del Día":
                    st.info("💡 Registra partidas ganadas con el tipo: '🟡 Partida ganada (+)' para que aparezcan aquí.")
                else:
                    st.info("💡 Aún no hay victorias en el historial general.")
        else:
            st.info("📭 Sin registros en la base de datos.")

    # --- TAB 3: RULETA DIARIA (VISTA JUGADOR) ---
    with tab_ruleta:
        st.markdown("### 🎡 SORTEO DE RULETA DIARIA")
        st.caption("🎯 Los jugadores con 3 o más partidas jugadas hoy participan automáticamente")
        
        hora_actual = datetime.now().strftime("%I:%M %p")
        st.info(f"🕐 Hora actual: {hora_actual} | Fecha: {fecha_hoy_str}")

        if not df_movimientos.empty:
            df_jugadas_hoy = df_movimientos[
                (df_movimientos["Fecha"] == fecha_hoy_str) & 
                (df_movimientos["Tipo"] == "🔴 Partida jugada (-)")
            ]
            
            conteo = df_jugadas_hoy.groupby("Cliente").size().reset_index(name="Cant")
            calificados_list = conteo[conteo["Cant"] >= 3]["Cliente"].tolist()

            if len(calificados_list) > 0:
                st.write(f"👥 **Jugadores Calificados Hoy ({len(calificados_list)}):**")
                
                cols_cal = st.columns(min(len(calificados_list), 6))
                for idx, nom in enumerate(calificados_list[:6]):
                    partidas = conteo[conteo['Cliente'] == nom]['Cant'].values[0]
                    cols_cal[idx].markdown(f"""
                        <div class='gaming-card' style='padding: 10px; border-color: #238636;'>
                            <div style='font-size: 24px;'>✅</div>
                            <div style='font-weight: bold; color: #238636;'>{nom}</div>
                            <div style='color: #8B949E; font-size: 11px;'>{partidas} partidas</div>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                if st.session_state["ganador_ruleta_hoy"]:
                    st.markdown(f"""
                        <div class="gaming-card" style="border-color: #FFD700; background: linear-gradient(135deg, #1C4429 0%, #111827 100%); padding: 35px; border-width: 3px;">
                            <div style="font-size: 16px; color: #FFD700; font-weight: 800;">🎉 ¡GANADOR OFICIAL DEL SORTEO DE HOY! 🎉</div>
                            <div style="font-size: 42px; font-weight: 900; color: #FFFFFF; text-shadow: 0 0 20px #FFD700;">👑 {st.session_state['ganador_ruleta_hoy']} 👑</div>
                            <div style="color: #3FB950; font-size: 14px; margin-top: 10px;">🏆 Premio: 3 partidas gratis</div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("⏳ La ruleta aún no ha sido girada el día de hoy. El administrador la girará al final de la jornada.")
                    
                    st.markdown("### 📊 Tu progreso")
                    for jugador in clientes_existentes:
                        if jugador in conteo['Cliente'].values:
                            partidas = conteo[conteo['Cliente'] == jugador]['Cant'].values[0]
                            if partidas < 3:
                                faltan = 3 - partidas
                                st.progress(partidas/3, text=f"{jugador}: {partidas}/3 partidas - Faltan {faltan} para calificar")
                            else:
                                st.success(f"✅ {jugador}: ¡Ya calificado con {partidas} partidas!")
                        else:
                            st.info(f"📌 {jugador}: 0/3 partidas - Registra tus partidas para participar")
            else:
                st.warning("⚠️ Aún no hay jugadores calificados con 3 partidas hoy.")
                
                if not df_jugadas_hoy.empty:
                    st.markdown("### 📊 Progreso de jugadores hoy:")
                    for _, row in conteo.iterrows():
                        partidas = row["Cant"]
                        if partidas < 3:
                            faltan = 3 - partidas
                            st.progress(partidas/3, text=f"{row['Cliente']}: {partidas}/3 partidas - Faltan {faltan}")
                        else:
                            st.success(f"✅ {row['Cliente']}: {partidas}/3 partidas - ¡CALIFICADO!")
                else:
                    st.info("💡 Registra tus primeras partidas para participar en la ruleta.")
        else:
            st.info("Sin registros en la base de datos.")

# ==============================================================================
# MODO 2: ADMINISTRADOR
# ==============================================================================
else:
    st.markdown("### 🔑 ACCESO ADMINISTRADOR")
    CLAVE_ADMIN = "ludo21010227" 
    
    password = st.text_input("Ingresa la contraseña de gestión:", type="password")

    if password == CLAVE_ADMIN:
        st.success("✅ Modo Administrador Activo")

        # --- SECCIÓN EXCLUSIVA DE GESTIÓN DE RULETA ---
        with st.expander("🎡 CONTROL DE RULETA DIARIA (EXCLUSIVO ADMIN)", expanded=True):
            
            hora_actual = datetime.now().strftime("%I:%M %p")
            st.info(f"🕐 Hora actual: {hora_actual} | Fecha: {fecha_hoy_str}")
            
            df_jugadas_hoy = df_movimientos[
                (df_movimientos["Fecha"] == fecha_hoy_str) & 
                (df_movimientos["Tipo"] == "🔴 Partida jugada (-)")
            ]
            
            conteo = df_jugadas_hoy.groupby("Cliente").size().reset_index(name="Cant")
            
            if not df_jugadas_hoy.empty:
                st.write(f"📊 **Total de partidas jugadas hoy:** {len(df_jugadas_hoy)}")
                
                st.write("📋 **Progreso de jugadores:**")
                for _, row in conteo.iterrows():
                    partidas = row["Cant"]
                    progreso = min(partidas, 3)
                    barra = "🟩" * progreso + "⬜" * (3 - progreso)
                    if partidas >= 3:
                        st.success(f"✅ {row['Cliente']}: {barra} {partidas}/3 - ¡CALIFICADO! 🎯")
                    else:
                        st.info(f"📌 {row['Cliente']}: {barra} {partidas}/3")
            else:
                st.warning("⚠️ Aún no hay partidas registradas hoy con '🔴 Partida jugada (-)'")
                st.info("💡 Registra partidas con el tipo: 🔴 Partida jugada (-)")
            
            calificados_list = conteo[conteo["Cant"] >= 3]["Cliente"].tolist()
            
            st.markdown("---")
            
            if len(calificados_list) > 0:
                st.success(f"🎯 **Participantes Calificados para la Ruleta ({len(calificados_list)}):**")
                
                cols = st.columns(min(len(calificados_list), 4))
                for idx, jugador in enumerate(calificados_list[:4]):
                    cols[idx].markdown(f"""
                        <div class="gaming-card" style="padding: 10px; border-color: #FFD700;">
                            <div style="font-size: 24px;">🎯</div>
                            <div style="font-weight: 800; color: #FFD700;">{jugador}</div>
                            <div style="color: #8B949E; font-size: 12px;">{conteo[conteo['Cliente'] == jugador]['Cant'].values[0]} partidas</div>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.session_state["ganador_ruleta_hoy"]:
                    st.markdown(f"""
                        <div class="gaming-card" style="border-color: #238636; background: linear-gradient(135deg, #1C4429 0%, #111827 100%); padding: 35px;">
                            <div style="font-size: 16px; color: #3FB950; font-weight: 800;">🎉 ¡RULETA DE HOY YA FUE GIRADA! 🎉</div>
                            <div style="font-size: 42px; font-weight: 900; color: #FFFFFF; text-shadow: 0 0 10px #3FB950;">👑 {st.session_state['ganador_ruleta_hoy']} 👑</div>
                            <div style="color: #8B949E; margin-top: 10px;">El ganador ya fue seleccionado para hoy</div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    if st.button("🎡 ¡GIRAR RULETA AHORA!", type="primary", use_container_width=True):
                        placeholder = st.empty()
                        
                        for i in range(30):
                            seleccionado_temp = random.choice(calificados_list)
                            placeholder.markdown(f"""
                                <div class="gaming-card" style="border-color: #A371F7; padding: 30px;">
                                    <div style="font-size: 14px; color: #A371F7; font-weight: 800;">🔄 GIRANDO RULETA EN VIVO...</div>
                                    <div style="font-size: 42px; font-weight: 900; color: #FFFFFF; transition: all 0.1s ease;">
                                        {seleccionado_temp}
                                    </div>
                                    <div style="color: #8B949E; font-size: 12px; margin-top: 10px;">
                                        Participante {i+1}/30
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                            time.sleep(0.06 + (i * 0.008))
                        
                        ganador_final = random.choice(calificados_list)
                        st.session_state["ganador_ruleta_hoy"] = ganador_final
                        
                        placeholder.markdown(f"""
                            <div class="gaming-card" style="border-color: #FFD700; background: linear-gradient(135deg, #1C4429 0%, #111827 100%); padding: 35px; border-width: 3px;">
                                <div style="font-size: 18px; color: #FFD700; font-weight: 800;">🎉 ¡GANADOR DEL PREMIO EXTRA! 🎉</div>
                                <div style="font-size: 52px; font-weight: 900; color: #FFFFFF; text-shadow: 0 0 30px #FFD700;">👑 {ganador_final} 👑</div>
                                <div style="color: #3FB950; font-size: 16px; margin-top: 10px;">🏆 Premio: 3 partidas gratis</div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        st.balloons()
                        st.success(f"✅ ¡{ganador_final} ha ganado la ruleta de hoy!")
                        
                        time.sleep(3)
                        st.rerun()
            else:
                st.warning("⚠️ Aún no hay jugadores con 3 partidas hoy.")
                st.info("📌 Los jugadores aparecerán aquí cuando completen 3 partidas jugadas.")
                # --- REGISTRO DE MOVIMIENTOS ---
        with st.expander("➕ REGISTRAR NUEVO MOVIMIENTO", expanded=True):
            
            if "mostrar_nuevo_jugador" not in st.session_state:
                st.session_state["mostrar_nuevo_jugador"] = False
            
            with st.form(key="registro_movimiento_form"):
                
                st.markdown("### 📝 DATOS DE LA TRANSACCIÓN")
                
                mostrar_nuevo = st.checkbox(
                    "➕ Agregar nuevo jugador", 
                    value=st.session_state["mostrar_nuevo_jugador"],
                    key="checkbox_nuevo_jugador"
                )
                
                st.session_state["mostrar_nuevo_jugador"] = mostrar_nuevo
                
                if mostrar_nuevo:
                    cliente_final = st.text_input(
                        "✏️ Nombre del Nuevo Jugador:", 
                        placeholder="Ej: Juan Pérez",
                        key="input_nuevo_jugador"
                    ).strip()
                    st.caption(f"📋 Jugadores existentes: {', '.join(clientes_existentes)}")
                else:
                    cliente_final = st.selectbox(
                        "👤 Seleccionar Jugador Existente:", 
                        clientes_existentes,
                        key="select_jugador_existente"
                    )

                opciones_tipo = [
                    "🟢 Saldo agregado (+)",
                    "🔴 Partida jugada (-)",
                    "🟡 Partida ganada (+)",
                    "🔵 Reintegro (+)",
                    "🟣 Retiro (-)"
                ]
                
                st.info("💡 Para sumar una victoria al ranking, selecciona '🟡 Partida ganada (+)")
                
                tipo_movimiento = st.selectbox(
                    "Tipo de Movimiento:", 
                    opciones_tipo,
                    key="select_tipo_movimiento"
                )
                
                monto = st.number_input(
                    "Monto ($):", 
                    min_value=0.0, 
                    step=1.0, 
                    format="%.2f", 
                    value=0.0,
                    key="input_monto"
                )

                fecha_actual = st.date_input(
                    "Fecha:", 
                    datetime.now().date(),
                    key="input_fecha"
                )
                
                col_h1, col_h2, col_ampm = st.columns([1, 1, 1])
                hora_now = datetime.now()
                h_12_default = hora_now.hour % 12
                if h_12_default == 0:
                    h_12_default = 12
                ampm_default = "PM" if hora_now.hour >= 12 else "AM"

                hora_num = col_h1.number_input(
                    "Hora (1-12):", 
                    min_value=1, 
                    max_value=12, 
                    value=h_12_default, 
                    step=1,
                    key="input_hora"
                )
                min_num = col_h2.number_input(
                    "Min (0-59):", 
                    min_value=0, 
                    max_value=59, 
                    value=hora_now.minute, 
                    step=1,
                    key="input_minutos"
                )
                ampm = col_ampm.selectbox(
                    "Período:", 
                    ["AM", "PM"], 
                    index=0 if ampm_default == "AM" else 1,
                    key="select_ampm"
                )

                hora_formateada = f"{hora_num:02d}:{min_num:02d} {ampm}"
                detalle = st.text_input(
                    "Observaciones:", 
                    placeholder="Mesa 1, Nequi, etc.",
                    key="input_detalle"
                )

                submit_registro = st.form_submit_button("💾 GUARDAR TRANSACCIÓN", type="primary")

                if submit_registro:
                    if not cliente_final:
                        st.error("❌ Debes indicar el nombre del jugador.")
                    elif monto <= 0:
                        st.warning("⚠️ Debes indicar un monto mayor a $0 para poder guardar la transacción.")
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
                            
                            if mostrar_nuevo:
                                st.session_state["mostrar_nuevo_jugador"] = False
                            
                            if tipo_movimiento == "🟡 Partida ganada (+)":
                                st.toast(f"🏆 ¡VICTORIA REGISTRADA! {cliente_final} +1 en el ranking", icon="🏆")
                            else:
                                st.toast(f"✅ Transacción de ${monto:,.2f} guardada con éxito a {cliente_final}", icon="🎉")
                            
                            time.sleep(0.5)
                            st.rerun()

        # --- MÓDULO DE EDICIÓN DE MOVIMIENTOS ---
        with st.expander("✏️ EDITAR O CORREGIR MOVIMIENTO", expanded=False):
            if not df_movimientos.empty:
                df_edit = df_movimientos.copy()
                
                opciones_edicion = []
                for idx, row in df_edit.iterrows():
                    fila_real = idx + 2
                    label = f"Fila {fila_real} | {row['Fecha']} {row['Hora']} | {row['Cliente']} | {row['Tipo']} | ${row['Monto']:,.2f}"
                    opciones_edicion.append(label)
                
                opciones_edicion.reverse()
                
                movimiento_sel = st.selectbox("Selecciona el movimiento a corregir:", opciones_edicion, key="edit_selector")
                
                if movimiento_sel:
                    fila_sheets_sel = int(movimiento_sel.split(" | ")[0].replace("Fila ", ""))
                    idx_df = fila_sheets_sel - 2
                    registro_actual = df_edit.loc[idx_df]

                    col_e1, col_e2 = st.columns(2)
                    
                    with col_e1:
                        edit_cliente = st.text_input("Cliente:", value=str(registro_actual["Cliente"]), key="edit_cli")
                        
                        opciones_tipo_edit = [
                            "🟢 Saldo agregado (+)",
                            "🔴 Partida jugada (-)",
                            "🟡 Partida ganada (+)",
                            "🔵 Reintegro (+)",
                            "🟣 Retiro (-)"
                        ]
                        tipo_index = opciones_tipo_edit.index(registro_actual["Tipo"]) if registro_actual["Tipo"] in opciones_tipo_edit else 0
                        edit_tipo = st.selectbox("Tipo de Movimiento:", opciones_tipo_edit, index=tipo_index, key="edit_tipo")
                        edit_monto = st.number_input("Monto ($):", min_value=0.0, value=float(registro_actual["Monto"]), step=1.0, format="%.2f", key="edit_monto")

                    with col_e2:
                        try:
                            fecha_previa = datetime.strptime(str(registro_actual["Fecha"]), "%Y-%m-%d").date()
                        except Exception:
                            fecha_previa = datetime.now().date()
                            
                        edit_fecha = st.date_input("Fecha:", value=fecha_previa, key="edit_fecha")
                        
                        hora_str = str(registro_actual["Hora"])
                        try:
                            time_obj = datetime.strptime(hora_str, "%I:%M %p")
                            h_12_val = time_obj.hour % 12
                            if h_12_val == 0:
                                h_12_val = 12
                            m_val = time_obj.minute
                            ampm_val = "PM" if time_obj.hour >= 12 else "AM"
                        except Exception:
                            h_12_val, m_val, ampm_val = 12, 0, "AM"

                        col_eh1, col_eh2, col_eampm = st.columns([1, 1, 1])
                        edit_h = col_eh1.number_input("Hora (1-12):", min_value=1, max_value=12, value=h_12_val, key="edit_h")
                        edit_m = col_eh2.number_input("Min (0-59):", min_value=0, max_value=59, value=m_val, key="edit_m")
                        edit_ampm = col_eampm.selectbox("Período:", ["AM", "PM"], index=0 if ampm_val == "AM" else 1, key="edit_ampm")
                        
                        edit_hora_formateada = f"{edit_h:02d}:{edit_m:02d} {edit_ampm}"
                        edit_detalle = st.text_input("Observaciones:", value=str(registro_actual["Detalle"]), key="edit_det")

                    if st.button("💾 ACTUALIZAR MOVIMIENTO", type="primary"):
                        if not edit_cliente:
                            st.error("❌ El nombre del cliente no puede estar vacío.")
                        else:
                            with st.spinner("Actualizando registro en Google Sheets..."):
                                actualizar_movimiento(
                                    fila_sheets_sel,
                                    edit_fecha.strftime("%Y-%m-%d"),
                                    edit_hora_formateada,
                                    edit_cliente,
                                    edit_tipo,
                                    edit_monto,
                                    edit_detalle
                                )
                                st.toast(f"✅ Movimiento de la fila {fila_sheets_sel} actualizado correctamente.", icon="🎉")
                                time.sleep(0.8)
                                st.rerun()
            else:
                st.info("No hay registros disponibles para editar.")

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
            df_historial = df_movimientos.iloc[::-1].reset_index(drop=True)
            df_historial_formateado = df_historial.copy()
            
            for col in ["Monto", "Saldo_Anterior", "Saldo_Nuevo"]:
                if col in df_historial_formateado.columns:
                    df_historial_formateado[col] = df_historial_formateado[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
            
            st.dataframe(
                df_historial_formateado,
                use_container_width=True,
                hide_index=True
            )
    elif password != "":
        st.error("🔒 Contraseña incorrecta.")
