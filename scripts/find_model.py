#!/usr/bin/env python
"""
Quick script to find the correct Gemini model name
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key or api_key == "your_gemini_api_key_here":
    print("❌ API key not configured")
    sys.exit(1)

print("Testing Gemini API...")
print("=" * 60)

try:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    
    print("✅ API configured successfully")
    print("\n📋 Listing available models...\n")
    
    models = list(genai.list_models())
    
    if not models:
        print("❌ No models found!")
        sys.exit(1)
    
    text_gen_models = []
    for m in models:
        if 'generateContent' in m.supported_generation_methods:
            model_name = m.name
            text_gen_models.append(model_name)
            print(f"✅ {model_name}")
            print(f"   Display: {m.display_name}")
            print(f"   Methods: {', '.join(m.supported_generation_methods)}")
            print()
    
    if text_gen_models:
        print("=" * 60)
        print("🎯 RECOMMENDED MODEL:")
        print("=" * 60)
        recommended = text_gen_models[0]
        print(f"\nUse this in your code:")
        print(f'model = genai.GenerativeModel("{recommended}")')
        print(f"\nModel name: {recommended}")
    else:
        print("❌ No models support generateContent")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
