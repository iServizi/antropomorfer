import streamlit as st
from openai import OpenAI
from PIL import Image, ImageOps
from io import BytesIO
import base64, os, httpx, requests, uuid, boto3
from datetime import datetime
import threading, time

# ─── Konfiguracja strony ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Antropomorfer",
    page_icon="🐾",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── CSS – nowy wygląd ──────────────────────────────────────────────────────
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

# ─── Konfiguracja AWS S3 ────────────────────────────────────────────────────
S3_BUCKET = os.environ.get("AWS_S3_BUCKET_NAME", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_REGION", "eu-central-1"),
    )

def zapisz_do_s3(output_img, input_file):
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
    try:
        s3 = get_s3_client()
        s3_response = s3.get_object(Bucket=bucket, Key=key)
        return Image.open(BytesIO(s3_response["Body"].read()))
    except Exception as s3_err:
        st.error(f"Nie udało się pobrać {key}: {s3_err}")
        return None

# ─── Funkcje pomocnicze OpenAI ──────────────────────────────────────────────
def to_buffer(image: Image.Image) -> BytesIO:
    buf = BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return buf

def save_image_from_response(response) -> Image.Image:
    item = response.data[0]
    if getattr(item, "b64_json", None):
        image_data = base64.b64decode(item.b64_json)
    elif getattr(item, "url", None):
        image_data = requests.get(item.url).content
    else:
        raise ValueError("Brak danych obrazu w odpowiedzi API")
    return Image.open(BytesIO(image_data))

def build_prompt(sex: str) -> str:
    return f"""
You are a highly skilled cinematic portrait artist and visual transformation expert.

Your task is to analyze the uploaded image and determine whether it contains a real animal (dog, cat, rabbit, horse, bird, etc.).

Follow these instructions EXACTLY:

1. Animal Detection
   - Identify whether there is a real animal visible in the image.
   - If NO real animal is detected:
     - Generate a plain pastel pink background.
     - Center the text: "NO ANIMAL ON THE PHOTO"
     - Use clean black typography.
     - Do not generate any additional objects or decorations.

2. Human Transformation
   - If a real animal IS detected:
     - Replace ONLY the animal with a realistic human {sex} portrait representing what this animal would look like as a person.
     - Preserve the original pose, camera angle, framing, lighting direction, mood, and perspective.
     - Keep the background and surroundings EXACTLY identical to the source image.
     - Do not alter objects, furniture, scenery, shadows, or composition outside the animal itself.

3. Appearance Mapping Rules
   Carefully translate the animal's physical traits into believable human characteristics:
   - Fur color → skin tone, hair color, eyebrows, eyelashes
   - Eye color → human eye color
   - Fur texture/pattern → hairstyle, freckles, skin texture, makeup accents, facial features, clothing details
   - Animal personality and expression → human facial expression and vibe
   - Animal age → estimated human age
   - Animal breed/species characteristics → facial structure, ethnicity cues, body language, fashion style

4. Color Translation Logic
   - If the animal has predominantly very dark or black fur:
     Generate very deep rich skin tones inspired by the animal coloration.
     Use dark eyes and matching facial features. Preserve elegance and realism.
   - If the animal has predominantly white fur:
     Incorporate realistic albinism traits: pale skin, white/platinum hair,
     very light eyebrows/lashes, pale blue, gray, pinkish, or light hazel eyes.
     Maintain a natural, beautiful, high-fashion appearance.
   - If the animal has mixed or patterned fur:
     Reflect those patterns subtly in hair highlights, freckles,
     heterochromia, skin undertones, makeup, or clothing accents.

5. Human Personality & Style
   The human {sex} should appear: charming, friendly, approachable, relaxed,
   socially confident, stylish and expressive.
   The result should feel believable, emotionally warm, and visually premium.

6. Image Style
   - Hyper-realistic photography
   - Cinematic portrait lighting
   - Natural skin texture
   - Professional DSLR quality
   - Ultra-detailed eyes
   - High dynamic range
   - Photorealistic color grading
   - Authentic human proportions
   - No cartoon, anime, CGI, or exaggerated fantasy elements unless strongly implied by the source image.

7. Critical Constraints
   - Keep the exact original background.
   - Preserve original image composition.
   - Replace ONLY the animal.
   - The final person must clearly feel like the human incarnation of that specific animal.
   - Avoid generic humans.
   - Focus heavily on translating the animal's identity, mood, and coloration into human form.
"""

# ─── Nagłówek strony ────────────────────────────────────────────────────────
banner_path = os.path.join(BASE_DIR, "antropomorfer.png")
if os.path.exists(banner_path):
    st.image(banner_path, use_container_width=True)

