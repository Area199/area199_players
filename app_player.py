import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import math
import urllib.parse
import os

# ==============================================================================
# 1. BRANDING & UI AREA199
# ==============================================================================
def init_area199_ui():
    st.set_page_config(page_title="AREA199 | PLAYER HUB", page_icon="🩸", layout="centered")
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700;900&display=swap');
            .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Rajdhani', sans-serif; }
            div[data-baseweb="input"] > div { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
            .stButton>button { border: 2px solid #E20613; color: #E20613; font-weight: 800; background: transparent; width: 100%; height: 45px; }
            .stButton>button:hover { background: #E20613; color: white; border-color: #E20613; }
        </style>
    """, unsafe_allow_html=True)

init_area199_ui()

# ==============================================================================
# 2. CORE: SISTEMA DI AUTENTICAZIONE SMART
# ==============================================================================
@st.cache_resource
def get_db():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds).open("AREA199_DB")
    except Exception as e:
        st.error(f"ERRORE CONNESSIONE DB: {e}")
        st.stop()

def check_login(name_in, pin_in):
    try:
        sh = get_db()
        records = sh.worksheet("ATHLETE_PINS").get_all_records()
        tn = str(name_in).strip().lower()
        tp = str(pin_in).strip().replace(".0", "")
        for r in records:
            db_n = str(r.get('name') or '').strip().lower()
            db_p = str(r.get('pin') or '').strip().replace(".0", "")
            if db_n == tn and db_p == tp: return db_n
        return None
    except: return None

def get_performance_data(db_name):
    try:
        sh = get_db()
        df_p = pd.DataFrame(sh.worksheet("PLAYERS").get_all_records())
        found_id, player_info = None, None
        for _, row in df_p.iterrows():
            fullName = f"{str(row['Nome'])} {str(row['Cognome'])}".lower()
            if db_name in fullName or fullName in db_name:
                found_id, player_info = str(row['ID']), row
                break
        if not found_id: return None, None
        wks_t = sh.worksheet("TEST_ARCHIVE")
        data_t = wks_t.get_all_values()
        df_t = pd.DataFrame(data_t[1:], columns=data_t[0])
        return player_info, df_t[df_t['ID_Atleta'] == found_id]
    except: return None, None

# ==============================================================================
# 3. INTERFACCIA E RENDERING SCUDO (BLU)
# ==============================================================================
if 'auth' not in st.session_state: st.session_state.auth = False

if os.path.exists("logo.png"):
    st.image("logo.png", width=120)
else:
    st.markdown("<h2 style='color:#E20613;'>Dott. Antonio Petruzzi | AREA199</h2>", unsafe_allow_html=True)

if not st.session_state.auth:
    with st.form("login_lab"):
        n = st.text_input("Inserisci Nome e Cognome")
        p = st.text_input("PIN Atleta", type="password")
        if st.form_submit_button("ACCEDI AL PROFILO"):
            match = check_login(n, p)
            if match:
                info, tests = get_performance_data(match)
                if info is not None:
                    st.session_state.auth = True
                    st.session_state.data = (info, tests)
                    st.rerun()
                else: st.error("Atleta non trovato nel Database PLAYERS.")
            else: st.error("Accesso Negato: Nome o PIN errati.")
    
    with st.expander("Richiedi Assistenza PIN"):
        safe_mail = urllib.parse.quote("info@area199.com")
        st.markdown(f'<div style="text-align:center;"><a href="mailto:{safe_mail}" style="color:#E20613; text-decoration:none; font-weight:bold;">📧 INVIA RICHIESTA EMAIL</a></div>', unsafe_allow_html=True)

else:
    info, tests = st.session_state.data
    if st.button("CHIUDI SESSIONE"):
        st.session_state.auth = False
        st.rerun()

    if tests.empty:
        st.warning("Dati non ancora elaborati per questo profilo.")
    else:
        last = tests.iloc[-1]
        def s(v): 
            try: return int(max(40, min(99, float(str(v).replace(',','.')) * (10 if float(str(v).replace(',','.')) < 10 else 0.5)))) 
            except: return 60
        
        scores = [s(last.get('PAC_30m',0)), s(last.get('AGI_Illin',0)), s(last.get('PHY_Salto',0)), s(last.get('STA_YoYo',0)), s(last.get('TEC_Skill',0))]
        overall = int(sum(scores)/5)

        # HTML CARD SCUDO BLU AREA199
        card_shield = f"""
        <div class="fut-card-shield">
            <div class="top-section">
                <div class="rating">{overall}</div>
                <div class="pos">{str(info['Ruolo']).upper()[:3]}</div>
            </div>
            <div class="image-section">
                <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}">
            </div>
            <div class="name-section">{info['Cognome']}</div>
            <div class="stats-section">
                <div class="stat"><span>VEL</span> {scores[0]}</div>
                <div class="stat"><span>AGI</span> {scores[1]}</div>
                <div class="stat"><span>FIS</span> {scores[2]}</div>
                <div class="stat"><span>RES</span> {scores[3]}</div>
                <div class="stat"><span>TEC</span> {scores[4]}</div>
                <div class="stat" style="color:#E20613;"><span>OVR</span> {overall}</div>
            </div>
        </div>

        <style>
            .fut-card-shield {{
                font-family: 'Rajdhani', sans-serif;
                width: 300px; height: 440px;
                background: linear-gradient(to bottom, #080c11 0%, #152248 40%, #0d1226 100%);
                clip-path: polygon(0% 0%, 100% 0%, 100% 85%, 50% 100%, 0% 85%);
                border-top: 3px solid #E20613;
                margin: 20px auto; color: white; text-align: center;
                position: relative; padding: 20px;
                box-shadow: 0 15px 35px rgba(0,0,0,0.5);
            }}
            .top-section {{ position: absolute; top: 30px; left: 25px; text-align: left; }}
            .rating {{ font-size: 50px; font-weight: 900; line-height: 0.8; color: #FFFFFF; }}
            .pos {{ font-size: 18px; font-weight: bold; color: #E20613; }}
            .image-section img {{ width: 160px; height: 160px; object-fit: contain; margin-top: 20px; }}
            .name-section {{ font-size: 26px; font-weight: 900; text-transform: uppercase; margin-top: 5px; border-bottom: 2px solid #E20613; display: inline-block; padding: 0 10px; }}
            .stats-section {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 20px 40px; font-weight: bold; font-size: 16px; }}
            .stat {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .stat span {{ color: #E20613; font-weight: 800; }}
        </style>
        """
        st.markdown(card_shield, unsafe_allow_html=True)

        # RADAR CHART
        fig = go.Figure(data=go.Scatterpolar(r=scores, theta=['VEL','AGI','FIS','RES','TEC'], fill='toself', line_color='#E20613', fillcolor='rgba(226, 6, 19, 0.3)'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#333")), paper_bgcolor='black', font_color='white', height=300, margin=dict(t=30, b=30))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
