import requests
import json
import time

BASE_URL = "http://localhost:8000/api/agent/chat"
SESSION_URL = "http://localhost:8000/api/agent/session"

def create_session():
    try:
        response = requests.post(SESSION_URL, params={'userId': 'capability_tester'})
        if response.status_code == 200:
            return response.json()['sessionId']
    except Exception as e:
        print(f"Error creating session: {e}")
    return None

def send_message(session_id, message):
    print(f"\nUser: {message}")
    try:
        response = requests.post(BASE_URL, json={'message': message, 'sessionId': session_id})
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print(f"Agent: {result.get('result')}")
                return True
            else:
                print(f"Error: {result.get('error')}")
        else:
            print(f"HTTP Error: {response.status_code}")
    except Exception as e:
        print(f"Exception: {e}")
    return False

def verify_capabilities():
    print("=== Verifying Agent Capabilities ===")
    session_id = create_session()
    if not session_id:
        print("Failed to start session. Is server running?")
        return

    # 1. Knowledge Base Question (ISO 27001) - Ask for a bit more detail to test length
    print("\n--- Test 1: Knowledge Base ---")
    send_message(session_id, "Explain ISO 27001 briefly.")

    # 2. CRUD & Reasoning (Create properly)
    print("\n--- Test 2: Setup (CRUD) ---")
    # Use explicit commands
    send_message(session_id, "Create scope Alpha-Scope")
    send_message(session_id, "Create scope Beta-Scope")
    
    # 3. Analysis (Use correct syntax)
    print("\n--- Test 3: Analysis Capability ---")
    send_message(session_id, "Analyze scope Alpha-Scope")

    # 4. Comparison
    print("\n--- Test 4: Comparison Capability ---")
    send_message(session_id, "Compare Alpha-Scope and Beta-Scope")

if __name__ == "__main__":
    verify_capabilities()