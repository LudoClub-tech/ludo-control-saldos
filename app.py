import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import os
import random
import time
import pytz

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

# ==============================================================================
# FUNCIONES PARA RANKING MEJORADO
# ==============================================================================

def calcular_nivel(victorias_totales):
    """Calcula el nivel según las victorias totales"""
    if victorias_totales >= 200:
        return "👑 DIAMANTE"
    elif victorias_totales >= 100:
        return "💎 PLATINO"
    elif victorias_totales >= 60:
        return "🥇 ORO"
    elif victorias_totales >= 30:
        return "🥈 PLATA"
    elif victorias_totales >= 10:
        return "🥉 BRONCE"
    else:
        return "🔰 NOVATO"

def obtener_ranking_dia(fecha_hoy, df_movimientos):
    """Obtiene el ranking de victorias del día"""
    df_victorias = df_movimientos[
        (df_movimientos["Fecha"] == fecha_hoy) & 
        (df_movimientos["Tipo"] == "🟡 Partida ganada (+)")
    ]
    
    if df_victorias.empty:
        return pd.DataFrame(columns=["Posición", "Cliente", "Victorias"])
    
    ranking = df_victorias.groupby("Cliente").size().reset_index(name="Victorias")
    ranking = ranking.sort_values(by="Victorias", ascending=False).reset_index(drop=True)
    ranking.insert(0, "Posición", range(1, len(ranking) + 1))
    
    return ranking

def obtener_ranking_mes(month_key, df_movimientos):
    """Obtiene el ranking de victorias del mes"""
    df_victorias = df_movimientos[
        (df_movimientos["Fecha"].str.startswith(month_key)) & 
        (df_movimientos["Tipo"] == "🟡 Partida ganada (+)")
    ]
    
    if df_victorias.empty:
        return pd.DataFrame(columns=["Posición", "Cliente", "Victorias"])
    
    ranking = df_victorias.groupby("Cliente").size().reset_index(name="Victorias")
    ranking = ranking.sort_values(by="Victorias", ascending=False).reset_index(drop=True)
    ranking.insert(0, "Posición", range(1, len(ranking) + 1))
    
    return ranking

def obtener_ranking_global(df_movimientos):
    """Obtiene el ranking global de victorias (histórico)"""
    df_victorias = df_movimientos[df_movimientos["Tipo"] == "🟡 Partida ganada (+)"]
    
    if df_victorias.empty:
        return pd.DataFrame(columns=["Posición", "Cliente", "Victorias"])
    
    ranking = df_victorias.groupby("Cliente").size().reset_index(name="Victorias")
    ranking = ranking.sort_values(by="Victorias", ascending=False).reset_index(drop=True)
    ranking.insert(0, "Posición", range(1, len(ranking) + 1))
    
    return ranking

def obtener_estadisticas_ranking(ranking_df):
    """Calcula estadísticas del ranking"""
    if ranking_df.empty:
        return {"total_jugadores": 0, "total_victorias": 0, "promedio": 0, "max_victorias": 0}
    
    total_victorias = ranking_df["Victorias"].sum()
    return {
        "total_jugadores": len(ranking_df),
        "total_victorias": total_victorias,
        "promedio": round(total_victorias / len(ranking_df), 1),
        "max_victorias": ranking_df["Victorias"].max()
    }

