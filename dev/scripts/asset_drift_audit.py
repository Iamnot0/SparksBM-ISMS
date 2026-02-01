#!/usr/bin/env python3
"""
Asset Drift Audit Script
Automates the reconciliation of assets between two ISMS domains.
"""

import sys
import os
import requests
import json
import time
from typing import Dict, List

# Configuration
BASE_URL = "http://localhost:8000/api/agent"
SESSION_USER = "drift_auditor"

def create_session():
    try:
        res = requests.post(f"{BASE_URL}/session", params={"userId": SESSION_USER})
        if res.status_code == 200:
            return res.json().get("sessionId")
    except Exception as e:
        print(f"❌ Failed to create session: {e}")
        sys.exit(1)
    return None

def send_query(session_id: str, query: str) -> Dict:
    res = requests.post(f"{BASE_URL}/chat", json={
        "message": query,
        "sessionId": session_id
    })
    if res.status_code == 200:
        return res.json().get("result")
    return {"error": f"HTTP {res.status_code}"}

def run_drift_audit(domain1: str, domain2: str):
    print(f"\n🔍 Starting Asset Drift Audit: '{domain1}' vs '{domain2}'")
    session_id = create_session()
    
    # 1. Trigger Comparison via Agent
    # The agent uses VeriniceTool.compareDomains under the hood
    print("   • Requesting domain comparison...")
    query = f"Compare the '{domain1}' domain with the '{domain2}' domain."
    result = send_query(session_id, query)
    
    print("\n📊 Audit Results:")
    if isinstance(result, str):
        print(result)
    elif isinstance(result, dict):
        # Format structured output if available
        diffs = result.get('differences', {})
        for obj_type, data in diffs.items():
            print(f"\n   Object Type: {obj_type.upper()}")
            only1 = data.get('only_in_domain1', [])
            only2 = data.get('only_in_domain2', [])
            common = data.get('common', [])
            
            print(f"     - Only in {domain1}: {len(only1)}")
            for item in only1[:3]: print(f"       • {item.get('name')} ({item.get('id')})")
            if len(only1)>3: print("       ...")
            
            print(f"     - Only in {domain2}: {len(only2)}")
            for item in only2[:3]: print(f"       • {item.get('name')} ({item.get('id')})")
            if len(only2)>3: print("       ...")
            
            print(f"     - Common: {len(common)}")

    print("\n✅ Drift Audit Complete.")

if __name__ == "__main__":
    # Use defaults found in previous logs
    run_drift_audit("ISO 27001", "DS-GVO")
