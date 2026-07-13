from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os
import sqlite3
import hashlib
import jwt
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging
from pathlib import Path
import requests
import json
import secrets
import string
import qrcode
from qrcode.constants import ERROR_CORRECT_H
import io
import base64
from utils import (
    translate_text,
    generate_audio_file_with_url,
    SUPPORTED_LANGUAGES,
    get_supported_languages
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

app = FastAPI(
    title="MultiLingo Web App",
    description="Full-stack web application for text-to-speech conversion and translation with user authentication",
    version="2.0.0"
)

# Security
security = HTTPBearer(auto_error=False)

# Resolve project paths relative to this file so the app works from any cwd.
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "users.db")))

# Route all legacy sqlite connections to the project-local database file.
_sqlite_connect = sqlite3.connect

def connect_db(database, *args, **kwargs):
    if str(database) == "users.db":
        database = str(DB_PATH)
    return _sqlite_connect(database, *args, **kwargs)

sqlite3.connect = connect_db

# Create directories for static files and audio
static_dir = STATIC_DIR
static_dir.mkdir(exist_ok=True)
(static_dir / "audio").mkdir(exist_ok=True)
(static_dir / "css").mkdir(exist_ok=True)
(static_dir / "js").mkdir(exist_ok=True)
(static_dir / "qr").mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Database setup
def init_db():
    """Initialize SQLite database for user authentication"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # Create the users table with new columns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            telegram_chat_id TEXT,
            telegram_linked_at TIMESTAMP,
            telegram_verification_token TEXT,
            telegram_verified BOOLEAN DEFAULT 0,
            preferred_language TEXT DEFAULT 'en',
            audio_notifications BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create train status subscriptions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS train_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            train_number TEXT NOT NULL,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (username) REFERENCES users (username),
            UNIQUE(username, train_number)
        )
    """)
    
    # Add telegram columns if they don't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN telegram_chat_id TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN telegram_linked_at TIMESTAMP")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN telegram_verification_token TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN telegram_verified BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN preferred_language TEXT DEFAULT 'en'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN audio_notifications BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class TTSRequest(BaseModel):
    text: str
    language: str = "en"

class TranslateAndSpeakRequest(BaseModel):
    text: str
    target_languages: List[str]
    source_language: str = "auto"

class TranslationResult(BaseModel):
    language: str
    translated_text: str
    audio_url: Optional[str] = None

class MultiLanguageTextRequest(BaseModel):
    texts: List[dict]

class GenerateAudioRequest(BaseModel):
    text: str
    language: str

class TelegramLinkRequest(BaseModel):
    chat_id: str

class TelegramSendMessageRequest(BaseModel):
    message: str

class TelegramVerificationRequest(BaseModel):
    token: str
    chat_id: str

class TrainSubscriptionRequest(BaseModel):
    train_number: str
    train_name: Optional[str] = None

class UserPreferencesRequest(BaseModel):
    preferred_language: str
    audio_notifications: bool = False

class GeminiTranslationRequest(BaseModel):
    text: str
    target_language: str

# Utility functions
def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == hashed

def create_access_token(data: dict) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Verify JWT token and return user data"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_user(username: str) -> Optional[Dict]:
    """Get user from database"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, password_hash FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {"username": user[0], "password_hash": user[1]}
    return None

def create_user(username: str, password: str) -> bool:
    """Create new user in database"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    try:
        password_hash = hash_password(password)
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                      (username, password_hash))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def update_user_telegram_chat_id(username: str, chat_id: str) -> bool:
    """Update user's Telegram chat ID"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users 
            SET telegram_chat_id = ?, telegram_linked_at = CURRENT_TIMESTAMP 
            WHERE username = ?
        """, (chat_id, username))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        logger.error(f"Error updating telegram chat ID: {str(e)}")
        conn.close()
        return False

def get_user_telegram_chat_id(username: str) -> Optional[str]:
    """Get user's Telegram chat ID"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_chat_id FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result and result[0] else None

def send_telegram_message(chat_id: str, message: str) -> bool:
    """Send message to Telegram chat"""
    from telegram_bot import send_message
    try:
        send_message(chat_id, message)
        return True
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")
        return False

def generate_verification_token() -> str:
    """Generate a secure verification token"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

