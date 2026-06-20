import streamlit as st
from openai import OpenAI
from PIL import Image, ImageOps
from io import BytesIO
import base64, os, httpx, requests, uuid, boto3
from datetime import datetime
#import threading, time
#import importlib
from tools.image_tools import detect_animal, generate_no_animal_image, tools as img_tools
from tools.animal_transformer import transform_animal_to_human, tools as animal_transformer
import json

tools_all = img_tools + animal_transformer

# ─── Page configuration ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Antropomorfer",
    page_icon="🐾",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── CSS –------------──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600;700&family=Nunito:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Nunito', sans-serif;
}

/* Tło strony */
.stApp {
    background: linear-gradient(160deg, #fff8ee 0%, #f0fdf8 100%);
}

/* Nagłówki */
h1, h2, h3 {
    font-family: 'Fredoka', sans-serif !important;
}

/* Główny tytuł */
.main-title {
    font-family: 'Fredoka', sans-serif;
    font-size: 2.8rem;
    font-weight: 700;
    line-height: 1.15;
    text-align: center;
    margin: 0.5rem 0 0.75rem 0;
    color: #1a2233;
}
.main-title span {
    color: #f97316;
}

/* Podtytuł */
.subtitle {
    font-family: 'Nunito', sans-serif;
    font-size: 1.15rem;
    color: #6b7a99;
    text-align: center;
    margin-bottom: 2rem;
    font-weight: 600;
}

/* Przycisk główny */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #f97316 0%, #f59e0b 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 50px !important;
    font-family: 'Fredoka', sans-serif !important;
    font-size: 1.2rem !important;
    font-weight: 600 !important;
    padding: 0.7rem 2.5rem !important;
    box-shadow: 0 6px 20px rgba(249,115,22,0.35) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
    width: 100%;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 28px rgba(249,115,22,0.45) !important;
}

/* Przycisk drugorzędny */
div[data-testid="stButton"] > button[kind="secondary"] {
    border-radius: 50px !important;
    font-family: 'Nunito', sans-serif !important;
    font-weight: 700 !important;
    width: 100%;
}

/* Radio buttons */
div[role="radiogroup"] label {
    font-family: 'Nunito', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
}

/* Ukryj domyślny header Streamlit */
#MainMenu, header, footer { visibility: hidden; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: transparent;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 50px !important;
    font-family: 'Nunito', sans-serif !important;
    font-weight: 700 !important;
    padding: 6px 20px !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #f97316, #f59e0b) !important;
    color: white !important;
}

/* Spinner */
.stSpinner > div {
    border-top-color: #f97316 !important;
}

/* Upload widget */
[data-testid="stFileUploader"] {
    border-radius: 16px !important;
}
[data-testid="stFileUploaderDropzone"] {
    border-radius: 16px !important;
    border: 2px dashed #f97316 !important;
    background: #fff8ee !important;
}

/* Alert sukces */
.stSuccess {
    border-radius: 12px !important;
}

