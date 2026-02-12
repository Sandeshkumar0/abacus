#!/usr/bin/env python
"""List all available Gemini models for your API key"""

import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key or api_key == "your_gemini_api_key_here":
    print("❌ API key not configured")
    exit(1)

print("=" * 70)
print("🔍 LISTING AVAILABLE GEMINI MODELS")
print("=" * 70)
print()

try:
    genai.configure(api_key=api_key)
    print("✅ API key configured successfully")
    print()
    
    print("📋 Available models:")
    print("-" * 70)
    
    models = genai.list_models()
    
    text_models = []
    for model in models:
        # Check if model supports generateContent
        if 'generateContent' in model.supported_generation_methods:
            text_models.append(model.name)
            print(f"✅ {model.name}")
            print(f"   Display Name: {model.display_name}")
            print(f"   Description: {model.description}")
            print(f"   Supported methods: {', '.join(model.supported_generation_methods)}")
            print()
    
    print("=" * 70)
    print("📝 RECOMMENDED MODEL TO USE:")
    print("=" * 70)
    
    if text_models:
        # Get the base name (remove 'models/' prefix)
        recommended = text_models[0].replace('models/', '')
        print(f"✅ Use this model: {recommended}")
        print()
        print("Update your code to use:")
        print(f'   model = genai.GenerativeModel("{recommended}")')
    else:
        print("❌ No models found that support generateContent")
    
    print("=" * 70)
    
except Exception as e:
    print(f"❌ Error: {e}")
    print()
    print("Possible issues:")
    print("  - API key might be invalid")
    print("  - Network connection issue")
    print("  - API quota exceeded")