def store_verification_token(username: str, token: str) -> bool:
    """Store verification token for user"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users 
            SET telegram_verification_token = ?, telegram_verified = 0 
            WHERE username = ?
        """, (token, username))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        logger.error(f"Error storing verification token: {str(e)}")
        conn.close()
        return False

def verify_token_and_link(token: str, chat_id: str) -> Optional[str]:
    """Verify token and link Telegram account, return username if successful"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    try:
        # Find user with this token
        cursor.execute("""
            SELECT username FROM users 
            WHERE telegram_verification_token = ? AND telegram_verified = 0
        """, (token,))
        result = cursor.fetchone()
        
        if result:
            username = result[0]
            # Update user with chat_id and mark as verified
            cursor.execute("""
                UPDATE users 
                SET telegram_chat_id = ?, telegram_verified = 1, 
                    telegram_linked_at = CURRENT_TIMESTAMP,
                    telegram_verification_token = NULL
                WHERE username = ?
            """, (chat_id, username))
            conn.commit()
            conn.close()
            return username
        
        conn.close()
        return None
    except Exception as e:
        logger.error(f"Error verifying token: {str(e)}")
        conn.close()
        return None

def get_user_by_chat_id(chat_id: str) -> Optional[str]:
    """Get username by Telegram chat ID"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE telegram_chat_id = ? AND telegram_verified = 1", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

def generate_audio_file(text: str, language: str) -> tuple[str, str]:
    """Generate audio file from text and return file path and URL with validation"""
    try:
        # Validate input
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Empty text provided for audio generation")
        
        if not language or not language.strip():
            raise HTTPException(status_code=400, detail="Language not specified")
        
        # Generate audio
        filepath, audio_url = generate_audio_file_with_url(text.strip(), language.strip(), str(static_dir / "audio"))
        
        return filepath, audio_url
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error generating audio: {error_message}")
        
        # Provide more specific error messages
        if "language" in error_message.lower() or "supported" in error_message.lower():
            raise HTTPException(status_code=400, detail=f"Language error: {error_message}")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to generate audio: {error_message}")

def translate_text_wrapper(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """Translate text from source language to target language with validation"""
    try:
        # Validate input
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Empty text provided for translation")
        
        if not target_lang or not target_lang.strip():
            raise HTTPException(status_code=400, detail="Target language not specified")
        
        # Perform translation
        result = translate_text(text.strip(), target_lang.strip(), source_lang)
        
        # Validate result
        if not result or result.strip() == "":
            raise HTTPException(status_code=500, detail="Translation returned empty result")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error translating text: {error_message}")
        
        # Provide more specific error messages
        if "language" in error_message.lower():
            raise HTTPException(status_code=400, detail=f"Language error: {error_message}")
        elif "network" in error_message.lower() or "connection" in error_message.lower():
            raise HTTPException(status_code=503, detail="Translation service unavailable. Please check your internet connection.")
        else:
            raise HTTPException(status_code=500, detail=f"Translation failed: {error_message}")

def translate_with_gemini(text: str, target_language: str) -> str:
    """Translate text using Gemini API with enhanced error handling"""
    try:
        # Validate input
        if not text or not text.strip():
            logger.warning("Empty text provided for Gemini translation")
            return text
        
        if not target_language or target_language.lower() in ['en', 'english']:
            logger.info("Target language is English, returning original text")
            return text
        
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "AIzaSyBwUWCGI0z54hn0oylWRcFhtlVnTg58uZ0"))
        
        # Enhanced prompt for better translation
        prompt = f"""Translate the following text from English to {target_language}. 
        Make sure the translation is natural and accurate.
        If this is a train announcement or railway-related text, use appropriate formal language.
        Preserve all numbers and technical terms.
        
        Text to translate: {text}
        
        Important: Return ONLY the translated text, no explanations."""
        
        model = "gemini-2.0-flash"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            system_instruction=[
                types.Part.from_text(text="You are a professional translator. Provide accurate translations maintaining the tone and style of the original text. For formal or technical content, use appropriate formal language in the target language."),
            ],
            temperature=0.1,  # Lower temperature for consistent translations
        )
        
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        if response and response.text:
            translated_text = response.text.strip()
            if translated_text and len(translated_text) > 0:
                logger.info(f"Successfully translated with Gemini to {target_language}")
                return translated_text
            else:
                logger.warning("Gemini returned empty translation")
                raise Exception("Empty translation from Gemini")
        else:
            logger.warning("No response from Gemini")
            raise Exception("No response from Gemini")
            
    except Exception as e:
        logger.error(f"Error translating with Gemini to {target_language}: {str(e)}")
        # Fallback to Google Translator
        logger.info("Falling back to Deep Translator")
        return translate_text(text, target_language, "auto")

