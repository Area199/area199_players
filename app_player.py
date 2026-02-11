import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import math
import urllib.parse
import os
import openai

# ==============================================================================
# 1. BRANDING & UI AREA199
# ==============================================================================
def init_area199_ui():
    st.set_page_config(page_title="AREA199 | PLAYER HUB", page_icon="🩸", layout="centered")
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700;900&display=swap');
            .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Rajdhani', sans-serif; }
            
            .stButton>button { 
                border: 2px solid #E20613 !important; 
                color: #FFFFFF !important; 
                font-weight: 800 !important; 
                background-color: #000000 !important;
                width: 100%; height: 50px;
                text-transform: uppercase;
                border-radius: 5px;
            }
            .stButton>button:hover { background-color: #E20613 !important; color: #FFFFFF !important; }

            div[data-baseweb="input"] > div { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
            input { color: white !important; }
        </style>
    """, unsafe_allow_html=True)

init_area199_ui()

# ==============================================================================
# 2. DATA UTILITIES
# ==============================================================================
def clean_float(val):
    if val is None or str(val).strip() == "": return 0.0
    try:
        return float(str(val).replace(',', '.').strip())
    except:
        return 0.0

@st.cache_resource
def get_db():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds).open("AREA199_DB")
    except:
        st.error("Connessione DB fallita.")
        st.stop()

def get_full_data(db_name):
    try:
        sh = get_db()
        df_p = pd.DataFrame(sh.worksheet("PLAYERS").get_all_records())
        player_info = None
        target_login = db_name.lower().strip()
        
        for _, row in df_p.iterrows():
            name_check = f"{str(row['Nome'])} {str(row['Cognome'])}".lower().strip()
            rev_check = f"{str(row['Cognome'])} {str(row['Nome'])}".lower().strip()
            if target_login == name_check or target_login == rev_check:
                player_info = row
                break
        
        if player_info is None: return None, None, None
        
        data_t = sh.worksheet("TEST_ARCHIVE").get_all_values()
        df_t = pd.DataFrame(data_t[1:], columns=data_t[0])
        my_tests = df_t[df_t['ID_Atleta'].astype(str) == str(player_info['ID'])]
        
        df_tgt = pd.DataFrame(sh.worksheet("ROLE_TARGETS").get_all_records())
        role_tgt = df_tgt[df_tgt['Ruolo'] == player_info['Ruolo']].iloc[0] if not df_tgt[df_tgt['Ruolo'] == player_info['Ruolo']].empty else None
        
        return player_info, my_tests, role_tgt
    except:
        return None, None, None

def get_ai_feedback(info, scores):
    try:
        client = openai.OpenAI(api_key=st.secrets.get("openai_key"))
        prompt = f"Sei il Dott. Petruzzi, AREA199. Atleta: {info['Nome']} {info['Cognome']} ({info['Ruolo']}). Score: VEL:{scores[0]}, AGI:{scores[1]}, FIS:{scores[2]}, RES:{scores[3]}, TEC:{scores[4]}. Analizza punti forti e deboli con rigore scientifico e incoraggiamento. Max 60 parole."
        resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": prompt}])
        return resp.choices[0].message.content
    except:
        return "Performance analizzata. Mantieni l'intensità elevata nella prossima sessione."

# ==============================================================================
# 3. RENDERING
# ==============================================================================
if 'auth' not in st.session_state: st.session_state.auth = False

if os.path.exists("logo.png"):
    st.image("logo.png", width=140)
else:
    st.markdown("<h2 style='color:#E20613;'>AREA 199</h2>", unsafe_allow_html=True)

if not st.session_state.auth:
    with st.form("login_atleta"):
        user_name = st.text_input("Nome e Cognome")
        user_pin = st.text_input("PIN Atleta", type="password")
        if st.form_submit_button("ENTRA"):
            sh = get_db()
            records = sh.worksheet("ATHLETE_PINS").get_all_records()
            for r in records:
                if str(r.get('name')).strip().lower() == user_name.strip().lower() and str(r.get('pin')).replace(".0","") == user_pin.strip():
                    info, tests, tgt = get_full_data(user_name)
                    if info is not None:
                        st.session_state.auth, st.session_state.data = True, (info, tests, tgt)
                        st.rerun()
            st.error("Credenziali Errate.")
else:
    info, tests, tgt = st.session_state.data
    target_scores, current_scores, overall = [75]*5, [50]*5, 50
    
    if st.button("LOGOUT"): st.session_state.auth = False; st.rerun()

    if tests is not None and not tests.empty:
        last_test = tests.iloc[-1]
        
        def map_score(val):
            v = clean_float(val)
            if v < 10: return int(max(40, min(99, 100 - (v * 5))))
            return int(max(40, min(99, v / 1.5 if v > 100 else v * 2)))

        current_scores = [map_score(last_test.get('PAC_30m')), map_score(last_test.get('AGI_Illin')), map_score(last_test.get('PHY_Salto')), map_score(last_test.get('STA_YoYo')), map_score(last_test.get('TEC_Skill'))]
        if tgt is not None:
            target_scores = [clean_float(tgt.get('PAC_Target')), clean_float(tgt.get('AGI_Target')), clean_float(tgt.get('PHY_Target')), clean_float(tgt.get('STA_Target')), clean_float(tgt.get('TEC_Target'))]
        
        overall = int(sum(current_scores)/5)

        st.markdown(f"""
        <div class="shield-main">
            <div class="header-stats">
                <div class="val-ovr">{overall}</div>
                <div class="val-pos">{str(info['Ruolo']).upper()[:3]}</div>
            </div>
            <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}" class="face-img">
            <div class="full-name-box">{info['Nome']}<br>{info['Cognome']}</div>
            <div class="grid-stats">
                <div class="grid-row"><span>VEL</span> {current_scores[0]}</div>
                <div class="grid-row"><span>AGI</span> {current_scores[1]}</div>
                <div class="grid-row"><span>FIS</span> {current_scores[2]}</div>
                <div class="grid-row"><span>RES</span> {current_scores[3]}</div>
                <div class="grid-row"><span>TEC</span> {current_scores[4]}</div>
            </div>
        </div>
        <style>
            .shield-main {{
                width: 300px; height: 460px; margin: 30px auto; padding: 25px;
                background: linear-gradient(to bottom, #080c11 0%, #152248 40%, #0d1226 100%);
                clip-path: polygon(0% 0%, 100% 0%, 100% 85%, 50% 100%, 0% 85%);
                border-top: 3px solid #E20613; text-align: center; color: white; position: relative;
                box-shadow: 0 15px 40px rgba(0,0,0,0.6);
            }}
            .header-stats {{ position: absolute; top: 25px; left: 25px; text-align: left; }}
            .val-ovr {{ font-size: 55px; font-weight: 900; line-height: 0.8; }}
            .val-pos {{ font-size: 18px; color: #E20613; font-weight: bold; }}
            .face-img {{ width: 155px; height: 155px; object-fit: contain; margin-top: 25px; }}
            .full-name-box {{ font-size: 21px; font-weight: 900; text-transform: uppercase; margin: 10px 0; border-bottom: 2px solid #E20613; display: inline-block; padding-bottom: 5px; }}
            .grid-stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px 40px; font-size: 16px; font-weight: bold; }}
            .grid-row {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .grid-row span {{ color: #E20613; }}
        </style>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background:#111; padding:20px; border-radius:10px; border-left:5px solid #E20613; margin:25px 0;">
            <p style="color:#E20613; font-weight:900; margin-bottom:10px;">🧠 ANALISI DOTT. PETRUZZI:</p>
            <p style="font-style:italic; font-size:1.0em;">"{get_ai_feedback(info, current_scores)}"</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<h4 style='text-align:center;'>PERFORMANCE VS OBIETTIVO ELITE</h4>", unsafe_allow_html=True)
        categories = ['VEL','AGI','FIS','RES','TEC']
        radar_fig = go.Figure()
        radar_fig.add_trace(go.Scatterpolar(r=target_scores, theta=categories, fill='toself', name='Target Elite', line_color='#00FF00', opacity=0.3))
        radar_fig.add_trace(go.Scatterpolar(r=current_scores, theta=categories, fill='toself', name='Tua Performance', line_color='#E20613'))
        radar_fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444")),
            paper_bgcolor='black', font_color='white', showlegend=False, height=500, margin=dict(t=50, b=50)
        )
        st.plotly_chart(radar_fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.warning("Dati non disponibili.")
