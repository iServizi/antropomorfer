# 🐾 ANTROPOMORFER
Szczegóły projektu — spełnienie wymagań na ocenę 5 oraz rekomendacja na LinkedIn:

## 🛠️ Tech Stack
- **Backend** — skrypt napisany w języku Python
- **Frontend** — interfejs użytkownika w formie aplikacji webowej opartej na frameworku Streamlit
- **Integracja z modelem AI** — komunikacja z zewnętrznym modelem LLM OpenAI `gpt-5.2` w celu orkiestracji procesu rozpoznawania obrazu oraz generowania wyników przy użyciu zdefiniowanych narzędzi
- **Integracja z modelem AI** — komunikacja z zewnętrznym modelem OpenAI `gpt-image-1` (image + prompt to image), który został użyty w zdefiniowanym narzędziu w celu transformacji zwierzęcia na człowieka, na podstawie załadowanego zdjęcia oraz z wykorzystaniem rozbudowanego promptingu — definicja narzędzia w **animal_transformer.py**
- **Integracja z modelem AI** — komunikacja z zewnętrznym modelem `gemini-flash-lite-latest`, który został użyty w zdefiniowanym narzędziu w celu rozpoznania zwierzęcia na załadowanym zdjęciu — definicja narzędzia w **image_tools.py**
- **Integracja z chmurą AWS** — komunikacja z zewnętrznym serwisem Amazon S3 w celu zapisywania, przechowywania oraz wyświetlania wygenerowanych obrazów w galerii aplikacji

## 🚀 Link do aplikacji
👉 [https://s1203136-antropomorfer.hf.space](https://s1203136-antropomorfer.hf.space)

## ⚙️ Wymagania
- OpenAI API token
- Opcjonalnie, w celu użycia własnego klucza Gemini API oraz połączenia z własnym zasobnikiem AWS S3: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET_NAME, AWS_REGION, GEMINI_API_KEY

## 📂 Struktura projektu
```text
SRC/
├── tools/                      # Moduły narzędziowe aplikacji
│   ├── __init__.py
│   ├── animal_transformer.py   # Transformacja zwierzęcia na człowieka
│   └── image_tools.py          # Rozpoznawanie zwierzęcia na zdjęciu oraz generowanie obrazka "NO ANIMAL ON THE PHOTO"
├── antropomorfer.png           # Logo / grafika główna
├── README.md                   # Dokumentacja projektu
└── streamlit_app.py            # Główny plik uruchomieniowy (UI)
```