def get_user_preferences(username: str) -> Dict:
    """Get user preferences from database"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT preferred_language, audio_notifications 
        FROM users WHERE username = ?
    """, (username,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            "preferred_language": result[0] or "en",
            "audio_notifications": bool(result[1]) if result[1] is not None else False
        }
    return {"preferred_language": "en", "audio_notifications": False}

def update_user_preferences(username: str, preferred_language: str, audio_notifications: bool) -> bool:
    """Update user preferences in database"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users 
            SET preferred_language = ?, audio_notifications = ? 
            WHERE username = ?
        """, (preferred_language, audio_notifications, username))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        logger.error(f"Error updating user preferences: {str(e)}")
        conn.close()
        return False

# Static file endpoints
@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main login/signup page"""
    try:
        with open(static_dir / "index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("""
        <html>
            <body>
                <h1>MultiLingo Web App</h1>
                <p>Please run the setup to create the frontend files.</p>
                <p>Static files not found. Make sure to create the HTML, CSS, and JS files.</p>
            </body>
        </html>
        """)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard page"""
    try:
        with open(static_dir / "dashboard.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("""
        <html>
            <body>
                <h1>Dashboard</h1>
                <p>Dashboard HTML file not found.</p>
            </body>
        </html>
        """)

@app.get("/profile", response_class=HTMLResponse)
async def profile_page():
    """Serve the profile page"""
    try:
        with open(static_dir / "profile.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("""
        <html>
            <body>
                <h1>Profile</h1>
                <p>Profile HTML file not found.</p>
            </body>
        </html>
        """)

@app.get("/translate", response_class=HTMLResponse)
async def translate_page():
    """Serve the translate page"""
    try:
        with open(static_dir / "translate.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("""
        <html>
            <body>
                <h1>Translate</h1>
                <p>Translate HTML file not found.</p>
            </body>
        </html>
        """)

# Authentication endpoints
@app.post("/signup")
async def signup(user: UserCreate):
    """User registration endpoint"""
    if len(user.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long")
    
    if len(user.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
    
    if create_user(user.username, user.password):
        return {"message": "User created successfully"}
    else:
        raise HTTPException(status_code=400, detail="Username already exists")

@app.post("/login")
async def login(user: UserLogin):
    """User login endpoint"""
    db_user = get_user(user.username)
    
    if not db_user or not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Voice translation endpoints (protected)
@app.post("/generate-audio")
async def generate_audio(request: GenerateAudioRequest, current_user: Dict = Depends(verify_token)):
    """Generate audio from text (protected endpoint)"""
    try:
        filepath, audio_url = generate_audio_file(request.text, request.language)
        return {
            "message": "Audio generated successfully",
            "audio_url": audio_url,
            "language": request.language,
            "text": request.text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/text-to-speech")
async def text_to_speech(request: TTSRequest, current_user: Dict = Depends(verify_token)):
    """Convert text to speech and return audio URL"""
    try:
        filepath, audio_url = generate_audio_file(request.text, request.language)
        return {
            "audio_url": audio_url,
            "language": request.language,
            "text": request.text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate-and-speak")
async def translate_and_speak(request: TranslateAndSpeakRequest, current_user: Dict = Depends(verify_token)):
    """Translate text to multiple languages and generate audio files"""
    results = []
    
    for target_lang in request.target_languages:
        try:
            # Translate text
            translated_text = translate_text_wrapper(request.text, target_lang, request.source_language)
            
            # Generate audio file
            filepath, audio_url = generate_audio_file(translated_text, target_lang)
            
            results.append(TranslationResult(
                language=target_lang,
                translated_text=translated_text,
                audio_url=audio_url
            ))
            
        except Exception as e:
            logger.error(f"Error processing language {target_lang}: {str(e)}")
            results.append(TranslationResult(
                language=target_lang,
                translated_text="Translation failed",
                audio_url=None
            ))
    
    return {"results": results}

@app.post("/multi-language-speak")
async def multi_language_speak(request: MultiLanguageTextRequest, current_user: Dict = Depends(verify_token)):
    """Convert multiple texts in different languages to speech"""
    results = []
    
    for item in request.texts:
        try:
            text = item.get("text", "")
            language = item.get("language", "en")
            
            if not text:
                results.append({
                    "language": language,
                    "status": "error",
                    "message": "Text is required"
                })
                continue
            
            filepath, audio_url = generate_audio_file(text, language)
            results.append({
                "language": language,
                "text": text,
                "audio_url": audio_url,
                "status": "success"
            })
            
        except Exception as e:
            logger.error(f"Error processing text: {str(e)}")
            results.append({
                "language": item.get("language", "unknown"),
                "status": "error",
                "message": str(e)
            })
    
    return {"results": results}

@app.get("/supported-languages")
async def get_supported_languages_endpoint():
    """Get list of commonly supported languages for TTS and translation"""
    return {"languages": get_supported_languages(extended=True)}

@app.get("/me")
async def get_current_user(current_user: Dict = Depends(verify_token)):
    """Get current user information"""
    telegram_chat_id = get_user_telegram_chat_id(current_user["username"])
    
    # Check if user is verified and get preferences
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT telegram_verified, preferred_language, audio_notifications 
        FROM users WHERE username = ?
    """, (current_user["username"],))
    result = cursor.fetchone()
    conn.close()
    
    telegram_verified = result[0] if result and result[0] else False
    preferred_language = result[1] if result and result[1] else "en"
    audio_notifications = bool(result[2]) if result and result[2] is not None else False
    
    return {
        "username": current_user["username"],
        "telegram_linked": telegram_chat_id is not None and telegram_verified,
        "telegram_verified": telegram_verified,
        "telegram_chat_id": telegram_chat_id if telegram_verified else None,
        "preferred_language": preferred_language,
        "audio_notifications": audio_notifications
    }

