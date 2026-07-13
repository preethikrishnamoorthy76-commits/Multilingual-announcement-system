"""
Common utilities for voice translation functionality.
Shared between the web app and Telegram bot.
"""

import os
import uuid
import tempfile
from gtts import gTTS
from deep_translator import GoogleTranslator
from typing import Optional, Dict

# Language codes for translation (from telegram_bot.py as priority)
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'es': 'Spanish', 
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh': 'Chinese',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'ta': 'Tamil',
    'te': 'Telugu'
}

# Extended language mapping for web app compatibility
EXTENDED_LANGUAGES = {
    **SUPPORTED_LANGUAGES,
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)", 
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
    "fil": "Filipino"
}

def translate_text(text: str, target_language: str, source_language: str = "auto") -> str:
    """Translate text using Google Translator with proper error handling and language code mapping"""
    try:
        # Language code mapping for compatibility between deep-translator and gTTS
        language_map = {
            'zh': 'zh-CN',  # Chinese simplified
            'zh-cn': 'zh-CN',
            'zh-tw': 'zh-TW',
            'fil': 'tl',  # Filipino to Tagalog
            'he': 'iw',   # Hebrew mapping
        }
        
        # Map target language if needed
        mapped_target = language_map.get(target_language.lower(), target_language)
        mapped_source = language_map.get(source_language.lower(), source_language) if source_language != "auto" else "auto"
        
        # Validate input
        if not text or not text.strip():
            raise ValueError("Empty text provided for translation")
        
        # Initialize translator with timeout
        translator = GoogleTranslator(source=mapped_source, target=mapped_target)
        
        # Perform translation
        translated = translator.translate(text.strip())
        
        # Validate output
        if not translated or translated.strip() == "":
            raise ValueError("Translation returned empty result")
            
        return translated.strip()
        
    except ValueError as ve:
        raise Exception(f"Translation validation error: {str(ve)}")
    except Exception as e:
        error_msg = str(e).lower()
        if "language" in error_msg:
            raise Exception(f"Unsupported language code. Source: {source_language}, Target: {target_language}")
        elif "network" in error_msg or "connection" in error_msg:
            raise Exception("Network error during translation. Please check your internet connection.")
        else:
            raise Exception(f"Translation failed: {str(e)}")

def generate_audio(text: str, language: str = "en") -> str:
    """Generate audio file from text using gTTS with proper language code mapping"""
    try:
        # Validate input
        if not text or not text.strip():
            raise ValueError("Empty text provided for audio generation")
        
        # Language code mapping for gTTS compatibility
        # Map to what gTTS actually expects
        gtts_language_map = {
            'zh': 'zh-CN',      # Chinese
            'zh-cn': 'zh-CN',   # Chinese simplified
            'zh-CN': 'zh-CN',   # Chinese simplified (already correct)
            'zh-tw': 'zh-TW',   # Chinese traditional
            'zh-TW': 'zh-TW',   # Chinese traditional (already correct)
            'fil': 'tl',        # Filipino to Tagalog
            'he': 'iw',         # Hebrew mapping for gTTS
        }
        
        # Map language code if needed (case-insensitive lookup)
        lang_lower = language.lower()
        mapped_lang = gtts_language_map.get(lang_lower, language)
        
        # Validate language support
        from gtts.lang import tts_langs
        supported_langs = tts_langs()
        if mapped_lang not in supported_langs:
            raise ValueError(f"Language '{language}' is not supported by gTTS. Supported: {list(supported_langs.keys())}")
        
        # Create a unique filename
        filename = f"voice_{uuid.uuid4().hex}.mp3"
        file_path = os.path.join(tempfile.gettempdir(), filename)
        
        # Generate audio with error handling
        tts = gTTS(text=text.strip(), lang=mapped_lang, slow=False)
        tts.save(file_path)
        
        # Verify file was created
        if not os.path.exists(file_path):
            raise Exception("Audio file was not created successfully")
        
        return file_path
        
    except ValueError as ve:
        print(f"Audio generation validation error: {str(ve)}")
        return None
    except Exception as e:
        print(f"Audio generation error: {str(e)}")
        return None

