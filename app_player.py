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
# 1. BRANDING & UI AREA199 (CSS FIX)
# ==============================================================================
def init_area199_ui():
    st.set_page_config(page_title="AREA199 | PLAYER HUB", page_icon="🩸", layout="centered")
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700;900&display=swap');
            .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Rajdhani', sans-serif; }
            
            /* FIX BOTTONI: Scritta Bianca, Bordo Rosso, Sfondo Nero */
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

            /* INPUT STYLE */
            div[data-baseweb="input"] > div { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
            input { color: white !important; }
        </style>
    """, unsafe_allow_html=True)

init_area199_ui()

# ==============================================================================
# 2. UTILITIES & DATA ENGINE
# ==============================================================================

def clean_float(val):
    """Gestisce separatori decimali (virgola e punto)"""
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
        st.error("Errore Connessione Google Sheets.")
        st.stop()

def fetch_all_data(db_name):
    try:
        sh = get_db()
        # 1. Info Atleta da PLAYERS
        df_p = pd.DataFrame(sh.worksheet("PLAYERS").get_all_records())
        player_info = None
        target_login = db_name.lower().strip()
        
        for _, row in df_p.iterrows():
            fn = f"{str(row['Nome'])} {str(row['Cognome'])}".lower().strip()
            if target_login == fn or target_login == f"{str(row['Cognome'])} {str(row['Nome'])}".lower().strip():
                player_info = row
                break
        
        if player_info is None: return None, None, None
        
        # 2. Test da TEST_ARCHIVE
        data_t = sh.worksheet("TEST_ARCHIVE").get_all_values()
        df_t = pd.DataFrame(data_t[1:], columns=data_t[0])
        my_tests = df_t[df_t['ID_Atleta'].astype(str) == str(player_info['ID'])]
        
        # 3. Target da ROLE_TARGETS
        df_tgt = pd.DataFrame(sh.worksheet("ROLE_TARGETS").get_all_records())
        role_tgt = df_tgt[df_tgt['Ruolo'] == player_info['Ruolo']].iloc[0] if not df_tgt[df_tgt['Ruolo'] == player_info['Ruolo']].empty else None
        
        return player_info, my_tests, role_tgt
    except:
        return None, None, None

def get_ai_commentary(info, scores):
    try:
        api_key = st.secrets.get("openai_key")
        client = openai.OpenAI(api_key=api_key)
        prompt = f"Sei il Dott. Antonio Petruzzi. Analizza questi score (0-99) di un {info['Ruolo']}: VEL:{scores[0]}, AGI:{scores[1]}, FIS:{scores[2]}, RES:{scores[3]}, TEC:{scores[4]}. Esalta i punti forti e incoraggia sui punti deboli spiegando l'importanza in campo. Sii breve (max 60 parole) e motivante."
        resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": prompt}])
        return resp.choices[0].message.content
    except:
        return "Continua a lavorare con intensità. La performance è una scienza che richiede costanza."

# ==============================================================================
# 3. APP LOGIC
# ==============================================================================

if 'auth' not in st.session_state: st.session_state.auth = False

# Visualizzazione Logo
if os.path.exists("logo.png"):
    st.image("logo.png", width=130)
else:
    st.markdown("<h2 style='color:#E20613;'>AREA 199</h2>", unsafe_allow_html=True)

if not st.session_state.auth:
    st.subheader("Login Accesso Atleta")
    with st.form("login"):
        n = st.text_input("Inserisci Nome e Cognome")
        p = st.text_input("Il tuo PIN", type="password")
        if st.form_submit_button("ACCEDI"):
            sh = get_db()
            pins = sh.worksheet("ATHLETE_PINS").get_all_records()
            for r in pins:
                if str(r.get('name')).strip().lower() == n.strip().lower() and str(r.get('pin')).replace(".0","") == p.strip():
                    info, tests, tgt = fetch_all_data(n)
                    if info is not None:
                        st.session_state.auth, st.session_state.data = True, (info, tests, tgt)
                        st.rerun()
            st.error("Credenziali non valide.")
    
    with st.expander("Hai dimenticato il PIN?"):
        st.markdown('<center><a href="mailto:info@area199.com" style="color:#E20613; text-decoration:none;">Contatta lo Staff</a></center>', unsafe_allow_html=True)

else:
    info, tests, tgt = st.session_state.data
    
    # Inizializzazione sicura per prevenire NameError
    target_scores = [75, 75, 75, 75, 75]
    current_scores = [50, 50, 50, 50, 50]
    overall = 50
    
    if st.button("LOGOUT"): st.session_state.auth = False; st.rerun()

    if not tests.empty:
        last = tests.iloc[-1]
        
        # Mappatura Score (Qui usiamo il calcolo del Hub Coach per coerenza)
        def score_calc(val):
            v = clean_float(val)
            # Logica: 0-10 sec (Sprint) -> decrescente; >10 cm/liv (Fisico/Res) -> crescente
            if v < 10: return int(max(40, min(99, 100 - (v * 5)))) # Esempio Sprint 4.20 -> ~79
            return int(max(40, min(99, v / 1.5 if v > 100 else v * 2)))

        current_scores = [
            score_calc(last.get('PAC_30m')),
            score_calc(last.get('AGI_Illin')),
            score_calc(last.get('PHY_Salto')),
            score_calc(last.get('STA_YoYo')),
            score_calc(last.get('TEC_Skill'))
        ]
        
        if tgt is not None:
            target_scores = [
                clean_float(tgt.get('PAC_Target', 75)),
                clean_float(tgt.get('AGI_Target', 75)),
                clean_float(tgt.get('PHY_Target', 70)),
                clean_float(tgt.get('STA_Target', 70)),
                clean_float(tgt.get('TEC_Target', 75))
            ]
        
        overall = int(sum(current_scores)/5)

        # RENDERING SCUDO BLU AREA199
        st.markdown(f"""
        <div class="card-shield">
            <div class="ovr-header">
                <div class="val">{overall}</div>
                <div class="pos">{str(info['Ruolo']).upper()[:3]}</div>
            </div>
            <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}" class="p-img">
            <div class="p-name">{info['Nome']}<br>{info['Cognome']}</div>
            <div class="stats-grid">
                <div class="st-row"><span>VEL</span> {current_scores[0]}</div>
                <div class="st-row"><span>AGI</span> {current_scores[1]}</div>
                <div class="st-row"><span>FIS</span> {current_scores[2]}</div>
                <div class="st-row"><span>RES</span> {current_scores[3]}</div>
                <div class="st-row"><span>TEC</span> {current_scores[4]}</div>
            </div>
        </div>
        <style>
            .card-shield {{
                width: 300px; height: 460px; margin: 30px auto; padding: 25px;
                background: linear-gradient(to bottom, #080c11 0%, #152248 40%, #0d1226 100%);
                clip-path: polygon(0% 0%, 100% 0%, 100% 85%, 50% 100%, 0% 85%);
                border-top: 3px solid #E20613; text-align: center; color: white; position: relative;
                box-shadow: 0 15px 45px rgba(0,0,0,0.7);
            }}
            .ovr-header {{ position: absolute; top: 25px; left: 25px; text-align: left; }}
            .val {{ font-size: 55px; font-weight: 900; line-height: 0.8; }}
            .pos {{ font-size: 18px; color: #E20613; font-weight: bold; }}
            .p-img {{ width: 155px; height: 155px; object-fit: contain; margin-top: 25px; }}
            .p-name {{ font-size: 21px; font-weight: 900; text-transform: uppercase; line-height: 1; margin: 10px 0; border-bottom: 2px solid #E20613; display: inline-block; padding-bottom: 5px; }}
            .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px 40px; font-size: 16px; font-weight: bold; }}
            .st-row {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .st-row span {{ color: #E20613; }}
        </style>
        """, unsafe_allow_html=True)

        # AI COMMENTARY
        st.markdown(f"""
        <div style="background:#111; padding:20px; border-radius:10px; border-left:5px solid #E20613; margin:25px 0;">
            <p style="color:#E20613; font-weight:900; margin-bottom:10px;">🧠 ANALISI DOTT. PETRUZZI:</p>
            <p style="font-style:italic; font-size:1.0em;">"{get_ai_commentary(info, current_scores)}"</p>
        </div>
        """, unsafe_allow_html=True)

        # RADAR GRANDE (DUALE: PERFORMANCE VS TARGET VERDE)
                st.markdown("<h4 style='text-align:center;'>PERFORMANCE VS OBIETTIVO ELITE</h4>", unsafe_allow_html=True)
        cats = ['VEL','AGI','FIS','RES','TEC']
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=target_scores, theta=cats, fill='toself', name='Target Elite', line_color='#00FF00', opacity=0.3))
        fig.add_trace(go.Scatterpolar(r=current_scores, theta=cats, fill='toself', name='Tua Performance', line_color='#E20613'))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444")),
            paper_bgcolor='black', font_color='white', showlegend=False, height=500, margin=dict(t=50, b=50)
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.warning("Dati dei test non ancora disponibili.")