def guardar_ganador_mes(month_key, ranking_df):
    """Guarda el ganador del mes en una hoja de Excel"""
    try:
        if ranking_df.empty:
            return False, "No hay datos para guardar"
        
        ganador = ranking_df.iloc[0]["Cliente"]
        victorias = ranking_df.iloc[0]["Victorias"]
        
        try:
            sheet_meses = client.open("Ludo_Control_Saldos").worksheet("Ganadores_Mensuales")
        except:
            sheet_meses = client.open("Ludo_Control_Saldos").add_worksheet("Ganadores_Mensuales", rows=100, cols=10)
            sheet_meses.append_row(["Mes", "Ganador", "Victorias", "Segundo", "Tercero"])
        
        segundo = ranking_df.iloc[1]["Cliente"] if len(ranking_df) >= 2 else "-"
        tercero = ranking_df.iloc[2]["Cliente"] if len(ranking_df) >= 3 else "-"
        
        datos = sheet_meses.get_all_records()
        df_existente = pd.DataFrame(datos)
        if not df_existente.empty:
            existe = df_existente[df_existente["Mes"] == month_key]
            if not existe.empty:
                fila = existe.index[0] + 2
                sheet_meses.update_cell(fila, 2, ganador)
                sheet_meses.update_cell(fila, 3, victorias)
                sheet_meses.update_cell(fila, 4, segundo)
                sheet_meses.update_cell(fila, 5, tercero)
                return True, f"✅ Ganador del mes {month_key} actualizado: {ganador}"
        
        sheet_meses.append_row([month_key, ganador, victorias, segundo, tercero])
        return True, f"✅ Ganador del mes {month_key} guardado: {ganador}"
        
    except Exception as e:
        return False, f"❌ Error al guardar ganador del mes: {e}"

def resetear_ranking_mes(month_key, sheet):
    """Reinicia el ranking del mes eliminando SOLO las victorias del mes actual"""
    try:
        df = obtener_datos()
        
        df_victorias_mes = df[
            (df["Fecha"].str.startswith(month_key)) & 
            (df["Tipo"] == "🟡 Partida ganada (+)")
        ]
        
        if df_victorias_mes.empty:
            return False, f"No hay victorias en el mes {month_key} para reiniciar."
        
        filas = []
        for idx in df_victorias_mes.index:
            filas.append(idx + 2)
        
        for fila in sorted(filas, reverse=True):
            sheet.delete_rows(fila)
        
        return True, f"✅ Ranking del mes {month_key} reiniciado. Se eliminaron {len(filas)} victorias."
        
    except Exception as e:
        return False, f"❌ Error al reiniciar ranking del mes: {e}"

# --- INICIALIZACIÓN DE ESTADO DE SESIÓN ---
if "ganador_ruleta_hoy" not in st.session_state:
    st.session_state["ganador_ruleta_hoy"] = None
if "bloqueo_envio_admin" not in st.session_state:
    st.session_state["bloqueo_envio_admin"] = False
if "mostrar_nuevo" not in st.session_state:
    st.session_state["mostrar_nuevo"] = False

# Cargar datos
df_movimientos = obtener_datos()
clientes_base = ["Dani", "Mis amores", "Wis", "Wilson"]
clientes_existentes = sorted(list(set(clientes_base + df_movimientos["Cliente"].dropna().unique().tolist())))

