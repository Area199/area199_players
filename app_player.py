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
# 1. BRANDING & UI AREA199 (CSS AGGIORNATO)
# ==============================================================================
def init_area199_ui():
    st.set_page_config(page_title="AREA199 | PLAYER HUB", page_icon="🩸", layout="centered")
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700;900&display=swap');
            .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Rajdhani', sans-serif; }
            
            /* BOTTONI: Testo Bianco, Bordo Rosso, Sfondo Nero */
            .stButton>button { 
                border: 2px solid #E20613 !important; 
                color: #FFFFFF !important; 
                font-weight: 800 !important; 
                background-color: #000000 !important;
                width: 100%; height: 50px;
                text-transform: uppercase;
                border-radius: 5px;
            }
            .stButton>button:hover { 
                background-color: #E20613 !important; 
                color: #FFFFFF !important; 
            }

            /* INPUT STYLE */
            div[data-baseweb="input"] > div { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
            input { color: white !important; }
        </style>
    """, unsafe_allow_html=True)

init_area199_ui()

# ==============================================================================
# 2. CORE: DATA UTILITIES
# ==============================================================================

def clean_float(val):
    """Converte stringhe con virgola o punto in float in modo sicuro"""
    if val is None or str(val).strip() == "": return 0.0
    try:
        return float(str(val).replace(',', '.').strip())
    except ValueError:
        return 0.0

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
        # 1. Ricerca Atleta
        df_p = pd.DataFrame(sh.worksheet("PLAYERS").get_all_records())
        player_info = None
        target_login = db_name.lower().strip()
        
        for _, row in df_p.iterrows():
            fn = f"{str(row['Nome'])} {str(row['Cognome'])}".lower().strip()
            rev_fn = f"{str(row['Cognome'])} {str(row['Nome'])}".lower().strip()
            if target_login == fn or target_login == rev_fn:
                player_info = row
                break
        
        if player_info is None: return None, None, None
        
        # 2. Ricerca Test
        df_t = pd.DataFrame(sh.worksheet("TEST_ARCHIVE").get_all_values())
        if not df_t.empty:
            df_t.columns = df_t.iloc[0]; df_t = df_t[1:]
            my_tests = df_t[df_t['ID_Atleta'].astype(str) == str(player_info['ID'])]
        else:
            my_tests = pd.DataFrame()
            
        # 3. Ricerca Target
        df_tgt = pd.DataFrame(sh.worksheet("ROLE_TARGETS").get_all_records())
        role_tgt = df_tgt[df_tgt['Ruolo'] == player_info['Ruolo']].iloc[0] if not df_tgt[df_tgt['Ruolo'] == player_info['Ruolo']].empty else None
        
        return player_info, my_tests, role_tgt
    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        return None, None, None

def get_ai_motivation(info, scores):
    try:
        client = openai.OpenAI(api_key=st.secrets.get("openai_key"))
        sys_prompt = f"Sei il Dott. Antonio Petruzzi, AREA199. Analizza questi score (0-99) di un {info['Ruolo']}: VEL:{scores[0]}, AGI:{scores[1]}, FIS:{scores[2]}, RES:{scores[3]}, TEC:{scores[4]}. Esalta i punti forti, incoraggia con rigore scientifico sui deboli. Max 50 parole."
        resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": sys_prompt}])
        return resp.choices[0].message.content
    except: return "Focus sulla prossima sessione. La scienza della performance non ammette distrazioni."

# ==============================================================================
# 3. RENDERING DASHBOARD
# ==============================================================================
if 'auth' not in st.session_state: st.session_state.auth = False

# Logo Fallback
if os.path.exists("logo.png"):
    st.image("logo.png", width=140)
else:
    st.markdown("<h2 style='color:#E20613; text-align:center;'>AREA 199 LAB</h2>", unsafe_allow_html=True)

if not st.session_state.auth:
    st.markdown("<h3 style='text-align:center;'>LOGIN ATLETA</h3>", unsafe_allow_html=True)
    with st.form("login"):
        n = st.text_input("Nome e Cognome")
        p = st.text_input("PIN Atleta", type="password")
        if st.form_submit_button("ACCEDI"):
            sh = get_db()
            records = sh.worksheet("ATHLETE_PINS").get_all_records()
            for r in records:
                if str(r.get('name')).strip().lower() == n.strip().lower() and str(r.get('pin')).replace(".0","") == p.strip():
                    info, tests, tgt = get_performance_and_targets(n)
                    if info is not None:
                        st.session_state.auth, st.session_state.data = True, (info, tests, tgt)
                        st.rerun()
            st.error("Credenziali Errate.")
else:
    info, tests, tgt = st.session_state.data
    
    # Inizializzazione sicura variabili
    target_scores = [75, 75, 75, 75, 75]
    current_scores = [50, 50, 50, 50, 50]
    
    if st.button("LOGOUT SESSIONE"): st.session_state.auth = False; st.rerun()

    if tests is not None and not tests.empty:
        last = tests.iloc[-1]
        
        # Mappatura Score con clean_float (Punto e Virgola gestiti)
        def score_map(val):
            v = clean_float(val)
            # Logica: se < 10 (tempi), inverti; se > 10 (misure), scala.
            return int(max(40, min(99, v * 10 if v < 10 else v / 2)))

        current_scores = [
            score_map(last.get('PAC_30m', 0)),
            score_map(last.get('AGI_Illin', 0)),
            score_map(last.get('PHY_Salto', 0)),
            score_map(last.get('STA_YoYo', 0)),
            score_map(last.get('TEC_Skill', 0))
        ]
        
        if tgt is not None:
            target_scores = [tgt.get('PAC_Target',75), tgt.get('AGI_Target',75), tgt.get('PHY_Target',75), tgt.get('STA_Target',75), tgt.get('TEC_Target',75)]
        
        ovr = int(sum(current_scores)/5)

        # SCUDO AREA199 BLU
        shield_html = f"""
        <div class="shield-main">
            <div class="ovr-header">
                <div class="ovr-val">{ovr}</div>
                <div class="ovr-pos">{str(info['Ruolo']).upper()[:3]}</div>
            </div>
            <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}" class="p-face">
            <div class="p-full-name">{info['Nome']}<br>{info['Cognome']}</div>
            <div class="stats-grid-shield">
                <div class="s-row"><span>VEL</span> {current_scores[0]}</div>
                <div class="s-row"><span>AGI</span> {current_scores[1]}</div>
                <div class="s-row"><span>FIS</span> {current_scores[2]}</div>
                <div class="s-row"><span>RES</span> {current_scores[3]}</div>
                <div class="s-row"><span>TEC</span> {current_scores[4]}</div>
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
            .ovr-header {{ position: absolute; top: 25px; left: 25px; text-align: left; }}
            .ovr-val {{ font-size: 55px; font-weight: 900; line-height: 0.8; }}
            .ovr-pos {{ font-size: 18px; color: #E20613; font-weight: bold; }}
            .p-face {{ width: 150px; height: 150px; object-fit: contain; margin-top: 25px; }}
            .p-full-name {{ font-size: 20px; font-weight: 900; text-transform: uppercase; margin: 10px 0; border-bottom: 2px solid #E20613; display: inline-block; padding-bottom: 5px; }}
            .stats-grid-shield {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 10px 40px; font-size: 16px; font-weight: bold; }}
            .s-row {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .s-row span {{ color: #E20613; }}
        </style>
        """
        st.markdown(shield_html, unsafe_allow_html=True)

        # COMMENTO AI
        st.markdown(f"""
        <div style="background:#111; padding:20px; border-radius:10px; border-left:5px solid #E20613; margin:25px 0;">
            <p style="color:#E20613; font-weight:900; margin-bottom:10px;">🧠 ANALISI DOTT. PETRUZZI:</p>
            <p style="font-style:italic; font-size:1.0em; line-height:1.4;">"{get_ai_motivation(info, current_scores)}"</p>
        </div>
        """, unsafe_allow_html=True)

        # RADAR GRANDE DUALE
        st.markdown("<h4 style='text-align:center;'>PERFORMANCE VS TARGET ELITE</h4>", unsafe_allow_html=True)
        cats = ['VEL','AGI','FIS','RES','TEC']
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=target_scores, theta=cats, fill='toself', name='Target Elite', line_color='#00FF00', opacity=0.3))
        fig.add_trace(go.Scatterpolar(r=current_scores, theta=cats, fill='toself', name='Attuale', line_color='#E20613'))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444")),
            paper_bgcolor='black', font_color='white', showlegend=False, height=500, margin=dict(t=50, b=50)
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.warning("Dati dei test non ancora disponibili per questo profilo.")