@app.post("/api/user/preferences")
async def update_preferences(request: UserPreferencesRequest, current_user: Dict = Depends(verify_token)):
    """Update user preferences"""
    try:
        success = update_user_preferences(
            current_user["username"], 
            request.preferred_language, 
            request.audio_notifications
        )
        
        if success:
            return {
                "message": "Preferences updated successfully",
                "preferred_language": request.preferred_language,
                "audio_notifications": request.audio_notifications
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to update preferences")
    except Exception as e:
        logger.error(f"Error updating preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update preferences: {str(e)}")

@app.get("/api/user/preferences")
async def get_preferences(current_user: Dict = Depends(verify_token)):
    """Get user preferences"""
    try:
        preferences = get_user_preferences(current_user["username"])
        return preferences
    except Exception as e:
        logger.error(f"Error getting preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get preferences: {str(e)}")

@app.get("/api/user/profile")
async def get_user_profile(current_user: Dict = Depends(verify_token)):
    """Get user profile information"""
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT username, telegram_chat_id, telegram_verified, 
                   preferred_language, audio_notifications, created_at
            FROM users WHERE username = ?
        """, (current_user["username"],))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                "username": result[0],
                "telegram_linked": result[1] is not None and result[2],
                "telegram_chat_id": result[1] if result[2] else None,
                "preferred_language": result[3] or "en",
                "audio_notifications": bool(result[4]),
                "member_since": result[5]
            }
        else:
            raise HTTPException(status_code=404, detail="User not found")
            
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get user profile: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get preferences: {str(e)}")

@app.post("/api/translate/gemini")
async def translate_gemini(request: GeminiTranslationRequest, current_user: Dict = Depends(verify_token)):
    """Translate text using Gemini API"""
    try:
        translated_text = translate_with_gemini(request.text, request.target_language)
        
        return {
            "original_text": request.text,
            "translated_text": translated_text,
            "target_language": request.target_language
        }
    except Exception as e:
        logger.error(f"Error with Gemini translation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to translate with Gemini: {str(e)}")

# Telegram integration endpoints (moved to profile)
# @app.get("/telegram", response_class=HTMLResponse)
# async def telegram_page():
#     """Serve the Telegram integration page - REMOVED: functionality moved to profile"""
#     return RedirectResponse(url="/profile")

@app.post("/api/telegram/generate-token")
async def generate_telegram_token(current_user: Dict = Depends(verify_token)):
    """Generate verification token for Telegram linking"""
    try:
        token = generate_verification_token()
        success = store_verification_token(current_user["username"], token)
        
        if success:
            return {
                "token": token,
                "message": "Verification token generated. Send this token to the Telegram bot using: /verify <token>",
                "expires_info": "Token will expire after successful verification or when a new token is generated."
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to generate verification token")
    except Exception as e:
        logger.error(f"Error generating token: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate token: {str(e)}")

@app.post("/api/telegram/get-token")
async def get_user_token_by_chat_id(request: dict):
    """Get user token by Telegram chat ID for internal API calls"""
    try:
        chat_id = request.get("chat_id")
        if not chat_id:
            raise HTTPException(status_code=400, detail="Chat ID is required")
        
        # Get username by chat_id
        username = get_user_by_chat_id(chat_id)
        if not username:
            raise HTTPException(status_code=404, detail="User not found or not verified")
        
        # Get user details
        user = get_user(username)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create a token for API access
        token_data = {"sub": username, "exp": datetime.utcnow() + timedelta(hours=24)}
        token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
        
        return {"token": token, "username": username}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting token by chat ID: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/telegram/verify-token")
async def verify_telegram_token(request: dict):
    """Verify Telegram integration token"""
    try:
        token = request.get("token")
        chat_id = request.get("chat_id")
        
        if not token or not chat_id:
            raise HTTPException(status_code=400, detail="Token and chat_id are required")
        
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        
        # Find user with this verification token
        cursor.execute("""
            SELECT username, telegram_verification_token FROM users 
            WHERE telegram_verification_token = ? AND telegram_verified = 0
        """, (token,))
        
        user = cursor.fetchone()
        if not user:
            conn.close()
            raise HTTPException(status_code=404, detail="Invalid or expired verification token")
        
        username = user[0]
        
        # Update user with chat_id and mark as verified
        cursor.execute("""
            UPDATE users 
            SET telegram_chat_id = ?, telegram_verified = 1, 
                telegram_linked_at = CURRENT_TIMESTAMP,
                telegram_verification_token = NULL
            WHERE username = ?
        """, (chat_id, username))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Telegram verification successful for user: {username}")
        
        return {
            "message": "Telegram account successfully linked",
            "username": username,
            "chat_id": chat_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying telegram token: {str(e)}")
        raise HTTPException(status_code=500, detail="Verification failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying token: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to verify token: {str(e)}")

@app.post("/api/telegram/link")
async def link_telegram(request: TelegramLinkRequest, current_user: Dict = Depends(verify_token)):
    """Link user's account with Telegram chat ID (legacy endpoint - now requires verification)"""
    try:
        # Check if user already has a verified account
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_verified FROM users WHERE username = ?", (current_user["username"],))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            raise HTTPException(status_code=400, detail="Telegram account already verified. Use token-based verification for security.")
        
        # For backward compatibility, allow direct linking but mark as unverified
        success = update_user_telegram_chat_id(current_user["username"], request.chat_id)
        if success:
            return {
                "message": "Telegram chat ID saved but not verified. Please use token verification for full access.",
                "chat_id": request.chat_id,
                "verified": False
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to link Telegram account")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking Telegram: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to link Telegram: {str(e)}")

@app.get("/api/telegram/pending-token")
async def get_pending_token(current_user: Dict = Depends(verify_token)):
    """Get the current pending verification token for the user"""
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT telegram_verification_token 
            FROM users 
            WHERE username = ? AND telegram_verified = 0
        """, (current_user["username"],))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return {"token": result[0]}
        else:
            raise HTTPException(status_code=404, detail="No pending verification token found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pending token: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get pending token: {str(e)}")

@app.post("/api/telegram/send-message")
async def send_telegram_message_api(request: TelegramSendMessageRequest, current_user: Dict = Depends(verify_token)):
    """Send message to user's linked Telegram chat"""
    try:
        # Check if user is verified
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_chat_id, telegram_verified FROM users WHERE username = ?", (current_user["username"],))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result[0]:
            raise HTTPException(status_code=400, detail="No Telegram account linked. Please link your Telegram first.")
        
        chat_id, verified = result
        if not verified:
            raise HTTPException(status_code=400, detail="Telegram account not verified. Please complete verification process.")
        
        success = send_telegram_message(chat_id, request.message)
        if success:
            return {
                "message": "Message sent successfully to Telegram",
                "chat_id": chat_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send message to Telegram")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

@app.post("/api/telegram/unlink")
async def unlink_telegram(current_user: Dict = Depends(verify_token)):
    """Unlink user's Telegram account"""
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        
        # Clear all telegram-related fields
        cursor.execute("""
            UPDATE users 
            SET telegram_chat_id = NULL, 
                telegram_verified = 0, 
                telegram_verification_token = NULL,
                telegram_linked_at = NULL
            WHERE username = ?
        """, (current_user["username"],))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        if success:
            return {"message": "Telegram account unlinked successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to unlink Telegram account")
    except Exception as e:
        logger.error(f"Error unlinking Telegram: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to unlink Telegram: {str(e)}")

@app.get("/api/telegram/status")
async def get_telegram_status(current_user: Dict = Depends(verify_token)):
    """Get Telegram linking status for current user"""
    try:
        chat_id = get_user_telegram_chat_id(current_user["username"])
        
        # Check verification status
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_verified, telegram_verification_token FROM users WHERE username = ?", (current_user["username"],))
        result = cursor.fetchone()
        conn.close()
        
        verified = result[0] if result and result[0] else False
        has_pending_token = result[1] is not None if result else False
        
        return {
            "linked": chat_id is not None and verified,
            "verified": verified,
            "chat_id": chat_id if verified else None,
            "has_pending_verification": has_pending_token
        }
    except Exception as e:
        logger.error(f"Error getting Telegram status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get Telegram status: {str(e)}")

@app.get("/api/telegram/qr-code")
async def generate_telegram_qr_code(current_user: Dict = Depends(verify_token)):
    """Generate QR code for Telegram verification link"""
    try:
        # Get the current verification token
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_verification_token FROM users WHERE username = ?", (current_user["username"],))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result[0]:
            raise HTTPException(status_code=404, detail="No verification token found. Please generate a token first.")
        
        token = result[0]
        bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "Multilingotrain_bot")
        telegram_url = f"https://t.me/{bot_username}?text={token}"
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=ERROR_CORRECT_H,
            box_size=8,
            border=4,
        )
        qr.add_data(telegram_url)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 for embedding in response
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        # Also save to static folder for direct access
        qr_filename = f"telegram_qr_{current_user['username']}.png"
        qr_path = static_dir / "qr" / qr_filename
        
        # Create qr directory if it doesn't exist
        qr_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(qr_path))
        
        return {
            "qr_code_base64": f"data:image/png;base64,{img_base64}",
            "qr_code_url": f"/static/qr/{qr_filename}",
            "telegram_url": telegram_url,
            "token": token,
            "bot_username": bot_username
        }
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate QR code: {str(e)}")

