import streamlit as st
from openai import OpenAI
from PIL import Image, ImageOps
from io import BytesIO
import base64, os, httpx, requests, uuid, boto3
from datetime import datetime

# --- Konfiguracja strony ---
st.set_page_config(
    page_title="Antropomorfer",
    page_icon="🐾",
    layout="centered",
)

# --- Konfiguracja AWS S3 ---
S3_BUCKET = os.environ.get("AWS_S3_BUCKET_NAME", "twoja-nazwa-bucketu")
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    #aws_session_token=os.environ.get("AWS_SESSION_TOKEN") # DODAJ TO
    region_name=os.environ.get("AWS_REGION", "eu-central-1")
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Funkcje pomocnicze AWS S3 ---
def zapisz_do_s3(output_img, input_file):
    uid = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_prefix = f"wyniki/{timestamp}_{uid}"
    
    # Przygotowanie buforów
    buf_wynik = BytesIO()
    output_img.convert("RGB").save(buf_wynik, format="PNG")
    buf_wynik.seek(0)
    
    input_file.seek(0)
    ori_img = ImageOps.exif_transpose(Image.open(input_file)).convert("RGB")
    buf_ori = BytesIO()
    ori_img.save(buf_ori, format="PNG")
    buf_ori.seek(0)

    try:
        s3_client.upload_fileobj(buf_ori, S3_BUCKET, f"{folder_prefix}/oryginal.png")
        s3_client.upload_fileobj(buf_wynik, S3_BUCKET, f"{folder_prefix}/wynik.png")
        return True
    except Exception as e:
        st.error(f"Błąd zapisu AWS S3: {e}")
        return False

# --- Funkcje pomocnicze OpenAI ---
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

# --- UI: Podział na zakładki ---
tab_gen, tab_gal = st.tabs(["✨ Generator", "📚 Galeria S3"])

with tab_gen:
    if os.path.exists(os.path.join(BASE_DIR, "antropomorfer.png")):
        st.image(os.path.join(BASE_DIR, "antropomorfer.png"), use_container_width=True)

    st.markdown("<p style='font-size: 22px;'>Wgraj zdjęcie ze zwierzakiem — zamienimy go w człowieka!</p>", unsafe_allow_html=True)

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    if not OPENAI_API_KEY:
        OPENAI_API_KEY = st.text_input("Klucz OpenAI API", type="password", placeholder="sk-...")

    uploaded_file = st.file_uploader("Wybierz zdjęcie", type=["jpg", "jpeg", "png", "webp"])

    if uploaded_file is not None:
        preview = ImageOps.exif_transpose(Image.open(uploaded_file))
        st.image(preview, caption="Podgląd", use_container_width=True)

    sex_label = st.radio("Płeć zwierzaka", options=["Chłopak", "Dziewczynka"], horizontal=True)
    sex = "female" if sex_label == "Dziewczynka" else "male"

    generate_btn = st.button("✨ Generuj i wyślij do chmury", use_container_width=True)

    if generate_btn:
        if not OPENAI_API_KEY or not uploaded_file:
            st.error("Uzupełnij klucz API i wgraj zdjęcie!")
            st.stop()

        uploaded_file.seek(0)
        img = ImageOps.exif_transpose(Image.open(uploaded_file)).convert("RGBA")
        img.thumbnail((1024, 1024), Image.LANCZOS)

        prompt = f"""
You are a highly skilled cinematic portrait artist and visual transformation expert.

Your task is to analyze the uploaded image and determine whether it contains a real animal (dog, cat, rabbit, horse, bird, etc.).

Follow these instructions EXACTLY:

1. Animal Detection
   - Identify whether there is a real animal visible in the image.
   - If NO real animal is detected:
     - Generate a plain pastel pink background.
     - Center the text:
       "NO ANIMAL ON THE PHOTO"
     - Use clean black typography.
     - Do not generate any additional objects or decorations.

2. Human Transformation
   - If a real animal IS detected:
     - Replace ONLY the animal with a realistic human {sex} portrait representing what this animal would look like as a person.
     - Preserve the original pose, camera angle, framing, lighting direction, mood, and perspective.
     - Keep the background and surroundings EXACTLY identical to the source image.
     - Do not alter objects, furniture, scenery, shadows, or composition outside the animal itself.

3. Appearance Mapping Rules
   Carefully translate the animal’s physical traits into believable human characteristics:

   - Fur color → skin tone, hair color, eyebrows, eyelashes
   - Eye color → human eye color
   - Fur texture/pattern → hairstyle, freckles, skin texture, makeup accents, facial features, clothing details
   - Animal personality and expression → human facial expression and vibe
   - Animal age → estimated human age
   - Animal breed/species characteristics → facial structure, ethnicity cues, body language, fashion style

4. Color Translation Logic
   - If the animal has predominantly very dark or black fur:
     - Generate very deep rich skin tones inspired by the animal coloration.
     - Use dark eyes and matching facial features.
     - Preserve elegance and realism.
   - If the animal has predominantly white fur:
     - Incorporate realistic albinism traits:
       pale skin, white/platinum hair, very light eyebrows/lashes,
       pale blue, gray, pinkish, or light hazel eyes.
     - Maintain a natural, beautiful, high-fashion appearance.
   - If the animal has mixed or patterned fur:
     - Reflect those patterns subtly in hair highlights, freckles,
       heterochromia, skin undertones, makeup, or clothing accents.

5. Human Personality & Style
   - The human {sex} should appear:
     - charming
     - friendly
     - approachable
     - relaxed
     - socially confident
     - stylish and expressive
   - The result should feel believable, emotionally warm,
     and visually premium.

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
   - Focus heavily on translating the animal’s identity, mood, and coloration into human form.
"""

        with st.spinner("Generowanie obrazu i zapis w S3..."):
            try:
                # --- KROK 1: Generowanie obrazu ---
                st.write("🔍 Łączenie z OpenAI...")
                client = OpenAI(api_key=OPENAI_API_KEY, timeout=httpx.Timeout(120.0, connect=10.0))
                
                st.write("🔍 Wysyłanie obrazu do API...")
                response = client.images.edit(
                    model="gpt-image-1",
                    image=("image.png", to_buffer(img), "image/png"),
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                )
                st.write("✅ Obraz wygenerowany przez OpenAI")
        
                # --- KROK 2: Odczyt obrazu z odpowiedzi ---
                output_image = save_image_from_response(response)
                st.write(f"✅ Obraz odczytany z odpowiedzi, rozmiar: {output_image.size}")
        
                # --- KROK 3: Zapis do S3 ---
                st.write(f"🔍 Łączenie z S3, bucket: `{S3_BUCKET}`...")
                wynik = zapisz_do_s3(output_image, uploaded_file)
                
                if wynik:
                    st.success("✅ Obraz wygenerowany i zapisany w AWS S3!")
                else:
                    st.error("❌ Zapis do S3 nie powiódł się — sprawdź logi powyżej")
        
                # --- KROK 4: Podgląd wyniku ---
                st.image(output_image, caption="Wynik", use_container_width=True)
        
            except Exception as e:
                st.error(f"❌ Błąd: {e}")
                st.exception(e)  # ← pokazuje pełny traceback w UI

