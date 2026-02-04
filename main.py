from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from supabase import create_client
import os
from dotenv import load_dotenv
import uuid

load_dotenv()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Initialize Supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

@app.get("/")
def read_root():
    return {"status": "MediTranslate API running"}

@app.post("/api/translate")
async def translate_text(
    text: str = Form(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...)
):
    """Translate text using Groq"""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"Translate from {source_lang} to {target_lang}. Return ONLY the translation:\n\n{text}"
            }],
            temperature=0.3
        )
        
        translation = response.choices[0].message.content.strip()
        
        return {
            "original": text,
            "translated": translation,
            "source_lang": source_lang,
            "target_lang": target_lang
        }
    except Exception as e:
        return {"error": str(e)}, 500

@app.post("/api/audio/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    source_lang: str = Form("English")
):
    """Transcribe audio using Groq Whisper"""
    temp_filename = None
    try:
        # Read audio file
        audio_bytes = await audio.read()
        
        # Save temporarily
        file_ext = audio.filename.split('.')[-1] if '.' in audio.filename else 'webm'
        temp_filename = f"temp_{uuid.uuid4()}.{file_ext}"
        
        with open(temp_filename, "wb") as f:
            f.write(audio_bytes)
        
        # Transcribe with Groq Whisper
        with open(temp_filename, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(temp_filename, audio_file.read()),
                model="whisper-large-v3",
                language="en" if "english" in source_lang.lower() else "es",
                response_format="json"
            )
        
        # Clean up
        os.remove(temp_filename)
        
        return {
            "transcript": transcription.text,
            "language": source_lang
        }
    except Exception as e:
        # Clean up temp file if exists
        if temp_filename and os.path.exists(temp_filename):
            os.remove(temp_filename)
        return {"error": str(e)}, 500

@app.post("/api/audio/process")
async def process_audio_full(
    audio: UploadFile = File(...),
    conversation_id: str = Form(...),
    sender_role: str = Form(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...)
):
    """
    Complete audio processing pipeline:
    1. Transcribe audio with Whisper
    2. Translate transcript
    3. Upload audio to storage
    4. Return everything
    """
    try:
        # Step 1: Transcribe
        transcribe_result = await transcribe_audio(audio, source_lang)
        transcript = transcribe_result["transcript"]
        
        # Step 2: Translate
        translate_result = await translate_text(transcript, source_lang, target_lang)
        translation = translate_result["translated"]
        
        # Step 3: Upload audio - need to reset file pointer
        audio_bytes = await audio.read()  # Read again for upload
        
        # Create new UploadFile-like object for upload
        file_ext = audio.filename.split('.')[-1] if '.' in audio.filename else 'webm'
        filename = f"{conversation_id}/{sender_role}/{uuid.uuid4()}.{file_ext}"
        
        upload_result = supabase.storage.from_('audio-files').upload(
            filename,
            audio_bytes,
            {'content-type': audio.content_type}
        )
        
        public_url = supabase.storage.from_('audio-files').get_public_url(filename)
        
        return {
            "transcript": transcript,
            "translation": translation,
            "audio_url": public_url,
            "source_lang": source_lang,
            "target_lang": target_lang
        }
    except Exception as e:
        return {"error": str(e)}, 500

@app.post("/api/audio/upload")
async def upload_audio(
    audio: UploadFile = File(...),
    conversation_id: str = Form(...),
    sender_role: str = Form(...)
):
    """Upload audio file to Supabase storage"""
    try:
        file_ext = audio.filename.split('.')[-1] if '.' in audio.filename else 'webm'
        filename = f"{conversation_id}/{sender_role}/{uuid.uuid4()}.{file_ext}"
        
        content = await audio.read()
        
        result = supabase.storage.from_('audio-files').upload(
            filename,
            content,
            {'content-type': audio.content_type}
        )
        
        public_url = supabase.storage.from_('audio-files').get_public_url(filename)
        
        return {
            "audio_url": public_url,
            "filename": filename
        }
    except Exception as e:
        return {"error": str(e)}, 500

@app.post("/api/audio/transcribe-translate")
async def transcribe_and_translate(
    transcript: str = Form(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...)
):
    """Receives pre-transcribed text and translates it (for browser speech recognition)"""
    try:
        translation_result = await translate_text(transcript, source_lang, target_lang)
        
        return {
            "transcript": transcript,
            "translation": translation_result["translated"],
            "source_lang": source_lang,
            "target_lang": target_lang
        }
    except Exception as e:
        return {"error": str(e)}, 500

@app.get("/test/supabase")
def test_supabase():
    """Test Supabase connection"""
    try:
        result = supabase.table('conversations').select("*").limit(1).execute()
        return {"status": "connected", "data": result.data}
    except Exception as e:
        return {"status": "error", "message": str(e)}