st.markdown('<h1 class="main-title">Zamień swojego zwierzaka<br>w <span>człowieka!</span></h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Wgraj zdjęcie ze zwierzakiem — zamienimy go w człowieka!</p>', unsafe_allow_html=True)

# ─── Zakładki ───────────────────────────────────────────────────────────────
tab_gen, tab_gal = st.tabs(["✨ Generator", "📚 Galeria S3"])

# ═══════════════════════════════════════════════════════════════════
# ZAKŁADKA 1 – GENERATOR
# ═══════════════════════════════════════════════════════════════════
with tab_gen:

    # Klucz API
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY_", "")
    if not OPENAI_API_KEY:
        OPENAI_API_KEY = st.text_input(
            "Klucz OpenAI API",
            type="password",
            placeholder="sk-...",
            help="Znajdziesz go na platform.openai.com/api-keys",
        )

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

    # Wybór płci
    st.markdown("#### Kim ma się stać?")
    sex_label = st.radio(
        "Płeć",
        options=["Chłopak", "Dziewczynka"],
        horizontal=True,
        label_visibility="collapsed",
    )
    sex = "female" if sex_label == "Dziewczynka" else "male"

    # Przycisk generowania
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button(
        "✨ Przekształć!",
        type="primary",
        disabled=(not uploaded_file),
        use_container_width=True,
    )

    if not uploaded_file:
        st.caption("Najpierw wgraj zdjęcie, aby aktywować przycisk.")

    # ─── Logika generowania ────────────────────────────────────────
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

        def render_progress_bar(progress: float) -> str:
            total = 12
            filled = int(progress * total)
            icons = ""
            for i in range(total):
                if i < filled:
                    icons += "👣"
                else:
                    icons += "🐾"
            pct = int(progress * 100)
            return f"""
            <div style="text-align:center; padding:1.5rem; background:white;
                        border-radius:24px; border:1px solid #f3e8d4;
                        box-shadow:0 4px 24px rgba(249,115,22,0.06);">
                <p style="font-family:'Fredoka',sans-serif; font-size:1.3rem;
                          color:#1a2233; margin-bottom:0.75rem;">
                    Trwa transformacja...
                </p>
                <div style="font-size:2.2rem; letter-spacing:6px;
                            margin-bottom:0.75rem; line-height:1.6;">
                    {icons}
                </div>
                <div style="background:#f3e8d4; border-radius:50px;
                            height:14px; margin:0.5rem 0.5rem 0.75rem;">
                    <div style="background:linear-gradient(135deg,#f97316,#f59e0b);
                                height:100%; width:{pct}%; border-radius:50px;
                                transition:width 0.4s ease;"></div>
                </div>
                <p style="color:#6b7a99; font-family:'Nunito',sans-serif;
                          font-weight:600; font-size:0.95rem; margin:0;">
                    🐾 łapy zamieniają się w stopy... {pct}%
                </p>
            </div>
            """

        result = {"image": None, "error": None, "done": False}

        def api_call(img):
            try:
                client = OpenAI(
                    api_key=OPENAI_API_KEY,
                    timeout=httpx.Timeout(120.0, connect=10.0),
                )
                response = client.images.edit(
                    model="gpt-image-1",
                    image=("image.png", to_buffer(img), "image/png"),
                    prompt=build_prompt(sex),
                    n=1,
                    size="1024x1024",
                )
                result["image"] = save_image_from_response(response)
            except Exception as e:
                result["error"] = e
            finally:
                result["done"] = True

        thread = threading.Thread(target=api_call, args=(img,))
        thread.start()

        progress_placeholder = st.empty()
        elapsed = 0
        estimated = 55  # sekund – typowy czas API

        while not result["done"]:
            progress = min(elapsed / estimated, 0.95)
            progress_placeholder.markdown(
                render_progress_bar(progress),
                unsafe_allow_html=True,
            )
            time.sleep(0.5)
            elapsed += 0.5

        thread.join()
        progress_placeholder.markdown(
            render_progress_bar(1.0),
            unsafe_allow_html=True,
        )
        time.sleep(0.4)
        progress_placeholder.empty()

        if result["error"]:
            st.error(f"Błąd: {result['error']}")
            st.exception(result["error"])
        else:
            output_image = result["image"]

            # Zapis do S3
            s3_saved = zapisz_do_s3(output_image, uploaded_file)

            # Wynik
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
            output_image.convert("RGB").save(buf_dl, format="PNG")
            buf_dl.seek(0)
            st.download_button(
                label="⬇️ Pobierz wynik",
                data=buf_dl,
                file_name="antropomorfer-wynik.png",
                mime="image/png",
                use_container_width=True,
            )

            if s3_saved:
                st.success("Wynik zapisany w AWS S3!")

# ═══════════════════════════════════════════════════════════════════
# ZAKŁADKA 2 – GALERIA S3
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
