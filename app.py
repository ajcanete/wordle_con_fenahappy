import streamlit as st
import random
import string
from supabase import create_client, Client
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Wordle Multijugador", page_icon="🧩", layout="centered")

import os
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# --- INICIALIZACIÓN DE SUPABASE ---
@st.cache_resource
def init_supabase() -> Client | None:
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        if url == "TU_SUPABASE_URL_AQUI": return None
        return create_client(url, key)
    except Exception:
        return None

supabase = init_supabase()

# --- LIMPIEZA DE BBDD (LAZY GC) ---
def clean_old_rooms():
    if not supabase: return
    try:
        # Borrar salas con más de 2 horas de antigüedad
        limite = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        supabase.table('wordle_rooms').delete().lt('created_at', limite).execute()
    except Exception:
        pass

# --- GESTIÓN DE ESTADO ---
import random
def generar_nombre_bioquimico():
    adjetivos = ["Ansioso", "Estresado", "Oxidativo", "Agudo", "Crónico", "Inhibido", "Reactivo", "Metabólico", "Murino", "Fluorescente", "Tóxico", "Genético"]
    sustantivos = ["Cortisol", "Ratón", "Hipocampo", "Macrófago", "Glucocorticoide", "Receptor", "Citocina", "Enzima", "Anticuerpo", "Dopamina", "Placebo", "Genoma"]
    return f"{random.choice(sustantivos)} {random.choice(adjetivos)}"

def init_local_state():
    if 'current_input' not in st.session_state: st.session_state.current_input = ""
    if 'mode' not in st.session_state: st.session_state.mode = "single"
    if 'room_code' not in st.session_state: st.session_state.room_code = None
    if 'max_intentos' not in st.session_state: st.session_state.max_intentos = 6
    if 'player_name' not in st.session_state: st.session_state.player_name = generar_nombre_bioquimico()
    if 'player_victories' not in st.session_state: st.session_state.player_victories = 0

def init_single_player(word="PYTHON", hint="Lenguaje de programación", max_intentos=6):
    st.session_state.secret_word = word.upper()
    st.session_state.hint = hint
    st.session_state.guesses = []
    st.session_state.game_status = "playing"
    st.session_state.current_input = ""
    st.session_state.room_code = None
    st.session_state.max_intentos = max_intentos

init_local_state()

# --- COMPONENTE JS PARA EL TABLERO ---
_COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "wordle_grid_component")
if not os.path.exists(_COMPONENT_DIR):
    os.makedirs(_COMPONENT_DIR)
    
_HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { margin: 0; padding: 0; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; background-color: transparent; }
        .wordle-row { display: flex; justify-content: center; gap: 6px; margin-bottom: 6px; width: 100%; }
        .wordle-box {
            width: 14vw; max-width: 55px; aspect-ratio: 1 / 1;
            display: flex; align-items: center; justify-content: center;
            font-size: clamp(20px, 6vw, 32px); font-weight: bold; color: white;
            border: 2px solid #3a3a3c; border-radius: 4px; text-transform: uppercase;
        }
        .green { background-color: #538d4e; border-color: #538d4e; }
        .yellow { background-color: #b59f3b; border-color: #b59f3b; }
        .gray { background-color: #3a3a3c; border-color: #3a3a3c; }
        .empty { background-color: transparent; color: #d7dadc; }
        .current-input { border-color: #565758; }
        
        /* Estilos del Teclado Virtual Integrado */
        #keyboard-container { width: 100%; max-width: 500px; padding: 10px; display: flex; flex-direction: column; gap: 6px; margin-top: 15px; }
        .kbd-row { display: flex; justify-content: center; gap: 4px; width: 100%; }
        .kbd-key-wrapper {
            flex: 1; height: 55px; border-radius: 4px; border: none; background-color: #818384; color: white;
            font-weight: bold; font-size: clamp(14px, 4vw, 18px); cursor: pointer; text-transform: uppercase;
            display: flex; align-items: center; justify-content: center; user-select: none;
            touch-action: manipulation;
        }
        .kbd-key-wrapper:active { background-color: #565758; }
        .kbd-key-wrapper.wide { flex: 1.5; font-size: clamp(12px, 3.5vw, 16px); }
        .kbd-key-wrapper.green { background-color: #538d4e; }
        .kbd-key-wrapper.yellow { background-color: #b59f3b; }
        .kbd-key-wrapper.gray { background-color: #3a3a3c; }
        
        #hidden-input { opacity: 0; position: absolute; z-index: -1; pointer-events: none; }
        #board-container { cursor: text; padding: 10px; width: 100%; max-width: 400px; display: flex; flex-direction: column; align-items: center;}
    </style>
</head>
<body>
    <div id="board-container"></div>
    <div id="keyboard-container"></div>
    <input type="text" id="hidden-input" autocomplete="off" autocorrect="off" autocapitalize="characters" spellcheck="false" />
    
    <script>
        // --- Streamlit Iframe Protocol ---
        function sendMessageToStreamlitClient(type, data) {
            const outData = Object.assign({ isStreamlitMessage: true, type: type }, data);
            window.parent.postMessage(outData, "*");
        }
        const Streamlit = {
            setComponentReady: function() { sendMessageToStreamlitClient("streamlit:componentReady", {apiVersion: 1}); },
            setFrameHeight: function() { sendMessageToStreamlitClient("streamlit:setFrameHeight", {height: document.body.scrollHeight}); },
            setComponentValue: function(value) { sendMessageToStreamlitClient("streamlit:setComponentValue", {value: value}); }
        };

        // --- Game Logic ---
        let guesses = [];
        let secretLength = 5;
        let maxIntentos = 6;
        let status = 'playing';
        let secret = '';
        
        const inputEl = document.getElementById('hidden-input');
        const boardEl = document.getElementById('board-container');
        const kbdEl = document.getElementById('keyboard-container');
        
        const kbLayout = [
            ['Q','W','E','R','T','Y','U','I','O','P'],
            ['A','S','D','F','G','H','J','K','L'],
            ['ENTER','Z','X','C','V','B','N','M','DEL']
        ];
        
        function evaluateGuess(guess, sec) {
            let res = Array(sec.length).fill('gray');
            let secCounts = {};
            for(let c of sec) { secCounts[c] = (secCounts[c] || 0) + 1; }
            for(let i=0; i<guess.length; i++) {
                if(guess[i] === sec[i]) { res[i] = 'green'; secCounts[guess[i]]--; }
            }
            for(let i=0; i<guess.length; i++) {
                if(res[i] === 'gray' && secCounts[guess[i]] > 0) {
                    res[i] = 'yellow'; secCounts[guess[i]]--;
                }
            }
            return res;
        }
        
        function renderKeyboard() {
            let letterColors = {};
            for (let g of guesses) {
                let colors = evaluateGuess(g, secret);
                for (let i = 0; i < secretLength; i++) {
                    let char = g[i];
                    let color = colors[i];
                    if (color === 'green') letterColors[char] = 'green';
                    else if (color === 'yellow' && letterColors[char] !== 'green') letterColors[char] = 'yellow';
                    else if (color === 'gray' && !letterColors[char]) letterColors[char] = 'gray';
                }
            }

            let html = '';
            for (let row of kbLayout) {
                html += '<div class="kbd-row">';
                for (let key of row) {
                    let kClass = '';
                    if (key === 'ENTER' || key === 'DEL') kClass += ' wide';
                    else if (letterColors[key]) kClass += ' ' + letterColors[key];
                    
                    html += `<div class="kbd-key-wrapper ${kClass}" data-key="${key}">${key === 'DEL' ? '⌫' : key}</div>`;
                }
                html += '</div>';
            }
            kbdEl.innerHTML = html;
            
            document.querySelectorAll('.kbd-key-wrapper').forEach(el => {
                el.addEventListener('click', (e) => {
                    if (status !== 'playing') return;
                    let k = e.target.getAttribute('data-key');
                    if (k === 'ENTER') {
                        if(inputEl.value.length === secretLength) {
                            const val = inputEl.value;
                            inputEl.value = '';
                            Streamlit.setComponentValue({ guess: val, timestamp: Date.now() });
                        }
                    } else if (k === 'DEL') {
                        inputEl.value = inputEl.value.slice(0, -1);
                        renderBoard();
                    } else {
                        if (inputEl.value.length < secretLength) {
                            inputEl.value += k;
                            renderBoard();
                        }
                    }
                });
            });
            Streamlit.setFrameHeight();
        }
        
        function renderBoard() {
            let html = '';
            let currentVal = inputEl.value.toUpperCase();
            
            for(let row = 0; row < maxIntentos; row++) {
                let rowHtml = '<div class="wordle-row">';
                if(row < guesses.length) {
                    let g = guesses[row];
                    let colors = evaluateGuess(g, secret);
                    for(let i=0; i<secretLength; i++) {
                        rowHtml += `<div class="wordle-box ${colors[i]}">${g[i]}</div>`;
                    }
                } else if(row === guesses.length && status === 'playing') {
                    for(let i=0; i<secretLength; i++) {
                        let char = currentVal[i] || '';
                        let cClass = char ? 'current-input' : 'empty';
                        rowHtml += `<div class="wordle-box ${cClass}">${char}</div>`;
                    }
                } else {
                    for(let i=0; i<secretLength; i++) {
                        rowHtml += `<div class="wordle-box empty"></div>`;
                    }
                }
                rowHtml += '</div>';
                html += rowHtml;
            }
            boardEl.innerHTML = html;
            Streamlit.setFrameHeight();
        }
        
        // --- Streamlit Event Listener ---
        window.addEventListener("message", function(event) {
            if (event.data.type === "streamlit:render") {
                const data = event.data.args;
                guesses = data.guesses;
                secretLength = data.secret.length;
                secret = data.secret;
                maxIntentos = data.max_intentos;
                status = data.status;
                
                inputEl.maxLength = secretLength;
                if(status === 'playing') { inputEl.focus(); } 
                else { inputEl.blur(); }
                
                renderBoard();
                if(status !== 'spectator') {
                    kbdEl.style.display = "flex";
                    renderKeyboard();
                } else {
                    kbdEl.style.display = "none";
                }
            }
        });

        Streamlit.setComponentReady();
        
        // --- Interactions ---
        inputEl.addEventListener('input', () => {
            inputEl.value = inputEl.value.toUpperCase().replace(/[^A-ZÑ]/g, '');
            renderBoard();
        });
        
        boardEl.addEventListener('click', () => {
            if(status === 'playing') inputEl.focus();
        });
        
        inputEl.addEventListener('keydown', (e) => {
            if(e.key === 'Enter') {
                if(inputEl.value.length === secretLength && status === 'playing') {
                    const val = inputEl.value;
                    inputEl.value = '';
                    Streamlit.setComponentValue({ guess: val, timestamp: Date.now() });
                }
            }
        });
    </script>
</body>
</html>
"""
with open(os.path.join(_COMPONENT_DIR, "index.html"), "w", encoding="utf-8") as f:
    f.write(_HTML_CONTENT)

wordle_interactive_grid = components.declare_component("wordle_interactive_grid", path=_COMPONENT_DIR)


def view_single_player():
    if 'secret_word' not in st.session_state or st.session_state.mode != "single":
        st.session_state.mode = "single"
        init_single_player()
        
    st.info(f"💡 **Pista:** {st.session_state.hint}")
    
    guess_data = wordle_interactive_grid(
        guesses=st.session_state.guesses, 
        secret=st.session_state.secret_word, 
        max_intentos=st.session_state.max_intentos, 
        status=st.session_state.game_status,
        key="single_grid"
    )
    
    if guess_data and isinstance(guess_data, dict) and st.session_state.game_status == "playing":
        if 'last_ts' not in st.session_state: st.session_state.last_ts = 0
        if guess_data.get('timestamp', 0) > st.session_state.last_ts:
            st.session_state.last_ts = guess_data['timestamp']
            guess = guess_data.get('guess', '')
            st.session_state.guesses.append(guess)
            if guess == st.session_state.secret_word:
                st.session_state.game_status = "won"
                st.session_state.player_victories += 1
            elif len(st.session_state.guesses) >= st.session_state.max_intentos:
                st.session_state.game_status = "lost"
            st.rerun()
    
    if st.session_state.game_status == "won":
        st.success("🎉 ¡Felicidades! Has adivinado la palabra.")
    elif st.session_state.game_status == "lost":
        st.error(f"💀 Fin del juego. La palabra era: {st.session_state.secret_word}")

def view_p1_create():
    st.session_state.mode = "p1"
    if not supabase:
        st.error("Configura Supabase en `.streamlit/secrets.toml` para usar el modo multijugador.")
        return
        
    if not st.session_state.room_code:
        st.subheader("Crear Nueva Sala")
        with st.form("create_room_form"):
            word = st.text_input("Palabra Secreta (Letras)", value="").strip().upper()
            hint = st.text_input("Pista para el oponente", value="").strip()
            max_int = st.slider("Intentos permitidos", 3, 10, 6)
            submit = st.form_submit_button("Generar Sala")
            
            if submit:
                if not word.isalpha(): st.error("La palabra secreta debe contener solo letras.")
                elif not hint: st.error("Debes proveer una pista.")
                else:
                    codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                    try:
                        clean_old_rooms()
                        supabase.table('wordle_rooms').insert({
                            'codigo_sala': codigo, 'palabra_secreta': word, 'pista': hint,
                            'intentos': [], 'estado': 'playing', 'max_intentos': max_int,
                            'creador_nombre': st.session_state.player_name,
                            'creador_victorias': st.session_state.player_victories
                        }).execute()
                        st.session_state.room_code = codigo
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear sala: {e}")
    else:
        st.subheader(f"Sala: {st.session_state.room_code}")
        
        # Obtener la URL base desde secrets o usar localhost por defecto
        base_url = "http://localhost:8501"
        if "app" in st.secrets and "base_url" in st.secrets["app"]:
            base_url = st.secrets["app"]["base_url"].rstrip('/')
            
        share_link = f"{base_url}/?sala={st.session_state.room_code}"
        st.info("🔗 **Comparte este enlace con tu oponente:**")
        st.code(share_link, language="text")
        
        st_autorefresh(interval=3000, key="p1_autorefresh")
        
        try:
            response = supabase.table('wordle_rooms').select('*').eq('codigo_sala', st.session_state.room_code).execute()
            if len(response.data) > 0:
                room_data = response.data[0]
                status = room_data['estado']
                adv_nombre = room_data.get('adivinador_nombre')
                
                if status == "playing":
                    if adv_nombre:
                        st.write(f"Jugando contra: **{adv_nombre}** (🏆 {room_data.get('adivinador_victorias', 0)})")
                    else:
                        st.write("Esperando a que el otro jugador se una...")
                
                st.write(f"💡 **Pista:** {room_data['pista']}")
                wordle_interactive_grid(
                    guesses=room_data['intentos'], 
                    secret=room_data['palabra_secreta'], 
                    max_intentos=room_data.get('max_intentos', 6), 
                    status="spectator", 
                    key="p1_grid_view"
                )
                
                if status == "won": st.success(f"🎉 ¡{adv_nombre or 'El jugador'} ha adivinado la palabra!")
                elif status == "lost": st.error(f"💀 No logró adivinar. La palabra era: {room_data['palabra_secreta']}")
                
                if status in ["won", "lost"]:
                    siguiente = room_data.get('siguiente_sala')
                    if siguiente:
                        st.success("¡Tu oponente ha creado la revancha!")
                        if st.button("Unirse a la revancha como adivinador", type="primary", use_container_width=True):
                            try:
                                resp2 = supabase.table('wordle_rooms').select('*').eq('codigo_sala', siguiente).execute()
                                if len(resp2.data) > 0:
                                    r2 = resp2.data[0]
                                    st.session_state.mode = "p2"
                                    st.session_state.room_code = siguiente
                                    st.session_state.secret_word = r2['palabra_secreta']
                                    st.session_state.hint = r2['pista']
                                    st.session_state.guesses = r2['intentos']
                                    st.session_state.game_status = r2['estado']
                                    st.session_state.max_intentos = r2.get('max_intentos', 6)
                                    st.session_state.current_input = ""
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error al unirse: {e}")
                    else:
                        if st.button("Salir"):
                            st.session_state.room_code = None
                            st.rerun()
        except Exception as e:
            st.error(f"Error leyendo sala: {e}")

def view_p2_join():
    st.session_state.mode = "p2"
    if not supabase:
        st.error("Configura Supabase en `.streamlit/secrets.toml` para usar el modo multijugador.")
        return
        
    if not st.session_state.room_code:
        st.subheader("Unirse a una Sala")
        with st.form("join_room_form"):
            codigo = st.text_input("Código de Sala (4 caracteres)", max_chars=4).strip().upper()
            submit = st.form_submit_button("Unirse")
            
            if submit and len(codigo) == 4:
                try:
                    response = supabase.table('wordle_rooms').select('*').eq('codigo_sala', codigo).execute()
                    if len(response.data) > 0:
                        st.session_state.room_code = codigo
                        st.rerun() # Hacer rerun para que caiga en la lógica de actualización
                    else:
                        st.error("Sala no encontrada.")
                except Exception as e:
                    st.error(f"Error al conectar: {e}")
    else:
        # Fetching room logic separated so it updates the name automatically
        try:
            response = supabase.table('wordle_rooms').select('*').eq('codigo_sala', st.session_state.room_code).execute()
            if len(response.data) > 0:
                room_data = response.data[0]
                # Si recién nos unimos, registramos nuestro nombre
                if not room_data.get('adivinador_nombre'):
                    supabase.table('wordle_rooms').update({
                        'adivinador_nombre': st.session_state.player_name,
                        'adivinador_victorias': st.session_state.player_victories
                    }).eq('codigo_sala', st.session_state.room_code).execute()
                    
                st.session_state.secret_word = room_data['palabra_secreta']
                st.session_state.hint = room_data['pista']
                st.session_state.guesses = room_data['intentos']
                st.session_state.game_status = room_data['estado']
                st.session_state.max_intentos = room_data.get('max_intentos', 6)
            else:
                st.error("La sala ya no existe.")
                return
        except Exception as e:
            st.error(f"Error leyendo sala: {e}")
            return
            
        st.subheader(f"Sala: {st.session_state.room_code}")
        if room_data.get('creador_nombre'):
            st.write(f"Anfitrión: **{room_data['creador_nombre']}** (🏆 {room_data.get('creador_victorias', 0)})")
            
        st.info(f"💡 **Pista:** {st.session_state.hint}")
        
        guess_data = wordle_interactive_grid(
            guesses=st.session_state.guesses, 
            secret=st.session_state.secret_word, 
            max_intentos=st.session_state.max_intentos, 
            status=st.session_state.game_status,
            key="p2_grid"
        )
        
        if guess_data and isinstance(guess_data, dict) and st.session_state.game_status == "playing":
            if 'last_ts' not in st.session_state: st.session_state.last_ts = 0
            if guess_data.get('timestamp', 0) > st.session_state.last_ts:
                st.session_state.last_ts = guess_data['timestamp']
                guess = guess_data.get('guess', '')
                st.session_state.guesses.append(guess)
                if guess == st.session_state.secret_word:
                    st.session_state.game_status = "won"
                    st.session_state.player_victories += 1
                elif len(st.session_state.guesses) >= st.session_state.max_intentos:
                    st.session_state.game_status = "lost"
                
                try:
                    supabase.table('wordle_rooms').update({
                        'intentos': st.session_state.guesses,
                        'estado': st.session_state.game_status,
                        'adivinador_victorias': st.session_state.player_victories
                    }).eq('codigo_sala', st.session_state.room_code).execute()
                except Exception:
                    pass
                st.rerun()
        
        if st.session_state.game_status == "won": st.success("🎉 ¡Felicidades! Has adivinado la palabra.")
        elif st.session_state.game_status == "lost": st.error(f"💀 Fin del juego. La palabra era: {st.session_state.secret_word}")
            
        if st.session_state.game_status in ["won", "lost"]:
            st.markdown("---")
            st.markdown("### 🔄 Cambio de Roles")
            st.write("¡Ahora te toca a ti crear la palabra para tu oponente!")
            with st.form("revancha_form"):
                word = st.text_input("Nueva Palabra Secreta", value="").strip().upper()
                hint = st.text_input("Pista", value="").strip()
                max_int = st.slider("Intentos permitidos", 3, 10, 6)
                submit_revancha = st.form_submit_button("Crear Revancha", type="primary")
                
                if submit_revancha:
                    if not word.isalpha(): st.error("La palabra debe contener solo letras.")
                    elif not hint: st.error("Debes proveer una pista.")
                    else:
                        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                        try:
                            supabase.table('wordle_rooms').insert({
                                'codigo_sala': codigo, 'palabra_secreta': word, 'pista': hint,
                                'intentos': [], 'estado': 'playing', 'max_intentos': max_int,
                                'creador_nombre': st.session_state.player_name,
                                'creador_victorias': st.session_state.player_victories,
                                'adivinador_nombre': room_data.get('creador_nombre'),
                                'adivinador_victorias': room_data.get('creador_victorias', 0)
                            }).execute()
                            supabase.table('wordle_rooms').update({ 'siguiente_sala': codigo }).eq('codigo_sala', st.session_state.room_code).execute()
                            st.session_state.mode = "p1"
                            st.session_state.room_code = codigo
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al crear revancha: {e}")
            
            if st.button("Salir de la sala"):
                st.session_state.room_code = None
                st.rerun()

def main():
    # Detectar unirse por URL
    if "sala" in st.query_params:
        codigo_url = st.query_params["sala"].upper()
        if st.session_state.room_code != codigo_url:
            st.session_state.mode = "p2"
            st.session_state.room_code = codigo_url
            st.query_params.clear()
            st.rerun()

    st.sidebar.title("🎮 Perfil y Modos")
    
    nuevo_nombre = st.sidebar.text_input("Tu Nickname", value=st.session_state.player_name)
    if nuevo_nombre and nuevo_nombre != st.session_state.player_name:
        st.session_state.player_name = nuevo_nombre
    
    st.sidebar.caption(f"🏆 Victorias Locales: {st.session_state.player_victories}")
    st.sidebar.markdown("---")
    
    if 'mode' not in st.session_state: st.session_state.mode = "single"
    opciones = ["Modo de Prueba (Local)", "Crear Sala (Jugador 1)", "Unirse a Sala (Jugador 2)"]
    
    idx = 0
    if st.session_state.mode == "single": idx = 0
    elif st.session_state.mode == "p1": idx = 1
    elif st.session_state.mode == "p2": idx = 2

    mode_selection = st.sidebar.radio("Selecciona un modo:", opciones, index=idx)
    
    if mode_selection != opciones[idx]:
        if mode_selection == opciones[0]: st.session_state.mode = "single"
        elif mode_selection == opciones[1]: st.session_state.mode = "p1"
        elif mode_selection == opciones[2]: st.session_state.mode = "p2"
        st.session_state.room_code = None
        st.rerun()

    if mode_selection == "Modo de Prueba (Local)":
        if st.sidebar.button("Generar Nueva Palabra Local", use_container_width=True):
            init_single_player(random.choice(["PYTHON", "DATOS", "NUBE", "JUEGO", "MOVIL"]), "Término tecnológico", 6)
            st.rerun()
        st.title("🧩 Wordle (Pruebas)")
        view_single_player()
        
    elif mode_selection == "Crear Sala (Jugador 1)":
        st.title("🧩 Jugador 1: Anfitrión")
        view_p1_create()
        
    elif mode_selection == "Unirse a Sala (Jugador 2)":
        st.title("🧩 Jugador 2: Adivina")
        view_p2_join()

if __name__ == "__main__":
    main()
