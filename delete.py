import requests
import time
import os
import json
from utils import (
    translate_text, 
    generate_audio, 
    SUPPORTED_LANGUAGES,
    get_help_message,
    get_languages_message,
    is_language_supported,
    get_language_name
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", '8327968816:AAHAV5BCDfG3IERUr5IPne_1wJyCJTQTiBY')
URL = f'https://api.telegram.org/bot{TOKEN}/'
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
MOCK_API_URL = os.getenv("MOCK_API_URL", "http://127.0.0.1:5001/api")

def get_updates(offset=None):
    params = {'timeout': 100, 'offset': offset}
    response = requests.get(URL + 'getUpdates', params=params)
    return response.json()

def send_message(chat_id, text, reply_markup=None):
    params = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    requests.post(URL + 'sendMessage', params=params)

def edit_message(chat_id, message_id, text, reply_markup=None):
    params = {
        'chat_id': chat_id, 
        'message_id': message_id,
        'text': text, 
        'parse_mode': 'Markdown'
    }
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    response = requests.post(URL + 'editMessageText', params=params)
    return response.json()

def answer_callback_query(callback_query_id, text=None, show_alert=False):
    params = {
        'callback_query_id': callback_query_id,
        'show_alert': show_alert
    }
    if text:
        params['text'] = text
    requests.post(URL + 'answerCallbackQuery', params=params)

def send_audio(chat_id, audio_file_path, caption=None):
    """Send audio file to Telegram chat"""
    with open(audio_file_path, 'rb') as audio_file:
        files = {'audio': audio_file}
        params = {'chat_id': chat_id}
        if caption:
            params['caption'] = caption
        response = requests.post(URL + 'sendAudio', files=files, data=params)
    return response.json()

def create_main_menu():
    """Create main menu with inline keyboard buttons"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚂 Train Management", "callback_data": "train_menu"},
                {"text": "🔔 Notifications", "callback_data": "notification_menu"}
            ],
            [
                {"text": "🌍 Language Settings", "callback_data": "language_menu"},
                {"text": "ℹ️ Help", "callback_data": "help"}
            ],
            [
                {"text": "🆔 My Chat ID", "callback_data": "chat_id"},
                {"text": "🔧 Account", "callback_data": "account_menu"}
            ]
        ]
    }
    return keyboard

def create_train_menu():
    """Create train management menu"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📋 List All Trains", "callback_data": "list_trains"},
                {"text": "📊 Train Status", "callback_data": "train_status"}
            ],
            [
                {"text": "➕ Subscribe to Train", "callback_data": "subscribe_menu"},
                {"text": "➖ Unsubscribe", "callback_data": "unsubscribe_menu"}
            ],
            [
                {"text": "🚫 Stop All Subscriptions", "callback_data": "stop_all_subs"}
            ],
            [
                {"text": "🔙 Back to Main Menu", "callback_data": "main_menu"}
            ]
        ]
    }
    return keyboard

def create_notification_menu():
    """Create notification settings menu"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔊 Enable Audio Notifications", "callback_data": "enable_audio"},
                {"text": "🔇 Disable Audio Notifications", "callback_data": "disable_audio"}
            ],
            [
                {"text": "📋 My Subscriptions", "callback_data": "my_subscriptions"}
            ],
            [
                {"text": "🔙 Back to Main Menu", "callback_data": "main_menu"}
            ]
        ]
    }
    return keyboard

def create_language_menu():
    """Create language preferences menu"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔤 Change Preferred Language", "callback_data": "change_language"}
            ],
            [
                {"text": "� Current Language Settings", "callback_data": "current_language"}
            ],
            [
                {"text": "🌐 Supported Languages", "callback_data": "languages"}
            ],
            [
                {"text": "🔙 Back to Main Menu", "callback_data": "main_menu"}
            ]
        ]
    }
    return keyboard

def create_account_menu():
    """Create account management menu"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔗 Verify Account", "callback_data": "verify_account"}
            ],
            [
                {"text": "📱 Account Status", "callback_data": "account_status"}
            ],
            [
                {"text": "🔙 Back to Main Menu", "callback_data": "main_menu"}
            ]
        ]
    }
    return keyboard

def create_back_button():
    """Create a simple back button"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔙 Back to Main Menu", "callback_data": "main_menu"}
            ]
        ]
    }
    return keyboard

