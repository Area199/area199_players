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
                border: 2px solid #E20613 !important; color: #FFFFFF !important; 
                font-weight: 800 !important; background-color: #000000 !important;
                width: 100%; height: 50px; text-transform: uppercase; border-radius: 5px;
            }
            .stButton>button:hover { background-color: #E20613 !important; }
            div[data-baseweb="input"] > div { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
            input { color: white !important; }
        </style>
    """, unsafe_allow_html=True)

init_area199_ui()

# ==============================================================================
# 2. MOTORE DI CALCOLO GAUSSIANO (ALLINEATO AL COACH HUB)
# ==============================================================================
def clean_num(val):
    if val is None or str(val).strip() == "": return 0.0
    try: return float(str(val).replace(',', '.').strip())
    except: return 0.0

def calculate_dynamic_score(test_col_name, raw_value, birth_year, df_all_tests, lower_is_better=False):
    if df_all_tests.empty or raw_value <= 0: return 40
    try:
        df_all_tests['Anno_Rif'] = pd.to_numeric(df_all_tests['Anno_Rif'], errors='coerce')
        cohort = df_all_tests[(df_all_tests['Anno_Rif'] >= birth_year - 2) & (df_all_tests['Anno_Rif'] <= birth_year + 2)]
        if len(cohort) < 3: cohort = df_all_tests
        
        values = pd.to_numeric(cohort[test_col_name].astype(str).str.replace(',','.'), errors='coerce').dropna()
        values = values[values > 0].tolist()
        if len(values) < 2: return 65
        
        series = pd.Series(values)
        mean_val, std_val = series.mean(), series.std()
        if std_val == 0: return 70
        
        z_score = (raw_value - mean_val) / std_val
        if lower_is_better: z_score = -z_score
        
        percentile = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
        return int(max(30, min(99, 30 + (percentile * (99 - 30)))))
    except: return 50

# ==============================================================================
# 3. DATA ENGINE
# ==============================================================================
@st.cache_resource
def get_db():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive'])
    return gspread.authorize(creds).open("AREA199_DB")

def fetch_data(db_name):
    try:
        sh = get_db()
        df_p = pd.DataFrame(sh.worksheet("PLAYERS").get_all_records())
        p_info = None
        target = db_name.lower().strip()
        for _, row in df_p.iterrows():
            fn = f"{str(row['Nome'])} {str(row['Cognome'])}".lower().strip()
            if target == fn or target == f"{str(row['Cognome'])} {str(row['Nome'])}".lower().strip():
                p_info = row; break
        if p_info is None: return None
        
        df_t = pd.DataFrame(sh.worksheet("TEST_ARCHIVE").get_all_values())
        df_t.columns = df_t.iloc[0]; df_t = df_t[1:]
        role_tgt = pd.DataFrame(sh.worksheet("ROLE_TARGETS").get_all_records())
        tgt = role_tgt[role_tgt['Ruolo'] == p_info['Ruolo']].iloc[0] if not role_tgt[role_tgt['Ruolo'] == p_info['Ruolo']].empty else None
        
        return {"info": p_info, "tests": df_t[df_t['ID_Atleta'].astype(str) == str(p_info['ID'])], "tgt": tgt, "all_t": df_t}
    except: return None

# ==============================================================================
# 4. RENDERING DASHBOARD
# ==============================================================================
if 'player_payload' not in st.session_state: st.session_state.player_payload = None

if os.path.exists("logo.png"): st.image("logo.png", width=140)

if st.session_state.player_payload is None:
    st.subheader("Login Atleta")
    with st.form("login"):
        n, p = st.text_input("Nome e Cognome"), st.text_input("PIN", type="password")
        if st.form_submit_button("ACCEDI"):
            pins = get_db().worksheet("ATHLETE_PINS").get_all_records()
            for r in pins:
                if str(r.get('name')).strip().lower() == n.strip().lower() and str(r.get('pin')).replace(".0","") == p.strip():
                    payload = fetch_data(n)
                    if payload:
                        st.session_state.player_payload = payload
                        st.rerun()
            st.error("Credenziali non valide.")
else:
    data = st.session_state.player_payload
    info, tests, tgt, all_t = data['info'], data['tests'], data['tgt'], data['all_t']
    
    if st.button("LOGOUT"):
        st.session_state.player_payload = None
        st.rerun()

    if not tests.empty:
        last = tests.iloc[-1]
        b_year = int(info['Anno'])
        s_pac = calculate_dynamic_score('PAC_30m', clean_num(last.get('PAC_30m')), b_year, all_t, True)
        s_agi = calculate_dynamic_score('AGI_Illin', clean_num(last.get('AGI_Illin')), b_year, all_t, True)
        s_phy = calculate_dynamic_score('PHY_Salto', clean_num(last.get('PHY_Salto')), b_year, all_t, False)
        s_sta = calculate_dynamic_score('STA_YoYo', clean_num(last.get('STA_YoYo')), b_year, all_t, False)
        s_tec = calculate_dynamic_score('TEC_Skill', clean_num(last.get('TEC_Skill')), b_year, all_t, True)
        
        scores = [s_pac, s_agi, s_phy, s_sta, s_tec]
        ovr = int(sum(scores)/5)

        st.markdown(f"""
        <div class="shield">
            <div class="h-data"><div class="ovr-v">{ovr}</div><div class="pos-v">{str(info['Ruolo']).upper()[:3]}</div></div>
            <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}" class="p-img">
            <div class="p-name">{info['Nome']}<br>{info['Cognome']}</div>
            <div class="s-grid">
                <div class="r"><span>VEL</span> {scores[0]}</div><div class="r"><span>AGI</span> {scores[1]}</div>
                <div class="r"><span>FIS</span> {scores[2]}</div><div class="r"><span>RES</span> {scores[3]}</div>
                <div class="r"><span>TEC</span> {scores[4]}</div>
            </div>
        </div>
        <style>
            .shield {{
                width: 300px; height: 460px; margin: 30px auto; padding: 25px;
                background: linear-gradient(to bottom, #080c11 0%, #152248 40%, #0d1226 100%);
                clip-path: polygon(0% 0%, 100% 0%, 100% 85%, 50% 100%, 0% 85%);
                border-top: 3px solid #E20613; text-align: center; color: white; position: relative;
                box-shadow: 0 15px 45px rgba(0,0,0,0.7);
            }}
            .h-data {{ position: absolute; top: 25px; left: 25px; text-align: left; }}
            .ovr-v {{ font-size: 55px; font-weight: 900; line-height: 0.8; }}
            .pos-v {{ font-size: 18px; color: #E20613; font-weight: bold; }}
            .p-img {{ width: 155px; height: 155px; object-fit: contain; margin-top: 25px; }}
            .p-name {{ font-size: 21px; font-weight: 900; text-transform: uppercase; line-height: 1; margin: 10px 0; border-bottom: 2px solid #E20613; display: inline-block; padding-bottom: 5px; }}
            .s-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px 40px; font-size: 16px; font-weight: bold; }}
            .r {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .r span {{ color: #E20613; }}
        </style>
        """, unsafe_allow_html=True)

        try:
            client = openai.OpenAI(api_key=st.secrets["openai_key"])
            resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": f"Sei il Dott. Petruzzi. Analizza: VEL:{scores[0]}, AGI:{scores[1]}, FIS:{scores[2]}, RES:{scores[3]}, TEC:{scores[4]} per un {info['Ruolo']}. Sii motivante e tecnico. Max 50 parole."}])
            comm = resp.choices[0].message.content
        except: comm = "Continua l'ottimo lavoro."
        
        st.markdown(f'<div style="background:#111; padding:20px; border-radius:10px; border-left:4px solid #E20613; margin:25px 0;"><p style="color:#E20613; font-weight:900;">🧠 ANALISI DOTT. PETRUZZI:</p><p style="font-style:italic;">"{comm}"</p></div>', unsafe_allow_html=True)

        t_scores = [tgt.get('PAC_Target',75), tgt.get('AGI_Target',75), tgt.get('PHY_Target',70), tgt.get('STA_Target',70), tgt.get('TEC_Target',75)] if tgt is not None else [75]*5
        fig = go.Figure()
        cats = ['VEL','AGI','FIS','RES','TEC']
        fig.add_trace(go.Scatterpolar(r=t_scores, theta=cats, fill='toself', name='Target Elite', line_color='#00FF00', opacity=0.3))
        fig.add_trace(go.Scatterpolar(r=scores, theta=cats, fill='toself', name='Tu', line_color='#E20613'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444")), paper_bgcolor='black', font_color='white', showlegend=False, height=500)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
