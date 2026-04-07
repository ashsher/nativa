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

---

## Prerequisites

- Docker 24+ and Docker Compose v2
- A domain name with DNS pointing to your server
- Telegram Bot Token (from @BotFather)
- Google Cloud project with Translation, TTS APIs enabled
- Google Gemini API key
- YouTube Data API v3 key
- Firebase project with Firestore enabled
- Cloudflare R2 bucket

---

## Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/nativa.git
cd nativa

# 2. Copy environment template and fill in all values
cp .env.example .env
nano .env

# 3. Start all services
docker compose up -d

# 4. Run database migrations
docker compose exec backend alembic upgrade head

# 5. Open http://localhost in your browser (or configure ngrok for Telegram testing)
```

---

## VPS Deployment (Contabo)

```bash
# Install Docker on Ubuntu 22.04
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Clone repo and configure
git clone https://github.com/your-org/nativa.git /opt/nativa
cd /opt/nativa
cp .env.example .env
nano .env  # Fill production values

# Add SSL certificates (Lets Encrypt)
apt install certbot
certbot certonly --standalone -d yourdomain.com
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem  nginx/ssl/key.pem

# Start
docker compose up -d

# Run migrations
docker compose exec backend alembic upgrade head

# Set Mini-App URL in @BotFather
# /newapp -> set URL to https://yourdomain.com
```

---

## Alembic Commands

```bash
# Apply all migrations
docker compose exec backend alembic upgrade head

# Create a new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Rollback one step
docker compose exec backend alembic downgrade -1
```

---

## Environment Variables

| Name | Description | Example |
|------|-------------|---------|
| DATABASE_URL | Async PostgreSQL connection string | postgresql+asyncpg://nativa:pass@db:5432/nativa |
| REDIS_URL | Redis connection string | redis://redis:6379/0 |
| TELEGRAM_BOT_TOKEN | Bot token from @BotFather | 123456:ABC-DEF... |
| MINI_APP_URL | Full HTTPS URL of the frontend | https://yourdomain.com |
| BACKEND_URL | Internal backend URL (for bot) | http://backend:8000 |
| GOOGLE_API_KEY | Google Cloud API key (Translation + TTS) | AIza... |
| GEMINI_API_KEY | Google Gemini API key | AIza... |
| YOUTUBE_API_KEY | YouTube Data API v3 key | AIza... |
| FIREBASE_CREDENTIALS | Path to Firebase service account JSON | /app/firebase.json |
| R2_ACCOUNT_ID | Cloudflare R2 account ID | abc123... |
| R2_ACCESS_KEY_ID | R2 access key | ... |
| R2_SECRET_ACCESS_KEY | R2 secret key | ... |
| R2_BUCKET_NAME | R2 bucket name | nativa-audio |
| R2_PUBLIC_URL | Public URL prefix for audio | https://pub.r2.dev/... |
| SECRET_KEY | App-level secret for internal signing | (generate 32 random bytes) |
| POSTGRES_DB | Database name | nativa |
| POSTGRES_USER | Database user | nativa |
| POSTGRES_PASSWORD | Database password | (strong random password) |

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/auth/validate | No | Validate Telegram InitData, return user |
| GET | /api/user/me | Yes | Get current user profile |
| PUT | /api/user/me | Yes | Update city, country, interests, hobbies |
| POST | /api/video/process | Yes | Submit YouTube URL, return tokenised subtitles |
| GET | /api/translate | Yes | Translate a word (Redis cached) |
| POST | /api/reading/process | Yes | Submit article URL or text |
| POST | /api/ai/explain | Yes | AI grammar explanation (Gemini 1.5 Flash) |
| GET | /api/vocabulary | Yes | Get full vocabulary deck |
| POST | /api/vocabulary | Yes | Add word to deck |
| DELETE | /api/vocabulary/{id} | Yes | Remove word from deck |
| GET | /api/vocabulary/review | Yes | Get words due today (SM-2) |
| POST | /api/vocabulary/review | Yes | Submit SM-2 rating |
| GET | /api/speaking/matches | Yes | Get recommended speaking partners (Jaccard) |
| POST | /api/speaking/connect | Yes | Create match, return Telegram deep-link |
| GET | /api/payment/status | Yes | Check premium status |
| POST | /api/payment/verify | Yes | Verify Telegram Stars payment |
| GET | /api/payment/create-invoice | Yes | Get Telegram Stars invoice link |
| GET | /api/content/recommended | Yes | Get curated beginner content |

---

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
