# Wordle Multijugador con Streamlit y Supabase

Un juego estilo Wordle en tiempo real para 2 jugadores (Jugador 1 crea la sala, Jugador 2 adivina).

## Configuración de la Base de Datos (Supabase)

Para que el juego funcione, debes crear un proyecto en [Supabase](https://supabase.com/) y ejecutar el siguiente script SQL en el SQL Editor para crear la tabla necesaria:

```sql
CREATE TABLE wordle_rooms (
  id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
  codigo_sala text NOT NULL UNIQUE,
  palabra_secreta text NOT NULL,
  pista text,
  intentos jsonb DEFAULT '[]'::jsonb,
  estado text DEFAULT 'playing',
  max_intentos integer DEFAULT 6,
  siguiente_sala text,
  creador_nombre text,
  adivinador_nombre text,
  creador_victorias integer DEFAULT 0,
  adivinador_victorias integer DEFAULT 0,
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- IMPORTANTE: Para evitar el error de "Row Level Security"
-- Ejecuta este comando para deshabilitar RLS o añade una política de acceso público:
ALTER TABLE wordle_rooms DISABLE ROW LEVEL SECURITY;

-- Si ya habías creado la tabla antes, puedes ejecutar esto en lugar de borrarla:
-- ALTER TABLE wordle_rooms ADD COLUMN creador_nombre text;
-- ALTER TABLE wordle_rooms ADD COLUMN adivinador_nombre text;
-- ALTER TABLE wordle_rooms ADD COLUMN creador_victorias integer DEFAULT 0;
-- ALTER TABLE wordle_rooms ADD COLUMN adivinador_victorias integer DEFAULT 0;
```

### Configuración Local

1. Renombra `.streamlit/secrets.toml.template` a `.streamlit/secrets.toml`.
2. Reemplaza los valores con la URL y la Anon Key de tu proyecto en Supabase (Se encuentran en Project Settings -> API).

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Despliegue en Streamlit Community Cloud

Para que cualquiera pueda jugar en línea, despliega la app de forma gratuita:

1. Sube este código a un repositorio público (o privado) en tu cuenta de **GitHub**.
2. Ve a [share.streamlit.io](https://share.streamlit.io/) e inicia sesión con tu cuenta de GitHub.
3. Haz clic en **"New app"**.
4. Selecciona tu repositorio, la rama (`main` o `master`) y el archivo principal (`app.py`).
5. **¡Importante!** Haz clic en **"Advanced settings..."** antes de desplegar.
6. En la sección **Secrets**, copia y pega el contenido de tu archivo `.streamlit/secrets.toml` con las credenciales reales de Supabase.
7. Haz clic en **Save** y luego en **Deploy!**.

Tu juego estará online en unos minutos.
