#!/usr/bin/env python
"""
Test script to verify Google Gemini API key configuration.
Run this to check if your API key is working correctly.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

print("=" * 60)
print("🔍 GEMINI API KEY CONFIGURATION TEST")
print("=" * 60)
print()

# Check if .env file exists
env_file = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_file):
    print("✅ .env file found:", env_file)
else:
    print("❌ .env file NOT found!")
    print("   Expected location:", env_file)
    sys.exit(1)

# Check if API key is set
api_key = os.getenv("GEMINI_API_KEY")
print()
print("🔑 API Key Status:")
print("-" * 60)

if not api_key:
    print("❌ GEMINI_API_KEY is NOT set in .env file")
    print()
    print("📝 To fix this:")
    print("   1. Open .env file")
    print("   2. Add: GEMINI_API_KEY=your_actual_api_key_here")
    print("   3. Get free key from: https://makersuite.google.com/app/apikey")
    sys.exit(1)
elif api_key == "your_gemini_api_key_here":
    print("⚠️  GEMINI_API_KEY is set to placeholder value")
    print("   Current value: your_gemini_api_key_here")
    print()
    print("📝 To fix this:")
    print("   1. Get your API key from: https://makersuite.google.com/app/apikey")
    print("   2. Replace 'your_gemini_api_key_here' with actual key")
    sys.exit(1)
else:
    print("✅ GEMINI_API_KEY is set")
    print(f"   Key length: {len(api_key)} characters")
    print(f"   Key preview: {api_key[:10]}...{api_key[-10:]}")

# Try to import and configure genai
print()
print("📦 Testing Google Generative AI Package:")
print("-" * 60)

try:
    import google.generativeai as genai
    print("✅ google.generativeai package imported successfully")
except ImportError as e:
    print("❌ Failed to import google.generativeai")
    print(f"   Error: {e}")
    print()
    print("📝 To fix this:")
    print("   Run: pip install google-generativeai")
    sys.exit(1)

# Try to configure with the API key
print()
print("⚙️  Testing API Key Configuration:")
print("-" * 60)

try:
    genai.configure(api_key=api_key)
    print("✅ API key configured successfully")
except Exception as e:
    print("❌ Failed to configure API key")
    print(f"   Error: {e}")
    print()
    print("📝 Possible issues:")
    print("   - API key might be invalid")
    print("   - Check for extra spaces in .env file")
    print("   - Verify key from: https://makersuite.google.com/app/apikey")
    sys.exit(1)

# Try to create a model
print()
print("🤖 Testing Model Creation:")
print("-" * 60)

try:
    model = genai.GenerativeModel("gemini-1.5-flash")
    print("✅ Model created successfully")
    print("   Model: gemini-1.5-flash")
except Exception as e:
    print("❌ Failed to create model")
    print(f"   Error: {e}")
    sys.exit(1)

# Try a simple API call
print()
print("🧪 Testing API Call:")
print("-" * 60)
print("Sending test prompt to Gemini...")

try:
    response = model.generate_content("Say 'Hello, API is working!' in one sentence.")
    
    if response and response.text:
        print("✅ API call successful!")
        print(f"   Response: {response.text}")
    else:
        print("⚠️  API call completed but no response text")
        print(f"   Response: {response}")
except Exception as e:
    print("❌ API call failed")
    print(f"   Error: {e}")
    print()
    print("📝 Possible issues:")
    print("   - API key might be invalid or expired")
    print("   - Network connection issue")
    print("   - API quota exceeded")
    print("   - Verify key at: https://makersuite.google.com/app/apikey")
    sys.exit(1)

# All tests passed!
print()
print("=" * 60)
print("🎉 ALL TESTS PASSED!")
print("=" * 60)
print()
print("✅ Your Gemini API key is configured correctly")
print("✅ AI features should work in your application")
print()
print("Next steps:")
print("  1. Restart your Django server")
print("  2. Test AI features in the application")
print("  3. Check for any warnings in server logs")
print()
print("=" * 60)
