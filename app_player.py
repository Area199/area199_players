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
            div[data-baseweb="input"] > div { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
            .stButton>button { border: 2px solid #E20613; color: #E20613; font-weight: 800; background: transparent; width: 100%; }
            .stButton>button:hover { background: #E20613; color: white; border-color: #E20613; }
        </style>
    """, unsafe_allow_html=True)

init_area199_ui()

# ==============================================================================
# 2. CORE: DATA RETRIEVAL & SMART MATCH
# ==============================================================================
@st.cache_resource
def get_db():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds).open("AREA199_DB")
    except Exception as e:
        st.error(f"ERRORE DB: {e}")
        st.stop()

def get_performance_and_targets(db_name):
    try:
        sh = get_db()
        # 1. Info Atleta
        df_p = pd.DataFrame(sh.worksheet("PLAYERS").get_all_records())
        player_info = None
        for _, row in df_p.iterrows():
            fullName = f"{str(row['Nome'])} {str(row['Cognome'])}".lower()
            if db_name in fullName or fullName in db_name:
                player_info = row
                break
        if player_info is None: return None, None, None
        
        # 2. Test
        df_t = pd.DataFrame(sh.worksheet("TEST_ARCHIVE").get_all_values())
        df_t.columns = df_t.iloc[0]; df_t = df_t[1:]
        my_tests = df_t[df_t['ID_Atleta'] == str(player_info['ID'])]
        
        # 3. Targets di Ruolo
        df_tgt = pd.DataFrame(sh.worksheet("ROLE_TARGETS").get_all_records())
        role_tgt = df_tgt[df_tgt['Ruolo'] == player_info['Ruolo']].iloc[0] if not df_tgt[df_tgt['Ruolo'] == player_info['Ruolo']].empty else None
        
        return player_info, my_tests, role_tgt
    except: return None, None, None

# ==============================================================================
# 3. AI ENGINE: DOTT. PETRUZZI INSIGHTS
# ==============================================================================
def get_ai_motivation(info, scores):
    try:
        client = openai.OpenAI(api_key=st.secrets["openai_key"])
        prompt = f"""
        Sei il Dott. Antonio Petruzzi, Human Performance Scientist. 
        Analizza questi score (0-99) per un {info['Ruolo']}: 
        VEL:{scores[0]}, AGI:{scores[1]}, FIS:{scores[2]}, RES:{scores[3]}, TEC:{scores[4]}.
        Scrivi un commento brevissimo e brutale sui pregi e incoraggia per i difetti. 
        Massimo 50 parole. Stile motivazionale elite.
        """
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": prompt}])
        return response.choices[0].message.content
    except:
        return "Continua a spingere. La performance è una scienza, la costanza è la tua arma."

# ==============================================================================
# 4. RENDERING & DASHBOARD
# ==============================================================================
if 'auth' not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    # --- LOGIN SCREEN ---
    if os.path.exists("logo.png"): st.image("logo.png", width=120)
    with st.form("login_atleta"):
        n = st.text_input("Nome e Cognome")
        p = st.text_input("PIN Atleta", type="password")
        if st.form_submit_button("ENTRA NEL LAB"):
            sh = get_db()
            records = sh.worksheet("ATHLETE_PINS").get_all_records()
            for r in records:
                if str(r.get('name')).strip().lower() == n.strip().lower() and str(r.get('pin')).replace(".0","") == p.strip():
                    info, tests, tgt = get_performance_and_targets(n.strip().lower())
                    if info is not None:
                        st.session_state.auth = True
                        st.session_state.data = (info, tests, tgt)
                        st.rerun()
            st.error("Credenziali non valide.")
else:
    info, tests, tgt = st.session_state.data
    if st.button("CHIUDI SESSIONE"): st.session_state.auth = False; st.rerun()

    if not tests.empty:
        last = tests.iloc[-1]
        def s(v): 
            try: return int(max(40, min(99, float(str(v).replace(',','.')) * (10 if float(str(v).replace(',','.')) < 10 else 0.5)))) 
            except: return 60
        
        current_scores = [s(last.get('PAC_30m',0)), s(last.get('AGI_Illin',0)), s(last.get('PHY_Salto',0)), s(last.get('STA_YoYo',0)), s(last.get('TEC_Skill',0))]
        target_scores = [tgt['PAC_Target'], tgt['AGI_Target'], tgt['PHY_Target'], tgt['STA_Target'], tgt['TEC_Target']] if tgt is not None else [75]*5
        overall = int(sum(current_scores)/5)

        # HTML CARD SCUDO BLU (NOME + COGNOME)
        card_shield = f"""
        <div class="shield-container">
            <div class="top-data">
                <div class="ovr">{overall}</div>
                <div class="pos">{str(info['Ruolo']).upper()[:3]}</div>
            </div>
            <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}" class="p-img">
            <div class="p-name">{info['Nome']}<br>{info['Cognome']}</div>
            <div class="stats-grid">
                <div class="s-item"><span>VEL</span> {current_scores[0]}</div>
                <div class="s-item"><span>AGI</span> {current_scores[1]}</div>
                <div class="s-item"><span>FIS</span> {current_scores[2]}</div>
                <div class="s-item"><span>RES</span> {current_scores[3]}</div>
                <div class="s-item"><span>TEC</span> {current_scores[4]}</div>
            </div>
        </div>
        <style>
            .shield-container {{
                font-family: 'Rajdhani', sans-serif; width: 300px; height: 460px;
                background: linear-gradient(to bottom, #080c11 0%, #152248 40%, #0d1226 100%);
                clip-path: polygon(0% 0%, 100% 0%, 100% 85%, 50% 100%, 0% 85%);
                border-top: 3px solid #E20613; margin: auto; text-align: center; color: white; position: relative;
            }}
            .top-data {{ position: absolute; top: 25px; left: 25px; text-align: left; }}
            .ovr {{ font-size: 55px; font-weight: 900; line-height: 0.8; }}
            .pos {{ font-size: 18px; color: #E20613; font-weight: bold; }}
            .p-img {{ width: 160px; height: 160px; object-fit: contain; margin-top: 25px; }}
            .p-name {{ font-size: 22px; font-weight: 900; text-transform: uppercase; line-height: 1; margin: 10px 0; border-bottom: 1px solid #E20613; display: inline-block; padding-bottom: 5px; }}
            .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px 45px; font-size: 16px; font-weight: bold; }}
            .s-item {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .s-item span {{ color: #E20613; }}
        </style>
        """
        st.markdown(card_shield, unsafe_allow_html=True)

        # AI INSIGHTS
        st.markdown(f"""
        <div style="background:#111; padding:15px; border-radius:10px; border-left:4px solid #E20613; margin:20px 0;">
            <p style="color:#E20613; font-weight:bold; margin-bottom:5px;">🧠 DOTT. PETRUZZI ANALYSIS:</p>
            <p style="font-style:italic; font-size:0.95em;">"{get_ai_motivation(info, current_scores)}"</p>
        </div>
        """, unsafe_allow_html=True)

        # RADAR DUAL (TARGET VERDE + PERFORMANCE ROSSA)
        fig = go.Figure()
        cats = ['VEL','AGI','FIS','RES','TEC']
        # Trace Target (Verde)
        fig.add_trace(go.Scatterpolar(r=target_scores, theta=cats, fill='toself', name='Target Elite', line_color='#00FF00', opacity=0.2))
        # Trace Attuale (Rosso/Bianco)
        fig.add_trace(go.Scatterpolar(r=current_scores, theta=cats, fill='toself', name='Tua Performance', line_color='#E20613'))
        
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444")), paper_bgcolor='black', font_color='white', showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
