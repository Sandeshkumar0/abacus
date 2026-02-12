#!/usr/bin/env python
"""Quick API key check"""
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print("=" * 60)
print("GEMINI API KEY CHECK")
print("=" * 60)

if not api_key:
    print("❌ NO API KEY FOUND")
    print("Check your .env file")
elif api_key == "your_gemini_api_key_here":
    print("⚠️  PLACEHOLDER VALUE DETECTED")
    print("Replace with real API key")
else:
    print("✅ API KEY FOUND")
    print(f"Length: {len(api_key)} chars")
    print(f"Preview: {api_key[:15]}...{api_key[-10:]}")
    
    # Quick import test
    try:
        import google.generativeai as genai
        print("✅ Package imported")
        
        genai.configure(api_key=api_key)
        print("✅ API configured")
        print()
        print("🎉 Configuration looks good!")
        print("Restart your Django server to apply changes.")
    except Exception as e:
        print(f"❌ Error: {e}")

print("=" * 60)
