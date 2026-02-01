#!/usr/bin/env python3
"""Quick test for create-and-link and subtype-filtered list queries"""

import sys
import os
import requests
import json
from typing import Dict

BASE_URL = "http://localhost:8000"

def send_message(message: str, session_id: str = None) -> Dict:
    """Send message to API"""
    url = f"{BASE_URL}/api/agent/chat"
    payload = {
        "message": message,
        "sessionId": session_id
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code == 200:
            return response.json()
        return {"error": f"HTTP {response.status_code}", "status": "error"}
    except Exception as e:
        return {"error": str(e), "status": "error"}

def test_create_and_link(session_id: str):
    """Test: create scope AA and link with IT-System asset"""
    print("\n" + "="*70)
    print("TEST 1: Create-and-Link Pattern")
    print("="*70)
    print("Prompt: create scope AA and link with IT-System asset")
    print("-"*70)
    
    result = send_message("create scope AA and link with IT-System asset", session_id)
    
    status = result.get('status', 'unknown')
    print(f"Status: {status}")
    
    if status == 'success':
        response_text = result.get('response', result.get('result', ''))
        print(f"✅ Success: {response_text[:300]}")
        return True
    else:
        error = result.get('error', result.get('response', 'Unknown error'))
        print(f"❌ Error: {error[:300]}")
        return False

def test_subtype_list_query(session_id: str):
    """Test: how many assets in our IT-System assets"""
    print("\n" + "="*70)
    print("TEST 2: Subtype-Filtered List Query")
    print("="*70)
    print("Prompt: how many assets in our IT-System assets")
    print("-"*70)
    
    result = send_message("how many assets in our IT-System assets", session_id)
    
    status = result.get('status', 'unknown')
    print(f"Status: {status}")
    
    if status == 'success':
        response_text = result.get('response', result.get('result', ''))
        print(f"✅ Success: {response_text[:300]}")
        return True
    else:
        error = result.get('error', result.get('response', 'Unknown error'))
        print(f"❌ Error: {error[:300]}")
        return False

if __name__ == '__main__':
    print("\n🧪 Quick Test Suite for Pattern Fixes")
    print("="*70)
    
    # Create session
    try:
        session_response = requests.post(
            f"{BASE_URL}/api/agent/session",
            params={'userId': 'quick_tester'},
            timeout=10
        )
        if session_response.status_code == 200:
            session_data = session_response.json()
            if session_data.get('status') == 'success':
                session_id = session_data.get('sessionId')
                print(f"✅ Session created: {session_id[:20]}...")
            else:
                print(f"❌ Session creation failed: {session_data}")
                sys.exit(1)
        else:
            print(f"❌ Session creation failed: HTTP {session_response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to create session: {e}")
        print("Make sure the server is running on http://localhost:8000")
        sys.exit(1)
    
    test1 = test_create_and_link(session_id)
    test2 = test_subtype_list_query(session_id)
    
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    print(f"Test 1 (Create-and-Link): {'✅ PASSED' if test1 else '❌ FAILED'}")
    print(f"Test 2 (Subtype List Query): {'✅ PASSED' if test2 else '❌ FAILED'}")
    print("="*70 + "\n")
