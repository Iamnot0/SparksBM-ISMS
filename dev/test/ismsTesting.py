#!/usr/bin/env python3
"""
Comprehensive ISMS Testing Script

Combines:
- Interactive ISMS Testing Console
- CRUD + Subtypes Testing
- Friendly Linking Testing

Author: QA Expert Tester
Usage: 
  python ismsTesting.py                    # Interactive mode
  python ismsTesting.py --crud             # Run CRUD + subtypes tests
  python ismsTesting.py --friendly         # Run friendly linking tests
  python ismsTesting.py --all              # Run all automated tests
"""

import sys
import os
import time
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

# Configure logging at the beginning of the script
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add paths
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.join(_current_dir, '..', '..')
_agentic_framework = os.path.join(_project_root, 'Agentic Framework')
if _agentic_framework not in sys.path:
    sys.path.insert(0, _agentic_framework)

BASE_URL = "http://localhost:8000"

# ============================================================================
# INTERACTIVE TESTING CONSOLE
# ============================================================================

class ISMSTester:
    """Interactive ISMS Testing Interface - Loop Based"""
    
    HELP_TEXT = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                        ISMS INTERACTIVE TESTING CONSOLE                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  CRUD OPERATIONS:                                                           ║
║    create <type> <name> [abbr] ["description"]                              ║
║    list <type>                                                              ║
║    get <type> <name or id>                                                  ║
║    update <type> <name> <field> <value>                                     ║
║    delete <type> <name>                                                     ║
║                                                                             ║
║  OBJECT TYPES: scope, asset, person, process, document, incident,          ║
║                control, scenario                                            ║
║                                                                             ║
║  COMPARISON & LINKING:                                                      ║
║    compare <name1> and <name2>       - Compare two objects                  ║
║    link <name1> with <name2>         - Link two objects                     ║
║    links <name>                      - Show all links for object            ║
║                                                                             ║
║  INFO COMMANDS:                                                             ║
║    domains                           - List all domains                     ║
║    units                             - List all units                       ║
║    subtypes <type>                   - Show valid subtypes for a type       ║
║                                                                             ║
║  TESTING UTILITIES:                                                         ║
║    history                           - Show command history                 ║
║    last                              - Show last response details           ║
║    session                           - Show current session info            ║
║    clear                             - Clear screen                         ║
║    help                              - Show this help                       ║
║    exit / quit                       - Exit the tester                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

    OBJECT_TYPES = ['scope', 'asset', 'person', 'process', 'document', 'incident', 'control', 'scenario']
    
    def __init__(self):
        self.session_id = None
        self.history: List[Dict] = []
        self.last_response: Optional[Dict] = None
        self.created_objects: Dict[str, List[Dict]] = {}  # Track created objects by type
        self.start_time = datetime.now()
    
    def log(self, message: str, level: str = "INFO"):
        """Log with timestamp and emoji"""
        timestamp = datetime.now().strftime("%I:%M %p")
        prefix = {
            "INFO": "ℹ️ ",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARN": "⚠️ ",
            "INPUT": "➡️ ",
            "RESPONSE": "📤"
        }.get(level, "ℹ️ ")
        print(f"{timestamp} {prefix} {message}")
    
    def create_session(self) -> bool:
        """Create API session"""
        try:
            response = requests.post(
                f"{BASE_URL}/api/agent/session",
                params={'userId': 'isms_tester'},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    self.session_id = data.get('sessionId')
                    self.log(f"Session created: {self.session_id[:30]}...", "SUCCESS")
                    return True
            self.log(f"Session creation failed: {response.status_code}", "ERROR")
            return False
        except requests.exceptions.ConnectionError:
            self.log("Cannot connect to API server. Is it running on localhost:8000?", "ERROR")
            return False
        except Exception as e:
            self.log(f"Session error: {str(e)}", "ERROR")
            return False
    
    def send_message(self, message: str, timeout: int = 120) -> Dict:
        """Send message to agent API"""
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
    
    def execute_command(self, cmd: str) -> str:
        """Execute an ISMS command and return formatted result"""
        cmd = cmd.strip()
        if not cmd:
            return ""
        
        # Record in history
        self.history.append({
            'time': datetime.now().isoformat(),
            'command': cmd
        })
        
        # Handle local commands first
        cmd_lower = cmd.lower()
        
        if cmd_lower in ['exit', 'quit', 'q']:
            return "EXIT"
        
        if cmd_lower == 'help':
            return self.HELP_TEXT
        
        if cmd_lower == 'clear':
            os.system('clear' if os.name != 'nt' else 'cls')
            return ""
        
        if cmd_lower == 'history':
            return self._format_history()
        
        if cmd_lower == 'last':
            return self._format_last_response()
        
        if cmd_lower == 'session':
            return self._format_session_info()
        
        if cmd_lower == 'created' or cmd_lower == 'tracked':
            return self._format_created_objects()
        
        # Send to API
        self.log(f"Sending: {cmd}", "INPUT")
        response = self.send_message(cmd)
        self.last_response = response
        
        # Track created objects
        self._track_created_object(cmd, response)
        
        # Format and return response
        return self._format_response(response)
    
    def _track_created_object(self, cmd: str, response: Dict):
        """Track created objects for later reference"""
        cmd_lower = cmd.lower()
        if cmd_lower.startswith('create'):
            result = str(response.get('result', ''))
            if 'created' in result.lower():
                # Parse object type from command
                parts = cmd.split()
                if len(parts) >= 3:
                    obj_type = parts[1].lower()
                    obj_name = parts[2]
                    
                    # Extract ID from response if present
                    obj_id = None
                    if 'ID:' in result:
                        try:
                            obj_id = result.split('ID:')[1].split(')')[0].strip()
                        except:
                            pass
                    
                    if obj_type not in self.created_objects:
                        self.created_objects[obj_type] = []
                    
                    self.created_objects[obj_type].append({
                        'name': obj_name,
                        'id': obj_id,
                        'created_at': datetime.now().isoformat()
                    })
    
    def _format_response(self, response: Dict) -> str:
        """Format API response for display"""
        if response.get('status') == 'error':
            error = response.get('error', 'Unknown error')
            return f"❌ Error: {error}"
        
        result = response.get('result', '')
        if isinstance(result, dict):
            return json.dumps(result, indent=2)
        return str(result)
    
    def _format_history(self) -> str:
        """Format command history"""
        if not self.history:
            return "No commands in history yet."
        
        lines = ["📜 Command History:", "─" * 50]
        for i, entry in enumerate(self.history[-20:], 1):  # Last 20
            time_str = entry['time'].split('T')[1][:8]
            lines.append(f"{i:3}. [{time_str}] {entry['command']}")
        return "\n".join(lines)
    
    def _format_last_response(self) -> str:
        """Format last response with full details"""
        if not self.last_response:
            return "No previous response."
        
        lines = ["📋 Last Response Details:", "─" * 50]
        lines.append(json.dumps(self.last_response, indent=2, default=str))
        return "\n".join(lines)
    
    def _format_session_info(self) -> str:
        """Format session information"""
        elapsed = datetime.now() - self.start_time
        lines = [
            "📊 Session Information:",
            "─" * 50,
            f"Session ID: {self.session_id}",
            f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Elapsed: {str(elapsed).split('.')[0]}",
            f"Commands executed: {len(self.history)}",
            f"Objects tracked: {sum(len(v) for v in self.created_objects.values())}"
        ]
        return "\n".join(lines)
    
    def _format_created_objects(self) -> str:
        """Format list of created/tracked objects"""
        if not self.created_objects:
            return "No objects created in this session yet."
        
        lines = ["📦 Created Objects This Session:", "─" * 50]
        for obj_type, objects in self.created_objects.items():
            lines.append(f"\n{obj_type.upper()}S ({len(objects)}):")
            for obj in objects:
                id_str = f" (ID: {obj['id'][:8]}...)" if obj.get('id') else ""
                lines.append(f"  • {obj['name']}{id_str}")
        return "\n".join(lines)
    
    def run_interactive_loop(self):
        """Main interactive testing loop"""
        print("\n" + "=" * 78)
        print("     🔐 ISMS INTERACTIVE TESTING CONSOLE - QA Expert Tester Mode 🔐")
        print("=" * 78)
        print("\nType 'help' for available commands, 'exit' to quit.\n")
        
        # Create session
        if not self.create_session():
            print("\n⚠️  Running in offline mode - some features may not work.\n")
            print("Please ensure:\n  1. API server is running on localhost:8000")
            print("  2. ISMS backend is running on localhost:8070")
            print("  3. Keycloak is running on localhost:8080\n")
            # Continue anyway for local commands
        
        print("─" * 78)
        
        while True:
            try:
                # Get user input
                user_input = input("\n🧪 ISMS> ").strip()
                
                if not user_input:
                    continue
                
                # Execute command
                result = self.execute_command(user_input)
                
                if result == "EXIT":
                    self.log("Exiting ISMS Tester. Goodbye!", "INFO")
                    break
                
                if result:
                    print(f"\n{result}")
                    
            except KeyboardInterrupt:
                print("\n")
                self.log("Interrupted. Type 'exit' to quit.", "WARN")
            except EOFError:
                break
        
        # Show session summary
        self._show_exit_summary()
    
    def _show_exit_summary(self):
        """Show summary when exiting"""
        print("\n" + "=" * 78)
        print("SESSION SUMMARY")
        print("=" * 78)
        print(self._format_session_info())
        if self.created_objects:
            print("\n" + self._format_created_objects())
        print("\n" + "=" * 78)


# ============================================================================
# CRUD + SUBTYPES TESTING
# ============================================================================

class CRUDSubtypeTester:
    """Test CRUD operations with subtypes"""
    
    def __init__(self):
        self.session_id = None
        self.test_results = []
        self.created_objects = {}  # Track created objects for cleanup
        
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
                params={'userId': 'crud_tester'},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    self.session_id = data.get('sessionId')
                    self.log(f"Session created: {self.session_id[:30]}...", "SUCCESS")
                    return True
            self.log(f"Session creation failed: {response.status_code}", "ERROR")
            return False
        except requests.exceptions.ConnectionError:
            self.log("Cannot connect to API server. Is it running on localhost:8000?", "ERROR")
            return False
        except Exception as e:
            self.log(f"Session error: {str(e)}", "ERROR")
            return False
    
    def send_message(self, message: str, timeout: int = 120) -> Dict:
        """Send message to agent API"""
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
    
    def record_result(self, test_name: str, passed: bool, message: str, details: str = ""):
        """Record test result"""
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'details': details,
            'time': datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if passed else "❌ FAIL"
        self.log(f"{status}: {test_name} - {message}", "TEST" if passed else "ERROR")
        if details and not passed:
            self.log(f"    Details: {details[:200]}", "WARN")
    
    def test_create_with_subtype(self, object_type: str, name: str, abbr: str, 
                                  description: str, subtype: Optional[str] = None) -> bool:
        """Test CREATE operation with subtype"""
        test_name = f"CREATE {object_type} with subtype"
        
        if subtype:
            cmd = f'create {object_type} {name} {abbr} "{description}" subType {subtype}'
        else:
            cmd = f'create {object_type} {name} {abbr} "{description}"'
        
        self.log(f"Testing: {cmd}", "TEST")
        response = self.send_message(cmd)
        
        if response.get('status') == 'success':
            result_text = str(response.get('result', ''))
            has_created = 'created' in result_text.lower() or 'success' in result_text.lower()
            
            # Track created object for cleanup
            if has_created and object_type not in self.created_objects:
                self.created_objects[object_type] = []
            if has_created:
                self.created_objects[object_type].append(name)
            
            self.record_result(test_name, has_created, 
                             "Object created successfully" if has_created else "Create failed",
                             result_text[:200])
            return has_created
        else:
            error = response.get('error', 'Unknown error')
            self.record_result(test_name, False, f"Create failed: {error}", str(response))
            return False
    
    def test_list(self, object_type: str) -> bool:
        """Test LIST operation"""
        test_name = f"LIST {object_type}s"
        
        cmd = f'list {object_type}s'
        self.log(f"Testing: {cmd}", "TEST")
        response = self.send_message(cmd)
        
        if response.get('status') == 'success':
            result_text = str(response.get('result', ''))
            has_results = 'found' in result_text.lower() or len(result_text) > 20
            self.record_result(test_name, has_results, 
                             "List operation successful" if has_results else "List returned empty",
                             result_text[:200])
            return has_results
        else:
            error = response.get('error', 'Unknown error')
            self.record_result(test_name, False, f"List failed: {error}", str(response))
            return False
    
    def test_get(self, object_type: str, name: str) -> bool:
        """Test GET operation"""
        test_name = f"GET {object_type} {name}"
        
        cmd = f'get {object_type} {name}'
        self.log(f"Testing: {cmd}", "TEST")
        response = self.send_message(cmd)
        
        if response.get('status') == 'success':
            result_text = str(response.get('result', ''))
            has_details = name.lower() in result_text.lower() or 'id:' in result_text.lower()
            self.record_result(test_name, has_details, 
                             "Get operation successful" if has_details else "Get returned no details",
                             result_text[:200])
            return has_details
        else:
            error = response.get('error', 'Unknown error')
            self.record_result(test_name, False, f"Get failed: {error}", str(response))
            return False
    
    def test_update(self, object_type: str, old_name: str, new_name: str) -> bool:
        """Test UPDATE operation - UPDATE is only for changing object names"""
        test_name = f"UPDATE {object_type} {old_name} to {new_name}"
        
        cmd = f'update {object_type} {old_name} to {new_name}'
        self.log(f"Testing: {cmd}", "TEST")
        response = self.send_message(cmd)
        
        if response.get('status') == 'success':
            result_text = str(response.get('result', ''))
            has_updated = 'updated' in result_text.lower() and new_name.lower() in result_text.lower()
            self.record_result(test_name, has_updated, 
                             "Update operation successful" if has_updated else "Update failed",
                             result_text[:200])
            return has_updated
        else:
            error = response.get('error', 'Unknown error')
            self.record_result(test_name, False, f"Update failed: {error}", str(response))
            return False
    
    def test_delete(self, object_type: str, name: str) -> bool:
        """Test DELETE operation"""
        test_name = f"DELETE {object_type} {name}"
        
        cmd = f'delete {object_type} {name}'
        self.log(f"Testing: {cmd}", "TEST")
        response = self.send_message(cmd)
        
        if response.get('status') == 'success':
            result_text = str(response.get('result', ''))
            has_deleted = 'deleted' in result_text.lower() or 'removed' in result_text.lower()
            self.record_result(test_name, has_deleted, 
                             "Delete operation successful" if has_deleted else "Delete failed",
                             result_text[:200])
            return has_deleted
        else:
            error = response.get('error', 'Unknown error')
            self.record_result(test_name, False, f"Delete failed: {error}", str(response))
            return False
    
    def run_comprehensive_test(self):
        """Run comprehensive CRUD + subtypes test suite"""
        print("\n" + "=" * 80)
        print("     🧪 COMPREHENSIVE CRUD + SUBTYPES TEST SUITE 🧪")
        print("=" * 80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Create session
        if not self.create_session():
            print("\n❌ Cannot connect to API server. Please ensure it's running.")
            return
        
        timestamp = int(time.time())
        
        # Test 1: CREATE operations with subtypes
        print("\n" + "-" * 80)
        print("TEST 1: CREATE Operations with Subtypes")
        print("-" * 80)
        
        # Create asset with subtype
        asset_name = f"TestAsset_{timestamp}"
        self.test_create_with_subtype('asset', asset_name, 'TA', 
                                      'Test IT System Asset', 'AST_IT-System')
        time.sleep(1)
        
        # Create person with subtype
        person_name = f"TestPerson_{timestamp}"
        self.test_create_with_subtype('person', person_name, 'TP', 
                                      'Test Data Protection Officer', 'PER_DataProtectionOfficer')
        time.sleep(1)
        
        # Create scope (no subtype typically)
        scope_name = f"TestScope_{timestamp}"
        self.test_create_with_subtype('scope', scope_name, 'TS', 
                                      'Test Scope for CRUD testing')
        time.sleep(1)
        
        # Test 2: LIST operations
        print("\n" + "-" * 80)
        print("TEST 2: LIST Operations")
        print("-" * 80)
        
        self.test_list('asset')
        time.sleep(1)
        self.test_list('person')
        time.sleep(1)
        self.test_list('scope')
        time.sleep(1)
        
        # Test 3: GET operations
        print("\n" + "-" * 80)
        print("TEST 3: GET Operations")
        print("-" * 80)
        
        self.test_get('asset', asset_name)
        time.sleep(1)
        self.test_get('person', person_name)
        time.sleep(1)
        self.test_get('scope', scope_name)
        time.sleep(1)
        
        # Test 4: UPDATE operations (UPDATE is only for changing object names)
        print("\n" + "-" * 80)
        print("TEST 4: UPDATE Operations (Name Changes Only)")
        print("-" * 80)
        
        # Update asset name
        new_asset_name = f"{asset_name}_Renamed"
        self.test_update('asset', asset_name, new_asset_name)
        time.sleep(1)
        asset_name = new_asset_name  # Update for DELETE test
        
        # Update person name
        new_person_name = f"{person_name}_Renamed"
        self.test_update('person', person_name, new_person_name)
        time.sleep(1)
        person_name = new_person_name  # Update for DELETE test
        
        # Update scope name
        new_scope_name = f"{scope_name}_Renamed"
        self.test_update('scope', scope_name, new_scope_name)
        time.sleep(1)
        scope_name = new_scope_name  # Update for DELETE test
        
        # Test 5: DELETE operations
        print("\n" + "-" * 80)
        print("TEST 5: DELETE Operations")
        print("-" * 80)
        
        self.test_delete('asset', asset_name)
        time.sleep(1)
        self.test_delete('person', person_name)
        time.sleep(1)
        self.test_delete('scope', scope_name)
        time.sleep(1)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for t in self.test_results if t['passed'])
        total = len(self.test_results)
        rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {total - passed}")
        print(f"Pass Rate: {rate:.1f}%")
        
        if total - passed > 0:
            print("\n❌ Failed Tests:")
            for t in self.test_results:
                if not t['passed']:
                    print(f"  • {t['test']}: {t['message']}")
        
        print("\n" + "=" * 80)
        if rate >= 80:
            print("✅ TEST SUITE PASSED")
        elif rate >= 60:
            print("⚠️  TEST SUITE PARTIALLY PASSED")
        else:
            print("❌ TEST SUITE FAILED")
        print("=" * 80)


# ============================================================================
# PROMPT ENGINEERING TEST SUITE
# ============================================================================

class PromptEngineeringTester:
    """Test real-world ISMS operation prompts from promptEngineering.txt"""
    
    # Prompts from promptEngineering.txt (lines 3-20)
    TEST_PROMPTS = [
        {
            'name': 'DPO Assignment Test',
            'prompt': "Create a new person 'John'.assign his role to 'DPO'",
            'expected_keywords': ['john', 'dpo', 'data protection', 'created'],
            'should_not_contain': ['what would you like to name', 'generic', 'i can help with documents']
        },
        {
            'name': 'Set Role for Person Test',
            'prompt': "set role for the Data protection officer for the person Ruby",
            'expected_keywords': ['ruby', 'data protection officer', 'role', 'subtype', 'created', 'dpo'],
            'should_not_contain': ['generic', 'i can help with documents', 'what would you like', 'could not find']
        },
        {
            'name': 'Asset Update Test',
            'prompt': "Update the asset 'Main Firewall'. Change its description to 'Palo Alto Next-Gen FW' and set its confidentiality to 'High'.",
            'expected_keywords': ['main firewall', 'palo alto', 'high', 'confidentiality', 'updated'],
            'should_not_contain': ['i need the asset name', 'what would you like', 'generic']
        },
        {
            'name': 'Create Scope and Link Test',
            'prompt': "Create a new Scope named 'Project Phoenix' and immediately link it with the 'IT-System assets' assets.",
            'expected_keywords': ['project phoenix', 'created', 'linked', 'it-system', 'it system'],
            'should_not_contain': ['what would you like to name', 'create a asset', 'generic']
        },
        {
            'name': 'List Active Assets Test',
            'prompt': "List all assets in our domain that is currently active.",
            'expected_keywords': ['assets', 'active', 'found', 'list'],
            'should_not_contain': ['generic', 'i can help with documents']
        },
        {
            'name': 'Subtypes Query - Scopes',
            'prompt': "show me all subtypes of Scope",
            'expected_keywords': ['subtypes', 'scope', 'scopes', 'controllers', 'processors'],
            'should_not_contain': ['generic', 'i can help with documents', 'no scope found']
        },
        {
            'name': 'Show Me All Assets Test',
            'prompt': "show me all assets in our isms",
            'expected_keywords': ['assets', 'found', 'list', 'table'],
            'should_not_contain': ['generic', 'i can help with documents', 'llm api configuration']
        },
        {
            'name': 'Subtypes Count Query - Assets',
            'prompt': "how many subtypes options for the assets",
            'expected_keywords': ['subtypes', 'assets', 'datatypes', 'it-systems', 'applications'],
            'should_not_contain': ['generic', 'i can help with documents', 'no asset found']
        },
        {
            'name': 'Conversational Assets Query',
            'prompt': "ok so how about assets? do we have any assets",
            'expected_keywords': ['assets', 'found', 'list'],
            'should_not_contain': ['generic', 'i can help with documents', 'isms operations']
        },
        {
            'name': 'Create Incident and Link Test',
            'prompt': "Create a new Incident named 'Phishing Attempt Jan-24'. Then, find the 'Email Server' asset and link it to this incident.",
            'expected_keywords': ['phishing attempt jan-24', 'created', 'email server', 'linked', 'incident'],
            'should_not_contain': ['what would you like to name', 'generic']
        },
        {
            'name': 'Create Controller Test',
            'prompt': "Create a \"Controller\" named 'MFA for VPN' and mark its status as 'Not Implemented'. Add a note saying 'Budget pending approval'.",
            'expected_keywords': ['mfa for vpn', 'controller', 'created', 'not implemented', 'budget'],
            'should_not_contain': ['what would you like to name', 'generic', 'i can help with documents']
        }
    ]
    
    def __init__(self):
        self.session_id = None
        self.test_results = []
        
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
                timeout=5
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
    
    def send_message(self, message: str, timeout: int = 120) -> Dict[str, Any]:
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
    
    def test_prompt(self, test_case: Dict) -> bool:
        """Test a single prompt from promptEngineering.txt"""
        name = test_case['name']
        prompt = test_case['prompt']
        expected_keywords = test_case.get('expected_keywords', [])
        should_not_contain = test_case.get('should_not_contain', [])
        
        self.log(f"Testing: {name}", "TEST")
        self.log(f"  Prompt: {prompt}", "INFO")
        
        response = self.send_message(prompt)
        time.sleep(1)
        
        status = response.get('status')
        result = str(response.get('result', ''))
        result_lower = result.lower()
        error = response.get('error', '')
        
        # Check if it's a service limit error (API quota)
        is_quota_error = 'service limit' in result_lower or 'quota' in result_lower or "i'm having trouble" in result_lower
        
        # Check if response contains expected keywords (at least some)
        has_keywords = any(keyword.lower() in result_lower for keyword in expected_keywords) if expected_keywords else True
        
        # Check if response contains generic/unhelpful phrases
        has_generic = any(phrase.lower() in result_lower for phrase in should_not_contain) if should_not_contain else False
        
        # Check if it's a successful operation
        is_success = status == 'success' and (
            'created' in result_lower or 
            'updated' in result_lower or 
            'found' in result_lower or 
            'linked' in result_lower or 
            'analyzed' in result_lower or
            'compared' in result_lower or
            'listed' in result_lower or
            'success' in result_lower or
            'subtypes' in result_lower or
            'available' in result_lower
        )
        
        passed = is_success and has_keywords and not is_quota_error and not has_generic
        message = f"Operation completed successfully" if passed else f"Failed: {error or 'No result'}"
        if is_quota_error:
            message += " (⚠️ API quota exceeded)"
        if has_generic:
            message += " (⚠️ Generic response detected)"
        
        self.log(f"{'✅ PASS' if passed else '❌ FAIL'}: {message}", "TEST" if passed else "ERROR")
        if result:
            result_preview = str(result)[:300] if len(str(result)) > 300 else str(result)
            self.log(f"   Response: {result_preview}", "INFO")
        
        self.test_results.append({
            'name': name,
            'prompt': prompt,
            'passed': passed,
            'status': status,
            'is_quota_error': is_quota_error,
            'has_generic': has_generic,
            'result_preview': str(result)[:300] if result else None,
            'error': error if not passed else None
        })
        
        return passed
    
    def setup_prerequisites(self):
        """Set up prerequisites for tests (create required objects)"""
        print("\n" + "-" * 80)
        print("Setting up test prerequisites...")
        print("-" * 80)
        
        # Create Main Firewall asset for Asset Update Test
        create_asset_msg = 'create asset "Main Firewall" MF "Main firewall asset for testing"'
        print(f"Creating prerequisite: {create_asset_msg}")
        response = self.send_message(create_asset_msg, timeout=60)
        if response.get('status') == 'success':
            print("✅ Created Main Firewall asset")
        else:
            error = response.get('error', 'Unknown error')
            print(f"⚠️  Could not create Main Firewall: {error[:100]}")
            # Continue anyway - asset might already exist
        
        time.sleep(2)
        
        # Create Ruby person for Set Role Test
        create_ruby_msg = 'create person "Ruby" RB "Ruby person for role assignment test"'
        print(f"Creating prerequisite: {create_ruby_msg}")
        response = self.send_message(create_ruby_msg, timeout=60)
        if response.get('status') == 'success':
            result = response.get('result', '')
            print(f"✅ Created Ruby person: {str(result)[:200]}")
        else:
            error = response.get('error', 'Unknown error')
            print(f"⚠️  Could not create Ruby: {error[:100]}")
            # Continue anyway - person might already exist
        
        time.sleep(3)
        
        # Create Tommy person for Add DPO Test
        create_tommy_msg = 'create person "Tommy" TM "Tommy person for DPO assignment test"'
        print(f"Creating prerequisite: {create_tommy_msg}")
        response = self.send_message(create_tommy_msg, timeout=60)
        if response.get('status') == 'success':
            result = response.get('result', '')
            print(f"✅ Created Tommy person: {str(result)[:200]}")
        else:
            error = response.get('error', 'Unknown error')
            print(f"⚠️  Could not create Tommy: {error[:100]}")
            # Continue anyway - person might already exist
        
        time.sleep(3)
        
        # Verify persons exist by trying to get them directly
        print("Verifying persons exist...")
        get_ruby_response = self.send_message('get person "Ruby"', timeout=60)
        if get_ruby_response.get('status') == 'success':
            print("✅ Verified Ruby person exists and is accessible")
        else:
            print(f"⚠️  Ruby person not accessible: {get_ruby_response.get('error', 'Unknown error')[:100]}")
        
        get_tommy_response = self.send_message('get person "Tommy"', timeout=60)
        if get_tommy_response.get('status') == 'success':
            print("✅ Verified Tommy person exists and is accessible")
        else:
            print(f"⚠️  Tommy person not accessible: {get_tommy_response.get('error', 'Unknown error')[:100]}")
            # Try creating Tommy again if not found
            print("Attempting to create Tommy again...")
            create_tommy_retry = self.send_message('create person "Tommy" TM "Tommy person for DPO assignment test"', timeout=60)
            if create_tommy_retry.get('status') == 'success':
                print("✅ Created Tommy person on retry")
            time.sleep(2)
        
        time.sleep(2)  # Additional delay to ensure objects are fully available
    
    def run_all_tests(self):
        """Run all prompt engineering tests from promptEngineering.txt"""
        print("\n" + "=" * 80)
        print("🧪 PROMPT ENGINEERING TEST SUITE")
        print("=" * 80)
        print("Testing prompts from: dev/docs/promptEngineering.txt (lines 3-20)")
        print("=" * 80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        if not self.create_session():
            print("❌ Failed to create session. Exiting.")
            return
        
        # Set up prerequisites (create required objects)
        self.setup_prerequisites()
        
        # Run all test prompts
        print("\n" + "-" * 80)
        print("Testing All Prompts")
        print("-" * 80)
        
        for i, test_case in enumerate(self.TEST_PROMPTS, 1):
            print(f"\n[{i}/{len(self.TEST_PROMPTS)}] ", end="")
            self.test_prompt(test_case)
            time.sleep(1)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['passed'])
        quota_errors = sum(1 for r in self.test_results if r.get('is_quota_error', False))
        generic_responses = sum(1 for r in self.test_results if r.get('has_generic', False))
        failed = total - passed - quota_errors
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  API Quota Errors: {quota_errors}")
        print(f"⚠️  Generic Responses: {generic_responses}")
        print(f"Pass Rate: {pass_rate:.1f}%")
        
        if failed > 0 or generic_responses > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['passed'] or result.get('has_generic', False):
                    print(f"  • {result['name']}")
                    print(f"    Prompt: {result['prompt']}")
                    if result.get('has_generic'):
                        print(f"    ⚠️  Generic response detected!")
                    if result.get('error'):
                        print(f"    Error: {result['error'][:100]}")
                    if result.get('result_preview'):
                        print(f"    Response: {result['result_preview'][:150]}...")
        
        if quota_errors > 0:
            print(f"\n⚠️  Tests Blocked by API Quota ({quota_errors}):")
            for result in self.test_results:
                if result.get('is_quota_error'):
                    print(f"  • {result['name']}")
        
        print("\n" + "=" * 80)
        if pass_rate == 100 and generic_responses == 0:
            print("✅ ALL TESTS PASSED - NO GENERIC RESPONSES")
        elif quota_errors == total:
            print("⚠️  ALL TESTS BLOCKED BY API QUOTA")
        elif pass_rate >= 80 and generic_responses == 0:
            print("✅ TEST SUITE PASSED (80%+ success rate, no generic responses)")
        elif pass_rate >= 60:
            print("⚠️  TEST SUITE PARTIALLY PASSED")
        else:
            print("❌ TEST SUITE FAILED")
        print("=" * 80)


# ============================================================================
# QUICK TEST RUNNER (Legacy support)
# ============================================================================

class QuickTest:
    """Quick test runner - run predefined test scenarios"""
    
    def __init__(self, tester: ISMSTester):
        self.tester = tester
        self.test_results: List[Dict] = []
    
    def _record_result(self, test_name: str, passed: bool, message: str, details: str = ""):
        """Record test result"""
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'details': details,
            'time': datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name} - {message}")
        if details and not passed:
            print(f"    Details: {details[:200]}")
    
    def run_crud_sequence(self, obj_type: str):
        """Run a complete CRUD sequence for an object type"""
        print(f"\n🧪 Running CRUD sequence for {obj_type}...\n")
        
        timestamp = int(time.time())
        name = f"Test{obj_type.capitalize()}_{timestamp}"
        abbr = f"T{obj_type[:3].upper()}"
        
        # Create
        print(f"1. CREATE {obj_type}...")
        result = self.tester.execute_command(f'create {obj_type} {name} {abbr} "Test object for CRUD sequence"')
        print(result)
        time.sleep(1)
        
        # List
        print(f"\n2. LIST {obj_type}s...")
        result = self.tester.execute_command(f"list {obj_type}")
        print(result)
        time.sleep(1)
        
        # Get
        print(f"\n3. GET {obj_type}...")
        result = self.tester.execute_command(f"get {obj_type} {name}")
        print(result)
        time.sleep(1)
        
        # Update
        print(f"\n4. UPDATE {obj_type}...")
        result = self.tester.execute_command(f'update {obj_type} {name} description "Updated by CRUD test"')
        print(result)
        time.sleep(1)
        
        # Delete
        print(f"\n5. DELETE {obj_type}...")
        result = self.tester.execute_command(f"delete {obj_type} {name}")
        print(result)
        
        print(f"\n✅ CRUD sequence for {obj_type} complete.\n")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    import argparse
    parser = argparse.ArgumentParser(description='Comprehensive ISMS Testing Console')
    parser.add_argument('--crud', action='store_true', 
                       help='Run CRUD + subtypes test suite')
    parser.add_argument('--prompts', action='store_true',
                       help='Run prompt engineering tests from promptEngineering.txt')
    parser.add_argument('--all', action='store_true',
                       help='Run all automated tests (CRUD + prompts)')
    parser.add_argument('--quick', '-q', action='store_true', 
                       help='Run quick CRUD test sequence')
    parser.add_argument('--type', '-t', type=str, default='scope',
                       help='Object type for quick test (default: scope)')
    args = parser.parse_args()
    
    if args.crud or args.prompts or args.all:
        # Automated test mode
        if args.all:
            # Run both test suites
            print("\n" + "=" * 80)
            print("🧪 RUNNING ALL AUTOMATED TESTS")
            print("=" * 80)
            
            # CRUD tests
            crud_tester = CRUDSubtypeTester()
            crud_tester.run_comprehensive_test()
            time.sleep(2)
            
            # Prompt engineering tests
            prompt_tester = PromptEngineeringTester()
            prompt_tester.run_all_tests()
        elif args.crud:
            crud_tester = CRUDSubtypeTester()
            crud_tester.run_comprehensive_test()
        elif args.prompts:
            prompt_tester = PromptEngineeringTester()
            prompt_tester.run_all_tests()
    elif args.quick:
        # Quick CRUD test mode
        tester = ISMSTester()
        if tester.create_session():
            quick = QuickTest(tester)
            quick.run_crud_sequence(args.type)
    else:
        # Interactive mode (default)
        tester = ISMSTester()
        tester.run_interactive_loop()


if __name__ == "__main__":
    main()
