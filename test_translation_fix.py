#!/usr/bin/env python3
"""
Test script to verify translation fixes for train announcements
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from train_notification_service import TrainNotificationService
import json

def test_translation_functionality():
    """Test the improved translation functionality"""
    print("🔧 Testing Train Announcement Translation Fixes")
    print("=" * 60)
    
    # Initialize the service
    service = TrainNotificationService()
    
    # Test announcement generation
    sample_train_data = {
        'data': {
            'train_number': '12345',
            'train_name': 'Express Special',
            'src_stn_name': 'Mumbai Central',
            'dest_stn_name': 'Delhi Junction',
            'current_station_name': 'Bhopal Junction'
        }
    }
    
    # Test different announcement types
    announcements = [
        ("Arrival", service.format_arrival_announcement(sample_train_data)),
        ("Departure", service.format_departure_announcement(sample_train_data)),
        ("Station Change", service.format_station_change_announcement(sample_train_data)),
        ("Delay", service.format_delay_announcement(sample_train_data, 30)),
        ("Monitoring Start", service.format_monitoring_start_announcement(sample_train_data))
    ]
    
    # Test languages
    test_languages = ['hindi', 'tamil', 'telugu', 'spanish', 'french']
    
    print("🎯 Testing Announcement Generation and Translation:")
    print()
    
    for announcement_type, announcement in announcements:
        print(f"📢 {announcement_type} Announcement:")
        print(f"   English: {announcement}")
        print()
        
        for lang in test_languages:
            try:
                # Test Gemini translation
                translated = service.translate_with_gemini(announcement, lang)
                print(f"   {lang.capitalize()}: {translated}")
                
                # Test audio generation
                audio_file = service.generate_audio_file(translated, lang)
                audio_status = "✅ Audio generated" if audio_file else "❌ Audio failed"
                print(f"   {lang.capitalize()} Audio: {audio_status}")
                
                # Clean up audio file
                if audio_file:
                    try:
                        os.remove(audio_file)
                    except:
                        pass
                
            except Exception as e:
                print(f"   {lang.capitalize()}: ❌ Error - {str(e)}")
        
        print("-" * 40)
    
    print("🎵 Testing Audio Generation for Different Languages:")
    print()
    
    test_text = "Train number 12345 Express Special is arriving on platform 3"
    
    for lang in test_languages:
        try:
            print(f"Testing {lang.capitalize()}...")
            
            # First translate
            translated_text = service.translate_with_gemini(test_text, lang)
            print(f"  Translated: {translated_text}")
            
            # Then generate audio
            audio_file = service.generate_audio_file(translated_text, lang)
            
            if audio_file and os.path.exists(audio_file):
                file_size = os.path.getsize(audio_file)
                print(f"  ✅ Audio generated: {os.path.basename(audio_file)} ({file_size} bytes)")
                os.remove(audio_file)  # Cleanup
            else:
                print(f"  ❌ Audio generation failed")
            
        except Exception as e:
            print(f"  ❌ Error testing {lang}: {str(e)}")
        
        print()
    
    print("🔍 Testing Train Number Formatting for Audio:")
    print()
    
    train_numbers = ['12345', '22638', '16057']
    
    for train_num in train_numbers:
        print(f"Train Number: {train_num}")
        
        for lang in ['english', 'hindi', 'tamil', 'telugu']:
            formatted = service.format_train_number_for_audio(train_num, lang)
            print(f"  {lang.capitalize()}: {formatted}")
        
        print()

if __name__ == "__main__":
    try:
        test_translation_functionality()
        print("✅ Translation test completed successfully!")
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()