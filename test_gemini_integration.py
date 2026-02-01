#!/usr/bin/env python3
"""
Test script for SparksBM Gemini Integration
Tests error handling for quota limits, authentication, and API errors
"""

import sys
import os
from pathlib import Path

# Add Agentic Framework to path
sys.path.insert(0, str(Path(__file__).parent / "AgenticFramework"))

def test_gemini_integration():
    """Test Gemini integration with error handling"""
    print("=" * 70)
    print("SparksBM Gemini Integration Test")
    print("=" * 70)
    print()
    
    # Check environment
    print("1. Environment Check:")
    api_key = os.getenv('GEMINI_API_KEY', '')
    if api_key:
        print(f"   ✅ GEMINI_API_KEY found: {api_key[:15]}...{api_key[-4:]}")
    else:
        print("   ❌ GEMINI_API_KEY not found")
        print("   Set it with: export GEMINI_API_KEY='your-key'")
        return
    
    # Check library
    print("\n2. Library Check:")
    try:
        import google.generativeai as genai
        print("   ✅ google-generativeai library installed")
    except ImportError:
        print("   ❌ google-generativeai library not installed")
        print("   Install with: pip install google-generativeai")
        return
    
    # Test engine creation
    print("\n3. Engine Creation:")
    try:
        from orchestrator.reasoningEngine import createReasoningEngine
        engine = createReasoningEngine("gemini")
        print(f"   ✅ Engine created: {type(engine).__name__}")
        print(f"   ✅ Available: {engine.isAvailable()}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return
    
    # Test API call with error handling
    if engine.isAvailable():
        print("\n4. API Call Test:")
        try:
            response = engine.reason("What is ISMS in one sentence?", response_mode="concise")
            print(f"   ✅ Success! Response: {response}")
        except Exception as e:
            error_msg = str(e)
            print(f"   ⚠️  Error occurred: {error_msg}")
            
            # Analyze error type
            if "quota" in error_msg.lower() or "exhausted" in error_msg.lower():
                print("\n   📊 Error Analysis:")
                print("   - Type: API Quota Exceeded")
                print("   - Cause: Daily request limit reached")
                print("   - Solution: Wait 24 hours or upgrade API plan")
                print("   - Note: gemini-cli and SparksBM share the same quota")
            elif "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                print("\n   📊 Error Analysis:")
                print("   - Type: Authentication Error")
                print("   - Cause: Invalid or missing API key")
                print("   - Solution: Check GEMINI_API_KEY environment variable")
            elif "blocked" in error_msg.lower():
                print("\n   📊 Error Analysis:")
                print("   - Type: Content Safety Filter")
                print("   - Cause: Request triggered safety filters")
                print("   - Solution: Rephrase the query")
            else:
                print("\n   📊 Error Analysis:")
                print("   - Type: Unknown Error")
                print("   - Details: See error message above")
    else:
        print("\n4. ⚠️  Engine not available - cannot test API calls")
    
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)
    print("\n📝 Notes:")
    print("   - Gemini API has daily quota limits (free tier)")
    print("   - Both gemini-cli and SparksBM use the same API key/quota")
    print("   - Quota resets every 24 hours")
    print("   - Error handling includes: quota, auth, safety, network errors")

if __name__ == "__main__":
    test_gemini_integration()
