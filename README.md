# Nativa — Immersion-Based Language Learning Telegram Mini-App

Nativa is a Telegram Mini-App that helps Uzbek-speaking users (primarily Generation Z)
learn English through authentic content immersion — YouTube videos with clickable subtitles,
article reading, SM-2 spaced repetition, and AI-powered grammar explanations.

---

## Architecture

```
Users
  |
  v
Telegram App
  |
  |  (WebView / Bot)
  v
Nginx (443 HTTPS / 80 redirect)
  |-- /           -> Frontend static files (HTML/CSS/JS)
  |-- /api/       -> FastAPI Backend (port 8000)
                       |-- PostgreSQL 16 (ORM: SQLAlchemy 2.0 async)
                       |-- Redis 7      (translation cache, quota counters)
                       |-- Firebase     (Firestore for speaking real-time)
                       |-- Cloudflare R2 (TTS audio MP3 storage)

External APIs:
  - YouTube Transcript API + YouTube Data API v3
  - Google Cloud Translation API v3
  - Google Cloud Text-to-Speech API
  - Google Gemini 1.5 Flash (grammar explanations)
  - Telegram Stars (payments)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Real-time | Firebase Firestore |
| Storage | Cloudflare R2 (S3-compatible) |
| Bot | python-telegram-bot v20+ |
| Frontend | HTML5, CSS3, Vanilla JavaScript (no build tools) |
| Reverse proxy | Nginx |
| Containerisation | Docker + Docker Compose |
| Translation | Google Cloud Translation API v3 |
| TTS | Google Cloud Text-to-Speech API |
| AI | Google Gemini 1.5 Flash |
| Video | youtube-transcript-api + YouTube Data API v3 |
| Payments | Telegram Stars |
