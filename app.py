import streamlit as st
import random
import string
from supabase import create_client, Client
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Wordle Multijugador", page_icon="🧩", layout="centered")

st.markdown("""
<style>
.main .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 500px; }
.wordle-row { display: flex; justify-content: center; gap: 6px; margin-bottom: 6px; }
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

/* Forzar que las columnas de Streamlit se mantengan horizontales en móviles */
div[data-testid="stHorizontalBlock"] {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 2px !important;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    width: auto !important;
    flex: 1 1 0% !important;
    min-width: 0 !important;
    padding: 0 !important;
}
div[data-testid="column"] button { 
    width: 100%; 
    padding: 12px 0; 
    font-size: clamp(10px, 3vw, 16px); 
    font-weight: bold; 
    margin-bottom: 2px;
}
</style>
""", unsafe_allow_html=True)

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

# --- LÓGICA DEL JUEGO ---

def evaluate_guess(guess: str, secret: str) -> list[str]:
    result = ['gray'] * len(guess)
    secret_counts = {}
    for char in secret: secret_counts[char] = secret_counts.get(char, 0) + 1
    for i in range(len(guess)):
        if guess[i] == secret[i]:
            result[i] = 'green'
            secret_counts[guess[i]] -= 1
    for i in range(len(guess)):
        if result[i] == 'gray' and guess[i] in secret_counts and secret_counts[guess[i]] > 0:
            result[i] = 'yellow'
            secret_counts[guess[i]] -= 1
    return result

# --- GESTIÓN DE ESTADO ---
def generar_nombre_bioquimico():
    adjetivos = ["Ansioso", "Estresado", "Oxidativo", "Agudo", "Crónico", "Inhibido", "Reactivo", "Metabólico", "Murino", "Fluorescente", "Tóxico", "Genético"]
    sustantivos = ["Cortisol", "Ratón", "Hipocampo", "Macrófago", "Glucocorticoide", "Receptor", "Citocina", "Enzima", "Anticuerpo", "Dopamina", "Placebo", "Genoma"]
    return f"{random.choice(sustantivos)}{random.choice(adjetivos)}"

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

# --- ACCIONES DEL TECLADO ---
def handle_key(key: str):
    if st.session_state.game_status != "playing": return
    word_len = len(st.session_state.secret_word)
    if len(st.session_state.current_input) < word_len:
        st.session_state.current_input += key

def handle_delete():
    if st.session_state.game_status != "playing": return
    if len(st.session_state.current_input) > 0:
        st.session_state.current_input = st.session_state.current_input[:-1]

def handle_enter():
    if st.session_state.game_status != "playing": return
    guess = st.session_state.current_input
    word_len = len(st.session_state.secret_word)
    if len(guess) == word_len:
        st.session_state.guesses.append(guess)
        if guess == st.session_state.secret_word:
            st.session_state.game_status = "won"
            st.session_state.player_victories += 1
        elif len(st.session_state.guesses) >= st.session_state.max_intentos:
            st.session_state.game_status = "lost"
        st.session_state.current_input = ""
        
        if st.session_state.mode == "p2" and st.session_state.room_code and supabase:
            try:
                supabase.table('wordle_rooms').update({
                    'intentos': st.session_state.guesses,
                    'estado': st.session_state.game_status
                }).eq('codigo_sala', st.session_state.room_code).execute()
            except Exception:
                pass


# --- COMPONENTES DE UI ---

def render_grid(guesses, secret, current_input, status, max_intentos):
    word_len = len(secret)
    for row in range(max_intentos):
        html_boxes = ""
        if row < len(guesses):
            guess = guesses[row]
            colors = evaluate_guess(guess, secret)
            for i in range(word_len): html_boxes += f'<div class="wordle-box {colors[i]}">{guess[i]}</div>'
        elif row == len(guesses) and status == "playing":
            for i in range(word_len):
                char = current_input[i] if i < len(current_input) else ""
                box_class = "current-input" if char else "empty"
                html_boxes += f'<div class="wordle-box {box_class}">{char}</div>'
        else:
            for i in range(word_len): html_boxes += f'<div class="wordle-box empty"></div>'
        st.markdown(f'<div class="wordle-row">{html_boxes}</div>', unsafe_allow_html=True)

def render_keyboard():
    disabled = st.session_state.get('game_status', 'playing') != 'playing'
    row1, row2, row3 = list("QWERTYUIOP"), list("ASDFGHJKL"), ["ENTER"] + list("ZXCVBNM") + ["DEL"]
    st.write("")
    c1 = st.columns(len(row1))
    for i, key in enumerate(row1): c1[i].button(key, key=f"k1_{key}", on_click=handle_key, args=(key,), disabled=disabled)
    c2 = st.columns([0.5] + [1]*len(row2) + [0.5])
    for i, key in enumerate(row2): c2[i+1].button(key, key=f"k2_{key}", on_click=handle_key, args=(key,), disabled=disabled)
    c3 = st.columns([1.5] + [1]*(len(row3)-2) + [1.5])
    c3[0].button("ENT", key="k_ENTER", on_click=handle_enter, disabled=disabled)
    for i, key in enumerate(row3[1:-1]): c3[i+1].button(key, key=f"k3_{key}", on_click=handle_key, args=(key,), disabled=disabled)
    c3[-1].button("DEL", key="k_DEL", on_click=handle_delete, disabled=disabled)


def view_single_player():
    if 'secret_word' not in st.session_state or st.session_state.mode != "single":
        st.session_state.mode = "single"
        init_single_player()
        
    st.info(f"💡 **Pista:** {st.session_state.hint}")
    render_grid(st.session_state.guesses, st.session_state.secret_word, st.session_state.current_input, st.session_state.game_status, st.session_state.max_intentos)
    render_keyboard()
    
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
                render_grid(room_data['intentos'], room_data['palabra_secreta'], "", status, room_data.get('max_intentos', 6))
                
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
        render_grid(st.session_state.guesses, st.session_state.secret_word, st.session_state.current_input, st.session_state.game_status, st.session_state.max_intentos)
        render_keyboard()
        
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
