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
# 1. BRANDING & UI AREA199 (RE-DESIGN)
# ==============================================================================
def init_area199_ui():
    st.set_page_config(page_title="AREA199 | PLAYER HUB", page_icon="🩸", layout="centered")
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700;900&display=swap');
            .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Rajdhani', sans-serif; }
            
            /* FIX PULSANTI: Nero con bordo e testo Rosso */
            .stButton>button { 
                border: 2px solid #E20613 !important; 
                color: #E20613 !important; 
                font-weight: 800 !important; 
                background-color: #000000 !important;
                width: 100%; height: 48px;
                text-transform: uppercase;
                transition: 0.3s;
            }
            .stButton>button:hover { 
                background-color: #E20613 !important; 
                color: #FFFFFF !important; 
            }

            /* INPUT STYLE */
            div[data-baseweb="input"] > div { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
            input { color: white !important; }
            label { color: #FFFFFF !important; font-weight: bold; }
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
        st.error(f"ERRORE CONNESSIONE DB: {e}")
        st.stop()

def get_performance_and_targets(db_name):
    try:
        sh = get_db()
        df_p = pd.DataFrame(sh.worksheet("PLAYERS").get_all_records())
        player_info = None
        target_login = db_name.lower()
        
        for _, row in df_p.iterrows():
            fn = f"{str(row['Nome'])} {str(row['Cognome'])}".lower()
            if target_login == fn or target_login == f"{str(row['Cognome'])} {str(row['Nome'])}".lower():
                player_info = row
                break
        if player_info is None: return None, None, None
        
        df_t = pd.DataFrame(sh.worksheet("TEST_ARCHIVE").get_all_values())
        df_t.columns = df_t.iloc[0]; df_t = df_t[1:]
        my_tests = df_t[df_t['ID_Atleta'] == str(player_info['ID'])]
        
        df_tgt = pd.DataFrame(sh.worksheet("ROLE_TARGETS").get_all_records())
        role_tgt = df_tgt[df_tgt['Ruolo'] == player_info['Ruolo']].iloc[0] if not df_tgt[df_tgt['Ruolo'] == player_info['Ruolo']].empty else None
        
        return player_info, my_tests, role_tgt
    except: return None, None, None

# ==============================================================================
# 3. AI ENGINE: DOTT. PETRUZZI INSIGHTS
# ==============================================================================
def get_ai_motivation(info, scores):
    try:
        api_key = st.secrets.get("openai_key")
        client = openai.OpenAI(api_key=api_key)
        sys_prompt = f"""
        Sei il Dott. Antonio Petruzzi, scienziato della performance AREA199. 
        Analizza questi score (0-99) di un {info['Ruolo']}: VEL:{scores[0]}, AGI:{scores[1]}, FIS:{scores[2]}, RES:{scores[3]}, TEC:{scores[4]}.
        1. Esalta i punti forti con tecnicismo. 
        2. Incoraggia a migliorare i punti deboli spiegando l'impatto sul campo.
        Sii brutale ma ispiratore. Massimo 50 parole.
        """
        resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": sys_prompt}])
        return resp.choices[0].message.content
    except: return "Focus totale sul prossimo blocco di lavoro. La scienza non mente."

# ==============================================================================
# 4. DASHBOARD & RENDERING
# ==============================================================================
if 'auth' not in st.session_state: st.session_state.auth = False

# LOGO INTEGRATO ALL'INTERNO
if os.path.exists("logo.png"):
    st.image("logo.png", width=140)

if not st.session_state.auth:
    st.markdown("<h3 style='text-align:center;'>PERFORMANCE LOGIN</h3>", unsafe_allow_html=True)
    with st.form("login"):
        n = st.text_input("Nome e Cognome")
        p = st.text_input("PIN Atleta", type="password")
        if st.form_submit_button("ENTRA NEL LAB"):
            sh = get_db()
            records = sh.worksheet("ATHLETE_PINS").get_all_records()
            for r in records:
                if str(r.get('name')).strip().lower() == n.strip().lower() and str(r.get('pin')).replace(".0","") == p.strip():
                    info, tests, tgt = get_performance_and_targets(n.strip().lower())
                    if info is not None:
                        st.session_state.auth, st.session_state.data = True, (info, tests, tgt)
                        st.rerun()
            st.error("Credenziali Errate.")
    
    with st.expander("Hai dimenticato il PIN?"):
        st.markdown('<center><a href="mailto:info@area199.com" style="color:#E20613;">Richiedi supporto tecnico</a></center>', unsafe_allow_html=True)

else:
    info, tests, tgt = st.session_state.data
    # INIZIALIZZAZIONE VARIABILI PER EVITARE NAMEERROR
    target_scores = [75, 75, 75, 75, 75] 
    current_scores = [60, 60, 60, 60, 60]
    
    if st.button("CHIUDI SESSIONE"): st.session_state.auth = False; st.rerun()

    if not tests.empty:
        last = tests.iloc[-1]
        def s(v): 
            try: return int(max(40, min(99, float(str(v).replace(',','.')) * (10 if float(str(v).replace(',','.')) < 10 else 0.5)))) 
            except: return 60
        
        current_scores = [s(last.get('PAC_30m',0)), s(last.get('AGI_Illin',0)), s(last.get('PHY_Salto',0)), s(last.get('STA_YoYo',0)), s(last.get('TEC_Skill',0))]
        if tgt is not None:
            target_scores = [tgt.get('PAC_Target',75), tgt.get('AGI_Target',75), tgt.get('PHY_Target',70), tgt.get('STA_Target',70), tgt.get('TEC_Target',75)]
        
        overall = int(sum(current_scores)/5)

        # SCUDO BLU CON NOME E COGNOME
        st.markdown(f"""
        <div class="fut-shield">
            <div class="ovr-box">
                <div class="val">{overall}</div>
                <div class="r-pos">{str(info['Ruolo']).upper()[:3]}</div>
            </div>
            <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}" class="fut-img">
            <div class="fullname">{info['Nome']}<br>{info['Cognome']}</div>
            <div class="stats-box">
                <div class="ln"><span>VEL</span> {current_scores[0]}</div>
                <div class="ln"><span>AGI</span> {current_scores[1]}</div>
                <div class="ln"><span>FIS</span> {current_scores[2]}</div>
                <div class="ln"><span>RES</span> {current_scores[3]}</div>
                <div class="ln"><span>TEC</span> {current_scores[4]}</div>
            </div>
        </div>
        <style>
            .fut-shield {{
                width: 300px; height: 460px; margin: auto; padding: 25px;
                background: linear-gradient(to bottom, #080c11 0%, #152248 40%, #0d1226 100%);
                clip-path: polygon(0% 0%, 100% 0%, 100% 85%, 50% 100%, 0% 85%);
                border-top: 3px solid #E20613; text-align: center; color: white; position: relative;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            }}
            .ovr-box {{ position: absolute; top: 25px; left: 25px; text-align: left; }}
            .val {{ font-size: 55px; font-weight: 900; line-height: 0.8; }}
            .r-pos {{ font-size: 18px; color: #E20613; font-weight: bold; }}
            .fut-img {{ width: 160px; height: 160px; object-fit: contain; margin-top: 25px; }}
            .fullname {{ font-size: 22px; font-weight: 900; text-transform: uppercase; line-height: 1; margin: 10px 0; border-bottom: 2px solid #E20613; display: inline-block; }}
            .stats-box {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px 45px; font-size: 16px; font-weight: bold; }}
            .ln {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .ln span {{ color: #E20613; }}
        </style>
        """, unsafe_allow_html=True)

        # AI COMMENTARY
        st.markdown(f"""
        <div style="background:#111; padding:15px; border-radius:10px; border-left:4px solid #E20613; margin:25px 0;">
            <p style="color:#E20613; font-weight:bold; margin-bottom:5px;">🧠 ANALYSIS DOTT. PETRUZZI:</p>
            <p style="font-style:italic; font-size:0.95em;">"{get_ai_motivation(info, current_scores)}"</p>
        </div>
        """, unsafe_allow_html=True)

        # RADAR GRANDE (DUALE)
        cats = ['VEL','AGI','FIS','RES','TEC']
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=target_scores, theta=cats, fill='toself', name='Target Elite', line_color='#00FF00', opacity=0.3))
        fig.add_trace(go.Scatterpolar(r=current_scores, theta=cats, fill='toself', name='Tua Performance', line_color='#E20613'))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444")),
            paper_bgcolor='black', font_color='white', showlegend=False, height=450, margin=dict(t=50, b=50)
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