# Zona horaria de Colombia
zona_colombia = pytz.timezone('America/Bogota')
ahora_colombia = datetime.now(zona_colombia)
fecha_hoy_str = ahora_colombia.strftime("%Y-%m-%d")
mes_actual = ahora_colombia.strftime("%Y-%m")

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
                    
                    victorias_totales = len(df_jugador[df_jugador["Tipo"] == "🟡 Partida ganada (+)"])
                    nivel_jugador = calcular_nivel(victorias_totales)

                    st.markdown(f"""
                        <div class="gaming-card saldo-card">
                            <div class="saldo-title">SALDO NETO DISPONIBLE</div>
                            <div class="saldo-amount">${saldo_actual:,.2f}</div>
                            <div style="color: #94A3B8; font-size: 13px; margin-top: 5px;">Jugador: <b>{jugador_seleccionado}</b></div>
                            <div style="color: #FFD700; font-size: 14px; font-weight: 700; margin-top: 5px;">{nivel_jugador}</div>
                            <div style="color: #8B949E; font-size: 12px; margin-top: 5px;">
                                📊 Saldo anterior: <b>${saldo_anterior:,.2f}</b> | Último movimiento: <b>${df_jugador.iloc[-1]['Monto']:,.2f}</b>
                            </div>
                            <div style="color: #8B949E; font-size: 12px;">
                                🏆 {victorias_totales} victorias totales
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
            ["🏆 Ranking del Día", "🏆 Ranking del Mes", "👑 Ranking Global", "📊 Ganadores Mensuales"], 
            horizontal=True,
            index=0,
            key="ranking_periodo"
        )
        
        st.markdown("---")
        
        # ============================================================
        # RANKING DEL DÍA
        # ============================================================
        if filtro_rango == "🏆 Ranking del Día":
            ranking_df = obtener_ranking_dia(fecha_hoy_str, df_movimientos)
            titulo = f"🏆 RANKING DEL DÍA ({fecha_hoy_str})"
            subtitulo = "🔥 ¿Quién ganó más partidas HOY?"
            
            st.markdown(f"### {titulo}")
            st.caption(subtitulo)
            
            if not ranking_df.empty:
                stats = obtener_estadisticas_ranking(ranking_df)
                
                col_est1, col_est2, col_est3, col_est4 = st.columns(4)
                with col_est1:
                    st.metric("👥 Jugadores", stats["total_jugadores"])
                with col_est2:
                    st.metric("🏆 Victorias", stats["total_victorias"])
                with col_est3:
                    st.metric("📊 Promedio", stats["promedio"])
                with col_est4:
                    st.metric("🔥 Máximo", stats["max_victorias"])
                
                st.markdown("---")
                st.markdown("### 🥇 PODIO DE CAMPEONES DEL DÍA")
                
                col_p1, col_p2, col_p3 = st.columns(3)
                
                if len(ranking_df) >= 1:
                    with col_p1:
                        nivel1 = calcular_nivel(ranking_df.iloc[0]["Victorias"])
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #FFD700; border-width: 3px;">
                                <div style="font-size: 50px;">🥇</div>
                                <div style="font-weight: 900; font-size: 22px; color: #FFD700;">{ranking_df.iloc[0]['Cliente']}</div>
                                <div style="color: #FFD700; font-size: 14px; font-weight: 700;">{nivel1}</div>
                                <div style="color: #FFD700; font-size: 32px; font-weight: 900;">{ranking_df.iloc[0]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                                <div style="color: #FFD700; font-size: 12px; margin-top: 5px;">👑 CAMPEÓN DEL DÍA</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                if len(ranking_df) >= 2:
                    with col_p2:
                        nivel2 = calcular_nivel(ranking_df.iloc[1]["Victorias"])
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #C0C0C0; border-width: 3px;">
                                <div style="font-size: 45px;">🥈</div>
                                <div style="font-weight: 900; font-size: 20px; color: #C0C0C0;">{ranking_df.iloc[1]['Cliente']}</div>
                                <div style="color: #C0C0C0; font-size: 14px; font-weight: 700;">{nivel2}</div>
                                <div style="color: #C0C0C0; font-size: 28px; font-weight: 900;">{ranking_df.iloc[1]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                if len(ranking_df) >= 3:
                    with col_p3:
                        nivel3 = calcular_nivel(ranking_df.iloc[2]["Victorias"])
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #CD7F32; border-width: 3px;">
                                <div style="font-size: 40px;">🥉</div>
                                <div style="font-weight: 900; font-size: 18px; color: #CD7F32;">{ranking_df.iloc[2]['Cliente']}</div>
                                <div style="color: #CD7F32; font-size: 14px; font-weight: 700;">{nivel3}</div>
                                <div style="color: #CD7F32; font-size: 24px; font-weight: 900;">{ranking_df.iloc[2]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                st.markdown("### 📊 TABLA DE POSICIONES DEL DÍA")
                
                def color_fila(row):
                    if row["Posición"] == 1:
                        return ['background-color: #FFD700; color: #000000; font-weight: bold;'] * len(row)
                    elif row["Posición"] == 2:
                        return ['background-color: #C0C0C0; color: #000000; font-weight: bold;'] * len(row)
                    elif row["Posición"] == 3:
                        return ['background-color: #CD7F32; color: #000000; font-weight: bold;'] * len(row)
                    else:
                        return [''] * len(row)
                
                st.dataframe(
                    ranking_df.style.apply(color_fila, axis=1),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("📭 No hay victorias registradas hoy.")
                st.info(f"💡 Registra partidas ganadas con el tipo: '🟡 Partida ganada (+)' para que aparezcan aquí.")
        
        # ============================================================
        # RANKING DEL MES
        # ============================================================
        elif filtro_rango == "🏆 Ranking del Mes":
            ranking_df = obtener_ranking_mes(mes_actual, df_movimientos)
            titulo = f"🏆 RANKING DEL MES ({mes_actual})"
            subtitulo = "🔥 ¿Quién ganó más partidas este MES?"
            
            st.markdown(f"### {titulo}")
            st.caption(subtitulo)
            st.info(f"📅 El ranking se reinicia automáticamente el 1 de cada mes. Estamos en: {mes_actual}")
            
            if not ranking_df.empty:
                stats = obtener_estadisticas_ranking(ranking_df)
                
                col_est1, col_est2, col_est3, col_est4 = st.columns(4)
                with col_est1:
                    st.metric("👥 Jugadores", stats["total_jugadores"])
                with col_est2:
                    st.metric("🏆 Victorias", stats["total_victorias"])
                with col_est3:
                    st.metric("📊 Promedio", stats["promedio"])
                with col_est4:
                    st.metric("🔥 Máximo", stats["max_victorias"])
                
                st.markdown("---")
                st.markdown("### 🥇 PODIO DE CAMPEONES DEL MES")
                
                col_p1, col_p2, col_p3 = st.columns(3)
                
                if len(ranking_df) >= 1:
                    with col_p1:
                        nivel1 = calcular_nivel(ranking_df.iloc[0]["Victorias"])
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #FFD700; border-width: 3px; background: linear-gradient(135deg, #1C1C00 0%, #2D2D00 100%);">
                                <div style="font-size: 50px;">🥇</div>
                                <div style="font-weight: 900; font-size: 22px; color: #FFD700;">{ranking_df.iloc[0]['Cliente']}</div>
                                <div style="color: #FFD700; font-size: 14px; font-weight: 700;">{nivel1}</div>
                                <div style="color: #FFD700; font-size: 32px; font-weight: 900;">{ranking_df.iloc[0]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                                <div style="color: #FFD700; font-size: 12px; margin-top: 5px;">👑 CAMPEÓN DEL MES</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                if len(ranking_df) >= 2:
                    with col_p2:
                        nivel2 = calcular_nivel(ranking_df.iloc[1]["Victorias"])
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #C0C0C0; border-width: 3px; background: linear-gradient(135deg, #1C1C1C 0%, #2D2D2D 100%);">
                                <div style="font-size: 45px;">🥈</div>
                                <div style="font-weight: 900; font-size: 20px; color: #C0C0C0;">{ranking_df.iloc[1]['Cliente']}</div>
                                <div style="color: #C0C0C0; font-size: 14px; font-weight: 700;">{nivel2}</div>
                                <div style="color: #C0C0C0; font-size: 28px; font-weight: 900;">{ranking_df.iloc[1]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                if len(ranking_df) >= 3:
                    with col_p3:
                        nivel3 = calcular_nivel(ranking_df.iloc[2]["Victorias"])
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #CD7F32; border-width: 3px; background: linear-gradient(135deg, #1C1C0A 0%, #2D2D0A 100%);">
                                <div style="font-size: 40px;">🥉</div>
                                <div style="font-weight: 900; font-size: 18px; color: #CD7F32;">{ranking_df.iloc[2]['Cliente']}</div>
                                <div style="color: #CD7F32; font-size: 14px; font-weight: 700;">{nivel3}</div>
                                <div style="color: #CD7F32; font-size: 24px; font-weight: 900;">{ranking_df.iloc[2]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                st.markdown("### 📊 TABLA DE POSICIONES DEL MES")
                
                def color_fila_mes(row):
                    if row["Posición"] == 1:
                        return ['background-color: #FFD700; color: #000000; font-weight: bold;'] * len(row)
                    elif row["Posición"] == 2:
                        return ['background-color: #C0C0C0; color: #000000; font-weight: bold;'] * len(row)
                    elif row["Posición"] == 3:
                        return ['background-color: #CD7F32; color: #000000; font-weight: bold;'] * len(row)
                    else:
                        return [''] * len(row)
                
                st.dataframe(
                    ranking_df.style.apply(color_fila_mes, axis=1),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("📭 No hay victorias registradas este mes.")
                st.info(f"💡 Registra partidas ganadas para que aparezcan aquí.")
        
        # ============================================================
        # RANKING GLOBAL (HISTÓRICO)
        # ============================================================
        elif filtro_rango == "👑 Ranking Global":
            ranking_df = obtener_ranking_global(df_movimientos)
            titulo = "👑 RANKING GLOBAL HISTÓRICO"
            subtitulo = "🏆 Los mejores de TODOS los tiempos"
            
            st.markdown(f"### {titulo}")
            st.caption(subtitulo)
            st.info("📊 Este ranking NUNCA se borra. Muestra el historial completo de victorias.")
            
            if not ranking_df.empty:
                stats = obtener_estadisticas_ranking(ranking_df)
                
                col_est1, col_est2, col_est3, col_est4 = st.columns(4)
                with col_est1:
                    st.metric("👥 Jugadores", stats["total_jugadores"])
                with col_est2:
                    st.metric("🏆 Victorias", stats["total_victorias"])
                with col_est3:
                    st.metric("📊 Promedio", stats["promedio"])
                with col_est4:
                    st.metric("🔥 Máximo", stats["max_victorias"])
                
                st.markdown("---")
                st.markdown("### 🥇 PODIO DE CAMPEONES GLOBALES")
                
                col_p1, col_p2, col_p3 = st.columns(3)
                
                if len(ranking_df) >= 1:
                    with col_p1:
                        nivel1 = calcular_nivel(ranking_df.iloc[0]["Victorias"])
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #FFD700; border-width: 3px; background: linear-gradient(135deg, #1C1C00 0%, #2D2D00 100%);">
                                <div style="font-size: 50px;">👑</div>
                                <div style="font-weight: 900; font-size: 22px; color: #FFD700;">{ranking_df.iloc[0]['Cliente']}</div>
                                <div style="color: #FFD700; font-size: 14px; font-weight: 700;">{nivel1}</div>
                                <div style="color: #FFD700; font-size: 32px; font-weight: 900;">{ranking_df.iloc[0]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                                <div style="color: #FFD700; font-size: 12px; margin-top: 5px;">🏆 LEYENDA</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                if len(ranking_df) >= 2:
                    with col_p2:
                        nivel2 = calcular_nivel(ranking_df.iloc[1]["Victorias"])
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #C0C0C0; border-width: 3px; background: linear-gradient(135deg, #1C1C1C 0%, #2D2D2D 100%);">
                                <div style="font-size: 45px;">🥈</div>
                                <div style="font-weight: 900; font-size: 20px; color: #C0C0C0;">{ranking_df.iloc[1]['Cliente']}</div>
                                <div style="color: #C0C0C0; font-size: 14px; font-weight: 700;">{nivel2}</div>
                                <div style="color: #C0C0C0; font-size: 28px; font-weight: 900;">{ranking_df.iloc[1]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                if len(ranking_df) >= 3:
                    with col_p3:
                        nivel3 = calcular_nivel(ranking_df.iloc[2]["Victorias"])
                        st.markdown(f"""
                            <div class="gaming-card" style="border-color: #CD7F32; border-width: 3px; background: linear-gradient(135deg, #1C1C0A 0%, #2D2D0A 100%);">
                                <div style="font-size: 40px;">🥉</div>
                                <div style="font-weight: 900; font-size: 18px; color: #CD7F32;">{ranking_df.iloc[2]['Cliente']}</div>
                                <div style="color: #CD7F32; font-size: 14px; font-weight: 700;">{nivel3}</div>
                                <div style="color: #CD7F32; font-size: 24px; font-weight: 900;">{ranking_df.iloc[2]['Victorias']}</div>
                                <div style="color: #8B949E; font-size: 13px;">Victorias</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                st.markdown("### 📊 TABLA DE POSICIONES GLOBALES")
                
                def color_fila_global(row):
                    if row["Posición"] == 1:
                        return ['background-color: #FFD700; color: #000000; font-weight: bold;'] * len(row)
                    elif row["Posición"] == 2:
                        return ['background-color: #C0C0C0; color: #000000; font-weight: bold;'] * len(row)
                    elif row["Posición"] == 3:
                        return ['background-color: #CD7F32; color: #000000; font-weight: bold;'] * len(row)
                    else:
                        return [''] * len(row)
                
                st.dataframe(
                    ranking_df.style.apply(color_fila_global, axis=1),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("📭 No hay victorias en el historial global.")
        
        # ============================================================
        # GANADORES MENSUALES
        # ============================================================
        else:
            st.markdown("### 📊 GANADORES MENSUALES")
            st.caption("🏆 Historial de campeones mes a mes")
            
            try:
                sheet_meses = client.open("Ludo_Control_Saldos").worksheet("Ganadores_Mensuales")
                datos = sheet_meses.get_all_records()
                df_meses = pd.DataFrame(datos)
                
                if not df_meses.empty:
                    df_meses = df_meses.sort_values(by="Mes", ascending=False)
                    
                    st.dataframe(
                        df_meses,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    ultimo = df_meses.iloc[0]
                    st.success(f"🏆 **ÚLTIMO GANADOR MENSUAL:** {ultimo['Ganador']} ({ultimo['Mes']}) con {ultimo['Victorias']} victorias")
                else:
                    st.info("📭 No hay ganadores mensuales registrados aún.")
                    st.info("💡 Usa el botón 'CERRAR MES' en el panel de administrador para guardar al ganador.")
            except:
                st.info("📭 No hay ganadores mensuales registrados aún.")
                st.info("💡 Usa el botón 'CERRAR MES' en el panel de administrador para guardar al ganador.")

    # --- TAB 3: RULETA DIARIA (VISTA JUGADOR) ---
    with tab_ruleta:
        st.markdown("### 🎡 SORTEO DE RULETA DIARIA")
        st.caption("🎯 Los jugadores con 3 o más partidas jugadas hoy participan automáticamente")
        
        hora_actual_str = ahora_colombia.strftime("%I:%M %p")
        st.info(f"🕐 Hora actual (Colombia): {hora_actual_str} | Fecha: {fecha_hoy_str}")

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
    CLAVE_ADMIN = "ludo22927613" 
    
    password = st.text_input("Ingresa la contraseña de gestión:", type="password")

    if password == CLAVE_ADMIN:
        st.success("✅ Modo Administrador Activo")

        # --- SECCIÓN EXCLUSIVA DE GESTIÓN DE RULETA ---
        with st.expander("🎡 CONTROL DE RULETA DIARIA (EXCLUSIVO ADMIN)", expanded=True):
            
            hora_actual_str = ahora_colombia.strftime("%I:%M %p")
            st.info(f"🕐 Hora actual (Colombia): {hora_actual_str} | Fecha: {fecha_hoy_str}")
            
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

        # --- SECCIÓN CERRAR MES ---
        with st.expander("📅 CERRAR MES - GUARDAR GANADOR", expanded=False):
            
            st.markdown("### 📅 CERRAR MES")
            st.caption(f"📊 Guarda al ganador del mes {mes_actual} y reinicia el ranking mensual")
            
            ranking_mes = obtener_ranking_mes(mes_actual, df_movimientos)
            
            if not ranking_mes.empty:
                st.write("**🏆 TOP 3 DEL MES ACTUAL:**")
                
                col1, col2, col3 = st.columns(3)
                
                if len(ranking_mes) >= 1:
                    with col1:
                        st.markdown(f"🥇 **{ranking_mes.iloc[0]['Cliente']}**\n{ranking_mes.iloc[0]['Victorias']} victorias")
                if len(ranking_mes) >= 2:
                    with col2:
                        st.markdown(f"🥈 **{ranking_mes.iloc[1]['Cliente']}**\n{ranking_mes.iloc[1]['Victorias']} victorias")
                if len(ranking_mes) >= 3:
                    with col3:
                        st.markdown(f"🥉 **{ranking_mes.iloc[2]['Cliente']}**\n{ranking_mes.iloc[2]['Victorias']} victorias")
                
                st.markdown("---")
                st.warning("⚠️ Esta acción guardará al ganador del mes y REINICIARÁ el ranking mensual a 0.")
                
                if st.button("📅 CERRAR MES Y REINICIAR RANKING", type="primary"):
                    with st.spinner("Guardando ganador del mes..."):
                        success, mensaje = guardar_ganador_mes(mes_actual, ranking_mes)
                        st.info(mensaje)
                        
                        if success:
                            success2, mensaje2 = resetear_ranking_mes(mes_actual, sheet)
                            if success2:
                                st.success(mensaje2)
                                st.balloons()
                                st.success(f"🏆 {ranking_mes.iloc[0]['Cliente']} es el CAMPEÓN del mes {mes_actual}!")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(mensaje2)
            else:
                st.info("📭 No hay victorias este mes. No se puede cerrar el mes.")

        # --- REGISTRO DE MOVIMIENTOS ---
        with st.expander("➕ REGISTRAR NUEVO MOVIMIENTO", expanded=True):
            
            if "mostrar_nuevo" not in st.session_state:
                st.session_state["mostrar_nuevo"] = False
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("👤 Jugador Existente", use_container_width=True, key="btn_existente"):
                    st.session_state["mostrar_nuevo"] = False
                    st.rerun()
            with col2:
                if st.button("➕ Nuevo Jugador", use_container_width=True, key="btn_nuevo"):
                    st.session_state["mostrar_nuevo"] = True
                    st.rerun()
            
            st.markdown("---")
            
            with st.form(key="registro_movimiento_form"):
                
                st.markdown("### 📝 DATOS DE LA TRANSACCIÓN")
                
                if st.session_state["mostrar_nuevo"]:
                    cliente_final = st.text_input(
                        "✏️ Escribe el nombre del nuevo jugador:",
                        placeholder="Ej: Juan Pérez",
                        key="nuevo_jugador_input"
                    ).strip()
                    
                    if clientes_existentes:
                        st.caption(f"💡 Jugadores existentes: {', '.join(clientes_existentes[:5])}" + 
                                  (f" y {len(clientes_existentes)-5} más..." if len(clientes_existentes) > 5 else ""))
                else:
                    cliente_final = st.selectbox(
                        "👤 Selecciona un jugador existente:",
                        clientes_existentes,
                        key="cliente_existente_select"
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
                    key="tipo_movimiento_select"
                )
                
                monto = st.number_input(
                    "Monto ($):", 
                    min_value=0.0, 
                    step=1.0, 
                    format="%.2f", 
                    value=0.0,
                    key="monto_input"
                )

                fecha_actual = st.date_input(
                    "Fecha:", 
                    datetime.now().date(),
                    key="fecha_input"
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
                    key="hora_input"
                )
                min_num = col_h2.number_input(
                    "Min (0-59):", 
                    min_value=0, 
                    max_value=59, 
                    value=hora_now.minute, 
                    step=1,
                    key="minutos_input"
                )
                ampm = col_ampm.selectbox(
                    "Período:", 
                    ["AM", "PM"], 
                    index=0 if ampm_default == "AM" else 1,
                    key="ampm_select"
                )

                hora_formateada = f"{hora_num:02d}:{min_num:02d} {ampm}"
                detalle = st.text_input(
                    "Observaciones:", 
                    placeholder="Mesa 1, Nequi, etc.",
                    key="detalle_input"
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
                            
                            if st.session_state["mostrar_nuevo"]:
                                st.session_state["mostrar_nuevo"] = False
                            
                            if tipo_movimiento == "🟡 Partida ganada (+)":
                                st.toast(f"🏆 ¡VICTORIA REGISTRADA! {cliente_final} +1 en el ranking", icon="🏆")
                            else:
                                st.toast(f"✅ Transacción de ${monto:,.2f} guardada con éxito a {cliente_final}", icon="🎉")
                            
                            time.sleep(0.8)
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