def create_start_button():
    """Create a start button for default interface"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚀 Start MultiLingo Bot", "callback_data": "main_menu"}
            ]
        ]
    }
    return keyboard

def create_language_selection_keyboard():
    """Create keyboard for language selection"""
    languages = {
        "en": "🇺🇸 English",
        "es": "🇪🇸 Spanish", 
        "fr": "🇫🇷 French",
        "de": "🇩🇪 German",
        "hi": "🇮🇳 Hindi",
        "ta": "🇮🇳 Tamil",
        "te": "🇮🇳 Telugu",
        "ar": "🇸🇦 Arabic",
        "zh": "🇨🇳 Chinese",
        "ja": "🇯🇵 Japanese",
        "ko": "🇰🇷 Korean",
        "ru": "🇷🇺 Russian",
        "pt": "🇧🇷 Portuguese",
        "it": "🇮🇹 Italian"
    }
    
    keyboard = {"inline_keyboard": []}
    
    # Add language buttons (2 per row)
    lang_items = list(languages.items())
    for i in range(0, len(lang_items), 2):
        row = []
        
        # First language
        code1, name1 = lang_items[i]
        row.append({"text": name1, "callback_data": f"set_lang_{code1}"})
        
        # Second language if exists
        if i + 1 < len(lang_items):
            code2, name2 = lang_items[i + 1]
            row.append({"text": name2, "callback_data": f"set_lang_{code2}"})
        
        keyboard["inline_keyboard"].append(row)
    
    # Add back button
    keyboard["inline_keyboard"].append([
        {"text": "🔙 Back to Language Menu", "callback_data": "language_menu"}
    ])
    
    return keyboard

def get_available_trains():
    """Get list of available trains from mock API"""
    try:
        # Get list of all available trains from the mock API
        response = requests.get(MOCK_API_URL.replace('/api', '') + '/', timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('available_trains', [])
        return []
    except Exception as e:
        print(f"Error getting available trains: {str(e)}")
        return []

def create_train_list_keyboard(trains, action_prefix="train_info", page=0, items_per_page=8):
    """Create keyboard with train list for selection"""
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_trains = trains[start_idx:end_idx]
    
    keyboard = {"inline_keyboard": []}
    
    # Add train buttons (2 per row)
    for i in range(0, len(page_trains), 2):
        row = []
        train1 = page_trains[i]
        train_num1 = train1.replace('train_', '')
        row.append({"text": f"🚂 {train_num1}", "callback_data": f"{action_prefix}_{train_num1}"})
        
        if i + 1 < len(page_trains):
            train2 = page_trains[i + 1]
            train_num2 = train2.replace('train_', '')
            row.append({"text": f"🚂 {train_num2}", "callback_data": f"{action_prefix}_{train_num2}"})
        
        keyboard["inline_keyboard"].append(row)
    
    # Add pagination buttons if needed
    nav_buttons = []
    if page > 0:
        nav_buttons.append({"text": "⬅️ Previous", "callback_data": f"{action_prefix}_page_{page-1}"})
    if end_idx < len(trains):
        nav_buttons.append({"text": "Next ➡️", "callback_data": f"{action_prefix}_page_{page+1}"})
    
    if nav_buttons:
        keyboard["inline_keyboard"].append(nav_buttons)
    
    # Add back button
    keyboard["inline_keyboard"].append([
        {"text": "🔙 Back to Train Menu", "callback_data": "train_menu"}
    ])
    
    return keyboard

def get_train_name_mapping():
    """Get train names mapping"""
    return {
        '11014': 'Lokmanya Tilak Express',
        '11301': 'Udyan Express',
        '12244': 'Bangalore Rajdhani',
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
        '22638': 'West Coast SF Express'
    }

def get_user_token_by_chat_id(chat_id: str) -> str:
    """Get user token by chat ID for API authentication"""
    try:
        response = requests.post(f'{APP_URL}/api/telegram/get-token', json={'chat_id': chat_id})
        if response.status_code == 200:
            data = response.json()
            return data.get('token', '')
        return ''
    except Exception as e:
        print(f"Error getting user token: {str(e)}")
        return ''

def get_user_preferences(chat_id: str):
    """Get user preferences including audio notifications"""
    try:
        token = get_user_token_by_chat_id(str(chat_id))
        if not token:
            return None
        
        response = requests.get(f'{APP_URL}/api/user/preferences',
                      headers={'Authorization': f'Bearer {token}'})
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error getting user preferences: {str(e)}")
        return None

def update_user_audio_notifications(chat_id: str, enable: bool):
    """Update user audio notification preference"""
    try:
        token = get_user_token_by_chat_id(str(chat_id))
        if not token:
            return False
        
        # Get current preferences first
        prefs = get_user_preferences(chat_id)
        if not prefs:
            prefs = {"preferred_language": "en", "audio_notifications": False}
        
        # Update audio notifications setting
        prefs["audio_notifications"] = enable
        
        response = requests.post(f'{APP_URL}/api/user/preferences',
                       json=prefs,
                       headers={'Authorization': f'Bearer {token}'})
        return response.status_code == 200
    except Exception as e:
        print(f"Error updating audio notifications: {str(e)}")
        return False

def update_user_preferred_language(chat_id: str, language: str):
    """Update user preferred language preference"""
    try:
        token = get_user_token_by_chat_id(str(chat_id))
        if not token:
            return False
        
        # Get current preferences first
        prefs = get_user_preferences(chat_id)
        if not prefs:
            prefs = {"preferred_language": "en", "audio_notifications": False}
        
        # Update preferred language setting
        prefs["preferred_language"] = language
        
        response = requests.post(f'{APP_URL}/api/user/preferences',
                       json=prefs,
                       headers={'Authorization': f'Bearer {token}'})
        return response.status_code == 200
    except Exception as e:
        print(f"Error updating preferred language: {str(e)}")
        return False

def get_user_subscriptions(chat_id: str):
    """Get user's train subscriptions"""
    try:
        token = get_user_token_by_chat_id(str(chat_id))
        if not token:
            return []
        
        response = requests.get(f'{APP_URL}/api/train-subscription/list',
                      headers={'Authorization': f'Bearer {token}'})
        if response.status_code == 200:
            data = response.json()
            return data.get('subscriptions', [])
        return []
    except Exception as e:
        print(f"Error getting subscriptions: {str(e)}")
        return []

