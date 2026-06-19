# 🐾 ANTROPOMORFER

Szczegóły projektu — spełnienie wymagań na ocenę 5 oraz rekomendacja na LinkedIn:

## 🛠️ Tech Stack

- **Backend** — skrypt napisany w języku Python
- **Frontend** — interfejs użytkownika w formie aplikacji webowej opartej na frameworku Streamlit
- **Integracja z modelem AI** — komunikacja z zewnętrznym modelem LLM OpenAI `gpt-5.2` w celu orkiestracji procesu rozpoznawania obrazu oraz generowania wynikow - uzywajac zdefiniowanych narzedzi
- **Integracja z modelem AI** — komunikacja z zewnętrznym modelem OpenAI `gpt-image-1` (image + prompt to image), ktory zostal uzyty w zdefiniowany narzedziu w celu transformacji zwierzecia na czlowieka, na podstawie zaladowanego zdjecia z wykorzystaniem rozbudowanego promptingu
- **Integracja z modelem AI** — komunikacja z zewnętrznym modelem `gemini-flash-lite-latest`, ktory zostal uzyty w zdefiniowanym narzedziu w celu rozpoznania zwierzecia na zaladowanym zdjeciu
- **Integracja z chmurą AWS** — komunikacja z zewnętrznym serwisem Amazon S3 w celu zapisywania, przechowywania oraz wyświetlania wygenerowanych obrazów w galerii aplikacji

## 🚀 Link do aplikacji

👉 [https://s1203136-antropomorfer.hf.space](https://s1203136-antropomorfer.hf.space)

## ⚙️ Wymagania

- OpenAI API token
- Opcjonalnie w celu uzycia wlasnego Gemini API Key oraz polaczenia z wlasnym AWS S3 bucket: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET_NAME, AWS_REGION, GEMINI_API_KEY
  
## Struktura plikow
SRC/
│
├── tools/
│   ├── __init__.py
│   ├── animal_transformer.py
│   └── image_tools.py
│
├── antropomorfer.png
├── README.md
└── streamlit_app.py
