#!/usr/bin/env python3
"""
Train Status Notification Service
Monitors train status changes and sends updates to subscribed Telegram users
"""

import sqlite3
import requests
import json
import time
import threading
import os
import tempfile
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from pathlib import Path
from gtts import gTTS

BASE_DIR = Path(__file__).resolve().parent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('train_notifications.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TrainNotificationService:
    def __init__(self, 
                 db_path: str = None,
                 telegram_token: str = None,
                 mock_api_url: str = None,
                 check_interval: int = 60):
        
        self.db_path = db_path or os.getenv("DB_PATH", str(BASE_DIR / "users.db"))
        self.telegram_token = telegram_token or os.getenv("TELEGRAM_BOT_TOKEN", "8327968816:AAHAV5BCDfG3IERUr5IPne_1wJyCJTQTiBY")
        self.telegram_url = f'https://api.telegram.org/bot{self.telegram_token}/'
        self.mock_api_url = mock_api_url or os.getenv("MOCK_API_URL", "http://127.0.0.1:5001/api")
        self.check_interval = check_interval
        self.is_running = False
        self.last_train_status = {}
        self.notification_thread = None
        
        # Initialize database tables
        self._init_database()
        
    def _init_database(self):
        """Initialize database tables if they don't exist"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    telegram_chat_id TEXT,
                    telegram_verified INTEGER DEFAULT 0,
                    preferred_language TEXT DEFAULT 'en',
                    audio_notifications INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create train_subscriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS train_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    train_number TEXT NOT NULL,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    UNIQUE(username, train_number),
                    FOREIGN KEY (username) REFERENCES users (username)
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info("Database tables initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
        
    def get_db_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_subscribed_users(self, train_number: str = None) -> List[Dict]:
        """Get all users subscribed to train notifications"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        if train_number:
            # Get users subscribed to specific train with their preferences
            query = """
                SELECT DISTINCT u.username, u.telegram_chat_id, ts.train_number, 
                       u.preferred_language, u.audio_notifications
                FROM users u
                JOIN train_subscriptions ts ON u.username = ts.username
                WHERE u.telegram_chat_id IS NOT NULL 
                AND u.telegram_verified = 1 
                AND ts.is_active = 1 
                AND ts.train_number = ?
            """
            cursor.execute(query, (train_number,))
        else:
            # Get all users with telegram notifications enabled with their preferences
            query = """
                SELECT DISTINCT u.username, u.telegram_chat_id, 
                       u.preferred_language, u.audio_notifications
                FROM users u
                WHERE u.telegram_chat_id IS NOT NULL 
                AND u.telegram_verified = 1
            """
            cursor.execute(query)
        
        users = []
        for row in cursor.fetchall():
            if train_number:
                users.append({
                    'username': row[0],
                    'chat_id': row[1],
                    'train_number': row[2],
                    'preferred_language': row[3] or 'en',
                    'audio_notifications': bool(row[4]) if row[4] is not None else False
                })
            else:
                users.append({
                    'username': row[0],
                    'chat_id': row[1],
                    'preferred_language': row[2] or 'en',
                    'audio_notifications': bool(row[3]) if row[3] is not None else False
                })
        
        conn.close()
        return users
    
    def subscribe_user_to_train(self, username: str, train_number: str) -> bool:
        """Subscribe a user to train notifications"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO train_subscriptions 
                (username, train_number, subscribed_at, is_active) 
                VALUES (?, ?, CURRENT_TIMESTAMP, 1)
            """, (username, train_number))
            
            conn.commit()
            conn.close()
            logger.info(f"User {username} subscribed to train {train_number}")
            return True
        except Exception as e:
            logger.error(f"Error subscribing user {username} to train {train_number}: {e}")
            return False
    
    def unsubscribe_user_from_train(self, username: str, train_number: str = None) -> bool:
        """Unsubscribe a user from train notifications"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            if train_number:
                cursor.execute("""
                    UPDATE train_subscriptions 
                    SET is_active = 0 
                    WHERE username = ? AND train_number = ?
                """, (username, train_number))
            else:
                cursor.execute("""
                    UPDATE train_subscriptions 
                    SET is_active = 0 
                    WHERE username = ?
                """, (username,))
            
            conn.commit()
            conn.close()
            logger.info(f"User {username} unsubscribed from train {train_number or 'all trains'}")
            return True
        except Exception as e:
            logger.error(f"Error unsubscribing user {username}: {e}")
            return False
    
    def send_telegram_message(self, chat_id: str, text: str) -> bool:
        """Send message to Telegram user"""
        try:
            params = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
            response = requests.post(self.telegram_url + 'sendMessage', params=params, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending telegram message to {chat_id}: {e}")
            return False
    
    def send_telegram_audio(self, chat_id: str, audio_file_path: str, caption: str = None) -> bool:
        """Send audio file to Telegram user"""
        try:
            with open(audio_file_path, 'rb') as audio_file:
                files = {'audio': audio_file}
                data = {'chat_id': chat_id}
                if caption:
                    data['caption'] = caption
                
                response = requests.post(
                    self.telegram_url + 'sendAudio', 
                    data=data, 
                    files=files, 
                    timeout=30
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending telegram audio to {chat_id}: {e}")
            return False
    
    def translate_with_gemini(self, text: str, target_language: str) -> str:
        """Translate text using Gemini API with enhanced error handling"""
        try:
            # Validate input
            if not text or not text.strip():
                logger.warning("Empty text provided for Gemini translation")
                return text
            
            if not target_language or target_language.lower() in ['en', 'english']:
                logger.info("Target language is English, returning original text")
                return text
            
            logger.info(f"Starting Gemini translation from English to {target_language}")
            logger.info(f"Text to translate: {text}")
            
            # Import and initialize Gemini
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "AIzaSyBwUWCGI0z54hn0oylWRcFhtlVnTg58uZ0"))
            
            # Create a more specific prompt based on content type
            if any(keyword in text.lower() for keyword in ['train', 'platform', 'station', 'delay', 'arrival', 'departure']):
                # This is a train announcement
                prompt = f"""You are translating a railway station announcement from English to {target_language}.
                
                Please translate this train announcement while following these rules:
                1. Keep all numbers (train numbers, platform numbers, times) exactly as digits
                2. Use formal, official language appropriate for public railway announcements
                3. Maintain the same structure and meaning
                4. Make it sound natural in {target_language}
                
                English text: {text}
                
                Translate to {target_language} (return only the translation, no explanations):"""
            else:
                # General text
                prompt = f"""Translate the following text from English to {target_language}. 
                Keep numbers as digits and maintain the original meaning and tone.
                
                Text: {text}
                
                Translation to {target_language}:"""
            
            # Create the request
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ]
            
            # Configure generation with lower temperature for consistency
            config = types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1000
            )
            
            logger.info(f"Sending request to Gemini for {target_language} translation")
            
            # Generate the translation
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
                config=config,
            )
            
            if response and hasattr(response, 'text') and response.text:
                translated_text = response.text.strip()
                logger.info(f"Gemini raw response: {translated_text}")
                
                # Clean up the response (remove any extra explanations)
                lines = translated_text.split('\n')
                # Take the longest line as it's most likely the translation
                if lines:
                    translated_text = max(lines, key=len).strip()
                
                # Additional cleanup - remove common prefixes
                prefixes_to_remove = [
                    f"Translation to {target_language}:",
                    f"{target_language} translation:",
                    f"In {target_language}:",
                    "Translation:",
                    "Here is the translation:",
                    "The translation is:"
                ]
                
                for prefix in prefixes_to_remove:
                    if translated_text.lower().startswith(prefix.lower()):
                        translated_text = translated_text[len(prefix):].strip()
                
                # Validate translation quality
                if len(translated_text) >= 10 and translated_text != text:
                    logger.info(f"✅ Gemini translation successful: {translated_text}")
                    return translated_text
                else:
                    logger.warning(f"❌ Gemini translation failed validation - too short or same as original")
                    return text
            else:
                logger.error("❌ Gemini returned no response")
                return text
                
        except ImportError as ie:
            logger.error(f"❌ Gemini import error: {ie}")
            return text
        except Exception as e:
            logger.error(f"❌ Gemini translation error: {str(e)}")
            return text
    
    def format_train_number_for_audio(self, train_number: str, language: str = "en") -> str:
        """Format train number as individual digits for audio pronunciation"""
        # Convert train number to individual digits
        digits = []
        for char in str(train_number):
            if char.isdigit():
                digits.append(char)
        
        # Language-specific digit names
        if language.lower() in ['tamil', 'ta']:
            tamil_digits = {
                '0': 'poojyam',
                '1': 'ondru',
                '2': 'erandu', 
                '3': 'moonu',
                '4': 'naangu',
                '5': 'inthu',
                '6': 'aaru',
                '7': 'ezhu',
                '8': 'ettu',
                '9': 'onbadhu'
            }
            # Convert each digit to Tamil pronunciation
            tamil_digits_list = [tamil_digits.get(digit, digit) for digit in digits]
            return ' '.join(tamil_digits_list)
            
        elif language.lower() in ['hindi', 'hi']:
            hindi_digits = {
                '0': 'shunya',
                '1': 'ek',
                '2': 'do',
                '3': 'teen',
                '4': 'char',
                '5': 'panch',
                '6': 'che',
                '7': 'saat',
                '8': 'aath',
                '9': 'nau'
            }
            hindi_digits_list = [hindi_digits.get(digit, digit) for digit in digits]
            return ' '.join(hindi_digits_list)
            
        elif language.lower() in ['telugu', 'te']:
            telugu_digits = {
                '0': 'bunny',
                '1': 'okati',
                '2': 'rendu',
                '3': 'moodu',
                '4': 'naalugu',
                '5': 'aidu',
                '6': 'aaru',
                '7': 'yedu',
                '8': 'enimidi',
                '9': 'tommidi'
            }
            telugu_digits_list = [telugu_digits.get(digit, digit) for digit in digits]
            return ' '.join(telugu_digits_list)
        
        # For other languages, join with spaces so TTS reads them as individual digits
        return ' '.join(digits)
    
    def prepare_text_for_audio(self, text: str, language: str = "en") -> str:
        """Prepare text for audio by formatting train numbers as individual digits"""
        import re
        
        # Find all train numbers in the text (assuming they are 4-5 digit numbers)
        # Pattern matches various forms of train number references
        patterns = [
            r'(train number\s+)(\d{4,5})',
            r'(train\s+)(\d{4,5})',
            r'(número de tren\s+)(\d{4,5})',  # Spanish
            r'(numéro de train\s+)(\d{4,5})',  # French
            r'(ट्रेन संख्या\s+)(\d{4,5})',  # Hindi - train number
            r'(रेल संख्या\s+)(\d{4,5})',  # Hindi alternative
            r'(ট্রেন নম্বর\s+)(\d{4,5})',  # Bengali
            r'(قطار نمبر\s+)(\d{4,5})',  # Urdu
            r'(ரயில் எண்\s+)(\d{4,5})',  # Tamil - rail number
            r'(ரயில்\s+)(\d{4,5})',  # Tamil - train
            r'(வண்டி எண்\s+)(\d{4,5})',  # Tamil - vehicle number
            r'(రైలు సంఖ్య\s+)(\d{4,5})',  # Telugu - train number
            r'(రైలు\s+)(\d{4,5})',  # Telugu - train
            r'(రైల్వే\s+)(\d{4,5})',  # Telugu - railway
        ]
        
        def replace_train_number(match):
            prefix = match.group(1)
            train_num = match.group(2)
            formatted_num = self.format_train_number_for_audio(train_num, language)
            return f"{prefix}{formatted_num}"
        
        modified_text = text
        
        # Apply all patterns
        for pattern in patterns:
            modified_text = re.sub(pattern, replace_train_number, modified_text, flags=re.IGNORECASE)
        
        # Also handle standalone train numbers (4-5 digits) but be more careful
        # Only replace if it's clearly a train number context
        pattern_standalone = r'\b(\d{4,5})\b'
        
        def replace_standalone_number(match):
            train_num = match.group(1)
            # Only format if it looks like a train number (4-5 digits)
            if len(train_num) >= 4:
                # Check if this appears to be in a train context
                full_match = match.group(0)
                start_pos = match.start()
                end_pos = match.end()
                
                # Get some context around the number
                context_start = max(0, start_pos - 50)
                context_end = min(len(modified_text), end_pos + 50)
                context = modified_text[context_start:context_end].lower()
                
                # Check for train-related keywords in context
                train_keywords = ['train', 'tren', 'ट्रेन', 'রেল', 'قطار', 'रेल', 'ரயில்', 'வண்டி', 'రైలు', 'రైల్వే']
                if any(keyword in context for keyword in train_keywords):
                    return self.format_train_number_for_audio(train_num, language)
            
            return train_num
        
        modified_text = re.sub(pattern_standalone, replace_standalone_number, modified_text)
        
        return modified_text

    def generate_audio_file(self, text: str, language: str = "en") -> Optional[str]:
        """Generate audio file from text using gTTS with enhanced language support"""
        try:
            # Validate input
            if not text or not text.strip():
                logger.error("Empty text provided for audio generation")
                return None

            # Prepare text for better audio pronunciation
            prepared_text = self.prepare_text_for_audio(text, language)
            logger.info(f"Prepared text for audio ({language}): {prepared_text[:100]}...")

            # Extended language mapping for gTTS compatibility
            lang_mapping = {
                'english': 'en',
                'spanish': 'es', 
                'french': 'fr',
                'german': 'de',
                'italian': 'it',
                'portuguese': 'pt',
                'russian': 'ru',
                'japanese': 'ja',
                'korean': 'ko',
                'chinese': 'zh',
                'chinese (simplified)': 'zh',
                'chinese (traditional)': 'zh-TW',
                'arabic': 'ar',
                'hindi': 'hi',
                'tamil': 'ta',
                'telugu': 'te',
                'bengali': 'bn',
                'urdu': 'ur',
                'marathi': 'mr',
                'gujarati': 'gu',
                'kannada': 'kn',
                'malayalam': 'ml',
                'punjabi': 'pa',
                'turkish': 'tr',
                'vietnamese': 'vi',
                'thai': 'th',
                'indonesian': 'id',
                'malay': 'ms',
                'filipino': 'tl',
                'dutch': 'nl',
                'polish': 'pl',
                'czech': 'cs',
                'hungarian': 'hu',
                'romanian': 'ro',
                'bulgarian': 'bg',
                'ukrainian': 'uk',
                'greek': 'el',
                'hebrew': 'he',
                'persian': 'fa',
                'swedish': 'sv',
                'norwegian': 'no',
                'danish': 'da',
                'finnish': 'fi'
            }

            # Convert language name to code if needed
            lang_code = lang_mapping.get(language.lower(), language.lower())

            # Try gTTS first (requires internet)
            try:
                from gtts.lang import tts_langs
                supported_langs = tts_langs()
                if lang_code not in supported_langs:
                    logger.warning(f"Language '{lang_code}' not supported by gTTS. Falling back to English.")
                    lang_code = 'en'

                # Create a unique filename (mp3)
                filename = f"train_notification_{int(time.time())}_{lang_code}.mp3"
                file_path = os.path.join(tempfile.gettempdir(), filename)

                logger.info(f"Generating audio with gTTS in {lang_code} for text length: {len(prepared_text)}")
                tts = gTTS(text=prepared_text, lang=lang_code, slow=False)
                tts.save(file_path)

                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    logger.info(f"Audio file created successfully with gTTS: {filename}")
                    return file_path
                else:
                    logger.error(f"gTTS created empty file: {filename}")
            except Exception as gtts_err:
                logger.warning(f"gTTS generation failed: {gtts_err}")

            # Fallback: try offline TTS via pyttsx3 if available
            try:
                import pyttsx3
                # Use wav for pyttsx3
                filename_wav = f"train_notification_{int(time.time())}_{lang_code}.wav"
                file_path_wav = os.path.join(tempfile.gettempdir(), filename_wav)

                logger.info(f"Generating audio with pyttsx3 (offline) to {file_path_wav}")
                engine = pyttsx3.init()
                engine.save_to_file(prepared_text, file_path_wav)
                engine.runAndWait()

                if os.path.exists(file_path_wav) and os.path.getsize(file_path_wav) > 0:
                    logger.info(f"Audio file created successfully with pyttsx3: {filename_wav}")
                    return file_path_wav
                else:
                    logger.error(f"pyttsx3 created empty file: {filename_wav}")
            except Exception as py_err:
                logger.warning(f"pyttsx3 fallback failed or not installed: {py_err}")

            logger.error("All audio generation methods failed")
            return None

        except Exception as e:
            logger.error(f"Audio generation error for language '{language}': {str(e)}")
            return None
    
    def get_current_train_status(self) -> Optional[Dict]:
        """Get current train status from mock API for all subscribed trains"""
        try:
            # Get all unique train numbers that users are subscribed to
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT train_number 
                FROM train_subscriptions 
                WHERE is_active = 1
            """)
            subscribed_trains = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not subscribed_trains:
                logger.info("No active train subscriptions found, trying to get available trains from API")
                # If no subscriptions, try to get available trains from the mock API
                try:
                    response = requests.get(f"{self.mock_api_url.replace('/api', '')}/", timeout=10)
                    if response.status_code == 200:
                        api_info = response.json()
                        available_trains = api_info.get('available_trains', [])
                        logger.info(f"Raw available trains from API: {available_trains[:3]}")
                        # Use just a few trains for demo (first 3)
                        if available_trains:
                            subscribed_trains = [train.replace('train_', '') for train in available_trains[:3]]
                            logger.info(f"Available trains from API: {available_trains[:3]}")
                            logger.info(f"Using demo trains (stripped): {subscribed_trains}")
                        else:
                            logger.warning("No available trains found in API")
                            return {}
                    else:
                        logger.warning(f"Could not get available trains from API: {response.status_code}")
                        return {}
                except Exception as e:
                    logger.error(f"Error getting available trains from API: {e}")
                    return {}
            
            # Get status for each subscribed train
            all_train_status = {}
            for train_number in subscribed_trains:
                try:
                    # The mock API expects train_id in format like "train_12345"
                    train_id = f"train_{train_number}"
                    logger.info(f"Getting status for train_number: {train_number}, train_id: {train_id}")
                    response = requests.get(
                        f"{self.mock_api_url}/train/status", 
                        params={'train_id': train_id},
                        timeout=10
                    )
                    if response.status_code == 200:
                        all_train_status[train_number] = response.json()
                        logger.debug(f"Got status for train {train_number}")
                    else:
                        logger.warning(f"Failed to get status for train {train_id}: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error getting status for train {train_number}: {e}")
                    continue
            
            return all_train_status if all_train_status else None
            
        except Exception as e:
            logger.error(f"Error getting train status: {e}")
            return None
    
    def get_random_platform(self) -> str:
        """Generate a random platform number"""
        import random
        return str(random.randint(1, 12))
    
    def get_current_time(self) -> str:
        """Get current time in HH:MM format"""
        return datetime.now().strftime("%H:%M")
    
    def format_arrival_announcement(self, train_data: Dict) -> str:
        """ Arrival Announcements"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        source_station = data.get('src_stn_name', 'N/A')
        platform_no = self.get_random_platform()
        
        return (f" Attention please. Train number {train_number}, {train_name}, "
                f"coming from {source_station}, is arriving shortly on platform number {platform_no}.")
    
    def format_departure_announcement(self, train_data: Dict) -> str:
        """Departure Announcements"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        source_station = data.get('src_stn_name', 'N/A')
        dest_station = data.get('dest_stn_name', 'N/A')
        platform_no = self.get_random_platform()
        departure_time = self.get_current_time()
        
        return (f"Train number {train_number}, {train_name}, "
                f"will depart at {departure_time} from platform number {platform_no}.")
    
    def format_delay_announcement(self, train_data: Dict, delay_minutes: int) -> str:
        """Delay Announcements"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        source_station = data.get('src_stn_name', 'N/A')
        dest_station = data.get('dest_stn_name', 'N/A')
        
        return (f"We regret to inform you that train number {train_number}, {train_name}, "
                f"from {source_station} to {dest_station}, is delayed by {delay_minutes} minutes.")
    
    def format_station_change_announcement(self, train_data: Dict) -> str:
        """ Station Arrival Announcements"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        platform_no = self.get_random_platform()
        
        return (f" Train number {train_number}, {train_name}, "
                f"is arriving on platform number {platform_no}. "
                f"Passengers are requested to stand behind the yellow line.")
    
    def format_cancellation_announcement(self, train_data: Dict) -> str:
        """ Cancellation Announcements"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        source_station = data.get('src_stn_name', 'N/A')
        dest_station = data.get('dest_stn_name', 'N/A')
        
        return (f" Attention please. Train number {train_number}, {train_name}, "
                f"from {source_station} to {dest_station}, has been cancelled. We regret the inconvenience.")
    
    def format_platform_change_announcement(self, train_data: Dict) -> str:
        """ Platform Change Announcements"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        old_platform = self.get_random_platform()
        new_platform = self.get_random_platform()
        
        return (f" Attention please. Train number {train_number}, {train_name}, "
                f"will now arrive/depart from platform number {new_platform} instead of {old_platform}.")
    
    def format_monitoring_start_announcement(self, train_data: Dict) -> str:
        """Initial monitoring announcement"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        source_station = data.get('src_stn_name', 'N/A')
        dest_station = data.get('dest_stn_name', 'N/A')
        arrival_time = self.get_current_time()
        
        return (f" Train number {train_number}, {train_name}, "
                f"from {source_station} to {dest_station}, "
                f"scheduled to arrive at {arrival_time}, is arriving shortly.")
    
    def format_boarding_announcement(self, train_data: Dict) -> str:
        """Boarding announcement"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        
        return (f"Passengers traveling by train number {train_number}, {train_name}, "
                f"please board the train. It will depart shortly.")
    
    def format_journey_completion_message(self, train_number: str, current_status: Dict) -> str:
        """Format journey completion message"""
        try:
            # Get train data
            train_data = None
            for train_id, data in current_status.items():
                if train_id == train_number and data.get('data'):
                    train_data = data['data']
                    break
            
            if not train_data:
                return (f" Train number {train_number} has arrived at its final destination. "
                        f"Thank you for traveling with us.")
            
            train_name = train_data.get('train_name', f'Train {train_number}')
            dest_station = train_data.get('dest_stn_name', 'destination')
            source_station = train_data.get('src_stn_name', 'source')
            platform_no = self.get_random_platform()
            
            return (f" Attention please. Train number {train_number}, {train_name}, "
                    f"coming from {source_station}, is arriving shortly on platform number {platform_no}.")
            
        except Exception as e:
            logger.error(f"Error formatting completion message: {e}")
            return (f" Train number {train_number} has arrived at its final destination. "
                    f"Thank you for traveling with us.")
    
    def format_departure_announcement(self, train_data: Dict, platform_no: str = "TBA") -> str:
        """Format departure announcement in railway station style"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        source_station = data.get('src_stn_name', 'N/A')
        dest_station = data.get('dest_stn_name', 'N/A')
        current_station = data.get('current_station_name', 'N/A')
        
        return (f"<b>Train number {train_number}, {train_name}, from {source_station} "
                f"to {dest_station}, is ready to depart from {current_station}.</b> "
                f"Passengers traveling by this train, please board the train. It will depart shortly.")
    
    def format_delay_announcement(self, train_data: Dict, delay_minutes: int) -> str:
        """Delay Announcements"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        source_station = data.get('src_stn_name', 'N/A')
        dest_station = data.get('dest_stn_name', 'N/A')
        
        return (f"We regret to inform you that train number {train_number}, {train_name}, "
                f"from {source_station} to {dest_station}, is delayed by {delay_minutes} minutes.")
    
    def format_station_change_announcement(self, train_data: Dict) -> str:
        """ Station Arrival Announcements"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        platform_no = self.get_random_platform()
        
        return (f" Train number {train_number}, {train_name}, "
                f"is arriving on platform number {platform_no}. "
                f"Passengers are requested to stand behind the yellow line.")
    
    def format_cancellation_announcement(self, train_data: Dict) -> str:
        """ Cancellation Announcements"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        source_station = data.get('src_stn_name', 'N/A')
        dest_station = data.get('dest_stn_name', 'N/A')
        
        return (f" Attention please. Train number {train_number}, {train_name}, "
                f"from {source_station} to {dest_station}, has been cancelled. We regret the inconvenience.")
    
    def format_monitoring_start_announcement(self, train_data: Dict) -> str:
        """Format monitoring start announcement in railway station style"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        source_station = data.get('src_stn_name', 'N/A')
        dest_station = data.get('dest_stn_name', 'N/A')
        
        return (f"<b>Attention please.</b> You are now receiving updates for train number "
                f"{train_number}, {train_name}, from {source_station} to {dest_station}. "
                f"We will keep you informed about any status changes.")
    
    def format_journey_progress_announcement(self, train_data: Dict, distance_covered: int) -> str:
        """Format journey progress announcement in railway station style"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        total_distance = data.get('total_distance', 0)
        current_station = data.get('current_station_name', 'N/A')
        
        progress_percent = round((distance_covered / total_distance) * 100, 1) if total_distance > 0 else 0
        
        return (f"<b>Journey Update:</b> Train number {train_number}, {train_name}, "
                f"has completed {distance_covered} km of {total_distance} km ({progress_percent}%). "
                f"Currently at {current_station}.")
    
    def format_platform_change_announcement(self, train_data: Dict) -> str:
        """ Platform Change Announcements"""
        data = train_data.get('data', {})
        train_number = data.get('train_number', 'N/A')
        train_name = data.get('train_name', 'N/A')
        old_platform = self.get_random_platform()
        new_platform = self.get_random_platform()
        
        return (f" Attention please. Train number {train_number}, {train_name}, "
                f"will now arrive/depart from platform number {new_platform} instead of {old_platform}.")
    
    def detect_status_changes(self, current_status: Dict) -> List[Dict]:
        """Detect changes in train status for all trains"""
        changes = []
        
        if not current_status:
            return changes
        
        if not self.last_train_status:
            # First time checking, consider it as initial status for all trains
            for train_number, train_data in current_status.items():
                changes.append({
                    'type': 'initial_status',
                    'message': f'Train {train_number} status monitoring started',
                    'data': train_data,
                    'train_number': train_number
                })
        else:
            # Check each train for changes
            for train_number, current_train_data in current_status.items():
                last_train_data = self.last_train_status.get(train_number)
                
                if not last_train_data:
                    # New train subscription
                    changes.append({
                        'type': 'initial_status',
                        'message': f'Train {train_number} status monitoring started',
                        'data': current_train_data,
                        'train_number': train_number
                    })
                    continue
                
                current_data = current_train_data.get('data', {})
                last_data = last_train_data.get('data', {})
                
                # Check for station change
                current_station = current_data.get('current_station_code')
                last_station = last_data.get('current_station_code')
                
                if current_station != last_station and current_station and last_station:
                    changes.append({
                        'type': 'station_change',
                        'message': f"Train {train_number} has arrived at {current_data.get('current_station_name', 'Unknown Station')}",
                        'data': current_train_data,
                        'train_number': train_number,
                        'old_station': last_data.get('current_station_name'),
                        'new_station': current_data.get('current_station_name')
                    })
                
                # Check for delay changes
                current_delay = current_data.get('delay', 0)
                last_delay = last_data.get('delay', 0)
                
                if current_delay != last_delay:
                    if current_delay > last_delay:
                        changes.append({
                            'type': 'delay_increase',
                            'message': f"Train {train_number} delay increased to {current_delay} minutes",
                            'data': current_train_data,
                            'train_number': train_number,
                            'old_delay': last_delay,
                            'new_delay': current_delay
                        })
                    elif current_delay < last_delay:
                        changes.append({
                            'type': 'delay_decrease',
                            'message': f"Train {train_number} delay reduced to {current_delay} minutes",
                            'data': current_train_data,
                            'train_number': train_number,
                            'old_delay': last_delay,
                            'new_delay': current_delay
                        })
                
                # Check for significant progress (every 50km)
                current_distance = current_data.get('distance_from_source', 0)
                last_distance = last_data.get('distance_from_source', 0)
                
                if current_distance - last_distance >= 50:
                    changes.append({
                        'type': 'progress_update',
                        'message': f"Train {train_number} has traveled {current_distance}km of {current_data.get('total_distance', 0)}km",
                        'data': current_train_data,
                        'train_number': train_number,
                        'distance_covered': current_distance
                    })
        
        return changes
    
    def send_notifications_for_changes(self, changes: List[Dict]):
        """Send notifications to subscribed users for status changes"""
        for change in changes:
            train_number = change.get('train_number')
            
            if change['type'] == 'initial_status':
                # Send arrival announcement for initial status
                users = self.get_subscribed_users(train_number)
                base_message = self.format_monitoring_start_announcement(change['data'])
                
                for user in users:
                    self.send_notification_to_user(user, base_message)
                    logger.info(f"Sent initial status for train {train_number} to {user['username']}")
            
            elif change['type'] == 'station_change':
                # Send station arrival announcement
                users = self.get_subscribed_users(train_number)
                base_message = self.format_station_change_announcement(change['data'])
                
                for user in users:
                    self.send_notification_to_user(user, base_message)
                    logger.info(f"Sent station change notification for train {train_number} to {user['username']}")
            
            elif change['type'] in ['delay_increase', 'delay_decrease']:
                # Send delay announcement
                users = self.get_subscribed_users(train_number)
                delay_minutes = change['new_delay']
                base_message = self.format_delay_announcement(change['data'], delay_minutes)
                
                for user in users:
                    self.send_notification_to_user(user, base_message)
                    logger.info(f"Sent delay update for train {train_number} to {user['username']}")
            
            elif change['type'] == 'progress_update':
                # Send departure announcement for progress updates
                users = self.get_subscribed_users(train_number)
                base_message = self.format_departure_announcement(change['data'])
                
                for user in users:
                    self.send_notification_to_user(user, base_message)
                    logger.info(f"Sent progress update for train {train_number} to {user['username']}")
        
        logger.info(f"Processed {len(changes)} notification changes")
    
    def send_notification_to_user(self, user: Dict, message: str):
        """Send notification to a single user with translation and audio support"""
        try:
            chat_id = user['chat_id']
            preferred_language = user.get('preferred_language', 'en')
            audio_enabled = user.get('audio_notifications', False)
            
            logger.info(f"Sending notification to {user['username']} in language: {preferred_language}")
            logger.info(f"Original message: {message[:100]}...")
            
            # Always start with the original message
            translated_message = message
            
            # Only translate if user's preferred language is not English
            if preferred_language and preferred_language.lower() not in ['en', 'english']:
                try:
                    # Remove HTML tags for translation but keep original structure
                    import re
                    clean_message = re.sub(r'<[^>]+>', '', message)
                    
                    logger.info(f"Attempting translation to {preferred_language} for {user['username']}")
                    logger.info(f"Clean message for translation: {clean_message}")
                    
                    # Try multiple translation methods (Deep Translator first - most reliable)
                    translated_text = None
                    translation_success = False
                    
                    # Method 1: Try Deep Translator first (primary method)
                    try:
                        logger.info(f"Trying Deep Translator to {preferred_language}")
                        from utils import translate_text
                        translated_text = translate_text(clean_message, preferred_language, 'en')
                        if translated_text and len(translated_text) > 10 and translated_text.lower() != clean_message.lower():
                            translation_success = True
                            logger.info(f"✅ Deep Translator success: {translated_text[:50]}...")
                        else:
                            logger.warning(f"❌ Deep Translator failed - result too short or same as original")
                    except Exception as deep_error:
                        logger.error(f"❌ Deep Translator error: {deep_error}")
                    
                    # Method 2: Try Google Translate directly as fallback
                    if not translation_success:
                        try:
                            logger.info(f"Trying direct Google Translate to {preferred_language}")
                            from deep_translator import GoogleTranslator
                            translator = GoogleTranslator(source='en', target=preferred_language)
                            translated_text = translator.translate(clean_message)
                            if translated_text and len(translated_text) > 10 and translated_text.lower() != clean_message.lower():
                                translation_success = True
                                logger.info(f"✅ Direct Google Translate success: {translated_text[:50]}...")
                            else:
                                logger.warning(f"❌ Direct Google Translate failed")
                        except Exception as google_error:
                            logger.error(f"❌ Direct Google Translate error: {google_error}")
                    
                    # Method 3: Try Gemini as last resort (if API key is working)
                    if not translation_success:
                        try:
                            logger.info(f"Trying Gemini translation to {preferred_language} as final fallback")
                            translated_text = self.translate_with_gemini(clean_message, preferred_language)
                            if translated_text and len(translated_text) > 10 and translated_text.lower() != clean_message.lower():
                                translation_success = True
                                logger.info(f"✅ Gemini translation successful: {translated_text[:50]}...")
                            else:
                                logger.warning(f"❌ Gemini translation failed - result too short or same as original")
                        except Exception as gemini_error:
                            logger.warning(f"❌ Gemini translation failed (expected - API key issue): {gemini_error}")
                    
                    # Use the translated text if successful
                    if translation_success and translated_text:
                        translated_message = translated_text
                        logger.info(f"🎯 FINAL TRANSLATION SUCCESS for {user['username']} in {preferred_language}")
                        logger.info(f"Final translated message: {translated_message}")
                    else:
                        logger.error(f"🚫 ALL TRANSLATION METHODS FAILED for {user['username']} - using original English")
                        translated_message = clean_message
                        
                except Exception as e:
                    logger.error(f"Translation process failed for {user['username']}: {e}")
                    translated_message = message
            else:
                logger.info(f"Using English (no translation needed) for {user['username']}")
            
            # Send text message with final translated content
            logger.info(f"Sending final message to {user['username']}: {translated_message[:100]}...")
            text_sent = self.send_telegram_message(chat_id, translated_message)
            
            # Send audio if enabled
            if audio_enabled and text_sent:
                try:
                    # Create clean text for audio (remove HTML and emojis)
                    import re
                    clean_text = re.sub(r'<[^>]+>', '', translated_message)
                    # Remove all emojis and special characters
                    clean_text = re.sub(r'[�⚠️�🚂📍📊🎯⏰✅🚉🔔📢🎵🏁🚪🚨]', '', clean_text)
                    clean_text = ' '.join(clean_text.split())  # Remove extra whitespace
                    
                    if len(clean_text) > 500:  # Limit text length for audio
                        clean_text = clean_text[:500] + "..."
                    
                    # Generate audio file (train numbers will be formatted automatically)
                    logger.info(f"Generating audio for {user['username']} in {preferred_language}: {clean_text[:100]}...")
                    audio_file_path = self.generate_audio_file(clean_text, preferred_language)
                    
                    if audio_file_path and os.path.exists(audio_file_path):
                        # Send audio with language-specific caption
                        caption = "🎵 Train Status Audio Update"
                        if preferred_language != 'en':
                            try:
                                caption_translated = self.translate_with_gemini("Train Status Audio Update", preferred_language)
                                if caption_translated and caption_translated != "Train Status Audio Update":
                                    caption = f"🎵 {caption_translated}"
                            except:
                                pass  # Keep original caption if translation fails
                        
                        audio_sent = self.send_telegram_audio(
                            chat_id, 
                            audio_file_path, 
                            caption=caption
                        )
                        
                        # Clean up temporary file
                        try:
                            os.remove(audio_file_path)
                        except Exception as cleanup_error:
                            logger.warning(f"Failed to cleanup audio file: {cleanup_error}")
                        
                        if audio_sent:
                            logger.info(f"Successfully sent audio notification to {user['username']} in {preferred_language}")
                        else:
                            logger.warning(f"Failed to send audio to {user['username']}")
                    else:
                        logger.warning(f"Failed to generate audio file for {user['username']} in {preferred_language}")
                        
                except Exception as e:
                    logger.error(f"Audio generation/sending failed for {user['username']}: {e}")
            
            return text_sent
            
        except Exception as e:
            logger.error(f"Failed to send notification to {user['username']}: {e}")
            return False
    
    def check_and_auto_unsubscribe(self, current_status: Dict):
        """Check if trains have reached destination and auto-unsubscribe users"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get all active subscriptions
            cursor.execute("""
                SELECT DISTINCT ts.train_number, ts.username, u.telegram_chat_id, u.preferred_language
                FROM train_subscriptions ts
                JOIN users u ON ts.username = u.username
                WHERE ts.is_active = 1 AND u.telegram_chat_id IS NOT NULL
            """)
            
            active_subscriptions = cursor.fetchall()
            
            for train_number, username, chat_id, preferred_language in active_subscriptions:
                # Check if this train has reached its destination
                if self.has_train_reached_destination(train_number, current_status):
                    # Auto-unsubscribe the user
                    cursor.execute("""
                        UPDATE train_subscriptions 
                        SET is_active = 0 
                        WHERE username = ? AND train_number = ?
                    """, (username, train_number))
                    
                    # Send final notification
                    final_message = self.format_journey_completion_message(train_number, current_status)
                    
                    # Translate to user's preferred language if not English
                    if preferred_language and preferred_language != 'en':
                        try:
                            final_message = self.translate_with_gemini(final_message, preferred_language)
                        except Exception as e:
                            logger.error(f"Translation failed for {username}: {e}")
                    
                    # Send final notification
                    self.send_telegram_message(chat_id, final_message)
                    
                    logger.info(f"Auto-unsubscribed {username} from train {train_number} - journey completed")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error in auto-unsubscribe check: {e}")
    
    def has_train_reached_destination(self, train_number: str, current_status: Dict) -> bool:
        """Check if a train has reached its final destination"""
        try:
            # Look for the train in current status
            train_data = None
            for train_id, data in current_status.items():
                if train_id == train_number and data.get('data'):
                    train_data = data['data']
                    break
            
            if not train_data:
                return False
            
            # Check various indicators that train has reached destination
            distance_from_source = train_data.get('distance_from_source', 0)
            total_distance = train_data.get('total_distance', 0)
            current_station = train_data.get('current_station_name', '').lower()
            dest_station = train_data.get('dest_stn_name', '').lower()
            
            # Train reached destination if:
            # 1. Distance covered is >= total distance
            # 2. Current station matches destination station
            # 3. Progress is 100%
            
            if total_distance > 0 and distance_from_source >= total_distance:
                return True
            
            if current_station and dest_station and current_station in dest_station:
                return True
            
            # Check if progress is 100%
            if total_distance > 0:
                progress = (distance_from_source / total_distance) * 100
                if progress >= 100:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking destination for train {train_number}: {e}")
            return False
    
    def format_journey_completion_message(self, train_number: str, current_status: Dict) -> str:
        """Format journey completion message in railway station announcement style"""
        try:
            # Get train data
            train_data = None
            for train_id, data in current_status.items():
                if train_id == train_number and data.get('data'):
                    train_data = data['data']
                    break
            
            if not train_data:
                return (f"🏁 <b>Attention please.</b> Train number {train_number} has reached its final destination. "
                        f"You have been automatically unsubscribed from notifications. Thank you for traveling with us.")
            
            train_name = train_data.get('train_name', f'Train {train_number}')
            dest_station = train_data.get('dest_stn_name', 'destination')
            current_station = train_data.get('current_station_name', dest_station)
            source_station = train_data.get('src_stn_name', 'source')
            
            message = f"🏁 <b>Attention please.</b> Train number {train_number}, {train_name}, "
            message += f"from {source_station} to {dest_station}, has arrived at its final destination "
            message += f"{current_station}. "
            message += f"We hope you had a pleasant journey. "
            message += f"Your subscription to this train has been automatically ended. "
            message += f"Thank you for using our notification service."
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting completion message: {e}")
            return (f"🏁 <b>Attention please.</b> Train number {train_number} has reached its final destination. "
                    f"You have been automatically unsubscribed from notifications. Thank you for traveling with us.")
    
    def check_train_status(self):
        """Check for train status updates and send notifications"""
        logger.info("Checking train status for updates...")
        
        current_status = self.get_current_train_status()
        if not current_status:
            logger.warning("Could not retrieve current train status")
            return
        
        # Check for trains that have reached their destination and auto-unsubscribe
        self.check_and_auto_unsubscribe(current_status)
        
        # Detect changes
        changes = self.detect_status_changes(current_status)
        
        if changes:
            logger.info(f"Detected {len(changes)} status changes")
            self.send_notifications_for_changes(changes)
        else:
            logger.info("No significant status changes detected")
        
        # Update last status
        self.last_train_status = current_status
    
    def start_monitoring(self):
        """Start the train status monitoring service"""
        if self.is_running:
            logger.warning("Monitoring service is already running")
            return
        
        self.is_running = True
        logger.info(f"Starting train status monitoring (check interval: {self.check_interval}s)")
        
        def monitoring_loop():
            while self.is_running:
                try:
                    self.check_train_status()
                    time.sleep(self.check_interval)
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(10)  # Wait 10 seconds before retrying
        
        self.notification_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.notification_thread.start()
        
        logger.info("Train status monitoring started successfully")
    
    def stop_monitoring(self):
        """Stop the train status monitoring service"""
        if not self.is_running:
            logger.warning("Monitoring service is not running")
            return
        
        self.is_running = False
        logger.info("Stopping train status monitoring...")
        
        if self.notification_thread:
            self.notification_thread.join(timeout=5)
        
        logger.info("Train status monitoring stopped")
    
    def send_manual_update(self, message: str, train_number: str = None):
        """Send a manual update to subscribed users in railway station announcement style"""
        users = self.get_subscribed_users(train_number)
        
        # Format as railway station announcement - general announcement
        base_message = f"📢 Attention please. {message}"
        
        sent_count = 0
        for user in users:
            if self.send_notification_to_user(user, base_message):
                sent_count += 1
        
        logger.info(f"Manual update sent to {sent_count} users")
        return sent_count


# CLI Interface
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Train Status Notification Service')
    parser.add_argument('--start', action='store_true', help='Start monitoring service')
    parser.add_argument('--stop', action='store_true', help='Stop monitoring service')
    parser.add_argument('--check', action='store_true', help='Check status once')
    parser.add_argument('--subscribe', nargs=2, metavar=('USERNAME', 'TRAIN_NUMBER'), 
                       help='Subscribe user to train notifications')
    parser.add_argument('--unsubscribe', nargs=2, metavar=('USERNAME', 'TRAIN_NUMBER'), 
                       help='Unsubscribe user from train notifications')
    parser.add_argument('--list-users', action='store_true', help='List subscribed users')
    parser.add_argument('--send-update', nargs='+', help='Send manual update message')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    
    args = parser.parse_args()
    
    service = TrainNotificationService(check_interval=args.interval)
    
    if args.start:
        print("Starting train status monitoring service...")
        service.start_monitoring()
        
        try:
            # Keep running until interrupted
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping service...")
            service.stop_monitoring()
            
    elif args.check:
        print("Checking train status...")
        service.check_train_status()
        
    elif args.subscribe:
        username, train_number = args.subscribe
        if service.subscribe_user_to_train(username, train_number):
            print(f"✅ User {username} subscribed to train {train_number}")
        else:
            print(f"❌ Failed to subscribe user {username}")
            
    elif args.unsubscribe:
        username, train_number = args.unsubscribe
        if service.unsubscribe_user_from_train(username, train_number):
            print(f"✅ User {username} unsubscribed from train {train_number}")
        else:
            print(f"❌ Failed to unsubscribe user {username}")
            
    elif args.list_users:
        users = service.get_subscribed_users()
        print(f"📋 Subscribed users ({len(users)}):")
        for user in users:
            print(f"  - {user['username']} (Chat ID: {user['chat_id']})")
            
    elif args.send_update:
        message = ' '.join(args.send_update)
        count = service.send_manual_update(message)
        print(f"✅ Manual update sent to {count} users")
        
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
