import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import math
import os
import openai

# ==============================================================================
# 1. BRANDING & UI AREA199
# ==============================================================================
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

# ==============================================================================
# 2. LOGICA DI CALCOLO SCIENTIFICA (Z-SCORE GAUSSIANO)
# ==============================================================================
def clean_num(val):
    if val is None or str(val).strip() == "": return 0.0
    try: return float(str(val).replace(',', '.').strip())
    except: return 0.0

def calculate_dynamic_score(test_col_name, raw_value, birth_year, df_all_tests, lower_is_better=False):
    """Calcola lo score 30-99 confrontando l'atleta con la coorte d'età."""
    val = clean_num(raw_value)
    if df_all_tests.empty or val <= 0: return 40
    
    try:
        # Selezione coorte +/- 2 anni
        df_all_tests['Anno_Rif'] = pd.to_numeric(df_all_tests['Anno_Rif'], errors='coerce')
        cohort = df_all_tests[(df_all_tests['Anno_Rif'] >= birth_year - 2) & (df_all_tests['Anno_Rif'] <= birth_year + 2)]
        if len(cohort) < 3: cohort = df_all_tests
        
        # Estrazione valori validi
        values = pd.to_numeric(cohort[test_col_name].astype(str).str.replace(',','.'), errors='coerce').dropna()
        values = values[values > 0].tolist()
        
        if len(values) < 2: return 65
        
        series = pd.Series(values)
        mu, sigma = series.mean(), series.std()
        if sigma == 0: return 70
        
        z = (val - mu) / sigma
        if lower_is_better: z = -z
        
        # Percentile via funzione Erf (Gaussiana)
        percentile = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        return int(max(30, min(99, 30 + (percentile * 69))))
    except: return 50

# ==============================================================================
# 3. DATA ACCESS
# ==============================================================================
@st.cache_resource
def get_db():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive'])
    return gspread.authorize(creds).open("AREA199_DB")

def fetch_data(name_query):
    sh = get_db()
    # 1. Trova Atleta
    df_p = pd.DataFrame(sh.worksheet("PLAYERS").get_all_records())
    p_info = None
    q = name_query.lower().strip()
    for _, row in df_p.iterrows():
        fn = f"{str(row['Nome'])} {str(row['Cognome'])}".lower().strip()
        if q == fn or q == f"{str(row['Cognome'])} {str(row['Nome'])}".lower().strip():
            p_info = row; break
    if p_info is None: return None
    
    # 2. Carica Test e Target
    df_t = pd.DataFrame(sh.worksheet("TEST_ARCHIVE").get_all_values())
    df_t.columns = df_t.iloc[0]; df_t = df_t[1:]
    
    df_tgt = pd.DataFrame(sh.worksheet("ROLE_TARGETS").get_all_records())
    tgt = df_tgt[df_tgt['Ruolo'] == p_info['Ruolo']].iloc[0] if not df_tgt[df_tgt['Ruolo'] == p_info['Ruolo']].empty else None
    
    return {"info": p_info, "tests": df_t[df_t['ID_Atleta'].astype(str) == str(p_info['ID'])], "tgt": tgt, "all_tests": df_t}

# ==============================================================================
# 4. MAIN INTERFACE
# ==============================================================================
if 'session' not in st.session_state: st.session_state.session = None

# Logo AREA199
if os.path.exists("logo.png"):
    st.image("logo.png", width=150)
else:
    st.markdown("<h1 style='color:#E20613; text-align:center;'>AREA 199</h1>", unsafe_allow_html=True)

if st.session_state.session is None:
    st.markdown("<h3 style='text-align:center;'>PLAYER PORTAL</h3>", unsafe_allow_html=True)
    with st.form("login"):
        n = st.text_input("Nome e Cognome")
        p = st.text_input("PIN Atleta", type="password")
        if st.form_submit_button("ACCEDI"):
            sh = get_db()
            valid_pins = sh.worksheet("ATHLETE_PINS").get_all_records()
            for r in valid_pins:
                if str(r.get('name')).strip().lower() == n.strip().lower() and str(r.get('pin')).replace(".0","") == p.strip():
                    payload = fetch_data(n)
                    if payload:
                        st.session_state.session = payload
                        st.rerun()
            st.error("Credenziali Errate.")
