from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from groq import Groq
import os
import tempfile
from dotenv import load_dotenv
import uuid

load_dotenv()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clients
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# ============ CONVERSATIONS ============

@app.post("/api/conversations")
async def create_conversation(
    patient_name: str = Form(...),
    doctor_lang: str = Form("English"),
    patient_lang: str = Form("Spanish")
):
    """Create a new conversation"""
    try:
        print(f"Creating conversation for patient: {patient_name}")
        
        result = supabase.table("conversations").insert({
            "patient_name": patient_name,
            "doctor_lang": doctor_lang,
            "patient_lang": patient_lang
        }).execute()
        
        print(f"Conversation created: {result.data}")
        return result.data[0]
    except Exception as e:
        print(f"Error creating conversation: {str(e)}")
        print(f"Error type: {type(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")



@app.get("/api/conversations")
async def get_conversations():
    """Get all conversations"""
    try:
        result = supabase.table("conversations")\
            .select("*")\
            .order("created_at", desc=True)\
            .execute()
        
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get single conversation"""
    try:
        result = supabase.table("conversations")\
            .select("*")\
            .eq("id", conversation_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ MESSAGES ============

@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    """Get all messages for a conversation"""
    try:
        result = supabase.table("messages")\
            .select("*")\
            .eq("conversation_id", conversation_id)\
            .order("created_at", desc=False)\
            .execute()
        
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversations/{conversation_id}/messages")
async def create_text_message(
    conversation_id: str,
    role: str = Form(...),
    text: str = Form(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...)
):
    """Create a text-only message"""
    try:
        # Translate text using Groq
        translation = translate_text(text, source_lang, target_lang)
        
        # Save to database
        result = supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "role": role,
            "original_text": text,
            "original_lang": source_lang,
            "translated_text": translation,
            "translated_lang": target_lang,
            "audio_url": None
        }).execute()
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    doctor_lang: str = Form(None),
    patient_lang: str = Form(None),
    patient_name: str = Form(None)
):
    """Update conversation languages or patient name"""
    try:
        update_data = {}
        if doctor_lang:
            update_data['doctor_lang'] = doctor_lang
        if patient_lang:
            update_data['patient_lang'] = patient_lang
        if patient_name:
            update_data['patient_name'] = patient_name
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        result = supabase.table("conversations")\
            .update(update_data)\
            .eq("id", conversation_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ AUDIO PROCESSING ============

@app.post("/api/conversations/{conversation_id}/audio")
async def process_audio(
    conversation_id: str,
    audio: UploadFile = File(...),
    role: str = Form(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...)
):
    """Process audio: transcribe, translate, save"""
    try:
        # Read audio
        audio_bytes = await audio.read()
        
        # Transcribe using Groq Whisper
        transcript = transcribe_audio(audio_bytes)
        
        # Translate
        translation = translate_text(transcript, source_lang, target_lang)
        
        # Upload audio to Supabase Storage
        file_path = f"{conversation_id}/{role}/{uuid.uuid4()}.webm"
        bucket = supabase.storage.from_("audio-files")
        bucket.upload(file_path, audio_bytes, {"content-type": "audio/webm"})
        audio_url = f"{SUPABASE_URL}/storage/v1/object/public/audio-files/{file_path}"
        
        # Save to database
        result = supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "role": role,
            "original_text": transcript,
            "original_lang": source_lang,
            "translated_text": translation,
            "translated_lang": target_lang,
            "audio_url": audio_url
        }).execute()
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ SUMMARY ============

@app.post("/api/conversations/{conversation_id}/summary")
async def generate_summary(conversation_id: str):
    """Generate medical summary of conversation"""
    try:
        # Get all messages
        messages = supabase.table("messages")\
            .select("*")\
            .eq("conversation_id", conversation_id)\
            .order("created_at", desc=False)\
            .execute()
        
        if not messages.data:
            raise HTTPException(status_code=404, detail="No messages found")
        
        # Build conversation text
        conversation_text = "\n".join([
            f"{msg['role'].upper()}: {msg['original_text']}"
            for msg in messages.data
        ])
        
        # Generate summary with Groq
        summary = generate_medical_summary(conversation_text)
        
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ HELPER FUNCTIONS ============

def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio using Groq Whisper"""
    try:
        # Use tempfile for cross-platform compatibility
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
        temp_path = temp_file.name
        
        try:
            # Write audio bytes
            temp_file.write(audio_bytes)
            temp_file.close()
            
            # Transcribe - Whisper auto-detects format
            with open(temp_path, "rb") as audio_file:
                transcription = groq_client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3-turbo",
                    response_format="text"
                )
            
            return transcription.strip()
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Translate text using Groq"""
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"Translate this medical conversation from {source_lang} to {target_lang}. Only respond with the translation, nothing else:\n\n{text}"
            }],
            temperature=0.3
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


def generate_medical_summary(conversation_text: str) -> str:
    """Generate medical summary using Groq"""
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"""Analyze this doctor-patient conversation and provide a structured medical summary:

{conversation_text}

Format the summary with these sections:
- Chief Complaint
- Symptoms
- Diagnosis (if mentioned)
- Medications (if mentioned)
- Follow-up Actions

Be concise and medical-focused."""
            }],
            temperature=0.5
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")


@app.get("/")
def health_check():
    return {"status": "healthy", "message": "MediTranslate API"}

# ============ DELETE CONVERSATION ============

@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages"""
    try:
        # Messages will be auto-deleted due to CASCADE
        result = supabase.table("conversations")\
            .delete()\
            .eq("id", conversation_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"success": True, "message": "Conversation deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ SEARCH ============

@app.get("/api/search")
async def search_conversations(q: str):
    """Search across all conversations and messages"""
    try:
        if not q or len(q.strip()) < 2:
            return []
        
        # Search in messages
        messages_result = supabase.table("messages")\
            .select("*, conversations!inner(patient_name)")\
            .or_(f"original_text.ilike.%{q}%,translated_text.ilike.%{q}%")\
            .limit(50)\
            .execute()
        
        # Format results with context
        results = []
        for msg in messages_result.data:
            # Get surrounding context (30 chars before and after)
            text = msg['original_text']
            idx = text.lower().find(q.lower())
            
            if idx >= 0:
                start = max(0, idx - 30)
                end = min(len(text), idx + len(q) + 30)
                context = text[start:end]
                if start > 0:
                    context = "..." + context
                if end < len(text):
                    context = context + "..."
            else:
                context = text[:100] + "..." if len(text) > 100 else text
            
            results.append({
                "message_id": msg['id'],
                "conversation_id": msg['conversation_id'],
                "patient_name": msg['conversations']['patient_name'],
                "text": msg['original_text'],
                "context": context,
                "role": msg['role'],
                "created_at": msg['created_at']
            })
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