def subscribe_to_train(chat_id: str, train_number: str):
    """Subscribe to train updates"""
    try:
        token = get_user_token_by_chat_id(str(chat_id))
        if not token:
            return False, "Account not verified. Please verify your account first."
        
        response = requests.post(f'{APP_URL}/api/train-subscription/subscribe',
                       json={'train_number': train_number},
                       headers={'Authorization': f'Bearer {token}'})
        
        if response.status_code == 200:
            return True, "Successfully subscribed to train updates!"
        else:
            error_data = response.json() if response.content else {}
            return False, error_data.get('detail', 'Subscription failed')
    except Exception as e:
        print(f"Error subscribing to train: {str(e)}")
        return False, "Subscription failed. Please try again."

def unsubscribe_from_train(chat_id: str, train_number: str):
    """Unsubscribe from train updates"""
    try:
        token = get_user_token_by_chat_id(str(chat_id))
        if not token:
            return False
        
        response = requests.delete(f'{APP_URL}/api/train-subscription/unsubscribe/{train_number}',
                     headers={'Authorization': f'Bearer {token}'})
        return response.status_code == 200
    except Exception as e:
        print(f"Error unsubscribing from train: {str(e)}")
        return False

def stop_all_subscriptions(chat_id: str):
    """Stop all train subscriptions for user"""
    try:
        subscriptions = get_user_subscriptions(chat_id)
        if not subscriptions:
            return True, "No active subscriptions found."
        
        success_count = 0
        for sub in subscriptions:
            if unsubscribe_from_train(chat_id, sub['train_number']):
                success_count += 1
        
        if success_count == len(subscriptions):
            return True, f"Successfully stopped all {success_count} subscriptions."
        else:
            return False, f"Stopped {success_count} out of {len(subscriptions)} subscriptions."
    except Exception as e:
        print(f"Error stopping all subscriptions: {str(e)}")
        return False, "Failed to stop subscriptions."

