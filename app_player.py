import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import math
import time
import urllib.parse

# ==============================================================================
# 1. CONFIGURAZIONE & STILE
# ==============================================================================
st.set_page_config(page_title="AREA199 | PLAYER ZONE", page_icon="🩸", layout="centered")

# CSS DARK / RED IDENTITY
st.markdown("""
<style>
    /* SFONDO E TESTI */
    .stApp { background-color: #000000; color: #ffffff; font-family: 'Helvetica', sans-serif; }
    
    /* INPUT FIELDS */
    div[data-baseweb="input"] > div { background-color: #111 !important; color: white !important; border: 1px solid #333 !important; }
    input { color: white !important; }
    label { color: #E20613 !important; font-weight: bold; }
    
    /* BOTTONI */
    .stButton>button { 
        border: 2px solid #E20613; color: #E20613; font-weight: 800; 
        text-transform: uppercase; width: 100%; background-color: transparent; 
        transition: all 0.3s; padding: 10px;
    }
    .stButton>button:hover { 
        background: #E20613; color: white; box-shadow: 0 0 15px rgba(226, 6, 19, 0.6); border-color: #E20613;
    }
    
    /* TITOLI */
    h1, h2, h3 { color: #ffffff !important; }
    
    /* MESSAGGI */
    .stAlert { background-color: #1a1a1a; border-left: 5px solid #E20613; color: white; }
    
    /* CARD CONTAINER */
    .metric-box { background: #161616; padding: 15px; border-radius: 10px; border: 1px solid #333; margin-bottom: 20px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. MOTORE DATI (BACKEND)
# ==============================================================================

@st.cache_resource
def get_db():
    """Connessione al Database Google"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        # Assicurati di aver impostato i secrets anche per questa app!
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client.open("AREA199_DB")
    except Exception as e:
        st.error(f"Errore Connessione DB: {e}")
        st.stop()

def check_credentials_by_name(name_input, pin_input):
    """
    Verifica Nome+PIN nel foglio ATHLETE_PINS.
    Ignora la colonna Email.
    """
    try:
        sh = get_db()
        wks = sh.worksheet("ATHLETE_PINS")
        records = wks.get_all_records()
        
        target_name = str(name_input).strip().lower()
        target_pin = str(pin_input).strip().replace(".0", "")
        
        for r in records:
            # Legge Colonna B (name) e C (pin)
            db_name = str(r.get('name') or r.get('Name') or '').strip().lower()
            db_pin = str(r.get('pin') or r.get('PIN') or '').strip().replace(".0", "")
            
            # CHECK FLESSIBILE: Cerca corrispondenza esatta o inversa
            # Es: Input "Luisa Mazzei" == DB "Luisa Mazzei"
            if db_name == target_name and db_pin == target_pin:
                return db_name # Ritorna il nome come scritto nel DB
                
            # Es: Input "Mazzei Luisa" == DB "Luisa Mazzei" (Tentativo inverso)
            parts = target_name.split()
            if len(parts) >= 2:
                reversed_target = f"{parts[1]} {parts[0]}" # Scambia primi due token
                if db_name == reversed_target and db_pin == target_pin:
                    return db_name

        return None
    except Exception as e:
        st.error(f"Errore Login: {e}")
        return None

def fetch_player_data_smart(login_name):
    """
    Usa il nome del login per trovare l'ID in PLAYERS e scaricare i Test.
    """
    try:
        sh = get_db()
        
        # 1. CERCA IDENTITÀ IN PLAYERS
        wks_p = sh.worksheet("PLAYERS")
        df_p = pd.DataFrame(wks_p.get_all_records())
        
        found_id = None
        player_info = None
        
        target = login_name.lower()
        
        for idx, row in df_p.iterrows():
            n = str(row.get('Nome', '')).strip().lower()
            c = str(row.get('Cognome', '')).strip().lower()
            
            # Combinazioni possibili nel DB
            combo1 = f"{n} {c}"
            combo2 = f"{c} {n}"
            
            if target == combo1 or target == combo2:
                found_id = str(row.get('ID'))
                player_info = row
                break
        
        if not found_id:
            return "NO_ID", None, None
            
        # 2. SCARICA TEST ARCHIVE
        wks_t = sh.worksheet("TEST_ARCHIVE")
        data_t = wks_t.get_all_values()
        headers = data_t.pop(0)
        df_t = pd.DataFrame(data_t, columns=headers)
        
        # Filtra per ID
        my_tests = df_t[df_t['ID_Atleta'] == found_id]
        
        return "OK", player_info, my_tests

    except Exception as e:
        return f"ERR: {e}", None, None

# ==============================================================================
# 3. INTERFACCIA UTENTE (FRONTEND)
# ==============================================================================

# --- HEADER LOGO ---
c1, c2, c3 = st.columns([1,2,1])
with c2:
    # Se hai il logo caricato nella repo, altrimenti usa testo
    st.markdown("<h1 style='text-align:center; color:#E20613; font-weight:900;'>AREA 199</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#888; font-size:0.8em; margin-top:-15px;'>PERFORMANCE HUB</p>", unsafe_allow_html=True)

# --- SESSIONE ---
if 'user_name' not in st.session_state: st.session_state.user_name = None
if 'p_info' not in st.session_state: st.session_state.p_info = None
if 'p_tests' not in st.session_state: st.session_state.p_tests = None

# --- VISTA 1: LOGIN ---
if st.session_state.user_name is None:
    st.markdown("---")
    st.markdown("<h3 style='text-align:center;'>ACCESSO ATLETA</h3>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        # Solo Nome e PIN
        name_in = st.text_input("Nome e Cognome")
        pin_in = st.text_input("PIN Segreto", type="password", max_chars=5)
        
        btn = st.form_submit_button("ENTRA NEL LAB")
        
        if btn:
            if not name_in or not pin_in:
                st.warning("Inserisci Nome e PIN.")
            else:
                with st.spinner("Verifica credenziali..."):
                    # 1. Check PINS
                    db_name_match = check_credentials_by_name(name_in, pin_in)
                    
                    if db_name_match:
                        # 2. Fetch Data
                        status, info, tests = fetch_player_data_smart(db_name_match)
                        
                        if status == "OK":
                            st.session_state.user_name = db_name_match
                            st.session_state.p_info = info
                            st.session_state.p_tests = tests
                            st.rerun()
                        elif status == "NO_ID":
                            st.error(f"Login OK, ma non trovo '{db_name_match}' nel database Giocatori. Contatta il Mister.")
                        else:
                            st.error(f"Errore Tecnico: {status}")
                    else:
                        st.error("Nome o PIN errati. Riprova.")

    # --- RECUPERO PIN (Simile App Coaching) ---
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("❓ Hai dimenticato il PIN?"):
        st.info("Richiedi il reset allo staff tecnico.")
        
        tua_email = "info@area199.com" # <--- INSERISCI LA TUA MAIL QUI
        subject = "Supporto AREA199: Perso PIN Atleta"
        body = "Salve, sono [Nome Atleta], ho smarrito il mio PIN."
        
        safe_sub = urllib.parse.quote(subject)
        safe_body = urllib.parse.quote(body)
        
        html_mail = f'''
        <a href="mailto:{tua_email}?subject={safe_sub}&body={safe_body}" style="text-decoration:none;">
            <div style="background:#222; border:1px solid #555; color:#ccc; padding:10px; text-align:center; border-radius:5px; font-size:0.9em;">
                ✉️ INVIA RICHIESTA EMAIL
            </div>
        </a>
        '''
        st.markdown(html_mail, unsafe_allow_html=True)

# --- VISTA 2: DASHBOARD (CARD) ---
else:
    p = st.session_state.p_info
    t = st.session_state.p_tests
    
    # Navbar
    col_l, col_r = st.columns([3,1])
    with col_l:
        st.write(f"Ciao, **{p['Nome']}** 👋")
    with col_r:
        if st.button("ESCI"):
            st.session_state.user_name = None
            st.rerun()
            
    st.divider()

    if t.empty:
        st.info("⏳ Nessun dato registrato. Attendi i primi test.")
    else:
        # Prendi l'ultima riga
        last = t.iloc[-1]
        
        # Helper pulizia numeri
        def get_val(key):
            try: return float(str(last.get(key, 0)).replace(',', '.'))
            except: return 0.0
            
        # Helper Calcolo Score (Semplificato)
        def calc_score(val, type="high"):
            if val <= 0: return 50
            # Logica semplice: Normalizza su scala 0-100 (da adattare se vuoi la gaussiana)
            score = 70 # Default medio
            if type == "low": # Tempo (meno è meglio)
                if val < 4.0: score = 95
                elif val > 6.0: score = 50
                else: score = 95 - ((val - 4.0) * 20)
            else: # Valore (più è meglio)
                score = min(99, max(40, val / 3 if val > 100 else val)) # Esempio grezzo
            return int(score)

        # ESTRAZIONE DATI REALI
        v_pac = get_val('PAC_30m')
        v_agi = get_val('AGI_Illin')
        v_phy = get_val('PHY_Salto')
        v_sta = get_val('STA_YoYo')
        v_tec = get_val('TEC_Skill')
        
        # SCORES (Logica placeholder, sostituire con la tua formula precisa se vuoi)
        # Qui metto una logica fittizia per far vedere la card "viva"
        s_vel = int(100 - (v_pac * 8)) if v_pac > 0 else 60
        s_agi = int(100 - (v_agi * 3)) if v_agi > 0 else 60
        s_fis = int(v_phy / 1.5) if v_phy > 0 else 60
        s_res = int(v_sta * 4) if v_sta > 0 else 60
        s_tec = int(100 - (v_tec * 2)) if v_tec > 0 else 60
        
        # Normalizzazione limiti grafici 40-99
        scores = [max(40, min(99, x)) for x in [s_vel, s_agi, s_fis, s_res, s_tec]]
        overall = int(sum(scores)/5)
        
        # --- RENDER CARD FUT ---
        st.markdown(f"""
        <div style="
            font-family: 'Arial', sans-serif;
            background: linear-gradient(145deg, #1a1a1a 0%, #000 100%);
            border: 2px solid #E20613; border-radius: 12px;
            padding: 20px; text-align: center; color: white;
            box-shadow: 0 10px 30px rgba(0,0,0,0.8);
            max-width: 320px; margin: 0 auto; position: relative;
        ">
            <div style="position: absolute; top: 15px; left: 15px; text-align: left;">
                <div style="font-size: 42px; font-weight: 900; color: #E20613; line-height: 1;">{overall}</div>
                <div style="font-size: 16px; font-weight: bold;">{str(p['Ruolo'])[:3].upper()}</div>
            </div>
            
            <div style="margin-top: 20px; margin-bottom: 10px;">
                <img src="{p['Foto'] if str(p['Foto']).startswith('http') else 'https://via.placeholder.com/150'}" 
                     style="width: 130px; height: 130px; object-fit: contain; filter: drop-shadow(0 0 5px rgba(255,255,255,0.2));">
            </div>
            
            <div style="font-size: 22px; font-weight: 900; text-transform: uppercase; border-bottom: 2px solid #E20613; padding-bottom: 5px; margin-bottom: 15px;">
                {p['Cognome']}
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; text-align: left; padding: 0 15px; font-size: 14px; font-weight: bold;">
                <div style="display:flex; justify-content:space-between;"><span>VEL</span> <span style="color:#E20613;">{scores[0]}</span></div>
                <div style="display:flex; justify-content:space-between;"><span>AGI</span> <span style="color:#E20613;">{scores[1]}</span></div>
                <div style="display:flex; justify-content:space-between;"><span>FIS</span> <span style="color:#E20613;">{scores[2]}</span></div>
                <div style="display:flex; justify-content:space-between;"><span>RES</span> <span style="color:#E20613;">{scores[3]}</span></div>
                <div style="display:flex; justify-content:space-between;"><span>TEC</span> <span style="color:#E20613;">{scores[4]}</span></div>
                <div style="display:flex; justify-content:space-between;"><span>ALL</span> <span style="color:#888;">{overall}</span></div>
            </div>
            
            <div style="margin-top: 15px; font-size: 10px; color: #666;">AGGIORNATO AL: {last['Data']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # --- GRAFICO RADAR ---
        st.write("")
        fig = go.Figure()
        cats = ['VEL', 'AGI', 'FIS', 'RES', 'TEC']
        
        fig.add_trace(go.Scatterpolar(
            r=scores, theta=cats, fill='toself', name='Tu', 
            line_color='#E20613', marker=dict(color='white')
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(color='#444')),
                bgcolor='rgba(0,0,0,0)'
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            margin=dict(t=20, b=20, l=40, r=40),
            showlegend=False,
            height=250
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