else:
    d = st.session_state.session
    info, tests, tgt, all_t = d['info'], d['tests'], d['tgt'], d['all_tests']
    
    if st.button("LOGOUT"): st.session_state.session = None; st.rerun()

    if not tests.empty:
        last = tests.iloc[-1]
        yr = int(info['Anno'])
        
        # CALCOLO PUNTEGGI DINAMICI (Allineati all'Hub)
        s_vel = calculate_dynamic_score('PAC_30m', last.get('PAC_30m'), yr, all_t, True)
        s_agi = calculate_dynamic_score('AGI_Illin', last.get('AGI_Illin'), yr, all_t, True)
        s_fis = calculate_dynamic_score('PHY_Salto', last.get('PHY_Salto'), yr, all_t, False)
        s_res = calculate_dynamic_score('STA_YoYo', last.get('STA_YoYo'), yr, all_t, False)
        s_tec = calculate_dynamic_score('TEC_Skill', last.get('TEC_Skill'), yr, all_t, True)
        
        scores = [s_vel, s_agi, s_fis, s_res, s_tec]
        ovr = int(sum(scores)/5)

        # SCUDO BLU AREA199
        st.markdown(f"""
        <div class="shield">
            <div class="ovr-header"><div class="val">{ovr}</div><div class="pos">{str(info['Ruolo']).upper()[:3]}</div></div>
            <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}" class="face">
            <div class="name">{info['Nome']}<br>{info['Cognome']}</div>
            <div class="stats">
                <div class="it"><span>VEL</span> {scores[0]}</div><div class="it"><span>AGI</span> {scores[1]}</div>
                <div class="it"><span>FIS</span> {scores[2]}</div><div class="it"><span>RES</span> {scores[3]}</div>
                <div class="it"><span>TEC</span> {scores[4]}</div>
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
            .ovr-header {{ position: absolute; top: 25px; left: 25px; text-align: left; }}
            .val {{ font-size: 55px; font-weight: 900; line-height: 0.8; }}
            .pos {{ font-size: 18px; color: #E20613; font-weight: bold; }}
            .face {{ width: 155px; height: 155px; object-fit: contain; margin-top: 25px; }}
            .name {{ font-size: 21px; font-weight: 900; text-transform: uppercase; line-height: 1; margin: 10px 0; border-bottom: 2px solid #E20613; display: inline-block; padding-bottom: 5px; }}
            .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px 40px; font-size: 16px; font-weight: bold; }}
            .it {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .it span {{ color: #E20613; }}
        </style>
        """, unsafe_allow_html=True)

        # AI COMMENTARY
        try:
            client = openai.OpenAI(api_key=st.secrets["openai_key"])
            resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": f"Sei il Dott. Petruzzi. Analizza Gerardo Petruzzi: VEL:{scores[0]}, AGI:{scores[1]}, FIS:{scores[2]}, RES:{scores[3]}, TEC:{scores[4]}. Ruolo: {info['Ruolo']}. Esalta i pregi, incoraggia i difetti. Max 50 parole."}])
            comm = resp.choices[0].message.content
            st.markdown(f'<div style="background:#111; padding:20px; border-radius:10px; border-left:5px solid #E20613; margin:25px 0;"><p style="color:#E20613; font-weight:900;">🧠 ANALISI DOTT. PETRUZZI:</p><p style="font-style:italic;">"{comm}"</p></div>', unsafe_allow_html=True)
        except: pass

        # RADAR DUAL (TARGET VS ATTUALE)
        t_scores = [tgt.get('PAC_Target',75), tgt.get('AGI_Target',75), tgt.get('PHY_Target',70), tgt.get('STA_Target',70), tgt.get('TEC_Target',75)] if tgt is not None else [75]*5
        fig = go.Figure()
        cats = ['VEL','AGI','FIS','RES','TEC']
        fig.add_trace(go.Scatterpolar(r=t_scores, theta=cats, fill='toself', name='Target Elite', line_color='#00FF00', opacity=0.3))
        fig.add_trace(go.Scatterpolar(r=scores, theta=cats, fill='toself', name='Tua Performance', line_color='#E20613'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444")), paper_bgcolor='black', font_color='white', showlegend=False, height=500)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.warning("Nessun dato test trovato.")
