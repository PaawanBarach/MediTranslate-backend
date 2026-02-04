# MediTranslate - Backend

FastAPI backend for real-time healthcare translation. Handles audio transcription, text translation, and conversation management.

## 🚀 [Live API](https://meditranslate-backend.onrender.com)

API Docs: [/docs](https://meditranslate-backend.onrender.com/docs)

---

## ✨ Features

- 🎙️ **Audio Transcription** - Groq Whisper Large v3 (30+ languages)
- 🌐 **Text Translation** - Groq Llama 3.3 70B (15+ language pairs)
- 💾 **Conversation Storage** - PostgreSQL via Supabase
- 📁 **Audio File Storage** - Supabase Storage buckets
- 🔍 **Full-Text Search** - Across all conversations
- 🤖 **Medical Summaries** - AI-powered extraction of key medical info

---

## 🛠️ Tech Stack

- **FastAPI** (Python 3.10+)
- **Uvicorn** ASGI server
- **Groq API** - Free unlimited LLM access
- **Supabase** - Managed PostgreSQL + Storage
- **python-multipart** - File upload handling

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env
uvicorn main:app --reload

📡 API Endpoints
Translation & Transcription
text
POST /api/translate              # Translate text
POST /api/audio/transcribe       # Transcribe audio
POST /api/audio/process          # Complete pipeline
Conversations
text
POST   /api/conversations        # Create new
GET    /api/conversations        # List all
GET    /api/conversations/{id}   # Get details
PATCH  /api/conversations/{id}   # Update languages
DELETE /api/conversations/{id}   # Delete
Messages
text
GET  /api/conversations/{id}/messages   # Fetch messages
POST /api/conversations/{id}/messages   # Send text
POST /api/conversations/{id}/audio      # Send audio
Search & Summary
text
GET  /api/search?q={query}              # Search all messages
POST /api/conversations/{id}/summary    # Generate AI summary
Full interactive docs: Visit /docs on any deployed instance


🔗 Related
Frontend Repository:  https://github.com/PaawanBarach/MediTranslate-frontend


Live App: medi-translate-rosy.vercel.app

👤 Author
[Paawan Barach]

GitHub: @(https://github.com/PaawanBarach/)