def get_train_status_from_api(train_number: str):
    """Get train status from mock API"""
    try:
        response = requests.get(f'{MOCK_API_URL}/train/status?train_id=train_{train_number}', timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error getting train status: {str(e)}")
        return None

def send_notification(chat_id, message_type, data):
    """Send formatted notification to Telegram user"""
    try:
        if message_type == "translation_complete":
            msg = f"✅ Translation Complete!\n\n"
            msg += f"📝 Original: {data.get('original_text', '')}\n"
            msg += f"🌍 Language: {data.get('target_language', '')}\n"
            msg += f"✨ Translated: {data.get('translated_text', '')}\n"
            if data.get('audio_url'):
                msg += f"\n🎵 Audio generated successfully!"
            send_message(chat_id, msg)
            
        elif message_type == "audio_complete":
            msg = f"🎵 Audio Generated!\n\n"
            msg += f"📝 Text: {data.get('text', '')}\n"
            msg += f"🌍 Language: {data.get('language', '')}\n"
            msg += f"✅ Audio file created successfully!"
            send_message(chat_id, msg)
            
        elif message_type == "train_status":
            msg = f"🚂 Train Status Update!\n\n"
            msg += f"🎫 Train: {data.get('train_name', '')}\n"
            msg += f"📍 Status: {data.get('status', '')}\n"
            if data.get('delay'):
                msg += f"⏰ Delay: {data.get('delay')}\n"
            send_message(chat_id, msg)
            
        elif message_type == "custom":
            send_message(chat_id, data.get('message', ''))
            
        else:
            send_message(chat_id, str(data))
            
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        return False
    return True

def handle_callback_query(callback_query):
    """Handle inline keyboard button callbacks"""
    chat_id = callback_query['message']['chat']['id']
    message_id = callback_query['message']['message_id']
    data = callback_query['data']
    callback_query_id = callback_query['id']
    
    try:
        if data == "main_menu":
            edit_message(chat_id, message_id, 
                        "🏠 *Main Menu*\n\nChoose an option below:", 
                        create_main_menu())
            
        elif data == "train_menu":
            edit_message(chat_id, message_id, 
                        "🚂 *Train Management*\n\nManage your train subscriptions and status:", 
                        create_train_menu())
            
        elif data == "notification_menu":
            prefs = get_user_preferences(chat_id)
            audio_status = "🔊 Enabled" if prefs and prefs.get('audio_notifications') else "🔇 Disabled"
            edit_message(chat_id, message_id, 
                        f"🔔 *Notification Settings*\n\nAudio Notifications: {audio_status}\n\nManage your notification preferences:", 
                        create_notification_menu())
            
        elif data == "language_menu":
            edit_message(chat_id, message_id, 
                        "🌍 *Language Settings*\n\nManage your preferred language for notifications:", 
                        create_language_menu())
            
        elif data == "account_menu":
            edit_message(chat_id, message_id, 
                        "🔧 *Account Management*\n\nManage your account settings:", 
                        create_account_menu())
            
        elif data == "list_trains":
            trains = get_available_trains()
            if trains:
                edit_message(chat_id, message_id, 
                            f"📋 *Available Trains* ({len(trains)} total)\n\nSelect a train to view details:", 
                            create_train_list_keyboard(trains, "train_info"))
            else:
                edit_message(chat_id, message_id, 
                            "❌ Unable to fetch train list. Please try again later.",
                            create_back_button())
                
        elif data == "subscribe_menu":
            trains = get_available_trains()
            if trains:
                edit_message(chat_id, message_id, 
                            "➕ *Subscribe to Train*\n\nSelect a train to subscribe for notifications:", 
                            create_train_list_keyboard(trains, "subscribe"))
            else:
                edit_message(chat_id, message_id, 
                            "❌ Unable to fetch train list. Please try again later.",
                            create_back_button())
                
        elif data == "unsubscribe_menu":
            subscriptions = get_user_subscriptions(chat_id)
            if subscriptions:
                trains = [f"train_{sub['train_number']}" for sub in subscriptions]
                edit_message(chat_id, message_id, 
                            "➖ *Unsubscribe from Train*\n\nSelect a train to unsubscribe:", 
                            create_train_list_keyboard(trains, "unsubscribe"))
            else:
                edit_message(chat_id, message_id, 
                            "📭 No active subscriptions found.",
                            create_back_button())
                
        elif data == "my_subscriptions":
            subscriptions = get_user_subscriptions(chat_id)
            train_names = get_train_name_mapping()
            
            if subscriptions:
                msg = "📋 *Your Train Subscriptions*\n\n"
                for i, sub in enumerate(subscriptions, 1):
                    train_name = train_names.get(sub['train_number'], f"Train {sub['train_number']}")
                    msg += f"{i}. 🚂 {train_name} ({sub['train_number']})\n"
                msg += f"\n📊 Total: {len(subscriptions)} active subscriptions"
            else:
                msg = "📭 *No Active Subscriptions*\n\nYou haven't subscribed to any trains yet."
            
            edit_message(chat_id, message_id, msg, create_back_button())
            
        elif data == "stop_all_subs":
            success, message = stop_all_subscriptions(chat_id)
            status_icon = "✅" if success else "❌"
            edit_message(chat_id, message_id, 
                        f"{status_icon} *Stop All Subscriptions*\n\n{message}",
                        create_back_button())
            
        elif data == "enable_audio":
            success = update_user_audio_notifications(chat_id, True)
            if success:
                edit_message(chat_id, message_id, 
                            "🔊 *Audio Notifications Enabled*\n\nYou will now receive audio notifications for train updates.",
                            create_back_button())
            else:
                edit_message(chat_id, message_id, 
                            "❌ Failed to enable audio notifications. Please verify your account first.",
                            create_back_button())
            
        elif data == "disable_audio":
            success = update_user_audio_notifications(chat_id, False)
            if success:
                edit_message(chat_id, message_id, 
                            "🔇 *Audio Notifications Disabled*\n\nYou will no longer receive audio notifications.",
                            create_back_button())
            else:
                edit_message(chat_id, message_id, 
                            "❌ Failed to disable audio notifications. Please try again.",
                            create_back_button())
        
        elif data == "change_language":
            edit_message(chat_id, message_id, 
                        "🔤 *Change Preferred Language*\n\nSelect your preferred language for notifications:",
                        create_language_selection_keyboard())
        
        elif data == "current_language":
            prefs = get_user_preferences(chat_id)
            if prefs:
                current_lang = prefs.get('preferred_language', 'en')
                lang_names = {
                    "en": "🇺🇸 English", "es": "🇪🇸 Spanish", "fr": "🇫🇷 French", "de": "🇩🇪 German",
                    "hi": "🇮🇳 Hindi", "ta": "🇮🇳 Tamil", "te": "🇮🇳 Telugu", "ar": "🇸🇦 Arabic",
                    "zh": "🇨🇳 Chinese", "ja": "🇯🇵 Japanese", "ko": "🇰🇷 Korean", "ru": "🇷🇺 Russian",
                    "pt": "🇧🇷 Portuguese", "it": "🇮🇹 Italian"
                }
                lang_display = lang_names.get(current_lang, f"Unknown ({current_lang})")
                audio_status = "✅ Enabled" if prefs.get('audio_notifications', False) else "❌ Disabled"
                
                edit_message(chat_id, message_id, 
                            f"📋 *Current Language Settings*\n\n🔤 Preferred Language: {lang_display}\n🔊 Audio Notifications: {audio_status}",
                            create_back_button())
            else:
                edit_message(chat_id, message_id, 
                            "❌ Unable to fetch your language settings. Please verify your account first.",
                            create_back_button())
        
        elif data.startswith("set_lang_"):
            language_code = data.replace("set_lang_", "")
            success = update_user_preferred_language(chat_id, language_code)
            
            if success:
                lang_names = {
                    "en": "🇺🇸 English", "es": "🇪🇸 Spanish", "fr": "🇫🇷 French", "de": "🇩🇪 German",
                    "hi": "🇮🇳 Hindi", "ta": "🇮🇳 Tamil", "te": "🇮🇳 Telugu", "ar": "🇸🇦 Arabic",
                    "zh": "🇨🇳 Chinese", "ja": "🇯🇵 Japanese", "ko": "🇰🇷 Korean", "ru": "🇷🇺 Russian",
                    "pt": "🇧🇷 Portuguese", "it": "🇮🇹 Italian"
                }
                lang_display = lang_names.get(language_code, language_code)
                
                edit_message(chat_id, message_id, 
                            f"✅ *Language Updated Successfully*\n\nYour preferred language has been set to: {lang_display}\n\nAll future notifications will use this language.",
                            create_back_button())
            else:
                edit_message(chat_id, message_id, 
                            "❌ Failed to update language preference. Please verify your account first.",
                            create_back_button())
            
        elif data == "train_status":
            trains = get_available_trains()
            if trains:
                edit_message(chat_id, message_id, 
                            "📊 *Train Status*\n\nSelect a train to view current status:", 
                            create_train_list_keyboard(trains, "status"))
            else:
                edit_message(chat_id, message_id, 
                            "❌ Unable to fetch train list. Please try again later.",
                            create_back_button())
                
        elif data == "chat_id":
            edit_message(chat_id, message_id, 
                        f"🆔 *Your Telegram Chat ID*\n\n`{chat_id}`\n\nCopy this ID to link your account on the MultiLingo web app!",
                        create_back_button())
            
        elif data == "help":
            help_text = """
🤖 *MultiLingo Bot Help*

*Main Features:*
🚂 *Train Management* - Subscribe to train updates, view status
🔔 *Notifications* - Configure audio notifications
🌍 *Language Settings* - Set preferred language for notifications
🔧 *Account* - Verify and manage your account

*Quick Commands:*
• Send any text for auto-translation to English
• Send an 8-character verification token to link your account
• Use the menu buttons for all features

*Train Features:*
• 📋 View all available trains
• ➕ Subscribe to train notifications  
• ➖ Unsubscribe from trains
• 🚫 Stop all subscriptions at once

*Settings:*
• 🔊/🔇 Enable/disable audio notifications
• 🔤 Change preferred language for notifications
• 📋 View current language settings

Your Chat ID: `{}`
            """.format(chat_id)
            edit_message(chat_id, message_id, help_text, create_back_button())
            
        elif data == "languages":
            edit_message(chat_id, message_id, get_languages_message(), create_back_button())
            
        elif data == "verify_account":
            edit_message(chat_id, message_id, 
                        "🔗 *Account Verification*\n\n1. Go to MultiLingo web app\n2. Generate a verification token\n3. Send the 8-character token here\n\nOr simply paste your verification token below:",
                        create_back_button())
            
        elif data == "account_status":
            token = get_user_token_by_chat_id(str(chat_id))
            if token:
                prefs = get_user_preferences(chat_id)
                subscriptions = get_user_subscriptions(chat_id)
                
                status_text = f"""
📱 *Account Status*

✅ *Account:* Verified and Linked
🆔 *Chat ID:* `{chat_id}`
🔔 *Audio Notifications:* {'Enabled' if prefs and prefs.get('audio_notifications') else 'Disabled'}
🚂 *Active Subscriptions:* {len(subscriptions)}

Your account is fully integrated with MultiLingo!
                """
            else:
                status_text = f"""
📱 *Account Status*

❌ *Account:* Not Verified
🆔 *Chat ID:* `{chat_id}`

To verify your account:
1. Go to MultiLingo web app
2. Generate a verification token  
3. Send the token here
                """
            
            edit_message(chat_id, message_id, status_text, create_back_button())
            
        elif data == "auto_translate":
            edit_message(chat_id, message_id, 
                        "🌍 *Auto-Translation Mode*\n\nSend me any text and I'll translate it to English automatically.\n\nJust type your message below!",
                        create_back_button())
            
        # Handle train-specific actions
        elif data.startswith("train_info_"):
            train_number = data.split("_")[-1]
            train_names = get_train_name_mapping()
            train_name = train_names.get(train_number, f"Train {train_number}")
            
            status_data = get_train_status_from_api(train_number)
            if status_data and status_data.get('data'):
                data_info = status_data['data']
                current_station = data_info.get('current_station_name', 'N/A')
                distance_covered = data_info.get('distance_from_source', 0)
                total_distance = data_info.get('total_distance', 0)
                progress = round((distance_covered / total_distance) * 100, 1) if total_distance > 0 else 0
                delay = data_info.get('delay', 0)
                
                status_text = f"""
🚂 *{train_name}* ({train_number})

📍 *Current Station:* {current_station}
📊 *Progress:* {distance_covered}/{total_distance} km ({progress}%)
⏰ *Status:* {'On Time' if delay == 0 else f'{delay} min delay'}
🕒 *Updated:* {data_info.get('update_time', 'N/A')}
                """
            else:
                status_text = f"🚂 *{train_name}* ({train_number})\n\n❌ Unable to fetch current status."
            
            # Create keyboard with Subscribe and Back buttons
            train_detail_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "➕ Subscribe to this Train", "callback_data": f"subscribe_{train_number}"}
                    ],
                    [
                        {"text": "🔙 Back to Main Menu", "callback_data": "main_menu"}
                    ]
                ]
            }
            
            edit_message(chat_id, message_id, status_text, train_detail_keyboard)
            
        elif data.startswith("subscribe_"):
            train_number = data.split("_")[-1]
            if train_number != "menu" and not train_number.startswith("page"):
                train_names = get_train_name_mapping()
                train_name = train_names.get(train_number, f"Train {train_number}")
                
                success, message = subscribe_to_train(chat_id, train_number)
                status_icon = "✅" if success else "❌"
                edit_message(chat_id, message_id, 
                            f"{status_icon} *Train Subscription*\n\n🚂 {train_name} ({train_number})\n\n{message}",
                            create_back_button())
                
        elif data.startswith("unsubscribe_"):
            train_number = data.split("_")[-1]
            if train_number != "menu" and not train_number.startswith("page"):
                train_names = get_train_name_mapping()
                train_name = train_names.get(train_number, f"Train {train_number}")
                
                success = unsubscribe_from_train(chat_id, train_number)
                status_icon = "✅" if success else "❌"
                message = "Successfully unsubscribed!" if success else "Failed to unsubscribe. Please try again."
                edit_message(chat_id, message_id, 
                            f"{status_icon} *Unsubscribe*\n\n🚂 {train_name} ({train_number})\n\n{message}",
                            create_back_button())
                
        elif data.startswith("status_"):
            train_number = data.split("_")[-1]
            if train_number != "menu" and not train_number.startswith("page"):
                train_names = get_train_name_mapping()
                train_name = train_names.get(train_number, f"Train {train_number}")
                
                status_data = get_train_status_from_api(train_number)
                if status_data and status_data.get('data'):
                    data_info = status_data['data']
                    current_station = data_info.get('current_station_name', 'N/A')
                    current_code = data_info.get('current_station_code', 'N/A')
                    distance_covered = data_info.get('distance_from_source', 0)
                    total_distance = data_info.get('total_distance', 0)
                    progress = round((distance_covered / total_distance) * 100, 1) if total_distance > 0 else 0
                    delay = data_info.get('delay', 0)
                    update_time = data_info.get('update_time', 'N/A')
                    
                    # Next station info
                    upcoming = data_info.get('upcoming_stations', [])
                    next_station_info = ""
                    if upcoming:
                        next_station = upcoming[0]
                        next_name = next_station.get('station_name', 'N/A')
                        next_eta = next_station.get('eta', 'N/A')
                        next_station_info = f"🎯 *Next Station:* {next_name} (ETA: {next_eta})\n"
                    
                    status_text = f"""
🚂 *{train_name}* ({train_number})

📍 *Current Station:* {current_station} ({current_code})
📊 *Progress:* {distance_covered}/{total_distance} km ({progress}%)
{next_station_info}⏰ *Status:* {'✅ On Time' if delay == 0 else f'🔴 {delay} min delay'}
🕒 *Last Updated:* {update_time}
                    """
                else:
                    status_text = f"🚂 *{train_name}* ({train_number})\n\n❌ Unable to fetch current status. Service may be unavailable."
                
                edit_message(chat_id, message_id, status_text, create_back_button())
        
        # Handle pagination
        elif "_page_" in data:
            parts = data.split("_page_")
            action_prefix = parts[0]
            page = int(parts[1])
            
            if action_prefix in ["train_info", "subscribe", "unsubscribe", "status"]:
                trains = get_available_trains()
                if action_prefix == "unsubscribe":
                    subscriptions = get_user_subscriptions(chat_id)
                    trains = [f"train_{sub['train_number']}" for sub in subscriptions]
                
                title_map = {
                    "train_info": "📋 *Available Trains*",
                    "subscribe": "➕ *Subscribe to Train*", 
                    "unsubscribe": "➖ *Unsubscribe from Train*",
                    "status": "📊 *Train Status*"
                }
                
                edit_message(chat_id, message_id, 
                            f"{title_map[action_prefix]}\n\nSelect a train:", 
                            create_train_list_keyboard(trains, action_prefix, page))
        
        answer_callback_query(callback_query_id)
        
    except Exception as e:
        print(f"Error handling callback query: {str(e)}")
        answer_callback_query(callback_query_id, "An error occurred. Please try again.", True)