# Train status endpoints
@app.get("/train-status", response_class=HTMLResponse)
async def train_status_page():
    """Serve the train status page"""
    try:
        with open(static_dir / "train_status.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("""
        <html>
            <body>
                <h1>Train Status</h1>
                <p>Train status HTML file not found.</p>
            </body>
        </html>
        """)

@app.get("/api/train-status/{train_number}")
async def get_train_status(train_number: str, current_user: Dict = Depends(verify_token)):
    """Get live train status from API"""
    try:
        url = os.getenv("MOCK_API_TRAIN_STATUS_URL", "http://127.0.0.1:5001/api/train/status")
        querystring = {"trainNo": train_number, "startDay": "1"}
        response = requests.get(url, params=querystring)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch train status")
            
    except Exception as e:
        logger.error(f"Error fetching train status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch train status: {str(e)}")

@app.get("/api/train-status-local")
async def get_local_train_status(current_user: Dict = Depends(verify_token)):
    """Get train status from local JSON file"""
    try:
        with open("trainStatus.json", "r") as f:
            import json
            data = json.load(f)
            return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Train status data not found")
    except Exception as e:
        logger.error(f"Error reading train status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to read train status: {str(e)}")

@app.post("/api/train-subscription/subscribe")
async def subscribe_to_train_updates(request: TrainSubscriptionRequest, current_user: Dict = Depends(verify_token)):
    """Subscribe to train status updates"""
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        
        # Check if user already subscribed to this train
        cursor.execute("""
            SELECT id FROM train_subscriptions 
            WHERE username = ? AND train_number = ? AND is_active = 1
        """, (current_user["username"], request.train_number))
        
        if cursor.fetchone():
            conn.close()
            return {"message": "Already subscribed to this train", "subscribed": True}
        
        # Add or reactivate subscription
        cursor.execute("""
            INSERT OR REPLACE INTO train_subscriptions (username, train_number, subscribed_at, is_active)
            VALUES (?, ?, CURRENT_TIMESTAMP, 1)
        """, (current_user["username"], request.train_number))
        
        conn.commit()
        conn.close()
        
        # Send notification to user's Telegram if linked
        chat_id = get_user_telegram_chat_id(current_user["username"])
        if chat_id:
            # Get current train status for the notification
            try:
                with open("trainStatus.json", "r") as f:
                    train_data = json.load(f)
                
                if train_data.get("status") and train_data.get("data"):
                    train_info = train_data["data"]
                    notification_message = f"🚂 *Train Subscription Activated!*\n\n"
                    notification_message += f"*Train:* {train_info.get('train_name', 'N/A')} ({request.train_number})\n"
                    notification_message += f"*Route:* {train_info.get('source_stn_name', 'N/A')} → {train_info.get('dest_stn_name', 'N/A')}\n\n"
                    notification_message += f"*Current Status:*\n"
                    notification_message += f"📍 *Location:* {train_info.get('current_station_name', 'N/A')}\n"
                    notification_message += f"⏰ *Last Update:* {train_info.get('status_as_of', 'N/A')}\n"
                    notification_message += f"⏱️ *Delay:* {train_info.get('delay', 0)} minutes\n"
                    notification_message += f"📏 *Distance Covered:* {train_info.get('distance_from_source', 0)}/{train_info.get('total_distance', 0)} km\n\n"
                    notification_message += f"You will receive updates for this train! 🔔"
                    
                    send_telegram_message(chat_id, notification_message)
                else:
                    # Fallback message if train data is not available
                    notification_message = f"🚂 *Train Subscription Activated!*\n\n"
                    notification_message += f"*Train Number:* {request.train_number}\n"
                    if request.train_name:
                        notification_message += f"*Train Name:* {request.train_name}\n"
                    notification_message += f"\nYou will receive updates for this train! 🔔"
                    
                    send_telegram_message(chat_id, notification_message)
                    
            except Exception as e:
                logger.error(f"Error sending subscription notification: {str(e)}")
                # Send basic notification even if detailed train data fails
                notification_message = f"🚂 *Train Subscription Activated!*\n\n"
                notification_message += f"*Train Number:* {request.train_number}\n"
                notification_message += f"\nYou will receive updates for this train! 🔔"
                send_telegram_message(chat_id, notification_message)
        
        return {
            "message": "Successfully subscribed to train updates",
            "train_number": request.train_number,
            "subscribed": True,
            "notification_sent": bool(chat_id)
        }
        
    except Exception as e:
        logger.error(f"Error subscribing to train updates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to subscribe: {str(e)}")

@app.delete("/api/train-subscription/unsubscribe/{train_number}")
async def unsubscribe_from_train_updates(train_number: str, current_user: Dict = Depends(verify_token)):
    """Unsubscribe from train status updates"""
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        
        # Deactivate subscription
        cursor.execute("""
            UPDATE train_subscriptions 
            SET is_active = 0 
            WHERE username = ? AND train_number = ?
        """, (current_user["username"], train_number))
        
        conn.commit()
        conn.close()
        
        # Send notification to user's Telegram if linked
        chat_id = get_user_telegram_chat_id(current_user["username"])
        if chat_id:
            notification_message = f"🚂 *Train Subscription Cancelled*\n\n"
            notification_message += f"*Train Number:* {train_number}\n"
            notification_message += f"\nYou will no longer receive updates for this train."
            send_telegram_message(chat_id, notification_message)
        
        return {
            "message": "Successfully unsubscribed from train updates",
            "train_number": train_number,
            "subscribed": False
        }
        
    except Exception as e:
        logger.error(f"Error unsubscribing from train updates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to unsubscribe: {str(e)}")

@app.get("/api/train-subscription/status/{train_number}")
async def get_subscription_status(train_number: str, current_user: Dict = Depends(verify_token)):
    """Check if user is subscribed to a specific train"""
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT is_active, subscribed_at FROM train_subscriptions 
            WHERE username = ? AND train_number = ?
        """, (current_user["username"], train_number))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return {
                "subscribed": True,
                "train_number": train_number,
                "subscribed_at": result[1]
            }
        else:
            return {
                "subscribed": False,
                "train_number": train_number
            }
            
    except Exception as e:
        logger.error(f"Error checking subscription status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check subscription: {str(e)}")

