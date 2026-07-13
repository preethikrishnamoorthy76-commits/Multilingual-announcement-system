"""
Test script to verify translation and audio generation functionality
"""
from utils import translate_text, generate_audio, SUPPORTED_LANGUAGES
import os

def test_translation():
    """Test translation functionality"""
    print("=" * 50)
    print("TESTING TRANSLATION FUNCTIONALITY")
    print("=" * 50)
    
    test_text = "Hello, how are you today?"
    print(f"\nOriginal text: {test_text}")
    print(f"Source language: auto (English)")
    
    # Test translation to various languages
    test_languages = ['es', 'fr', 'de', 'hi', 'zh', 'ja']
    
    for lang_code in test_languages:
        lang_name = SUPPORTED_LANGUAGES.get(lang_code, lang_code)
        print(f"\n--- Testing {lang_name} ({lang_code}) ---")
        
        try:
            translated = translate_text(test_text, lang_code, "auto")
            print(f"✅ Translation successful: {translated}")
        except Exception as e:
            print(f"❌ Translation failed: {str(e)}")

def test_audio_generation():
    """Test audio generation functionality"""
    print("\n" + "=" * 50)
    print("TESTING AUDIO GENERATION FUNCTIONALITY")
    print("=" * 50)
    
    test_cases = [
        ("Hello, this is a test", "en", "English"),
        ("Hola, esto es una prueba", "es", "Spanish"),
        ("Bonjour, ceci est un test", "fr", "French"),
        ("こんにちは、これはテストです", "ja", "Japanese"),
        ("你好，这是一个测试", "zh-cn", "Chinese"),
    ]
    
    for text, lang_code, lang_name in test_cases:
        print(f"\n--- Testing {lang_name} ({lang_code}) ---")
        print(f"Text: {text}")
        
        try:
            audio_path = generate_audio(text, lang_code)
            if audio_path and os.path.exists(audio_path):
                file_size = os.path.getsize(audio_path)
                print(f"✅ Audio generated successfully!")
                print(f"   File: {audio_path}")
                print(f"   Size: {file_size} bytes")
                
                # Clean up
                os.remove(audio_path)
                print(f"   Cleaned up test file")
            else:
                print(f"❌ Audio generation failed: File not created")
        except Exception as e:
            print(f"❌ Audio generation failed: {str(e)}")

def test_translation_and_audio():
    """Test combined translation and audio generation"""
    print("\n" + "=" * 50)
    print("TESTING TRANSLATION + AUDIO GENERATION")
    print("=" * 50)
    
    original_text = "Good morning! Welcome to our multilingual app."
    test_languages = ['es', 'fr', 'hi']
    
    print(f"\nOriginal text: {original_text}")
    
    for lang_code in test_languages:
        lang_name = SUPPORTED_LANGUAGES.get(lang_code, lang_code)
        print(f"\n--- Testing {lang_name} ({lang_code}) ---")
        
        try:
            # Translate
            translated = translate_text(original_text, lang_code, "auto")
            print(f"✅ Translated: {translated}")
            
            # Generate audio
            audio_path = generate_audio(translated, lang_code)
            if audio_path and os.path.exists(audio_path):
                file_size = os.path.getsize(audio_path)
                print(f"✅ Audio generated: {file_size} bytes")
                os.remove(audio_path)
            else:
                print(f"❌ Audio generation failed")
                
        except Exception as e:
            print(f"❌ Failed: {str(e)}")

def main():
    """Run all tests"""
    print("\n" + "=" * 50)
    print("MULTILINGO TRANSLATION & AUDIO TESTS")
    print("=" * 50)
    
    try:
        test_translation()
        test_audio_generation()
        test_translation_and_audio()
        
        print("\n" + "=" * 50)
        print("ALL TESTS COMPLETED")
        print("=" * 50)
        
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")

if __name__ == "__main__":
    main()