def process_message(chat_id, text, username=None):
    """Process incoming messages and handle commands"""
    try:
        text = text.strip()
        
        # Handle /start command - show main menu
        if text.startswith('/start'):
            welcome_msg = f"👋 Welcome {username or 'there'}!\n\n🤖 *MultiLingo Bot*\n\nI can help you with:\n• 🚂 Train status & subscriptions\n• 🌍 Text translation\n• 🔔 Smart notifications\n• 🎵 Audio generation\n\nUse the menu below to get started:"
            send_message(chat_id, welcome_msg, create_main_menu())
            
        # Handle verification tokens (8 characters, alphanumeric, uppercase)
        elif len(text) == 8 and text.isalnum() and text.isupper():
            try:
                response = requests.post(f'{APP_URL}/api/telegram/verify-token', 
                                       json={'token': text, 'chat_id': str(chat_id)})
                
                if response.status_code == 200:
                    data = response.json()
                    username = data.get('username', 'User')
                    welcome_msg = f"🎉 *Account Successfully Verified!*\n\n✅ Account Linked!\n👤 Username: {username}\n🆔 Chat ID: {chat_id}\n\n🔔 You will now receive notifications for:\n• ✨ Translation completions\n• 🎵 Audio generation updates\n• 🚂 Train status alerts\n• 📢 Custom messages\n\n� Your MultiLingo integration is now active!"
                    send_message(chat_id, welcome_msg, create_main_menu())
                else:
                    # If verification fails, continue with auto-translation
                    auto_translate_text(chat_id, text)
            except Exception as e:
                print(f"Error auto-verifying token: {str(e)}")
                auto_translate_text(chat_id, text)
                
        # Handle legacy commands (redirect to menu)
        elif text.startswith(('/help', '/mychatid', '/id')):
            help_text = f"""
🤖 *MultiLingo Bot - Updated!*

✨ *New Menu System!* Use the buttons below for all features.

*Quick Info:*
� Your Chat ID: `{chat_id}`
📝 Send any text for auto-translation
🔗 Send 8-character token to verify account

The bot has been upgraded with an easy-to-use menu system. Use the buttons below to access all features!
            """
            send_message(chat_id, help_text, create_main_menu())
            
        # Handle legacy train/translation commands (redirect to menu)
        elif text.startswith(('/train', '/translate', '/speak', '/languages')):
            redirect_msg = "🔄 *Command Updated!*\n\nThis command is now available through the menu system below. Please use the buttons for a better experience!"
            send_message(chat_id, redirect_msg, create_main_menu())
            
        # Show start button for any other text
        else:
            # Show start button instead of auto-translating by default
            default_msg = f"👋 Hello {username or 'there'}!\n\n🤖 Welcome to *MultiLingo Bot*\n\n✨ Choose an option below:\n\n🚀 **Start Bot** - Access all features including:\n• 🚂 Train management & subscriptions\n• 🔔 Smart notifications  \n• � Language settings\n• 🔧 Account management\n\n🌍 **Auto-Translate** - Translate text to English\n\n💡 *Tip: You can also send any text directly for auto-translation, or send an 8-character token to verify your account.*"
            send_message(chat_id, default_msg, create_start_button())
                
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        send_message(chat_id, "❌ Sorry, something went wrong. Please try again.", create_main_menu())