def generate_audio_file_with_url(text: str, language: str, static_audio_dir: str) -> tuple[str, str]:
    """Generate audio file from text and return file path and URL (for web app) with proper language mapping"""
    try:
        # Validate input
        if not text or not text.strip():
            raise ValueError("Empty text provided for audio generation")
        
        # Language code mapping for gTTS compatibility
        # Map to what gTTS actually expects
        gtts_language_map = {
            'zh': 'zh-CN',      # Chinese
            'zh-cn': 'zh-CN',   # Chinese simplified
            'zh-CN': 'zh-CN',   # Chinese simplified (already correct)
            'zh-tw': 'zh-TW',   # Chinese traditional
            'zh-TW': 'zh-TW',   # Chinese traditional (already correct)
            'fil': 'tl',        # Filipino to Tagalog
            'he': 'iw',         # Hebrew mapping for gTTS
        }
        
        # Map language code if needed (case-insensitive lookup)
        lang_lower = language.lower()
        mapped_lang = gtts_language_map.get(lang_lower, language)
        
        # Validate language support
        from gtts.lang import tts_langs
        supported_langs = tts_langs()
        if mapped_lang not in supported_langs:
            raise ValueError(f"Language '{language}' is not supported by gTTS. Available languages: {', '.join(list(supported_langs.keys())[:10])}...")
        
        # Generate audio
        tts = gTTS(text=text.strip(), lang=mapped_lang, slow=False)
        filename = f"voice_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(static_audio_dir, filename)
        tts.save(filepath)
        
        # Verify file was created
        if not os.path.exists(filepath):
            raise Exception("Audio file was not created successfully")
        
        audio_url = f"/static/audio/{filename}"
        return filepath, audio_url
        
    except ValueError as ve:
        raise Exception(f"Audio generation validation error: {str(ve)}")
    except Exception as e:
        raise Exception(f"Failed to generate audio: {str(e)}")

def get_supported_languages(extended: bool = False) -> Dict[str, str]:
    """Get dictionary of supported language codes and names"""
    if extended:
        return EXTENDED_LANGUAGES.copy()
    return SUPPORTED_LANGUAGES.copy()

def is_language_supported(language_code: str, extended: bool = False) -> bool:
    """Check if language code is supported"""
    if extended:
        return language_code in EXTENDED_LANGUAGES
    return language_code in SUPPORTED_LANGUAGES

def get_language_name(language_code: str, extended: bool = False) -> Optional[str]:
    """Get language name from code"""
    if extended:
        return EXTENDED_LANGUAGES.get(language_code)
    return SUPPORTED_LANGUAGES.get(language_code)

def get_help_message() -> str:
    """Get help message with available commands (for Telegram bot)"""
    return """
🤖 MultiLingo Bot Commands:

📝 /start - Start the bot and get your Chat ID
❓ /help - Show this help message
🌍 /languages - Show supported languages
🆔 /mychatid or /id - Get your Chat ID
🔐 /verify <token> - Verify your account with token from web app

📖 Translation Commands:
• /translate <target_lang> <text> - Translate text
  Example: /translate es Hello world

🎵 Audio Commands:
• /speak <lang> <text> - Generate audio
  Example: /speak en Hello world
• /translate_speak <target_lang> <text> - Translate and speak
  Example: /translate_speak fr Hello world

� Train Status Commands:
• /train_status - Get current train status
• /train_subscribe <train_number> - Subscribe to train notifications
  Example: /train_subscribe 22638
• /train_unsubscribe <train_number> - Unsubscribe from train notifications
  Example: /train_unsubscribe 22638

�🔗 Account Linking:
1. Login to MultiLingo web app
2. Go to Telegram section
3. Generate verification token
4. Send: /verify <your_token>
5. Get notifications for translations and train updates!

💡 Tips:
- Use language codes (en, es, fr, de, etc.)
- Send any text without commands for auto-translation to English
- Verify your account to receive web app notifications
- Subscribe to trains to get real-time status updates
"""

def get_languages_message() -> str:
    """Get formatted list of supported languages (for Telegram bot)"""
    msg = "🌍 Supported Languages:\n\n"
    for code, name in SUPPORTED_LANGUAGES.items():
        msg += f"• {code} - {name}\n"
    return msg
