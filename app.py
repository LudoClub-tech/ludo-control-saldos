import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random
import time
from streamlit_gsheets import GSheetsConnection

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS (LUDO CLUB)
# ---------------------------------------------------------
st.set_page_config(
    page_title="Gestión Ludo Club",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #0D1117; color: #C9D1D9; }
    
    .gaming-card {
        background: linear-gradient(145deg, #161B22, #0D1117);
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.4);
        text-align: center;
    }
    
    .metric-value {
        font-size: 32px;
        font-weight: 900;
        margin-top: 5px;
    }
    
    .metric-label {
        color: #8B949E;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    div.stButton > button:first-child {
        border-radius: 8px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. CONEXIÓN Y FUNCIONES DE GOOGLE SHEETS
# ---------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    try:
        df = conn.read(ttl="0s")
        if df.empty:
            return pd.DataFrame(columns=["Fecha", "Hora", "Cliente", "Tipo", "Monto", "Detalle"])
        return df
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return pd.DataFrame(columns=["Fecha", "Hora", "Cliente", "Tipo", "Monto", "Detalle"])

def guardar_movimiento(fecha, hora, cliente, tipo, monto, detalle):
    df_actual = cargar_datos()
    nuevo_registro = pd.DataFrame([{
        "Fecha": fecha,
        "Hora": hora,
        "Cliente": cliente,
        "Tipo": tipo,
        "Monto": float(monto),
        "Detalle": detalle
    }])
    df_actualizado = pd.concat([df_actual, nuevo_registro], ignore_index=True)
    conn.update(data=df_actualizado)
    st.cache_data.clear()

def calcular_neto(row):
    tipo = str(row["Tipo"])
    monto = float(row["Monto"])
    if "(+)" in tipo:
        return monto
    elif "(-)" in tipo:
        return -monto
    return 0.0

df_movimientos = cargar_datos()
fecha_hoy_str = datetime.now().strftime("%Y-%m-%d")

# ---------------------------------------------------------
# 3. BARRA LATERAL - SELECCIÓN DE ROL
# ---------------------------------------------------------
st.sidebar.markdown("## 🎲 LUDO CLUB")
rol = st.sidebar.radio("Selecciona tu Rol:", ["🎮 Jugador", "🛠️ Administrador"])

clientes_existentes = sorted(df_movimientos["Cliente"].dropna().unique().tolist()) if not df_movimientos.empty else []

# ---------------------------------------------------------
# 4. VISTA: JUGADOR (SALDOS, HISTORIAL Y RANKING DE GANADORES)
# ---------------------------------------------------------
if rol == "🎮 Jugador":
    st.markdown("# 🏆 Panel de Ludo Club")

    tabs_jugador = st.tabs(["💰 Mi Saldo e Historial", "🥇 Ranking de Ganadores", "🎡 Ganador Ruleta Hoy"])

    # TAB 1: SALDO DE JUGADOR
    with tabs_jugador[0]:
        if len(clientes_existentes) == 0:
            st.info("Aún no hay jugadores registrados.")
        else:
            cliente_sel = st.selectbox("Selecciona tu Nombre/Alias:", clientes_existentes)
            
            if cliente_sel:
                df_cli = df_movimientos[df_movimientos["Cliente"] == cliente_sel]
                
                saldo = 0.0
                if not df_cli.empty:
                    df_cli_calc = df_cli.copy()
                    df_cli_calc["Neto"] = df_cli_calc.apply(calcular_neto, axis=1)
                    saldo = df_cli_calc["Neto"].sum()

                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    st.markdown(f"""
                        <div class="gaming-card">
                            <div class="metric-label">Jugador Activo</div>
                            <div class="metric-value" style="color: #58A6FF;">👤 {cliente_sel}</div>
                        </div>
                    """, unsafe_allow_html=True)
                with col_s2:
                    st.markdown(f"""
                        <div class="gaming-card">
                            <div class="metric-label">Saldo Disponible</div>
                            <div class="metric-value" style="color: #3FB950;">${saldo:,.2f}</div>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("### 📜 Mi Historial de Movimientos")
                if not df_cli.empty:
                    st.dataframe(
                        df_cli[["Fecha", "Hora", "Tipo", "Monto", "Detalle"]].sort_index(ascending=False).style.format({"Monto": "${:,.2f}"}),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No tienes movimientos registrados.")

    # TAB 2: RANKING DE GANADORES
    with tabs_jugador[1]:
        st.markdown("### 🏆 PODIO DE GANADORES")
        filtro_ranking = st.radio("Ver victorias de:", ["Hoy", "Histórico"], horizontal=True)

        if not df_movimientos.empty:
            df_ganadas = df_movimientos[df_movimientos["Tipo"] == "🟡 Partida ganada (+)"]

            if filtro_ranking == "Hoy":
                df_ganadas = df_ganadas[df_ganadas["Fecha"] == fecha_hoy_str]

            if not df_ganadas.empty:
                ranking_df = df_ganadas.groupby("Cliente").size().reset_index(name="Victorias")
                ranking_df = ranking_df.sort_values(by="Victorias", ascending=False).reset_index(drop=True)

                # Medallas para el Top 3
                iconos = ["🥇", "🥈", "🥉"]
                ranking_df["Puesto"] = [iconos[i] if i < 3 else f"#{i+1}" for i in range(len(ranking_df))]

                ranking_df = ranking_df[["Puesto", "Cliente", "Victorias"]]
                st.dataframe(ranking_df, use_container_width=True, hide_index=True)
            else:
                st.info("Aún no hay partidas ganadas registradas para esta selección.")
        else:
            st.info("Sin registros en la base de datos.")

    # TAB 3: GANADOR DE LA RULETA DEL DÍA
    with tabs_jugador[2]:
        st.markdown("### 🎡 Sorteo del Día")
        if "ganador_ruleta_hoy" in st.session_state:
            ganador = st.session_state["ganador_ruleta_hoy"]
            st.markdown(f"""
                <div class="gaming-card" style="border-color: #238636; background: linear-gradient(135deg, #1C4429 0%, #111827 100%); padding: 35px;">
                    <div style="font-size: 16px; color: #3FB950; font-weight: 800;">👑 GANADOR DE LA RULETA DE HOY 👑</div>
                    <div style="font-size: 42px; font-weight: 900; color: #FFFFFF; text-shadow: 0 0 10px #3FB950;">🎉 {ganador} 🎉</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("El administrador aún no ha girado la ruleta del día de hoy.")

# ---------------------------------------------------------
# 5. VISTA: ADMINISTRADOR (MÉTRICAS + REGISTRO + RULETA)
# ---------------------------------------------------------
else:
    st.markdown("# 🔑 ACCESO ADMINISTRADOR")
    CLAVE_ADMIN = "ludo21010227" 
    
    password = st.text_input("Ingresa la contraseña de gestión:", type="password")

    if password == CLAVE_ADMIN:
        st.success("✅ Modo Administrador Activo")

        # Inicialización de estado para limpiar campos
        if "monto_input" not in st.session_state:
            st.session_state["monto_input"] = 0.0
        if "detalle_input" not in st.session_state:
            st.session_state["detalle_input"] = ""

        tabs_admin = st.tabs(["📊 Métricas & Crecimiento", "📝 Registrar Movimiento", "🎡 Control Ruleta", "📑 Consolidado & Historial"])

        # TAB 1: MÉTRICAS Y CRECIMIENTO
        with tabs_admin[0]:
            st.markdown("## 📈 Crecimiento y Actividad de Ludo Club")
            
            if df_movimientos.empty:
                st.info("Aún no hay datos para calcular estadísticas.")
            else:
                df_calc = df_movimientos.copy()
                df_calc["Fecha_dt"] = pd.to_datetime(df_calc["Fecha"], errors="coerce")
                
                hoy_dt = datetime.now().date()
                hace_7_dias = hoy_dt - timedelta(days=7)
                mes_actual = hoy_dt.month
                ano_actual = hoy_dt.year

                jugadores_hoy = df_calc[df_calc["Fecha_dt"].dt.date == hoy_dt]["Cliente"].nunique()
                total_jugadores = df_calc["Cliente"].nunique()

                # Cada 4 registros de "Partida jugada (-)" = 1 partida de Ludo
                df_partidas = df_calc[df_calc["Tipo"] == "🔴 Partida jugada (-)"]

                reg_hoy = len(df_partidas[df_partidas["Fecha_dt"].dt.date == hoy_dt])
                partidas_hoy = reg_hoy // 4

                reg_semana = len(df_partidas[df_partidas["Fecha_dt"].dt.date >= hace_7_dias])
                partidas_semana = reg_semana // 4

                reg_mes = len(df_partidas[(df_partidas["Fecha_dt"].dt.month == mes_actual) & (df_partidas["Fecha_dt"].dt.year == ano_actual)])
                partidas_mes = reg_mes // 4

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown(f"""
                        <div class="gaming-card">
                            <div class="metric-label">Jugadores Activos Hoy</div>
                            <div class="metric-value" style="color: #58A6FF;">👥 {jugadores_hoy}</div>
                            <div style="font-size: 11px; color: #8B949E;">De {total_jugadores} registrados</div>
                        </div>
                    """, unsafe_allow_html=True)

                with c2:
                    st.markdown(f"""
                        <div class="gaming-card">
                            <div class="metric-label">Partidas Hoy</div>
                            <div class="metric-value" style="color: #3FB950;">🎲 {partidas_hoy}</div>
                            <div style="font-size: 11px; color: #8B949E;">{reg_hoy} jugadas de 4 entradas</div>
                        </div>
                    """, unsafe_allow_html=True)

                with c3:
                    st.markdown(f"""
                        <div class="gaming-card">
                            <div class="metric-label">Partidas (7 Días)</div>
                            <div class="metric-value" style="color: #D29922;">📅 {partidas_semana}</div>
                            <div style="font-size: 11px; color: #8B949E;">{reg_semana} jugadas tot.</div>
                        </div>
                    """, unsafe_allow_html=True)

                with c4:
                    st.markdown(f"""
                        <div class="gaming-card">
                            <div class="metric-label">Partidas (Mes)</div>
                            <div class="metric-value" style="color: #A371F7;">🏆 {partidas_mes}</div>
                            <div style="font-size: 11px; color: #8B949E;">Mes actual</div>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("---")
                st.markdown("### 📊 Partidas Completadas por Día (Últimos 7 Días)")
                df_partidas_semana = df_partidas[df_partidas["Fecha_dt"].dt.date >= hace_7_dias]
                
                if not df_partidas_semana.empty:
                    conteo_diario = df_partidas_semana.groupby("Fecha").size().reset_index(name="Jugadas")
                    conteo_diario["Partidas Completas"] = conteo_diario["Jugadas"] // 4
                    st.bar_chart(data=conteo_diario, x="Fecha", y="Partidas Completas", color="#3FB950")

        # TAB 2: REGISTRAR MOVIMIENTO (NUEVO / EXISTENTE INTERACTIVO)
        with tabs_admin[1]:
            st.markdown("### ➕ Registrar Nuevo Movimiento")
            
            opcion_cliente = st.radio("Cliente:", ["Existente", "➕ Nuevo"], horizontal=True)

            if opcion_cliente == "Existente":
                cliente_final = st.selectbox("Seleccionar Jugador:", clientes_existentes)
            else:
                cliente_final = st.text_input("Nombre del Nuevo Jugador:").strip().title()

            opciones_tipo = [
                "🟢 Saldo agregado (+)",
                "🔴 Partida jugada (-)",
                "🟡 Partida ganada (+)",
                "🔵 Reintegro (+)",
                "🟣 Retiro (-)"
            ]
            tipo_movimiento = st.selectbox("Tipo de Movimiento:", opciones_tipo)
            
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
                        st.toast(f"✅ Transacción guardada con éxito para {cliente_final}", icon="🎉")
                        st.session_state["monto_input"] = 0.0
                        st.session_state["detalle_input"] = ""
                        time.sleep(0.8)
                    st.rerun()

        # TAB 3: RULETA DIARIA DE PREMIOS (EXCLUSIVO ADMIN)
        with tabs_admin[2]:
            st.markdown("### 🎡 Control de Ruleta Diaria")
            if not df_movimientos.empty:
                df_jugadas_hoy = df_movimientos[(df_movimientos["Fecha"] == fecha_hoy_str) & (df_movimientos["Tipo"] == "🔴 Partida jugada (-)")]
                conteo = df_jugadas_hoy.groupby("Cliente").size().reset_index(name="Cant")
                calificados_list = conteo[conteo["Cant"] >= 3]["Cliente"].tolist()

                if len(calificados_list) > 0:
                    st.write(f"👥 **Participantes Calificados para Girar Today (≥3 jugadas):** {', '.join(calificados_list)}")
                    
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
                        
                        # Guardar ganador en la base de datos
                        hora_actual_str = datetime.now().strftime("%I:%M %p")
                        guardar_movimiento(fecha_hoy_str, hora_actual_str, ganador_final, "🟡 Partida ganada (+)", 0.0, "🎉 GANADOR RULETA DIARIA")
                        
                        placeholder.markdown(f"""
                            <div class="gaming-card" style="border-color: #238636; background: linear-gradient(135deg, #1C4429 0%, #111827 100%); padding: 35px;">
                                <div style="font-size: 16px; color: #3FB950; font-weight: 800;">🎉 ¡GANADOR DEL PREMIO EXTRA! 🎉</div>
                                <div style="font-size: 42px; font-weight: 900; color: #FFFFFF;">👑 {ganador_final} 👑</div>
                            </div>
                        """, unsafe_allow_html=True)
                        st.balloons()
                        st.toast(f"✅ Ganador registrado en Google Sheets", icon="💾")
                else:
                    st.info("⚠️ Aún no hay jugadores calificados para girar la ruleta hoy (requiere 3 o más partidas jugadas).")

        # TAB 4: CONSOLIDADO DE SALDOS E HISTORIAL COMPLETO
        with tabs_admin[3]:
            st.markdown("### 📊 CONSOLIDADO GENERAL DE SALDOS")
            if not df_movimientos.empty:
                df_calc_saldos = df_movimientos.copy()
                df_calc_saldos["Neto"] = df_calc_saldos.apply(calcular_neto, axis=1)

                saldos_df = df_calc_saldos.groupby("Cliente")["Neto"].sum().reset_index()
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