def auto_translate_text(chat_id, text):
    """Auto-translate text to English"""
    try:
        if len(text) > 1:
            send_message(chat_id, "🔄 Auto-translating to English...")
            translated = translate_text(text, "en")
            
            if translated.lower() != text.lower():  # Only show if translation changed the text
                result_msg = f"🌍 *Auto-Translation (English)*\n\n📝 Original: {text}\n✅ Translated: {translated}\n\n💡 Use the menu below for more features:"
                send_message(chat_id, result_msg, create_main_menu())
            else:
                send_message(chat_id, f"✅ Text is already in English: {text}\n\n💡 Use the menu below for more features:", create_main_menu())
        else:
            send_message(chat_id, "👋 Hello! Send me any text to translate, or use the menu below:", create_main_menu())
    except Exception as e:
        print(f"Error in auto-translation: {str(e)}")
        send_message(chat_id, "❌ Translation failed. Please try again.", create_main_menu())

def main():
    last_update_id = None
    
    print("🤖 MultiLingo Bot v2.0 is starting...")
    print("✨ New features: Interactive menus, train management, audio notifications")
    
    while True:
        try:
            updates = get_updates(last_update_id)
            if 'result' in updates:
                for update in updates['result']:
                    # Handle regular messages
                    if 'message' in update:
                        chat_id = update['message']['chat']['id']
                        text = update['message'].get('text', '')
                        username = update['message'].get('from', {}).get('first_name', '')
                        
                        if text:
                            print(f"📨 Message from {username} ({chat_id}): {text}")
                            process_message(chat_id, text, username)
                    
                    # Handle callback queries (button presses)
                    elif 'callback_query' in update:
                        print(f"🔘 Button pressed: {update['callback_query']['data']}")
                        handle_callback_query(update['callback_query'])
                        
                    last_update_id = update['update_id'] + 1

        except Exception as e:
            print(f"❌ Error in main loop: {str(e)}")
            time.sleep(5)  # Wait 5 seconds before retrying
            
        time.sleep(1)

if __name__ == '__main__':
    main()