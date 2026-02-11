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
# 1. INIZIALIZZAZIONE BRANDING & UI AREA199
# ==============================================================================
def init_area199_ui():
    st.set_page_config(page_title="AREA199 | PLAYER HUB", page_icon="🩸", layout="centered")
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700;900&display=swap');
            .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Rajdhani', sans-serif; }
            
            /* STILE BOTTONI AREA199 */
            .stButton>button { 
                border: 2px solid #E20613 !important; color: #FFFFFF !important; 
                font-weight: 800 !important; background-color: #E20613 !important;
                width: 100%; height: 45px; text-transform: uppercase; border-radius: 5px;
                transition: 0.3s;
            }
            .stButton>button:hover { background-color: #b1050f !important; border-color: #b1050f !important; }

            /* INPUT STYLE */
            div[data-baseweb="input"] > div { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
            input { color: white !important; }
            label { color: #FFFFFF !important; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

init_area199_ui()

# ==============================================================================
# 2. MOTORE DI CALCOLO SCIENTIFICO (ALLINEATO HUB COACH)
# ==============================================================================
def clean_num(val):
    """Pulisce i dati gestendo virgole e formati non numerici"""
    if val is None or str(val).strip() in ["", "0", "None"]: return 0.0
    try:
        return float(str(val).replace(',', '.').strip())
    except:
        return 0.0

def calculate_dynamic_score(test_col_name, raw_value, birth_year, df_all_tests, lower_is_better=False):
    """Calcola il punteggio 30-99 basato sulla distribuzione statistica Z-Score"""
    val = clean_num(raw_value)
    if val <= 0 or df_all_tests.empty: return 40
    
    try:
        actual_col = next((c for c in df_all_tests.columns if c.lower() == test_col_name.lower()), None)
        if not actual_col: return 60
        
        # Filtro Coorte d'età
        df_all_tests['Anno_Rif'] = pd.to_numeric(df_all_tests['Anno_Rif'], errors='coerce')
        cohort = df_all_tests[(df_all_tests['Anno_Rif'] >= birth_year - 2) & (df_all_tests['Anno_Rif'] <= birth_year + 2)]
        if len(cohort) < 3: cohort = df_all_tests

        # Calcolo Statistico
        values = pd.to_numeric(cohort[actual_col].astype(str).str.replace(',', '.'), errors='coerce').dropna()
        values = values[values > 0].tolist()
        
        if len(values) < 2: return 65
        
        series = pd.Series(values)
        mu, sigma = series.mean(), series.std()
        if sigma == 0: return 70
        
        z = (val - mu) / sigma
        if lower_is_better: z = -z
        
        percentile = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        return int(max(30, min(99, 30 + (percentile * 69))))
    except:
        return 50

# ==============================================================================
# 3. ACCESSO DATI GOOGLE SHEETS
# ==============================================================================
@st.cache_resource
def get_db():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], 
            ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
        return gspread.authorize(creds).open("AREA199_DB")
    except Exception as e:
        st.error(f"Errore DB: {e}")
        st.stop()

def fetch_player_payload(name_query):
    """Recupera tutti i dati dell'atleta e lo storico test"""
    try:
        sh = get_db()
        df_p = pd.DataFrame(sh.worksheet("PLAYERS").get_all_records())
        p_info = None
        q = name_query.lower().strip()
        for _, row in df_p.iterrows():
            fn = f"{str(row['Nome'])} {str(row['Cognome'])}".lower().strip()
            if q == fn or q == f"{str(row['Cognome'])} {str(row['Nome'])}".lower().strip():
                p_info = row; break
        if p_info is None: return None
        
        wks_t = sh.worksheet("TEST_ARCHIVE")
        data_t = wks_t.get_all_values()
        df_t = pd.DataFrame(data_t[1:], columns=data_t[0])
        
        df_tgt = pd.DataFrame(sh.worksheet("ROLE_TARGETS").get_all_records())
        tgt = df_tgt[df_tgt['Ruolo'] == p_info['Ruolo']].iloc[0] if not df_tgt[df_tgt['Ruolo'] == p_info['Ruolo']].empty else None
        
        return {
            "info": p_info, 
            "my_tests": df_t[df_t['ID_Atleta'].astype(str) == str(p_info['ID'])], 
            "targets": tgt, 
            "all_tests": df_t
        }
    except:
        return None

# ==============================================================================
# 4. DASHBOARD ATLETA
# ==============================================================================
if 'auth_payload' not in st.session_state:
    st.session_state.auth_payload = None

# --- HEADER: LOGO E LOGOUT AFFIANCATI ---
header_col1, header_col2 = st.columns([2, 1])
with header_col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=130)
    else:
        st.markdown("<h2 style='color:#E20613; margin:0;'>AREA 199</h2>", unsafe_allow_html=True)

with header_col2:
    if st.session_state.auth_payload is not None:
        st.write("") # Spacer
        # FIX: Sostituito kind con type
        if st.button("🔴 LOGOUT", key="logout_btn", type="secondary"):
            st.session_state.auth_payload = None
            st.rerun()

# --- LOGICA NAVIGAZIONE ---
if st.session_state.auth_payload is None:
    st.markdown("<br><h3 style='text-align:center;'>PERFORMANCE PORTAL LOGIN</h3>", unsafe_allow_html=True)
    with st.form("login_form"):
        n = st.text_input("Nome e Cognome")
        p = st.text_input("PIN Atleta", type="password")
        if st.form_submit_button("ACCEDI AL LAB"):
            sh = get_db()
            records = sh.worksheet("ATHLETE_PINS").get_all_records()
            found_cred = False
            for r in records:
                if str(r.get('name')).strip().lower() == n.strip().lower() and str(r.get('pin')).replace(".0","") == p.strip():
                    found_cred = True; break
            
            if found_cred:
                with st.spinner("Caricamento dati..."):
                    payload = fetch_player_payload(n)
                    if payload:
                        st.session_state.auth_payload = payload
                        st.rerun()
                    else:
                        st.error("Atleta non trovato nel database PLAYERS.")
            else:
                st.error("Credenziali non valide.")
else:
    pay = st.session_state.auth_payload
    info, my_tests, tgt, all_tests = pay['info'], pay['my_tests'], pay['targets'], pay['all_tests']
    
    st.write(f"Benvenuto, **{info['Nome']} {info['Cognome']}**")
    st.divider()

    if not my_tests.empty:
        last = my_tests.iloc[-1]
        yr = int(info['Anno'])
        
        # Calcolo Score Scientifico
        s_vel = calculate_dynamic_score('PAC_30m', last.get('PAC_30m'), yr, all_tests, True)
        s_agi = calculate_dynamic_score('AGI_Illin', last.get('AGI_Illin'), yr, all_tests, True)
        s_fis = calculate_dynamic_score('PHY_Salto', last.get('PHY_Salto'), yr, all_tests, False)
        s_res = calculate_dynamic_score('STA_YoYo', last.get('STA_YoYo'), yr, all_tests, False)
        s_tec = calculate_dynamic_score('TEC_Skill', last.get('TEC_Skill'), yr, all_tests, True)
        
        scores = [s_vel, s_agi, s_fis, s_res, s_tec]
        ovr = int(sum(scores)/5)

        # SCUDO BLU
        st.markdown(f"""
        <div class="shield-container">
            <div class="ovr-header">
                <div class="ovr-rating">{ovr}</div>
                <div class="ovr-pos">{str(info['Ruolo']).upper()[:3]}</div>
            </div>
            <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}" class="p-img">
            <div class="p-name">{info['Nome']}<br>{info['Cognome']}</div>
            <div class="stats-grid">
                <div class="stat-row"><span>VEL</span> {scores[0]}</div>
                <div class="stat-row"><span>AGI</span> {scores[1]}</div>
                <div class="stat-row"><span>FIS</span> {scores[2]}</div>
                <div class="stat-row"><span>RES</span> {scores[3]}</div>
                <div class="stat-row"><span>TEC</span> {scores[4]}</div>
            </div>
        </div>
        <style>
            .shield-container {{
                width: 300px; height: 460px; margin: 30px auto; padding: 25px;
                background: linear-gradient(to bottom, #080c11 0%, #152248 40%, #0d1226 100%);
                clip-path: polygon(0% 0%, 100% 0%, 100% 85%, 50% 100%, 0% 85%);
                border-top: 3px solid #E20613; text-align: center; color: white; position: relative;
                box-shadow: 0 15px 40px rgba(0,0,0,0.6);
            }}
            .ovr-header {{ position: absolute; top: 25px; left: 25px; text-align: left; }}
            .ovr-rating {{ font-size: 55px; font-weight: 900; line-height: 0.8; }}
            .ovr-pos {{ font-size: 18px; color: #E20613; font-weight: bold; }}
            .p-img {{ width: 150px; height: 150px; object-fit: contain; margin-top: 25px; }}
            .p-name {{ font-size: 20px; font-weight: 900; text-transform: uppercase; line-height: 1; margin: 10px 0; border-bottom: 2px solid #E20613; display: inline-block; padding-bottom: 5px; }}
            .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px 40px; font-size: 16px; font-weight: bold; }}
            .stat-row {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .stat-row span {{ color: #E20613; }}
        </style>
        """, unsafe_allow_html=True)

        # AI FEEDBACK
        try:
            client = openai.OpenAI(api_key=st.secrets.get("openai_key") or st.secrets.get("openai_api_key"))
            resp = client.chat.completions.create(
                model="gpt-4o", 
                messages=[{"role": "system", "content": f"Sei il Dott. Petruzzi, AREA199. Analizza Gerardo Petruzzi: VEL:{scores[0]}, AGI:{scores[1]}, FIS:{scores[2]}, RES:{scores[3]}, TEC:{scores[4]}. Sii tecnico e motivante. Max 50 parole."}]
            )
            st.markdown(f"""
            <div style="background:#111; padding:20px; border-radius:10px; border-left:4px solid #E20613; margin:25px 0;">
                <p style="color:#E20613; font-weight:900; margin-bottom:10px;">🧠 ANALISI DOTT. PETRUZZI:</p>
                <p style="font-style:italic; font-size:1.0em; line-height:1.4;">"{resp.choices[0].message.content}"</p>
            </div>""", unsafe_allow_html=True)
        except: pass

        # RADAR CHART (NO ZOOM)
        st.markdown("<h4 style='text-align:center;'>PERFORMANCE VS TARGET ELITE</h4>", unsafe_allow_html=True)
        t_scores = [tgt.get('PAC_Target',75), tgt.get('AGI_Target',75), tgt.get('PHY_Target',70), tgt.get('STA_Target',70), tgt.get('TEC_Target',75)] if tgt is not None else [75]*5
        fig = go.Figure()
        cats = ['VEL','AGI','FIS','RES','TEC']
        fig.add_trace(go.Scatterpolar(r=t_scores, theta=cats, fill='toself', name='Target Elite', line_color='#00FF00', opacity=0.3))
        fig.add_trace(go.Scatterpolar(r=scores, theta=cats, fill='toself', name='La Tua Card', line_color='#E20613'))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444", fixedrange=True),
                angularaxis=dict(rotation=90, direction="clockwise")
            ),
            paper_bgcolor='black', font_color='white', showlegend=False, height=500,
            dragmode=False 
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})
        st.caption(f"Ultimo aggiornamento test: {last['Data']}")
    else:
        st.warning("Dati dei test non ancora disponibili.")
