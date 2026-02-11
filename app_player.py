import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import math
import time
import urllib.parse
import os

# ==============================================================================
# 1. INIZIALIZZAZIONE BRANDING AREA199
# ==============================================================================
def init_area199_ui():
    st.set_page_config(page_title="AREA199 | PLAYER HUB", page_icon="🩸", layout="centered")
    st.markdown("""
        <style>
            .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Helvetica', sans-serif; }
            input { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
            .stButton>button { border: 2px solid #E20613; color: #E20613; font-weight: 800; background: transparent; width: 100%; }
            .stButton>button:hover { background: #E20613; color: white; }
            .stAlert { background-color: #1a1a1a; border-left: 5px solid #E20613; color: white; }
        </style>
    """, unsafe_allow_html=True)

init_area199_ui()

# ==============================================================================
# 2. CORE: CONNESSIONE E LOGICA SMART MATCH
# ==============================================================================

@st.cache_resource
def get_db():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds).open("AREA199_DB")
    except Exception as e:
        st.error(f"Errore Critico DB: {e}")
        st.stop()

def check_login(name_in, pin_in):
    try:
        sh = get_db()
        records = sh.worksheet("ATHLETE_PINS").get_all_records()
        target_n = str(name_in).strip().lower()
        target_p = str(pin_in).strip().replace(".0", "")
        
        for r in records:
            db_n = str(r.get('name') or '').strip().lower()
            db_p = str(r.get('pin') or '').strip().replace(".0", "")
            if db_n == target_n and db_p == target_p: return db_n
        return None
    except: return None

def get_performance_data(db_name):
    try:
        sh = get_db()
        # Recupero ID da PLAYERS
        df_p = pd.DataFrame(sh.worksheet("PLAYERS").get_all_records())
        found_id = None
        player_info = None
        
        for _, row in df_p.iterrows():
            fullName = f"{str(row['Nome'])} {str(row['Cognome'])}".lower()
            if db_name in fullName or fullName in db_name:
                found_id = str(row['ID'])
                player_info = row
                break
        
        if not found_id: return None, None
        
        # Recupero Test
        wks_t = sh.worksheet("TEST_ARCHIVE")
        data_t = wks_t.get_all_values()
        df_t = pd.DataFrame(data_t[1:], columns=data_t[0])
        my_tests = df_t[df_t['ID_Atleta'] == found_id]
        
        return player_info, my_tests
    except: return None, None

# ==============================================================================
# 3. UI RENDERING
# ==============================================================================

if 'auth' not in st.session_state: st.session_state.auth = False

# --- LOGO ---
if os.path.exists("logo.png"):
    st.image("logo.png", width=150)
else:
    st.markdown("<h1 style='color:#E20613;'>AREA 199</h1>", unsafe_allow_html=True)

# --- LOGIN ---
if not st.session_state.auth:
    with st.form("login"):
        n = st.text_input("Nome e Cognome")
        p = st.text_input("PIN", type="password")
        if st.form_submit_button("ENTRA NEL LAB"):
            match = check_login(n, p)
            if match:
                info, tests = get_performance_data(match)
                if info is not None:
                    st.session_state.auth = True
                    st.session_state.data = (info, tests)
                    st.rerun()
                else: st.error("Atleta non trovato nel Database PLAYERS.")
            else: st.error("Credenziali Errate.")
    
    # Recupero PIN
    with st.expander("Hai dimenticato il PIN?"):
        safe_mail = urllib.parse.quote("info@area199.com")
        safe_sub = urllib.parse.quote("Recupero PIN Atleta")
        st.markdown(f'<a href="mailto:{safe_mail}?subject={safe_sub}" style="color:#E20613;">Contatta il Dott. Petruzzi</a>', unsafe_allow_html=True)

# --- DASHBOARD ---
else:
    info, tests = st.session_state.data
    if st.button("LOGOUT"):
        st.session_state.auth = False
        st.rerun()

    if tests.empty:
        st.warning("Nessun test disponibile.")
    else:
        last = tests.iloc[-1]
        
        # Calcolo Score Placeholder
        def s(v): 
            try: return int(max(40, min(99, float(str(v).replace(',','.')) * 10 if float(str(v).replace(',','.')) < 10 else float(str(v).replace(',','.')) / 2))) 
            except: return 50
        
        scores = [s(last.get('PAC_30m', 0)), s(last.get('AGI_Illin', 0)), s(last.get('PHY_Salto', 0)), s(last.get('STA_YoYo', 0)), s(last.get('TEC_Skill', 0))]
        avg = int(sum(scores)/5)

        # CARD HTML
        card = f"""
        <div style="background: linear-gradient(145deg, #111, #000); border: 2px solid #E20613; border-radius: 15px; padding: 25px; text-align: center; max-width: 320px; margin: auto; box-shadow: 0 10px 30px rgba(226, 6, 19, 0.3);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 48px; font-weight: 900; color: #E20613;">{avg}</span>
                <span style="font-weight: bold; color: #888;">{str(info['Ruolo']).upper()[:3]}</span>
            </div>
            <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}" style="width: 140px; height: 140px; object-fit: contain; margin: 15px 0;">
            <div style="font-size: 24px; font-weight: 900; text-transform: uppercase; border-bottom: 2px solid #E20613; padding-bottom: 5px;">{info['Cognome']}</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 20px; text-align: left; font-weight: bold; font-size: 14px;">
                <div>VEL <span style="color:#E20613;">{scores[0]}</span></div>
                <div>AGI <span style="color:#E20613;">{scores[1]}</span></div>
                <div>FIS <span style="color:#E20613;">{scores[2]}</span></div>
                <div>RES <span style="color:#E20613;">{scores[3]}</span></div>
                <div>TEC <span style="color:#E20613;">{scores[4]}</span></div>
                <div>ALL <span style="color:#888;">{avg}</span></div>
            </div>
            <div style="font-size: 10px; color: #444; margin-top: 15px;">DATA TEST: {last['Data']}</div>
        </div>
        """
        st.markdown(card, unsafe_allow_html=True)

        # RADAR
        fig = go.Figure(data=go.Scatterpolar(r=scores, theta=['VEL','AGI','FIS','RES','TEC'], fill='toself', line_color='#E20613'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), paper_bgcolor='black', font_color='white', showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