/* Oddzielnik */
hr {
    border-color: #f3e8d4;
    margin: 1.5rem 0;
}
</style>
""", unsafe_allow_html=True)

# ─── AWS S3 Configuration ────────────────────────────────────────────────────
S3_BUCKET = os.environ.get("AWS_S3_BUCKET_NAME", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_s3_client():
    """
        Gets AWS connection credentials.
    """
    return boto3.client(
        "s3",
        aws_access_key_id= os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key= os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_REGION", "eu-central-1")
    )

def zapisz_do_s3(output_img, input_file):
    """
    Sends the images to the AWS S3 bucket, oryginal and transformed.

    Parameters:
        output image, input file
    """
    if not S3_BUCKET:
        return False
    uid = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_prefix = f"wyniki/{timestamp}_{uid}"

    buf_wynik = BytesIO()
    output_img.convert("RGB").save(buf_wynik, format="PNG")
    buf_wynik.seek(0)

    input_file.seek(0)
    ori_img = ImageOps.exif_transpose(Image.open(input_file)).convert("RGB")
    buf_ori = BytesIO()
    ori_img.save(buf_ori, format="PNG")
    buf_ori.seek(0)

    try:
        s3 = get_s3_client()
        s3.upload_fileobj(buf_ori, S3_BUCKET, f"{folder_prefix}/oryginal.png")
        s3.upload_fileobj(buf_wynik, S3_BUCKET, f"{folder_prefix}/wynik.png")
        return True
    except Exception as e:
        st.error(f"Błąd zapisu AWS S3: {e}")
        return False

def pobierz_image_z_s3(bucket, key):
    """
    Retrieves images stored in an AWS S3 bucket.

    Parameters:
        bucket: AWS S3 bucket name.
        key: AWS access key.
    
    Returns:
        Image: Image retrieved from an AWS S3 bucket.
    """
    try:
        s3 = get_s3_client()
        s3_response = s3.get_object(Bucket=bucket, Key=key)
        return Image.open(BytesIO(s3_response["Body"].read()))
    except Exception as s3_err:
        st.error(f"Nie udało się pobrać {key}: {s3_err}")
        return None
    
#----Auxiliary functions-------------------------------------------------------

def handle_function_call(function_name, arguments):
    """
    Handles function calls requested by the orchestrator LLM.

    Parameters:
        function_name: Called function name.
        arguments: Called function arguments.
    
    Returns:
        json: Called function execution status.    
    """
    print(f"<function_call> Function: {function_name}, Arguments: {arguments}")

    arguments = json.loads(arguments)

    if function_name == "detect_animal":
        img_from_session = st.session_state.get("current_img")
        res = detect_animal(img_from_session)
        return json.dumps(res)
    elif function_name == "generate_no_animal_image":
        llm_status, img_no_animal = generate_no_animal_image()
        st.session_state["final_output_image"] = img_no_animal
        #display(img_no_animal)
        return json.dumps(llm_status)
    elif function_name == "transform_animal_to_human":
        img_from_session = st.session_state.get("current_img")
        llm_status, img = transform_animal_to_human(sex, img_from_session)
        st.session_state["final_output_image"] = img
        #display(img)
        return json.dumps(llm_status)
    else:
        return {"error": "Unknown function"}    
    

def execute_tool_calls(response_output):
    """
    Executes the functions requested by the model (API Response) and returns the results.

    Parameters:
        response_output:A list of output elements from the model's response (response.output).

    Returns:
        list: A list of function call results formatted as function_call_output.
    """
    tool_results = []

    for item in response_output:
        if item.type == "function_call":
            name = item.name
            args = item.arguments

            result = handle_function_call(name, args)

            tool_results.append({
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": result 
            })

    return tool_results

#----Main function for handling orchestrator requests.-------------------------------------------------------
def process_user_command(sex):
    """
    Orchestrator; processes the user command using gpt-5.2 and the following functions: detect_animal, generate_no_animal_image, transform_animal_to_human.

    Parameters:
        No parameters.

    Returns:
        tuple: (model response, message history)
    """
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=httpx.Timeout(120.0, connect=10.0),
    )

    orchest_user_prompt ="""You are a strict pipeline router. Your job is to start the workflow
                by calling the 'detect_animal' tool to verify the workspace image.
                You must use the provided tools to achieve the goal. Do not output plain text."""
    
    input_messages = [
        {"role": "system", "content": f"You are a helpful assistant.Target gender requested: '{sex}'."},
        {"role": "user", "content": orchest_user_prompt}
    ]

    while True:
        response = client.responses.create(
            model="gpt-5.2",  
            input=input_messages,
            tools=tools_all,
            max_output_tokens=1000
        )

        tool_results = execute_tool_calls(response.output)

        if tool_results:
            input_messages = input_messages + [item.model_dump() for item in response.output] + tool_results
        else:
            return response.output_text, input_messages

def render_progress_bar(progress: float) -> str:
    pct = int(progress * 100)
    
    return f"""
    <style>
        div[data-testid="stSpinner"] {{
            text-align: center !important;
            width: 100% !important;
        }}
        div[data-testid="stSpinner"] > div {{
            display: inline-flex !important;
            justify-content: center !important;
            align-items: center !important;
            width: 100% !important;
            margin: 0 auto !important;
        }}
    </style>

    <div id="custom-progress-container" style="text-align:center; padding:1.5rem; background:white;
                border-radius:24px; border:1px solid #f3e8d4;
                box-shadow:0 4px 24px rgba(249,115,22,0.06); margin-top: 1rem;">
        <p style="font-family:'Fredoka',sans-serif; font-size:1.3rem;
                  color:#1a2233; margin-bottom:0.75rem;">
            Trwa transformacja...
        </p>
        <div id="progress-icons" style="font-size:2.2rem; letter-spacing:6px;
                    margin-bottom:0.75rem; line-height:1.6;">
            🐾🐾🐾🐾🐾🐾🐾🐾🐾🐾🐾🐾
        </div>
        <div style="background:#f3e8d4; border-radius:50px;
                    height:14px; margin:0.5rem 0.5rem 0.75rem;">
            <div id="progress-fill" style="background:linear-gradient(135deg,#f97316,#f59e0b);
                        height:100%; width:{pct}%; border-radius:50px;
                        transition:width 0.3s ease;"></div>
        </div>
        <p style="color:#6b7a99; font-family:'Nunito',sans-serif;
                  font-weight:600; font-size:0.95rem; margin:0;">
            🐾 łapy zamieniają się w stopy... <span id="progress-pct">{pct}</span>%
        </p>
    </div>

    <script>
        (function() {{
            let currentPct = {pct};
            const fillEl = document.getElementById('progress-fill');
            const pctEl = document.getElementById('progress-pct');
            const iconsEl = document.getElementById('progress-icons');
            
            if (!fillEl || currentPct >= 100) return;

            // Funkcja generująca ikony stóp i łapek dynamicznie
            function updateIcons(p) {{
                let total = 12;
                let filled = Math.floor((p / 100) * total);
                let text = "";
                for(let i=0; i<total; i++) {{
                    text += (i < filled) ? "👣" : "🐾";
                }}
                if(iconsEl) iconsEl.innerText = text;
            }}

            // Pętla animacji działająca w tle przeglądarki
            const interval = setInterval(() => {{
                // Jeśli zewnętrzny kod usunie kontener (bo skończył), zatrzymaj pętlę
                if (!document.getElementById('custom-progress-container')) {{
                    clearInterval(interval);
                    return;
                }}

                // Symulujemy postęp: zwalnia im bliżej końca, czekając na serwer
                if (currentPct < 40) currentPct += 2;
                else if (currentPct < 75) currentPct += 0.8;
                else if (currentPct < 96) currentPct += 0.3;

                // Aktualizacja drzewa DOM na stronie
                fillEl.style.width = currentPct + '%';
                if(pctEl) pctEl.innerText = Math.floor(currentPct);
                updateIcons(currentPct);
            }}, 250);
        }})();
    </script>
    """

# ─── Page header ────────────────────────────────────────────────────────
banner_path = os.path.join(BASE_DIR, "antropomorfer.png")
if os.path.exists(banner_path):
    st.image(banner_path, use_container_width=True)

st.markdown('<h1 class="main-title">Zamień swojego zwierzaka<br>w <span>człowieka!</span></h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Wgraj zdjęcie ze zwierzakiem — zamienimy go w człowieka!</p>', unsafe_allow_html=True)

# ─── Zakładki ───────────────────────────────────────────────────────────────
tab_gen, tab_gal = st.tabs(["✨ Generator", "📚 Galeria S3"])

# ═══════════════════════════════════════════════════════════════════
# GENERATOR
# ═══════════════════════════════════════════════════════════════════
with tab_gen:

    # OPENAI API Key
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY_", "") #os.getenv("OPENAI_API_KEY", "")
    if not OPENAI_API_KEY:
        OPENAI_API_KEY = st.text_input(
            "Klucz OpenAI API",
            type="password",
            placeholder="sk-...",
            help="Znajdziesz go na platform.openai.com/api-keys",
        )
    
        st.session_state["user_api_key"] = OPENAI_API_KEY
        os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

    # Upload
    uploaded_file = st.file_uploader(
        "Wybierz zdjęcie zwierzaka",
        type=["jpg", "jpeg", "png", "webp"],
        help="JPG, PNG lub WEBP – maksymalnie 200 MB",
    )

    if uploaded_file is not None:
        preview = ImageOps.exif_transpose(Image.open(uploaded_file))
        st.image(preview, caption="Podgląd Twojego zdjęcia", use_container_width=True)

    st.markdown("---")

    # Sex selection
    st.markdown("#### Kim ma się stać?")
    sex_label = st.radio(
        "Płeć",
        options=["Chłopak", "Dziewczynka"],
        horizontal=True,
        label_visibility="collapsed",
    )
    sex = "female" if sex_label == "Dziewczynka" else "male"

    # Generation button
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button(
        "✨ Przekształć!",
        type="primary",
        disabled=(not uploaded_file),
        use_container_width=True,
    )

    if not uploaded_file:
        st.caption("Najpierw wgraj zdjęcie, aby aktywować przycisk.")

    # ─── Image generaiton logic ────────────────────────────────────────
    if generate_btn:
        if not OPENAI_API_KEY:
            st.error("Uzupełnij klucz OpenAI API!")
            st.stop()

        if not uploaded_file:
            st.error("Wgraj zdjęcie przed wygenerowaniem!")
            st.stop()

        uploaded_file.seek(0)
        img = ImageOps.exif_transpose(Image.open(uploaded_file)).convert("RGBA")
        img.thumbnail((1024, 1024), Image.LANCZOS)
        st.session_state["current_img"] = img

    # --- Initiate progress bar------------------------------------------

        komunikat_html = render_progress_bar(0.45)
        
        with st.spinner(text=""):
            pasek_placeholder = st.empty()
            pasek_placeholder.html(komunikat_html)
            response_content, messages = process_user_command(sex)
            pasek_placeholder.empty()

        st.empty().html(render_progress_bar(1.0))

        st.image(st.session_state["final_output_image"])

    # --- Store images in the AWS S3 bucket-------------------------------
        ostatni_output = None
        for msg in reversed(messages):
            if msg.get("type") == "function_call_output":
                try:
                    ostatni_output = json.loads(msg.get("output", "{}"))
                    break
                except json.JSONDecodeError:
                    continue

        #if ostatni_output and ostatni_output.get("message") == "Transformation img created.":
        if ostatni_output and ostatni_output.get("status") == "success_transform":    
            output_image = st.session_state.get("final_output_image")
            
            if output_image is not None:
                s3_saved = zapisz_do_s3(output_image, uploaded_file)
                st.markdown("---")
                st.markdown("### Gotowe!")
                col1, col2 = st.columns(2)
                with col1:
                    uploaded_file.seek(0)
                    st.image(
                        ImageOps.exif_transpose(Image.open(uploaded_file)),
                        caption="Oryginał",
                        use_container_width=True,
                    )
                with col2:
                    st.image(output_image, caption="Wynik AI", use_container_width=True)

                buf_dl = BytesIO()
                
                if isinstance(output_image, Image.Image):
                    output_image.convert("RGB").save(buf_dl, format="PNG")
                else:
                    buf_dl.write(output_image)
                
                buf_dl.seek(0)
                
                st.download_button(
                    label="⬇️ Pobierz wynik",
                    data=buf_dl,
                    file_name="antropomorfer-wynik.png",
                    mime="image/png",
                    use_container_width=True,
                )

                if s3_saved:
                    st.success("Wynik został pomyślnie zarchiwizowany w AWS S3!")
                else:
                    st.warning("⚠️ Obraz możesz pobrać lokalnie, ale nie został zapisany w chmurze AWS S3.")
            else:
                st.error("Błąd: W bazie sesji brakuje wygenerowanego obrazu (final_output_image)!")
        else:
            st.error("Obraz nie zostal wygenerowany.")    


# ═══════════════════════════════════════════════════════════════════
# GALERIA S3
# ═══════════════════════════════════════════════════════════════════
with tab_gal:
    st.markdown("""
    <style>
    [data-testid="stHorizontalBlock"] [data-testid="stImage"] img {
        height: 340px !important;
        width: 100% !important;
        object-fit: cover !important;
        object-position: center;
        border-radius: 16px;
    }
    </style>
    """, unsafe_allow_html=True)

    if not S3_BUCKET:
        st.info("Galeria wymaga skonfigurowania zmiennych środowiskowych AWS (AWS_S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION).")
    else:
        st.markdown(f"Bucket: `{S3_BUCKET}`")

    st.markdown("### Archiwum wyników z chmury")

    pobierz_galerie = st.button("🔄 Załaduj / Odśwież galerię z S3", use_container_width=True)

    if pobierz_galerie:
        if not S3_BUCKET:
            st.warning("Brak konfiguracji S3 — galeria niedostępna.")
        else:
            try:
                with st.spinner("Pobieranie listy plików z S3..."):
                    s3 = get_s3_client()
                    response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="wyniki/")

                if "Contents" not in response:
                    st.info("Brak zapisanych wyników w S3.")
                else:
                    folders: dict = {}
                    for obj in response["Contents"]:
                        key = obj["Key"]
                        folder_path = key.rsplit("/", 1)[0]
                        if folder_path not in folders:
                            folders[folder_path] = {}
                        if "oryginal.png" in key:
                            folders[folder_path]["ori_key"] = key
                        if "wynik.png" in key:
                            folders[folder_path]["wyn_key"] = key

                    for f_id in sorted(folders.keys(), reverse=True):
                        data = folders[f_id]
                        if "ori_key" in data and "wyn_key" in data:
                            with st.container():
                                st.markdown(f"**Sesja:** `{f_id.replace('wyniki/', '')}`")
                                col1, col2 = st.columns(2)

                                with st.spinner("Ładowanie zdjęć..."):
                                    img_ori = pobierz_image_z_s3(S3_BUCKET, data["ori_key"])
                                    img_wyn = pobierz_image_z_s3(S3_BUCKET, data["wyn_key"])

                                with col1:
                                    if img_ori:
                                        st.image(img_ori, caption="Oryginał", use_container_width=True)

                                with col2:
                                    if img_wyn:
                                        st.image(img_wyn, caption="Wynik AI", use_container_width=True)

                                st.divider()

            except Exception as e:
                st.error(f"Błąd pobierania z S3: {e}")
