#!/usr/bin/env python3
"""
Test all prompts from promptEngineering.txt (lines 3-28)
Tests if agent understands and processes all commands correctly
"""

import sys
import os
import time
import requests
from typing import Dict, List, Tuple
from datetime import datetime

# Add paths
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.join(_current_dir, '..', '..')

BASE_URL = "http://localhost:8000"
MAX_WAIT_TIME = 60  # Maximum seconds to wait for server
WAIT_INTERVAL = 2   # Seconds between checks

def wait_for_server(max_wait: int = MAX_WAIT_TIME, interval: int = WAIT_INTERVAL) -> bool:
    """Wait for API server to be ready"""
    print(f"\n⏳ Waiting for server at {BASE_URL}...")
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < max_wait:
        attempt += 1
        try:
            response = requests.get(f"{BASE_URL}/api/agent/tools", timeout=3)
            if response.status_code == 200:
                elapsed = time.time() - start_time
                print(f"✅ Server is ready! (waited {elapsed:.1f}s)")
                return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            elapsed = time.time() - start_time
            if attempt % 5 == 0:  # Print every 5 attempts
                print(f"   Still waiting... ({elapsed:.0f}s elapsed)")
            time.sleep(interval)
        except Exception as e:
            print(f"   Error checking server: {e}")
            time.sleep(interval)
    
    print(f"❌ Server not ready after {max_wait}s")
    return False

# Prompts from promptEngineering.txt (lines 3-28)
TEST_PROMPTS = [
    "Show me all scopes.",
    "remove them all.",
    "how many subtype do we have for scope in our isms.",
    "Create 3 scopes in our isms and give the scopes name (SCOPE-A,SCOPE-B,and SCOPE-C)",
    "Create 5 scopes in our isms and give the scopes name (SCOPE-A,SCOPE-B,and SCOPE-C)",
    "How many scopes?",
    "how many subtype do we have for assets in our isms.",
    "How many assets do we have in our isms and show me alll asets of IT-System subtypes.",
    "remove them all.",
    "Create 5 assets in our isms and give the asset name (Asset-A,E)",
    "Add 3 assets to our IT-System asset, and the other 2 add to the Datatypes assets.",
    "show me all scopes with thier subtypes.",
    "link the SCOPE-B with IT-System assets , and SCOPE-D link with Datatypes assets.",
    "Update the asset 'ASSET-A'. Change its description to 'description UPDATING' and set its confidentiality to 'High'",
    "Compare SCOPE-A and SCOPE-B",
    "what are those.",
    "how many persons do we have in our system?",
    "remove them all.",
    "create 5 persons now and give thier names (John,Anna,Jame,David,Eddie).",
    "now how many persons do we have in our system.",
    "add John,Anna,Eddie to DPO.",
    "show me all persons and who are dop.",
    "link DPO with SCOPE-A"
]

class PromptEngineeringTester:
    """Test all prompts from promptEngineering.txt"""
    
    def __init__(self):
        self.session_id = None
        self.results: List[Dict] = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️ ",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARN": "⚠️ ",
            "TEST": "🧪"
        }.get(level, "ℹ️ ")
        print(f"{timestamp} {prefix} {message}")
    
    def create_session(self) -> bool:
        """Create API session"""
        try:
            response = requests.post(
                f"{BASE_URL}/api/agent/session",
                params={'userId': 'prompt_engineering_tester'},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.session_id = data.get('sessionId')
                self.log(f"Session created: {self.session_id[:20]}...", "SUCCESS")
                return True
            return False
        except Exception as e:
            self.log(f"Error creating session: {e}", "ERROR")
            return False
    
    def send_message(self, message: str, timeout: int = 120) -> Dict:
        """Send message to API"""
        try:
            response = requests.post(
                f"{BASE_URL}/api/agent/chat",
                json={
                    'message': message,
                    'sessionId': self.session_id
                },
                timeout=timeout
            )
            if response.status_code == 200:
                return response.json()
            return {'status': 'error', 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def test_prompt(self, prompt: str, index: int) -> Tuple[bool, str]:
        """Test a single prompt"""
        self.log(f"[{index}/{len(TEST_PROMPTS)}] Testing: {prompt[:60]}...", "TEST")
        
        response = self.send_message(prompt)
        time.sleep(1)  # Small delay between requests
        
        status = response.get('status')
        result = str(response.get('result', ''))
        error = response.get('error', '')
        result_lower = result.lower() if result else ''
        
        # Check for common failure patterns
        is_error = status == 'error'
        has_generic_error = any(phrase in error.lower() for phrase in [
            "i couldn't process",
            "please try rephrasing",
            "generic",
            "no fallback answer",
            "unknown operation"
        ]) if error else False
        
        # Check for success indicators
        is_success = status == 'success' and not has_generic_error
        has_result = bool(result and len(result) > 10)
        
        passed = is_success and has_result and not has_generic_error
        
        # Store result
        self.results.append({
            'index': index,
            'prompt': prompt,
            'passed': passed,
            'status': status,
            'error': error,
            'result_preview': result[:200] if result else None,
            'has_generic_error': has_generic_error
        })
        
        if passed:
            self.log(f"✅ PASS: {prompt[:50]}...", "SUCCESS")
            if result:
                preview = result[:150] if len(result) > 150 else result
                self.log(f"   Response: {preview}", "INFO")
        else:
            self.log(f"❌ FAIL: {prompt[:50]}...", "ERROR")
            if error:
                self.log(f"   Error: {error[:150]}", "ERROR")
            elif not has_result:
                self.log(f"   No result returned", "ERROR")
            if result:
                preview = result[:150] if len(result) > 150 else result
                self.log(f"   Response: {preview}", "WARN")
        
        return passed, error or result[:100]
    
    def run_all_tests(self):
        """Run all prompts from promptEngineering.txt"""
        print("\n" + "=" * 80)
        print("🧪 PROMPT ENGINEERING TEST SUITE")
        print("=" * 80)
        print("Testing prompts from: dev/docs/promptEngineering.txt (lines 3-28)")
        print("=" * 80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Wait for server to be ready
        if not wait_for_server():
            print("\n❌ Server is not available. Please start the server and try again.")
            print("   Expected server at: http://localhost:8000")
            return
        
        if not self.create_session():
            print("❌ Failed to create session. Exiting.")
            return
        
        print("\n" + "-" * 80)
        print("Running All Test Prompts")
        print("-" * 80)
        
        for i, prompt in enumerate(TEST_PROMPTS, 1):
            self.test_prompt(prompt, i)
            time.sleep(1.5)  # Delay between prompts
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed
        generic_errors = sum(1 for r in self.results if r.get('has_generic_error', False))
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Generic Errors: {generic_errors}")
        print(f"Pass Rate: {pass_rate:.1f}%")
        
        if failed > 0:
            print("\n❌ Failed Tests:")
            for result in self.results:
                if not result['passed']:
                    print(f"\n  [{result['index']}] {result['prompt']}")
                    if result.get('error'):
                        print(f"      Error: {result['error'][:150]}")
                    if result.get('result_preview'):
                        print(f"      Response: {result['result_preview'][:150]}...")
        
        print("\n" + "=" * 80)
        if pass_rate == 100:
            print("✅ ALL TESTS PASSED")
        elif pass_rate >= 80:
            print("⚠️  MOST TESTS PASSED (80%+)")
        else:
            print("❌ MANY TESTS FAILED - NEEDS FIXING")
        print("=" * 80)

if __name__ == "__main__":
    tester = PromptEngineeringTester()
    tester.run_all_tests()