with tab_gal:    
    # --- CSS DLA IDEALNEGO DOPASOWANIA ---
    st.markdown("""
        <style>
        [data-testid="stHorizontalBlock"] [data-testid="stImage"] img {
            height: 380px !important;    
            width: 100% !important;     
            object-fit: cover !important; 
            object-position: center;     
            border-radius: 12px;         
        }
        </style>
        """, unsafe_allow_html=True)
    # -----------------------------------------------
    
    if st.button("🔄 Odśwież listę z S3"):
        st.rerun()
            
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix='wyniki/')
                
        if 'Contents' not in response:
            st.info("Brak zapisanych wyników w S3.")
        else:
            folders = {}
            for obj in response['Contents']:
                key = obj['Key']
                folder_path = key.rsplit('/', 1)[0]
                if folder_path not in folders: 
                    folders[folder_path] = {}
                
                # ZAMIAST URL: Zapisujemy sam klucz (Key) obiektu w S3
                if "oryginal.png" in key: 
                    folders[folder_path]['ori_key'] = key
                if "wynik.png" in key: 
                    folders[folder_path]['wyn_key'] = key
            
            # Funkcja pomocnicza do pobierania obrazka jako obiekt PIL w locie
            def pobierz_image_z_s3(bucket, key):
                try:
                    s3_response = s3_client.get_object(Bucket=bucket, Key=key)
                    return Image.open(BytesIO(s3_response['Body'].read()))
                except Exception as s3_err:
                    st.error(f"Nie udało się pobrać {key}: {s3_err}")
                    return None

            # Wyświetlanie wierszy
            for f_id in sorted(folders.keys(), reverse=True):
                data = folders[f_id]
                if 'ori_key' in data and 'wyn_key' in data:
                    with st.container():
                        st.markdown(f"**Sesja:** `{f_id.replace('wyniki/', '')}`")
                                                
                        col1, col2 = st.columns(2)
                        
                        # Pobieramy dane bezpośrednio przez serwer w Pythonie
                        with st.spinner("Ładowanie obrazów z S3..."):
                            img_ori = pobierz_image_z_s3(S3_BUCKET, data['ori_key'])
                            img_wyn = pobierz_image_z_s3(S3_BUCKET, data['wyn_key'])
                                                
                        with col1:
                            if img_ori:
                                st.image(img_ori, caption="Oryginał", use_container_width=True)
                                                
                        with col2:
                            if img_wyn:
                                st.image(img_wyn, caption="Wynik AI", use_container_width=True)
                                                
                        st.divider()
    except Exception as e:
        st.error(f"Błąd pobierania z S3: {e}")