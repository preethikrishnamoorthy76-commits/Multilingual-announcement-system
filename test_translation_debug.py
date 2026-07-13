#!/usr/bin/env python3
"""
Test script to debug translation issues in train notifications
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from train_notification_service import TrainNotificationService
import logging

# Configure logging to see debug messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_translation():
    """Test the translation functionality"""
    print("🧪 Testing Translation Functionality")
    print("=" * 50)
    
    # Initialize the service
    service = TrainNotificationService()
    
    # Test messages
    test_messages = [
        "Attention please. Train number 12345, Express Train, coming from Mumbai, is arriving shortly on platform number 3.",
        "Train number 67890, Superfast Express, will depart at 15:30 from platform number 7.",
        "We regret to inform you that train number 11111, Morning Express, from Delhi to Chennai, is delayed by 45 minutes."
    ]
    
    # Test languages
    test_languages = ['hindi', 'tamil', 'spanish', 'french']
    
    for message in test_messages:
        print(f"\n📝 Original Message: {message}")
        print("-" * 80)
        
        for lang in test_languages:
            print(f"\n🌍 Translating to {lang}:")
            try:
                # Test Gemini translation
                translated = service.translate_with_gemini(message, lang)
                print(f"✅ Gemini Result: {translated}")
                
                # Test if it's actually translated
                if translated.lower() != message.lower():
                    print("✅ Translation appears successful!")
                else:
                    print("❌ Translation appears to have failed - same as original")
                
            except Exception as e:
                print(f"❌ Translation failed: {e}")
        
        print("-" * 80)
    
    print("\n🎯 Testing complete notification flow:")
    
    # Test user notification
    test_user = {
        'username': 'test_user',
        'chat_id': 'test123',
        'preferred_language': 'hindi',
        'audio_notifications': False
    }
    
    test_message = "Attention please. Train number 12345, Chennai Express, is arriving shortly on platform number 2."
    
    print(f"👤 Test User: {test_user}")
    print(f"📨 Test Message: {test_message}")
    
    # Mock the telegram sending to avoid actual API calls
    original_send = service.send_telegram_message
    service.send_telegram_message = lambda chat_id, text: (print(f"📤 Would send to {chat_id}: {text}"), True)[1]
    
    try:
        result = service.send_notification_to_user(test_user, test_message)
        print(f"✅ Notification sent successfully: {result}")
    except Exception as e:
        print(f"❌ Notification failed: {e}")
    finally:
        # Restore original method
        service.send_telegram_message = original_send

if __name__ == "__main__":
    test_translation()