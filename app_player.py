import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import math
import urllib.parse
import os
import openai
import base64

# ==============================================================================
# 1. BRANDING & UI AREA199
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

            /* LOGOUT SPECIFICO */
            div.stButton > button[kind="secondary"] {
                height: 35px !important; font-size: 12px !important; background-color: transparent !important;
                border: 1px solid #555 !important; color: #888 !important;
            }
            div.stButton > button[kind="secondary"]:hover { border-color: #E20613 !important; color: white !important; }

            /* INPUT STYLE */
            div[data-baseweb="input"] > div { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
            input { color: white !important; }
        </style>
    """, unsafe_allow_html=True)

init_area199_ui()

# ==============================================================================
# 2. MOTORE DI CALCOLO GAUSSIANO (Z-SCORE)
# ==============================================================================
def clean_num(val):
    if val is None or str(val).strip() == "" or str(val).strip() == "0": return 0.0
    try: return float(str(val).replace(',', '.').strip())
    except: return 0.0

def calculate_dynamic_score(test_col_name, raw_value, birth_year, df_all_tests, lower_is_better=False):
    val = clean_num(raw_value)
    if val <= 0 or df_all_tests.empty: return 40
    
    try:
        actual_col = next((c for c in df_all_tests.columns if c.lower() == test_col_name.lower()), None)
        if not actual_col: return 60

        year_col = next((c for c in df_all_tests.columns if 'Anno' in c or 'Rif' in c), None)
        if year_col:
            df_all_tests[year_col] = pd.to_numeric(df_all_tests[year_col], errors='coerce')
            cohort = df_all_tests[(df_all_tests[year_col] >= birth_year - 2) & (df_all_tests[year_col] <= birth_year + 2)]
            if len(cohort) < 3: cohort = df_all_tests
        else:
            cohort = df_all_tests

        values = pd.to_numeric(cohort[actual_col].astype(str).str.replace(',','.'), errors='coerce').dropna()
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
        return 55

# ==============================================================================
# 3. ACCESSO DATI CLOUD & PERSISTENZA AI
# ==============================================================================
@st.cache_resource
def get_db():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive'])
    return gspread.authorize(creds).open("AREA199_DB")

def save_ai_comment_to_db(athlete_id, test_date, comment):
    """Salva il commento nel database per non riconsumare token al prossimo accesso"""
    try:
        sh = get_db()
        wks = sh.worksheet("TEST_ARCHIVE")
        headers = wks.row_values(1)
        if "AI_Comment" not in headers: return # Colonna mancante
        
        col_idx = headers.index("AI_Comment") + 1
        records = wks.get_all_records()
        for i, row in enumerate(records):
            if str(row.get('ID_Atleta')) == str(athlete_id) and str(row.get('Data')) == str(test_date):
                wks.update_cell(i + 2, col_idx, comment)
                break
    except: pass

def fetch_player_payload(name_query):
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

# CODIFICA LOGO IN BASE64 PER WATERMARK
logo_b64 = ""
if os.path.exists("logo.png"):
    try:
        with open("logo.png", "rb") as img_file:
            logo_b64 = base64.b64encode(img_file.read()).decode()
    except:
        pass
logo_data_uri = f"data:image/png;base64,{logo_b64}" if logo_b64 else ""

# --- HEADER: LOGO E LOGOUT ---
head_col1, head_col2 = st.columns([2, 1])
with head_col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=130)
    else:
        st.markdown("<h2 style='color:#E20613; margin:0;'>AREA 199</h2>", unsafe_allow_html=True)

with head_col2:
    if st.session_state.auth_payload is not None:
        st.write("") 
        if st.button("🔴 LOGOUT", key="logout_top"):
            st.session_state.auth_payload = None
            st.rerun()

# --- NAVIGAZIONE ---
if st.session_state.auth_payload is None:
    st.markdown("<br><h3 style='text-align:center;'>PERFORMANCE PORTAL</h3>", unsafe_allow_html=True)
    with st.form("login_atleta"):
        n = st.text_input("Nome e Cognome")
        p = st.text_input("PIN Atleta", type="password")
        if st.form_submit_button("ACCEDI"):
            sh = get_db()
            records = sh.worksheet("ATHLETE_PINS").get_all_records()
            for r in records:
                if str(r.get('name')).strip().lower() == n.strip().lower() and str(r.get('pin')).replace(".0","") == p.strip():
                    with st.spinner("Sincronizzazione..."):
                        payload = fetch_player_payload(n)
                        if payload:
                            st.session_state.auth_payload = payload
                            st.rerun()
            if not st.session_state.auth_payload:
                st.error("Credenziali non valide.")

    # --- BLOCCO RECUPERO PIN ---
    st.markdown("---")
    with st.expander("❓ Hai dimenticato il PIN?"):
        st.info("Contatta lo staff per il reset manuale. Scrivi a info@area199.com")
        tua_email = "info@area199.com"
        subject_text = "Supporto AREA199: Recupero PIN Atleta"
        body_text = "Salve Dottore, richiedo il reset del mio PIN per l'accesso alla dashboard."
        safe_subject = urllib.parse.quote(subject_text)
        safe_body = urllib.parse.quote(body_text)
        html_button = f'''
        <a href="mailto:{tua_email}?subject={safe_subject}&body={safe_body}" target="_blank">
            <button style="background-color:#1a1a1a; color:white; border:1px solid #E20613; padding:10px 20px; border-radius:5px; cursor:pointer; font-weight: bold; width: 100%; transition: 0.3s;">
                📧 INVIA RICHIESTA EMAIL
            </button>
        </a>
        '''
        st.markdown(html_button, unsafe_allow_html=True)

else:
    pay = st.session_state.auth_payload
    info, my_t, tgt, all_t = pay['info'], pay['my_tests'], pay['targets'], pay['all_tests']
    
    st.write(f"Atleta: **{info['Nome']} {info['Cognome']}**")
    st.divider()

    if not my_t.empty:
        last = my_t.iloc[-1]
        yr = int(info['Anno'])
        
        s_vel = calculate_dynamic_score('PAC_30m', last.get('PAC_30m'), yr, all_t, True)
        s_agi = calculate_dynamic_score('AGI_Illin', last.get('AGI_Illin'), yr, all_t, True)
        s_fis = calculate_dynamic_score('PHY_Salto', last.get('PHY_Salto'), yr, all_t, False)
        s_res = calculate_dynamic_score('STA_YoYo', last.get('STA_YoYo'), yr, all_t, False)
        s_tec = calculate_dynamic_score('TEC_Skill', last.get('TEC_Skill'), yr, all_t, True)
        
        scores = [s_vel, s_agi, s_fis, s_res, s_tec]
        ovr = int(sum(scores)/5)

        # HTML IMMAGINE WATERMARK (SE PRESENTE)
        watermark_html = f'<img src="{logo_data_uri}" class="watermark-img">' if logo_data_uri else '<div class="watermark-text">AREA199</div>'

        # SCUDO BLU CON WATERMARK LOGO AREA199
        st.markdown(f"""
        <div class="card-shield">
            <div class="watermark-bg">
                {watermark_html}
            </div>
            <div class="ovr-header">
                <div class="ovr-val">{ovr}</div>
                <div class="ovr-pos">{str(info['Ruolo']).upper()[:3]}</div>
            </div>
            <img src="{info['Foto'] if 'http' in str(info['Foto']) else 'https://via.placeholder.com/150'}" class="p-img">
            <div class="p-name">{info['Nome']}<br>{info['Cognome']}</div>
            <div class="stats-grid">
                <div class="st-row"><span>VEL</span> {scores[0]}</div>
                <div class="st-row"><span>AGI</span> {scores[1]}</div>
                <div class="st-row"><span>FIS</span> {scores[2]}</div>
                <div class="st-row"><span>RES</span> {scores[3]}</div>
                <div class="st-row"><span>TEC</span> {scores[4]}</div>
            </div>
        </div>
        <style>
            .card-shield {{
                width: 300px; height: 460px; margin: 30px auto; padding: 25px;
                background: linear-gradient(to bottom, #080c11 0%, #152248 40%, #0d1226 100%);
                clip-path: polygon(0% 0%, 100% 0%, 100% 85%, 50% 100%, 0% 85%);
                border-top: 3px solid #E20613; text-align: center; color: white; position: relative;
                box-shadow: 0 15px 45px rgba(0,0,0,0.7);
                overflow: hidden; 
            }}
            .watermark-bg {{
                position: absolute;
                top: 50%; left: 50%;
                transform: translate(-50%, -50%) rotate(-25deg);
                pointer-events: none; z-index: 0;
                width: 250px;
                display: flex; justify-content: center; align-items: center;
            }}
            .watermark-img {{
                width: 100%; height: auto; opacity: 0.15; filter: grayscale(100%);
            }}
            .watermark-text {{
                font-size: 50px; font-weight: 900; color: rgba(226, 6, 19, 0.15);
            }}
            .ovr-header, .p-img, .p-name, .stats-grid {{ position: relative; z-index: 1; }}
            .ovr-header {{ position: absolute; top: 25px; left: 25px; text-align: left; }}
            .ovr-val {{ font-size: 55px; font-weight: 900; line-height: 0.8; }}
            .ovr-pos {{ font-size: 18px; color: #E20613; font-weight: bold; }}
            .p-img {{ width: 155px; height: 155px; object-fit: contain; margin-top: 25px; }}
            .p-name {{ font-size: 21px; font-weight: 900; text-transform: uppercase; line-height: 1; margin: 10px 0; border-bottom: 2px solid #E20613; display: inline-block; padding-bottom: 5px; }}
            .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px 40px; font-size: 16px; font-weight: bold; }}
            .st-row {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .st-row span {{ color: #E20613; }}
        </style>
        """, unsafe_allow_html=True)

        # --- AI ANALYSIS CON CACHE DB (TOKEN SAVER) ---
        saved_comm = str(last.get('AI_Comment', '')).strip()
        if saved_comm and saved_comm not in ["", "0", "nan"]:
            comm = saved_comm
        else:
            with st.spinner("Analisi scientifica in corso..."):
                try:
                    client = openai.OpenAI(api_key=st.secrets["openai_key"])
                    resp = client.chat.completions.create(
                        model="gpt-4o", 
                        messages=[{"role": "system", "content": f"Sei il Dott. Petruzzi, scienziato AREA199. Analizza {info['Nome']} {info['Cognome']}: VEL:{scores[0]}, AGI:{scores[1]}, FIS:{scores[2]}, RES:{scores[3]}, TEC:{scores[4]}. Ruolo: {info['Ruolo']}. Sii tecnico e motivante. Max 50 parole."}]
                    )
                    comm = resp.choices[0].message.content
                    save_ai_comment_to_db(info['ID'], last['Data'], comm)
                except: comm = "Analisi pronta per la prossima sessione."

        st.markdown(f"""
            <div style="background:#111; padding:20px; border-radius:10px; border-left:4px solid #E20613; margin:25px 0;">
                <p style="color:#E20613; font-weight:900; margin-bottom:10px;">🧠 ANALISI DOTT. PETRUZZI:</p>
                <p style="font-style:italic; font-size:1.0em; line-height:1.4;">"{comm}"</p>
            </div>""", unsafe_allow_html=True)

        # RADAR PERFORMANCE 
        st.markdown("<h4 style='text-align:center;'>PERFORMANCE VS TARGET ELITE</h4>", unsafe_allow_html=True)
        t_scores = [tgt.get('PAC_Target',75), tgt.get('AGI_Target',75), tgt.get('PHY_Target',70), tgt.get('STA_Target',70), tgt.get('TEC_Target',75)] if tgt is not None else [75]*5
        fig = go.Figure()
        cats = ['VEL','AGI','FIS','RES','TEC']
        fig.add_trace(go.Scatterpolar(r=t_scores, theta=cats, fill='toself', name='Target Elite', line_color='#00FF00', opacity=0.3))
        fig.add_trace(go.Scatterpolar(r=scores, theta=cats, fill='toself', name='Tu', line_color='#E20613'))
        
        # AGGIUNTA IMMAGINE LOGO IN BACKGROUND PLOTLY
        layout_images = []
        if logo_data_uri:
            layout_images.append(dict(
                source=logo_data_uri,
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                sizex=0.7, sizey=0.7,
                xanchor="center", yanchor="center",
                opacity=0.15,
                layer="below"
            ))

        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444")), 
            paper_bgcolor='black', font_color='white', showlegend=False, height=500,
            dragmode=False,
            images=layout_images
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False, 'staticPlot': False})
    else:
        st.warning("Dati non pronti.")
