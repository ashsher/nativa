# Nativa

Language learning Telegram Mini-App for Uzbek speakers learning English.
Built as a BSc BISP final year project at WIUT (2025-2026).

**Live:** https://t.me/nativacombot

## What it does

- **Reading Mode** — paste article URL or text, every word becomes clickable with Uzbek translation, pronunciation and examples
- **Video Mode** — paste YouTube link, get clickable subtitles (subtitle retrieval currently unstable)
- **Vocabulary Mode** — saved words reviewed via SM-2 spaced repetition flashcards
- **Speaking Mode** — matched with conversation partners by cosine similarity of interests
- **Ask AI** — highlight any phrase, get grammar explanation in Uzbek via Google Gemini

## Tech Stack

**Backend:** Python 3.11 · FastAPI · SQLAlchemy 2.0 · PostgreSQL 16 · Redis 7  
**Frontend:** Vanilla HTML/CSS/JS inside Telegram Mini-App WebView  
**APIs:** Google Gemini 1.5 Flash · Google Cloud Translation · Google Cloud TTS · YouTube Transcript API  
**Infra:** Docker Compose · Nginx · Contabo VPS · Cloudflare R2 · Firebase Firestore

## Run locally

```bash
cp .env.example .env   # fill in API keys
docker compose up -d
```

## Author

Ashraf Shermatov — ashrafshermatov@gmail.com