@app.get("/api/train-subscription/list")
async def list_user_subscriptions(current_user: Dict = Depends(verify_token)):
    """Get all train subscriptions for the current user"""
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT train_number, subscribed_at, is_active 
            FROM train_subscriptions 
            WHERE username = ? 
            ORDER BY subscribed_at DESC
        """, (current_user["username"],))
        
        results = cursor.fetchall()
        conn.close()
        
        subscriptions = []
        for result in results:
            # Try to get train name from sample data or use train number
            train_name = get_train_name_from_cache(result[0])
            
            subscriptions.append({
                "train_number": result[0],
                "train_name": train_name,
                "subscribed_at": result[1],
                "is_active": bool(result[2])
            })
        
        return {
            "subscriptions": subscriptions,
            "total": len(subscriptions),
            "active": len([s for s in subscriptions if s["is_active"]])
        }
            
    except Exception as e:
        logger.error(f"Error listing subscriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list subscriptions: {str(e)}")

def get_train_name_from_cache(train_number: str) -> Optional[str]:
    """Get train name from cached data or sample data"""
    # Sample train names mapping
    train_names = {
        '11014': 'Lokmanya Tilak Express',
        '12244': 'Bengaluru Rajdhani',
        '12269': 'Chennai Duronto',
        '12322': 'Howrah Mail',
        '12433': 'Rajdhani Express',
        '12507': 'Aronai Express',
        '12635': 'Vaigai Express',
        '12639': 'Brindavan Express',
        '12647': 'Kongu Express',
        '12671': 'Nilagiri Express',
        '12809': 'Howrah Mail',
        '16057': 'Sapthagiri Express',
        '17229': 'Sabari Express',
        '20644': 'Ernakulam Express',
        '22638': 'West Coast Express'
    }
    return train_names.get(train_number)

# Import train notification service
from train_notification_service import TrainNotificationService

# Initialize train notification service
train_service = TrainNotificationService()

@app.post("/api/train-notifications/start")
async def start_train_notifications(current_user: Dict = Depends(verify_token)):
    """Start train notification monitoring service"""
    try:
        if not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        train_service.start_monitoring()
        return {
            "message": "Train notification service started",
            "status": "running"
        }
    except Exception as e:
        logger.error(f"Error starting train notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start service: {str(e)}")

@app.post("/api/train-notifications/stop")
async def stop_train_notifications(current_user: Dict = Depends(verify_token)):
    """Stop train notification monitoring service"""
    try:
        if not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        train_service.stop_monitoring()
        return {
            "message": "Train notification service stopped",
            "status": "stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping train notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop service: {str(e)}")

@app.get("/api/train-notifications/status")
async def get_train_notification_status(current_user: Dict = Depends(verify_token)):
    """Get train notification service status"""
    try:
        return {
            "service_running": train_service.is_running,
            "check_interval": train_service.check_interval,
            "subscribed_users_count": len(train_service.get_subscribed_users())
        }
    except Exception as e:
        logger.error(f"Error getting service status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@app.post("/api/train-notifications/manual-update")
async def send_manual_train_update(
    request: dict,
    current_user: Dict = Depends(verify_token)
):
    """Send manual train update to subscribers"""
    try:
        if not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        message = request.get("message", "")
        train_number = request.get("train_number")
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        sent_count = train_service.send_manual_update(message, train_number)
        
        return {
            "message": "Manual update sent successfully",
            "recipients_count": sent_count,
            "train_number": train_number
        }
    except Exception as e:
        logger.error(f"Error sending manual update: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send update: {str(e)}")

@app.get("/api/train-notifications/subscribers")
async def get_train_subscribers(current_user: Dict = Depends(verify_token)):
    """Get list of users subscribed to train notifications"""
    try:
        if not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        users = train_service.get_subscribed_users()
        return {
            "subscribers": users,
            "total_count": len(users)
        }
    except Exception as e:
        logger.error(f"Error getting subscribers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get subscribers: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "voice-translator-web-app"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
