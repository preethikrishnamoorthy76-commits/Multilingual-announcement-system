#!/usr/bin/env python3
"""
Test script for utils.py translation and audio functions
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from utils import translate_text, generate_audio_file_with_url, generate_audio, SUPPORTED_LANGUAGES
import tempfile

def test_utils_translation():
    """Test the translation functions in utils.py"""
    print("🔧 Testing Utils Translation Functions")
    print("=" * 50)
    
    # Test text
    test_texts = [
        "Train number 12345 Express Special is arriving on platform 3",
        "We regret to inform you that train number 22638 is delayed by 30 minutes",
        "Attention passengers, train number 16057 will depart from platform 2"
    ]
    
    # Test languages
    test_languages = ['es', 'fr', 'hi', 'ta', 'te', 'de', 'ru']
    
    print("🌍 Testing Deep Translator Function:")
    print()
    
    for i, text in enumerate(test_texts, 1):
        print(f"Test {i}: {text}")
        print()
        
        for lang in test_languages:
            try:
                translated = translate_text(text, lang, 'en')
                print(f"  {lang} ({SUPPORTED_LANGUAGES.get(lang, 'Unknown')}): {translated}")
            except Exception as e:
                print(f"  {lang}: ❌ Error - {str(e)}")
        
        print("-" * 40)
    
    print("🎵 Testing Audio Generation Functions:")
    print()
    
    test_text = "Train number 12345 is arriving on platform 3"
    
    for lang in test_languages:
        try:
            # Test translate then audio
            translated = translate_text(test_text, lang, 'en')
            print(f"{lang.upper()} - Translated: {translated}")
            
            # Test simple audio generation
            audio_file = generate_audio(translated, lang)
            if audio_file and os.path.exists(audio_file):
                file_size = os.path.getsize(audio_file)
                print(f"  ✅ Simple audio: {os.path.basename(audio_file)} ({file_size} bytes)")
                os.remove(audio_file)
            else:
                print(f"  ❌ Simple audio generation failed")
            
            # Test web app audio generation with URL
            static_dir = tempfile.mkdtemp()
            try:
                file_path, audio_url = generate_audio_file_with_url(translated, lang, static_dir)
                if file_path and os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    print(f"  ✅ Web audio: {os.path.basename(file_path)} ({file_size} bytes)")
                    print(f"      URL: {audio_url}")
                    os.remove(file_path)
                else:
                    print(f"  ❌ Web audio generation failed")
            except Exception as web_audio_error:
                print(f"  ❌ Web audio error: {str(web_audio_error)}")
            finally:
                # Cleanup temp directory
                try:
                    os.rmdir(static_dir)
                except:
                    pass
                    
        except Exception as e:
            print(f"  ❌ Error testing {lang}: {str(e)}")
        
        print()
    
    print("🔍 Testing Language Support:")
    print()
    
    print(f"Supported languages ({len(SUPPORTED_LANGUAGES)}):")
    for code, name in SUPPORTED_LANGUAGES.items():
        print(f"  {code}: {name}")
    
    print()
    print("Testing language validation:")
    
    valid_langs = ['en', 'es', 'fr', 'hi', 'ta']
    invalid_langs = ['xyz', 'invalid', '123']
    
    for lang in valid_langs + invalid_langs:
        try:
            result = translate_text("Hello world", lang, 'en')
            status = "✅ Valid" if lang in valid_langs else "❓ Unexpected success"
            print(f"  {lang}: {status} - {result}")
        except Exception as e:
            status = "❌ Invalid" if lang in invalid_langs else "❌ Unexpected error"
            print(f"  {lang}: {status} - {str(e)}")

if __name__ == "__main__":
    try:
        test_utils_translation()
        print("✅ Utils test completed successfully!")
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()