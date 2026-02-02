#!/usr/bin/env python3
"""
SparksBM ISMS Management Script
Comprehensive script for managing SparksBM ISMS:
- Setup domains (ISO, DSGVO, NIS-2, etc.) from templates
- Create units, domains, objects
- Check and list existing domains and units
- Manage SparksBM objects

Usage:
    Interactive mode:
        python sparksbmMgmt.py
        (Shows menu, select option 0-16)
    
    Command-line mode:
        python sparksbmMgmt.py <command>
        python sparksbmMgmt.py <menu-number>
    
    Examples:
        python sparksbmMgmt.py 1          # Setup domains (menu option 1)
        python sparksbmMgmt.py list-domains
        python sparksbmMgmt.py create-unit 'My Unit' 'Description' 1
"""

import requests
import json
import sys
import os
from typing import Dict, Optional, List

# Configuration - use env in deployed environments (e.g. Render), else localhost
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080").rstrip("/")
API_URL = os.getenv("VERINICE_API_URL", os.getenv("API_URL", "http://localhost:8070")).rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "sparksbm")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "sparksbm")
USERNAME = os.getenv("SPARKSBM_USERNAME", "admin@sparksbm.com")
PASSWORD = os.getenv("SPARKSBM_PASSWORD", "admin123")

# Endpoints
KEYCLOAK_TOKEN_URL = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
DOMAIN_TEMPLATES_URL = f"{API_URL}/domain-templates"
CREATE_DOMAINS_URL = f"{API_URL}/domain-templates/{{template_id}}/createdomains"
DOMAINS_URL = f"{API_URL}/domains"
UNITS_URL = f"{API_URL}/units"


class SparksBMKeycloakAdmin:
    """Keycloak Admin API operations"""
    
    def __init__(self):
        self.adminToken = None
        self.getAdminToken()
    
    def getAdminToken(self) -> bool:
        """Get admin token for Keycloak Admin API"""
        tokenUrl = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
        token_data = {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "admin",
            "password": "admin123"
        }
        try:
            response = requests.post(tokenUrl, data=token_data, timeout=10)
            response.raise_for_status()
            self.adminToken = response.json().get("access_token")
            return self.adminToken is not None
        except:
            return False
    
    def getClientScope(self, scope_name: str = "veo-license"):
        """Get client scope by name"""
        if not self.adminToken:
            return None
        
        url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/client-scopes"
        headers = {"Authorization": f"Bearer {self.adminToken}"}
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            scopes = response.json()
            for scope in scopes:
                if scope.get("name") == scope_name:
                    return scope
        return None
    
    def addTotalUnitsMapper(self, scope_id: str):
        """Add total_units protocol mapper to client scope"""
        if not self.adminToken:
            return False
        
        url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/client-scopes/{scope_id}/protocol-mappers/models"
        headers = {
            "Authorization": f"Bearer {self.adminToken}",
            "Content-Type": "application/json"
        }
        
        mapper = {
            "name": "total units",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-hardcoded-claim-mapper",
            "consentRequired": False,
            "config": {
                "claim.name": "total_units",
                "claim.value": "10000",
                "jsonType.label": "String",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
                "introspection.token.claim": "true"
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=mapper, timeout=10)
            return response.status_code in [200, 201]
        except:
            return False
    
    def addMapperToClient(self, client_uuid: str):
        """Add protocol mapper directly to client"""
        url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients/{client_uuid}/protocol-mappers/models"
        headers = {
            "Authorization": f"Bearer {self.adminToken}",
            "Content-Type": "application/json"
        }
        
        mapper = {
            "name": "total units",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-hardcoded-claim-mapper",
            "consentRequired": False,
            "config": {
                "claim.name": "total_units",
                "claim.value": "10000",
                "jsonType.label": "String",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
                "introspection.token.claim": "true"
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=mapper, timeout=10)
            return response.status_code in [200, 201]
        except:
            return False
    
    def fixTotalUnitsClaim(self):
        """Fix missing total_units claim by adding protocol mapper"""
        print("\n🔧 Fixing total_units claim...")
        
        # Try to get client scope first
        scope = self.getClientScope("veo-license")
        if scope:
            scope_id = scope.get("id")
            url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/client-scopes/{scope_id}/protocol-mappers/models"
            headers = {"Authorization": f"Bearer {self.adminToken}"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                mappers = response.json()
                for mapper in mappers:
                    if mapper.get("name") == "total units":
                        print("✅ 'total units' mapper already exists in veo-license scope")
                        return True
            
            if self.addTotalUnitsMapper(scope_id):
                print("✅ Added 'total units' mapper to veo-license scope")
                return True
        
        # Fallback: Add directly to client
        print("   Adding mapper directly to client...")
        url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients"
        headers = {"Authorization": f"Bearer {self.adminToken}"}
        params = {"clientId": CLIENT_ID}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            clients = response.json()
            if clients:
                client_uuid = clients[0].get("id")
                
                # Check if mapper exists
                url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients/{client_uuid}/protocol-mappers/models"
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    mappers = response.json()
                    for mapper in mappers:
                        if mapper.get("name") == "total units":
                            print("✅ 'total units' mapper already exists in client")
                            return True
                
                # Add mapper
                if self.addMapperToClient(client_uuid):
                    print("✅ Added 'total units' protocol mapper to client")
                    print("   Users need to re-authenticate to get new token")
                    return True
        
        print("❌ Failed to add protocol mapper")
        return False
    
    def fixClientCORS(self, client_id: str):
        """Fix CORS configuration for a client"""
        if not self.adminToken:
            return False
        
        url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients"
        headers = {"Authorization": f"Bearer {self.adminToken}"}
        params = {"clientId": client_id}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        clients = response.json()
        if not clients:
            return False
        
        client = clients[0]
        client_uuid = client.get("id")
        
        client["webOrigins"] = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "+"
        ]
        
        url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients/{client_uuid}"
        response = requests.put(url, headers=headers, json=client, timeout=10)
        return response.status_code in [200, 204]

    def fixAccountClientCORS(self):
        """Fix CORS configuration for the account client (used by Keycloak account management)"""
        if not self.adminToken:
            return False
        
        url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients"
        headers = {"Authorization": f"Bearer {self.adminToken}"}
        params = {"clientId": "account"}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            return False
        
        clients = response.json()
        if not clients:
            return False
        
        client = clients[0]
        client_uuid = client.get("id")
        
        web_origins = client.get("webOrigins", [])
        if "http://localhost:3001" not in web_origins:
            web_origins.append("http://localhost:3001")
        if "http://localhost:3000" not in web_origins:
            web_origins.append("http://localhost:3000")
        if "+" not in web_origins:
            web_origins.append("+")
        
        client["webOrigins"] = web_origins
        
        redirect_uris = client.get("redirectUris", [])
        if "http://localhost:3001/*" not in redirect_uris:
            redirect_uris.append("http://localhost:3001/*")
        client["redirectUris"] = redirect_uris
        
        url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients/{client_uuid}"
        response = requests.put(url, headers=headers, json=client, timeout=10)
        return response.status_code in [200, 204]


class SparksBMClient:
    """Client for interacting with SparksBM ISMS API using Keycloak authentication"""
    
    def __init__(self, keycloak_url: str = None, realm: str = None, 
                 client_id: str = None, username: str = None, password: str = None,
                 api_url: str = None):
        """Initialize SparksBM client"""
        self.keycloakUrl = keycloak_url or KEYCLOAK_URL
        self.realm = realm or REALM
        self.clientId = client_id or CLIENT_ID
        self.username = username or USERNAME
        self.password = password or PASSWORD
        self.apiUrl = api_url or API_URL
        self.accessToken = None
        self.session = requests.Session()
        
        # Get access token
        self.getAccessToken()
    
    def getAccessToken(self) -> bool:
        """Get access token from Keycloak"""
        print("🔐 Authenticating with Keycloak...")
        
        tokenUrl = f"{self.keycloakUrl}/realms/{self.realm}/protocol/openid-connect/token"
        
        token_data = {
            "grant_type": "password",
            "client_id": self.clientId,
            "username": self.username,
            "password": self.password
        }
        
        try:
            response = requests.post(tokenUrl, data=token_data, timeout=10)
            response.raise_for_status()
            
            token_response = response.json()
            self.accessToken = token_response.get("access_token")
            
            if not self.accessToken:
                print("❌ Failed to get access token")
                return False
            
            # Set authorization header for all requests
            self.session.headers.update({
                "Authorization": f"Bearer {self.accessToken}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            })
            
            print("✅ Authentication successful!")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Authentication failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:200]}")
            return False
    
    def makeRequest(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make authenticated request"""
        return self.session.request(method, url, **kwargs)
    
    def testConnection(self) -> bool:
        """Test connection to SparksBM API"""
        if not self.accessToken:
            print("❌ No access token available")
            return False
        
        try:
            # Test with domains endpoint
            response = self.makeRequest('GET', DOMAINS_URL, timeout=5)
            if response.status_code == 200:
                print(f"✅ Connected to SparksBM API at: {self.apiUrl}")
                return True
            else:
                print(f"⚠️  API returned status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False


class SparksBMDomainManager:
    """Manages domains and domain templates for SparksBM"""
    
    def __init__(self, client: SparksBMClient):
        """Initialize domain manager"""
        self.client = client
    
    def getFullDomainTemplate(self, template_id: str) -> Optional[Dict]:
        """Get full domain template (not just metadata)"""
        try:
            url = f"{API_URL}/content-creation/domain-templates/{template_id}"
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 403:
                    print("⚠️  Requires 'veo-content-creator' role to access full templates")
                elif e.response.status_code == 404:
                    print(f"⚠️  Template {template_id} not found")
            return None
    
    def checkTemplateCompleteness(self, template_id: str) -> Dict:
        """Check if a domain template has complete element type definitions"""
        result = {
            "template_id": template_id,
            "has_subtypes": False,
            "subtypes_by_type": {},
            "is_complete": False
        }
        
        full_template = self.getFullDomainTemplate(template_id)
        if not full_template:
            return result
        
        element_defs = full_template.get('elementTypeDefinitions', {})
        has_any_subtypes = False
        
        for obj_type, obj_def in element_defs.items():
            subTypes = obj_def.get('subTypes', {})
            if subTypes:
                has_any_subtypes = True
                result["subtypes_by_type"][obj_type] = list(subTypes.keys())
        
        result["has_subtypes"] = has_any_subtypes
        result["is_complete"] = has_any_subtypes
        result["template_name"] = full_template.get('name', 'Unknown')
        
        return result
    
    def updateDomainTemplateFromComplete(self, template_id: str, complete_template_data: Dict) -> bool:
        """Update an existing domain template with complete element type definitions"""
        try:
            # Get current template
            current_template = self.getFullDomainTemplate(template_id)
            if not current_template:
                print(f"❌ Template {template_id} not found or not accessible")
                return False
            
            # Merge element type definitions from complete template
            if 'elementTypeDefinitions' in complete_template_data:
                current_template['elementTypeDefinitions'] = complete_template_data['elementTypeDefinitions']
                print(f"   Updating element type definitions...")
            
            # Update template via PUT (if supported) or delete and recreate
            # Note: API might only support POST for creation, so we'll try POST with same ID
            url = f"{API_URL}/content-creation/domain-templates"
            
            # Use the same ID to update
            complete_template_data['id'] = template_id
            complete_template_data['name'] = current_template.get('name', complete_template_data.get('name'))
            complete_template_data['authority'] = current_template.get('authority', complete_template_data.get('authority'))
            complete_template_data['templateVersion'] = current_template.get('templateVersion', complete_template_data.get('templateVersion'))
            
            response = self.client.makeRequest('POST', url, json=complete_template_data)
            
            if response.status_code == 409:
                print(f"   ⚠️  Template already exists. Trying to update domains from updated template...")
                # Template exists, try to update existing domains
                return self.updateDomainsFromTemplate(template_id)
            elif response.status_code in [200, 201]:
                print(f"✅ Template updated successfully")
                return True
            else:
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to update template: {e}")
            return False
    
    def updateDomainsFromTemplate(self, template_id: str) -> bool:
        """Update existing domains to use the latest template version"""
        print(f"   Updating domains from template {template_id}...")
        # This would require domain update functionality
        # For now, just return True as domains are created from templates
        return True
    
    def importDomainTemplate(self, template_file_path: str) -> bool:
        """Import a complete domain template from JSON file"""
        try:
            with open(template_file_path, 'r') as f:
                template_data = json.load(f)
            
            url = f"{API_URL}/content-creation/domain-templates"
            response = self.client.makeRequest('POST', url, json=template_data)
            response.raise_for_status()
            
            if response.status_code in [200, 201]:
                result = response.json()
                template_id = result.get('resourceId')
                print(f"✅ Successfully imported domain template")
                if template_id:
                    print(f"   Template ID: {template_id}")
                return True
            return False
        except FileNotFoundError:
            print(f"❌ Template file not found: {template_file_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in template file: {e}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to import template: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return False
    
    def checkAllTemplatesCompleteness(self) -> List[Dict]:
        """Check completeness of all available domain templates"""
        print("\n🔍 Checking domain template completeness...")
        
        templates = self.getDomainTemplates()
        results = []
        
        for template in templates:
            template_id = template.get('id')
            print(f"\n   Checking: {template.get('name')} ({template_id})")
            result = self.checkTemplateCompleteness(template_id)
            results.append(result)
            
            if result["is_complete"]:
                print(f"   ✅ Has subTypes defined")
                for obj_type, subtypes in result["subtypes_by_type"].items():
                    print(f"      {obj_type}: {', '.join(subtypes[:3])}{'...' if len(subtypes) > 3 else ''}")
            else:
                print(f"   ❌ No subTypes defined (incomplete)")
        
        return results
    
    def getDomainTemplates(self) -> List[Dict]:
        """Fetch available domain templates"""
        print("\n📋 Fetching domain templates...")
        
        try:
            response = self.client.makeRequest('GET', DOMAIN_TEMPLATES_URL)
            response.raise_for_status()
            
            templates = response.json()
            print(f"✅ Found {len(templates)} domain template(s)")
            
            for template in templates:
                print(f"   - {template.get('name', 'Unknown')} (ID: {template.get('id')})")
                if template.get('description'):
                    print(f"     Description: {template.get('description')}")
            
            return templates
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch domain templates: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return []
    
    def createDomainFromTemplate(self, template_id: str, restrict_to_existing: bool = False) -> bool:
        """Create a domain from a domain template"""
        url = CREATE_DOMAINS_URL.format(template_id=template_id)
        params = {
            "restrictToClientsWithExistingDomain": str(restrict_to_existing).lower()
        }
        
        try:
            response = self.client.makeRequest('POST', url, params=params)
            response.raise_for_status()
            
            if response.status_code == 204:
                return True
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Failed to create domain: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"      Status: {e.response.status_code}")
                print(f"      Response: {e.response.text[:500]}")
            return False
    
    def setupDomains(self, restrict_to_existing: bool = False) -> bool:
        """Setup domains from all available templates"""
        print("=" * 70)
        print("SparksBM Domain Setup")
        print("=" * 70)
        
        # Get domain templates
        templates = self.getDomainTemplates()
        
        if not templates:
            print("\n⚠️  No domain templates found!")
            print("   This might mean:")
            print("   1. Domain templates need to be imported into the backend first")
            print("   2. Backend is not running or not accessible")
            print("   3. Check backend logs for domain template import errors")
            return False
        
        # Create domains from templates
        print("\n🏗️  Creating domains from templates...")
        created_count = 0
        
        for template in templates:
            template_id = template.get('id')
            template_name = template.get('name', 'Unknown')
            
            print(f"\n   Creating domain from template: {template_name}")
            
            if self.createDomainFromTemplate(template_id, restrict_to_existing):
                print(f"   ✅ Successfully created domain from '{template_name}'")
                created_count += 1
            else:
                print(f"   ⚠️  Failed to create domain from '{template_name}'")
                print(f"      (This might be normal if domain already exists)")
        
        # List all domains
        print("\n" + "=" * 70)
        domains = self.listDomains()
        
        if domains:
            print(f"\n✅ Setup complete! {created_count} domain(s) processed.")
            print(f"   Total domains available: {len(domains)}")
            print("\n🎉 You can now create units and select domains!")
        else:
            print("\n⚠️  No domains found after setup.")
            print("   You may need to check:")
            print("   1. Domain templates are properly configured")
            print("   2. Client has proper permissions")
            print("   3. Backend logs for errors")
        
        return True
    
    def listDomains(self) -> List[Dict]:
        """List all available domains"""
        print("\n📊 Fetching created domains...")
        
        try:
            response = self.client.makeRequest('GET', DOMAINS_URL)
            response.raise_for_status()
            
            domains = response.json()
            print(f"✅ Found {len(domains)} domain(s)")
            
            for domain in domains:
                print(f"   - {domain.get('name', 'Unknown')} (ID: {domain.get('id')})")
                if domain.get('abbreviation'):
                    print(f"     Abbreviation: {domain.get('abbreviation')}")
                if domain.get('description'):
                    desc = domain.get('description', '')[:100]
                    print(f"     Description: {desc}...")
            
            return domains
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch domains: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return []
    
    def listProfiles(self, domain_id: str) -> List[Dict]:
        """List all profiles in a domain"""
        url = f"{API_URL}/domains/{domain_id}/profiles"
        
        try:
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            profiles = response.json()
            if isinstance(profiles, dict) and 'items' in profiles:
                profiles = profiles['items']
            
            print(f"\n📋 Profiles in domain:")
            for profile in profiles:
                print(f"   - {profile.get('name', 'Unknown')} (ID: {profile.get('id')})")
                if profile.get('description'):
                    desc = profile.get('description', '')[:100]
                    print(f"     Description: {desc}...")
            
            return profiles
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch profiles: {e}")
            return []
    
    def importProfile(self, domain_id: str, profile_file_path: str = None, profile_data: Dict = None) -> bool:
        """Import a profile into a domain"""
        try:
            if profile_data:
                data = profile_data
            elif profile_file_path:
                with open(profile_file_path, 'r') as f:
                    data = json.load(f)
            else:
                print("❌ Either profile_file_path or profile_data must be provided")
                return False
            
            url = f"{API_URL}/content-creation/domains/{domain_id}/profiles"
            response = self.client.makeRequest('POST', url, json=data)
            response.raise_for_status()
            
            if response.status_code in [200, 201]:
                result = response.json()
                profile_id = result.get('resourceId') or result.get('id')
                print(f"✅ Successfully imported profile")
                if profile_id:
                    print(f"   Profile ID: {profile_id}")
                return True
            return False
        except FileNotFoundError:
            print(f"❌ Profile file not found: {profile_file_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in profile file: {e}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to import profile: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return False
    
    def exportProfile(self, domain_id: str, profile_id: str, output_file: str = None) -> Optional[Dict]:
        """Export a profile from a domain"""
        url = f"{API_URL}/domains/{domain_id}/profiles/{profile_id}/export"
        
        try:
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            profile_data = response.json()
            
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(profile_data, f, indent=2)
                print(f"✅ Exported profile to: {output_file}")
            
            return profile_data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to export profile: {e}")
            return None
    
    def copyProfileBetweenDomains(self, source_domain_id: str, profile_id: str, target_domain_id: str) -> bool:
        """Copy a profile from one domain to another"""
        print(f"\n📋 Copying profile from domain {source_domain_id} to {target_domain_id}...")
        
        # Export from source
        profile_data = self.exportProfile(source_domain_id, profile_id)
        if not profile_data:
            return False
        
        # Import to target
        return self.importProfile(target_domain_id, profile_data=profile_data)
    
    def deleteDomain(self, domain_id: str) -> bool:
        """Delete a domain"""
        url = f"{API_URL}/content-creation/domains/{domain_id}"
        
        try:
            response = self.client.makeRequest('DELETE', url)
            
            if response.status_code == 204:
                print(f"✅ Successfully deleted domain: {domain_id}")
                return True
            elif response.status_code == 409:
                print(f"❌ Cannot delete domain: Domain is in use")
                print(f"   Response: {response.text[:500]}")
                return False
            else:
                print(f"⚠️  Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to delete domain: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return False


class SparksBMUnitManager:
    """Manages units for SparksBM"""
    
    def __init__(self, client: SparksBMClient):
        """Initialize unit manager"""
        self.client = client
    
    def checkUnitLimit(self, silent: bool = False) -> tuple[int, int]:
        """Check current unit count vs limit"""
        try:
            # Get current units (silently)
            try:
                response = self.client.makeRequest('GET', UNITS_URL)
                response.raise_for_status()
                units = response.json()
                if isinstance(units, dict) and 'items' in units:
                    units = units['items']
                current_count = len(units)
            except:
                current_count = 0
            
            # Try to get max_units from token (if available)
            # Otherwise default to 2
            max_units = 2
            if hasattr(self.client, 'accessToken') and self.client.accessToken:
                try:
                    import base64
                    import json
                    # Decode JWT token to get max_units claim
                    token_parts = self.client.accessToken.split('.')
                    if len(token_parts) >= 2:
                        # Decode payload
                        payload = token_parts[1]
                        # Add padding if needed
                        payload += '=' * (4 - len(payload) % 4)
                        decoded = base64.urlsafe_b64decode(payload)
                        token_data = json.loads(decoded)
                        max_units = token_data.get('max_units', 2)
                except:
                    pass
            
            if not silent:
                print(f"📊 Current units: {current_count}, Maximum: {max_units}")
            
            return current_count, max_units
        except:
            return 0, 2
    
    def diagnoseUnitCreationIssue(self) -> Dict:
        """Diagnose why unit creation might be failing"""
        diagnosis = {
            "current_units": 0,
            "max_units_in_token": None,
            "total_units_in_token": None,
            "issue": None
        }
        
        try:
            # Get current units
            response = self.client.makeRequest('GET', UNITS_URL)
            if response.status_code == 200:
                units = response.json()
                if isinstance(units, dict) and 'items' in units:
                    units = units['items']
                diagnosis["current_units"] = len(units)
        except:
            pass
        
        # Decode token
        if self.client.accessToken:
            try:
                import base64
                token_parts = self.client.accessToken.split('.')
                if len(token_parts) >= 2:
                    payload = token_parts[1]
                    payload += '=' * (4 - len(payload) % 4)
                    decoded = base64.urlsafe_b64decode(payload)
                    token_data = json.loads(decoded)
                    max_units = token_data.get('max_units')
                    total_units = token_data.get('total_units')
                    diagnosis["max_units_in_token"] = int(max_units) if max_units else None
                    diagnosis["total_units_in_token"] = int(total_units) if total_units else None
            except:
                pass
        
        # Determine issue
        if diagnosis["total_units_in_token"] is None:
            diagnosis["issue"] = "total_units_missing"
        elif diagnosis["total_units_in_token"] == 0:
            diagnosis["issue"] = "total_units_zero"
        elif diagnosis["current_units"] >= (diagnosis["total_units_in_token"] or 0):
            diagnosis["issue"] = "limit_reached"
        else:
            diagnosis["issue"] = "unknown"
        
        return diagnosis
    
    def createUnit(self, name: str, description: str = "", domain_ids: List[str] = None) -> Optional[Dict]:
        """Create a new unit with specified domains"""
        print(f"\n🏗️  Creating unit: {name}")
        
        if not name:
            print("❌ Unit name is required")
            return None
        
        # Diagnose issue first
        diagnosis = self.diagnoseUnitCreationIssue()
        print(f"\n📊 Diagnosis:")
        print(f"   Current units: {diagnosis['current_units']}")
        print(f"   max_units in token: {diagnosis['max_units_in_token']}")
        print(f"   total_units in token: {diagnosis['total_units_in_token']}")
        
        if diagnosis["issue"] == "total_units_missing":
            print(f"\n❌ ISSUE: total_units claim is missing from token!")
            print(f"   The backend requires 'total_units' claim in the JWT token.")
            print(f"\n💡 Quick Fix:")
            print(f"   Run: python sparksbmMgmt.py fix-total-units")
            print(f"\n   Or manually:")
            print(f"   1. Keycloak Admin → Realm: {self.client.realm}")
            print(f"   2. Client scopes → veo-license → Mappers")
            print(f"   3. Add: Hardcoded claim 'total units' = 10000")
            return None
        elif diagnosis["issue"] == "total_units_zero":
            print(f"\n❌ ISSUE: total_units is 0 in token!")
            print(f"   This prevents any unit creation.")
            return None
        elif diagnosis["issue"] == "limit_reached":
            print(f"\n❌ ISSUE: Unit limit reached!")
            return None
        
        # If we get here, we can proceed with creation
        
        # Build unit data structure
        unit_data = {
            "name": name,
            "description": description or ""
        }
        
        # Add domains if provided
        if domain_ids:
            unit_data["domains"] = []
            for domain_id in domain_ids:
                unit_data["domains"].append({
                    "id": domain_id,
                    "targetUri": f"/domains/{domain_id}"
                })
        
        try:
            response = self.client.makeRequest('POST', UNITS_URL, json=unit_data)
            response.raise_for_status()
            
            if response.status_code in [200, 201]:
                result = response.json()
                unit_id = result.get('resourceId') or result.get('id')
                print(f"✅ Successfully created unit: {name}")
                if unit_id:
                    print(f"   Unit ID: {unit_id}")
                return result
            else:
                print(f"⚠️  Unexpected status code: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to create unit: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return None
    
    def listUnits(self) -> List[Dict]:
        """List all available units"""
        print("\n📊 Fetching units...")
        
        try:
            response = self.client.makeRequest('GET', UNITS_URL)
            response.raise_for_status()
            
            units = response.json()
            if isinstance(units, dict) and 'items' in units:
                units = units['items']
            
            print(f"✅ Found {len(units)} unit(s)")
            
            for unit in units:
                print(f"   - {unit.get('name', 'Unknown')} (ID: {unit.get('id')})")
                if unit.get('description'):
                    desc = unit.get('description', '')[:100]
                    print(f"     Description: {desc}...")
                # Show associated domains
                if unit.get('domains'):
                    domain_names = [d.get('name', d.get('id', 'Unknown')) for d in unit.get('domains', [])]
                    print(f"     Domains: {', '.join(domain_names)}")
            
            return units
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch units: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return []
    
    def getUnitDomains(self, unit_id: str) -> List[str]:
        """Get list of domain IDs associated with a unit"""
        try:
            response = self.client.makeRequest('GET', f"{UNITS_URL}/{unit_id}")
            response.raise_for_status()
            unit = response.json()
            domains = unit.get('domains', [])
            return [d.get('id') for d in domains if d.get('id')]
        except:
            return []
    
    def checkUnitDomainAssociation(self, unit_id: str, domain_id: str) -> bool:
        """Check if a unit is associated with a domain"""
        unit_domains = self.getUnitDomains(unit_id)
        return domain_id in unit_domains


class SparksBMObjectManager:
    """Manages objects (assets, controls, processes, etc.) for SparksBM"""
    
    OBJECT_TYPES = {
        "scope": "scopes",
        "asset": "assets",
        "control": "controls",
        "process": "processes",
        "person": "persons",
        "scenario": "scenarios",
        "incident": "incidents",
        "document": "documents"
    }
    
    DEFAULT_SUBTYPES = {
        "scope": "SCP_Scope",
        "asset": "AST_Application",
        "control": "CTL_TOM",
        "process": "PRO_DataTransfer",
        "person": "PER_Person",
        "scenario": "SCN_Scenario",
        "incident": "INC_Incident",
        "document": "DOC_Document"
    }
    
    def __init__(self, client: SparksBMClient):
        """Initialize object manager"""
        self.client = client
    
    def getValidSubTypes(self, domain_id: str, object_type: str) -> List[str]:
        """Get valid subTypes for an object type in a domain"""
        try:
            response = self.client.makeRequest('GET', f"{API_URL}/domains/{domain_id}")
            response.raise_for_status()
            domain = response.json()
            subTypes = domain.get('elementTypeDefinitions', {}).get(object_type.lower(), {}).get('subTypes', {})
            return list(subTypes.keys())
        except Exception as e:
            print(f"   ⚠️  Error fetching subTypes: {e}")
            return []
    
    def showValidSubTypes(self, domain_id: str, object_type: str = None):
        """Show all valid subTypes for a domain"""
        try:
            response = self.client.makeRequest('GET', f"{API_URL}/domains/{domain_id}")
            response.raise_for_status()
            domain = response.json()
            element_defs = domain.get('elementTypeDefinitions', {})
            
            print(f"\n📋 Valid subTypes for domain: {domain.get('name', domain_id)}")
            
            if object_type:
                # Show subTypes for specific object type
                obj_def = element_defs.get(object_type.lower(), {})
                subTypes = obj_def.get('subTypes', {})
                if subTypes:
                    print(f"\n{object_type.upper()} subTypes:")
                    for subType, details in subTypes.items():
                        statuses = details.get('statuses', [])
                        print(f"   - {subType}")
                        if statuses:
                            print(f"     Statuses: {', '.join(statuses)}")
                else:
                    print(f"\n❌ No subTypes defined for {object_type}")
            else:
                # Show all subTypes for all object types
                for obj_type, obj_def in element_defs.items():
                    subTypes = obj_def.get('subTypes', {})
                    if subTypes:
                        print(f"\n{obj_type.upper()}:")
                        for subType, details in subTypes.items():
                            statuses = details.get('statuses', [])
                            print(f"   - {subType}")
                            if statuses:
                                print(f"     Statuses: {', '.join(statuses[:3])}{'...' if len(statuses) > 3 else ''}")
                
                if not any(def_.get('subTypes', {}) for def_ in element_defs.values()):
                    print("\n❌ No subTypes defined in this domain!")
                    print("\n💡 This means:")
                    print("   1. The domain template may be incomplete")
                    print("   2. The domain was created without element type definitions")
                    print("   3. You need to import a complete domain template")
                    print("\n   To fix this, you may need to:")
                    print("   - Import domain templates with full definitions")
                    print("   - Or manually configure subTypes via domain configuration")
            
        except Exception as e:
            print(f"❌ Failed to fetch domain: {e}")
    
    def createObject(self, object_type: str, name: str, domain_id: str, unit_id: str, 
                     description: str = "", sub_type: str = None, abbreviation: str = None, unit_manager=None) -> Optional[Dict]:
        """Create an object (asset, control, process, etc.) in a domain"""
        plural = self.OBJECT_TYPES.get(object_type.lower())
        if not plural:
            print(f"❌ Unknown object type: {object_type}")
            print(f"   Available types: {', '.join(self.OBJECT_TYPES.keys())}")
            return None
        
        # Check if unit is associated with domain
        if unit_manager:
            if not unit_manager.checkUnitDomainAssociation(unit_id, domain_id):
                print(f"\n❌ Unit is not associated with this domain!")
                print(f"   Unit ID: {unit_id}")
                print(f"   Domain ID: {domain_id}")
                print(f"\n💡 Solution:")
                print(f"   1. The unit must be associated with the domain when creating the unit")
                print(f"   2. Or update the unit to include this domain")
                print(f"   3. Check unit domains: python sparksbmMgmt.py list-units")
                return None
        
        # Get valid subTypes for this domain
        valid_subtypes = self.getValidSubTypes(domain_id, object_type)
        
        if not valid_subtypes:
            print(f"\n❌ Domain has no subTypes defined for {object_type}!")
            print(f"   This domain template may be incomplete.")
            print(f"   You may need to:")
            print(f"   1. Import a complete domain template")
            print(f"   2. Or manually configure subTypes in Keycloak/domain config")
            return None
        
        # Use provided subType or first available
        if not sub_type:
            sub_type = valid_subtypes[0]
            print(f"   Using subType: {sub_type} (first available)")
        elif sub_type not in valid_subtypes:
            print(f"⚠️  Warning: {sub_type} not in valid subTypes, using: {valid_subtypes[0]}")
            sub_type = valid_subtypes[0]
        
        # Get valid statuses for this subType
        try:
            response = self.client.makeRequest('GET', f"{API_URL}/domains/{domain_id}")
            response.raise_for_status()
            domain = response.json()
            statuses = domain.get('elementTypeDefinitions', {}).get(object_type.lower(), {}).get('subTypes', {}).get(sub_type, {}).get('statuses', [])
            status = statuses[0] if statuses else "NEW"
        except:
            status = "NEW"
        
        url = f"{API_URL}/domains/{domain_id}/{plural}"
        
        # Base object data
        object_data = {
            "name": name,
            "owner": {
                "targetUri": f"{API_URL}/units/{unit_id}"
            },
            "subType": sub_type,
            "status": status
        }
        
        # Add abbreviation if provided
        if abbreviation:
            object_data["abbreviation"] = abbreviation
        
        # Add description if provided
        if description:
            object_data["description"] = description
        
        # Scope objects need special handling - they use "members" not "parts"
        # Members is optional and defaults to empty set
        # Don't include "parts" for scopes (that's for other object types)
        
        print(f"\n🏗️  Creating {object_type}: {name}")
        print(f"   Domain: {domain_id}")
        print(f"   Unit: {unit_id}")
        print(f"   SubType: {sub_type}")
        print(f"   Status: {status}")
        
        try:
            response = self.client.makeRequest('POST', url, json=object_data)
            response.raise_for_status()
            
            if response.status_code in [200, 201]:
                result = response.json()
                object_id = result.get('resourceId') or result.get('id')
                print(f"✅ Successfully created {object_type}: {name}")
                if object_id:
                    print(f"   Object ID: {object_id}")
                return result
            else:
                print(f"⚠️  Unexpected status code: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to create {object_type}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return None
    
    def listObjects(self, domain_id: str, object_type: str) -> List[Dict]:
        """List objects of a specific type in a domain"""
        plural = self.OBJECT_TYPES.get(object_type.lower())
        if not plural:
            print(f"❌ Unknown object type: {object_type}")
            return []
        
        url = f"{API_URL}/domains/{domain_id}/{plural}"
        
        try:
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            objects = response.json()
            if isinstance(objects, dict) and 'items' in objects:
                objects = objects['items']
            
            print(f"✅ Found {len(objects)} {object_type}(s) in domain")
            for obj in objects:
                print(f"   - {obj.get('name', 'Unknown')} (ID: {obj.get('id')})")
            
            return objects
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch {object_type}s: {e}")
            return []
    
    def listCatalogItems(self, domain_id: str) -> List[Dict]:
        """List catalog items in a domain"""
        url = f"{API_URL}/domains/{domain_id}/catalog-items"
        
        try:
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            items = response.json()
            if isinstance(items, dict) and 'items' in items:
                items = items['items']
            
            print(f"✅ Found {len(items)} catalog item(s) in domain")
            for item in items:
                print(f"   - {item.get('name', 'Unknown')} (ID: {item.get('id')})")
                if item.get('subType'):
                    print(f"     SubType: {item.get('subType')}")
            
            return items
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch catalog items: {e}")
            return []
    
    def listReports(self, domain_id: str) -> List[Dict]:
        """List available reports for a domain"""
        url = f"{API_URL}/api/reporting/reports"
        
        try:
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            reports = response.json()
            if isinstance(reports, dict):
                reports = reports.get('items', [])
            
            print(f"✅ Found {len(reports)} report(s) available")
            for report in reports:
                name = report.get('name', {})
                if isinstance(name, dict):
                    name = name.get('en', name.get('de', 'Unknown'))
                print(f"   - {name} (ID: {report.get('id')})")
                if report.get('description'):
                    desc = report.get('description', {})
                    if isinstance(desc, dict):
                        desc = desc.get('en', desc.get('de', ''))
                    if desc:
                        print(f"     Description: {desc[:100]}...")
            
            return reports
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch reports: {e}")
            return []
    
    def listRiskDefinitions(self, domain_id: str) -> List[Dict]:
        """List risk definitions in a domain"""
        try:
            response = self.client.makeRequest('GET', f"{API_URL}/domains/{domain_id}")
            response.raise_for_status()
            domain = response.json()
            
            risk_defs = domain.get('riskDefinitions', {})
            
            if risk_defs:
                print(f"✅ Found {len(risk_defs)} risk definition(s) in domain")
                for risk_id, risk_def in risk_defs.items():
                    print(f"   - {risk_id}")
                    if isinstance(risk_def, dict):
                        if risk_def.get('name'):
                            print(f"     Name: {risk_def.get('name')}")
                        if risk_def.get('description'):
                            print(f"     Description: {risk_def.get('description')[:100]}...")
            else:
                print("ℹ️  No risk definitions found in this domain")
            
            return list(risk_defs.values()) if risk_defs else []
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch risk definitions: {e}")
            return []
    
    def testScopeCreation(self, domain_id: str, unit_id: str, unit_manager=None) -> bool:
        """Test scope creation to verify it works"""
        print("\n🧪 Testing Scope Creation...")
        print(f"   Domain ID: {domain_id}")
        print(f"   Unit ID: {unit_id}")
        
        # Check unit-domain association
        if unit_manager:
            if not unit_manager.checkUnitDomainAssociation(unit_id, domain_id):
                print("\n❌ TEST FAILED: Unit is not associated with this domain!")
                print("   The unit must be associated with the domain to create objects.")
                print("\n💡 Solution:")
                print("   1. Check unit domains: python sparksbmMgmt.py list-units")
                print("   2. Create a new unit with this domain associated")
                print("   3. Or update the unit to include this domain")
                return False
            else:
                print("   ✅ Unit is associated with this domain")
        
        # Check if scope subTypes exist
        valid_subtypes = self.getValidSubTypes(domain_id, "scope")
        if not valid_subtypes:
            print("\n❌ TEST FAILED: No scope subTypes found in domain!")
            print("   This domain template may be incomplete.")
            print("   Solution: Use a domain created from the COMPLETE ISO 27001 template")
            return False
        
        print(f"\n✅ Found {len(valid_subtypes)} scope subType(s): {', '.join(valid_subtypes)}")
        
        # Try to create a test scope
        test_name = f"Test Scope {int(__import__('time').time())}"
        result = self.createObject("scope", test_name, domain_id, unit_id, "Test scope for verification", None, unit_manager)
        
        if result:
            print("\n✅ SCOPE CREATION TEST PASSED!")
            print("   Scope can be created successfully.")
            return True
        else:
            print("\n❌ SCOPE CREATION TEST FAILED!")
            print("   Check the error messages above for details.")
            return False


def checkBackendHealth():
    """Check backend health and connectivity"""
    print("=" * 70)
    print("SparksBM Backend Health Check")
    print("=" * 70)
    
    # Check backend
    print("\n🔍 Checking backend...")
    try:
        response = requests.get(f"{API_URL}/actuator/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running")
        else:
            print(f"⚠️  Backend returned status: {response.status_code}")
    except Exception as e:
        print(f"❌ Backend is not accessible: {e}")
    
    # Check Keycloak
    print("\n🔍 Checking Keycloak...")
    try:
        response = requests.get(f"{KEYCLOAK_URL}/realms/{REALM}", timeout=5)
        if response.status_code == 200:
            print("✅ Keycloak is running")
            realm_info = response.json()
            print(f"   Realm: {realm_info.get('realm', 'Unknown')}")
        else:
            print(f"⚠️  Keycloak returned status: {response.status_code}")
    except Exception as e:
        print(f"❌ Keycloak is not accessible: {e}")
    
    # Check Swagger
    print("\n🔍 Checking Swagger UI...")
    try:
        response = requests.get(f"{API_URL}/swagger-ui.html", timeout=5)
        if response.status_code == 200:
            print("✅ Swagger UI is accessible")
            print(f"   URL: {API_URL}/swagger-ui.html")
        else:
            print(f"⚠️  Swagger UI returned status: {response.status_code}")
    except Exception as e:
        print(f"❌ Swagger UI is not accessible: {e}")


def showMainMenu():
    """Display main menu"""
    print("\n" + "=" * 70)
    print("SparksBM ISMS Management")
    print("=" * 70)
    print("\n📋 DOMAIN MANAGEMENT:")
    print("  1. Setup domains from templates")
    print("  2. List all domains")
    print("  3. Delete domain")
    print("  4. List domain templates")
    print("  5. Check template completeness (subTypes)")
    print("  6. Import complete domain template")
    print("  7. Fix all domains (ensure complete subTypes)")
    print("  8. Show valid subTypes for domain")
    print("\n🏢 UNIT MANAGEMENT:")
    print("  9. List all units")
    print("  10. Create new unit")
    print("  11. Check unit creation limits")
    print("\n📦 OBJECT MANAGEMENT:")
    print("  12. Create object (scope, asset, control, process, etc.)")
    print("  13. List objects in domain")
    print("  14. Test scope creation")
    print("  15. List catalog items")
    print("  16. List reports")
    print("  17. List risk definitions")
    print("\n🔧 SYSTEM & CONFIGURATION:")
    print("  18. Check backend health")
    print("  19. Fix Keycloak CORS")
    print("  20. Fix total_units claim")
    print("\n  0. Exit")
    print("=" * 70)


def main():
    """Main function with interactive menu loop"""
    # Support command-line argument for non-interactive use
    if len(sys.argv) > 1:
        command = sys.argv[1]
        # Handle numeric commands from menu
        command_map = {
            "1": "setup-domains",
            "2": "list-domains",
            "3": "delete-domain",
            "4": "list-templates",
            "5": "check-templates",
            "6": "import-template",
            "7": "fix-all-domains",
            "8": "show-subtypes",
            "9": "list-units",
            "10": "create-unit",
            "11": "check-limits",
            "12": "create-object",
            "13": "list-objects",
            "14": "test-scope",
            "15": "list-catalog",
            "16": "list-reports",
            "17": "list-risk-definitions",
            "18": "check-backend",
            "19": "fix-cors",
            "20": "fix-total-units",
            "21": "list-profiles",
            "22": "export-profile",
            "23": "import-profile",
            "24": "copy-profile"
        }
        if command in command_map:
            command = command_map[command]
    else:
        command = None
    
    # Handle standalone commands (no loop needed)
    if command and command not in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "0"]:
        # Execute command directly (non-interactive mode)
        executeCommand(command)
        return
    
    # Interactive menu loop
    if not command:
        # Initialize client for interactive mode
        try:
            client = SparksBMClient()
            if not client.accessToken:
                print("❌ Failed to authenticate. Check your credentials and Keycloak configuration.")
                return
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return
        
        # Initialize managers
        domain_manager = SparksBMDomainManager(client)
        unit_manager = SparksBMUnitManager(client)
        object_manager = SparksBMObjectManager(client)
        
        while True:
            showMainMenu()
            try:
                choice = input("\nEnter choice (0-20): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n👋 Goodbye!")
                break
            
            if choice == "0":
                print("\n👋 Goodbye!")
                break
            
            # Map choice to command
            command_map = {
                "1": "setup-domains",
                "2": "list-domains",
                "3": "delete-domain",
                "4": "list-templates",
                "5": "check-templates",
                "6": "import-template",
                "7": "fix-all-domains",
                "8": "show-subtypes",
                "9": "list-units",
                "10": "create-unit",
                "11": "check-limits",
                "12": "create-object",
                "13": "list-objects",
                "14": "test-scope",
                "15": "list-catalog",
                "16": "list-reports",
                "17": "list-risk-definitions",
                "18": "check-backend",
                "19": "fix-cors",
                "20": "fix-total-units"
            }
            
            if choice in command_map:
                try:
                    executeCommand(command_map[choice], domain_manager, unit_manager, object_manager, client)
                    if choice not in ["18", "19", "20"]:  # Don't pause for system/quick commands
                        try:
                            input("\nPress Enter to continue...")
                        except (EOFError, KeyboardInterrupt):
                            print("\n")
                            break
                except KeyboardInterrupt:
                    print("\n\n⚠️  Operation cancelled")
                    try:
                        input("Press Enter to continue...")
                    except (EOFError, KeyboardInterrupt):
                        break
                except Exception as e:
                    print(f"\n❌ Error: {e}")
                    try:
                        input("Press Enter to continue...")
                    except (EOFError, KeyboardInterrupt):
                        break
            else:
                print("❌ Invalid choice. Please enter a number between 0-20.")
    else:
        # Command-line mode
        executeCommand(command)


def executeCommand(command, domain_manager=None, unit_manager=None, object_manager=None, client=None):
    """Execute a command"""
    # Handle commands that don't need authentication
    if command == "check-backend":
        checkBackendHealth()
        return
    
    if command == "fix-total-units":
        print("=" * 70)
        print("Fix total_units Claim in Keycloak")
        print("=" * 70)
        admin = SparksBMKeycloakAdmin()
        if not admin.adminToken:
            print("❌ Failed to get admin token")
            return
        if admin.fixTotalUnitsClaim():
            print("\n✅ Configuration updated!")
            print("   Re-authenticate to get new token with total_units claim")
        else:
            print("\n❌ Failed to fix. Manual steps:")
            print("   1. Keycloak Admin → Realm: sparksbm")
            print("   2. Client scopes → veo-license (or create it)")
            print("   3. Mappers → Add mapper")
            print("   4. Type: Hardcoded claim")
            print("   5. Name: total units")
            print("   6. Claim name: total_units")
            print("   7. Claim value: 10000")
            print("   8. Save")
        return
    
    if command == "fix-cors":
        print("=" * 70)
        print("Fix Keycloak CORS Configuration")
        print("=" * 70)
        admin = SparksBMKeycloakAdmin()
        if not admin.adminToken:
            print("❌ Failed to get admin token")
            return
        if admin.fixClientCORS(CLIENT_ID):
            print(f"✅ CORS configuration updated for client: {CLIENT_ID}")
            print("   Note: CORS error for /account endpoint is safe to ignore")
        else:
            print("❌ Failed to update CORS configuration")
        return
    
    # Initialize client if not provided
    if not client:
        try:
            client = SparksBMClient()
            if not client.accessToken:
                print("❌ Failed to authenticate.")
                return
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return
    
    # Test connection
    if not client.testConnection():
        print("⚠️  Connection test failed, but continuing...")
    
    # Initialize managers if not provided
    if not domain_manager:
        domain_manager = SparksBMDomainManager(client)
    if not unit_manager:
        unit_manager = SparksBMUnitManager(client)
    if not object_manager:
        object_manager = SparksBMObjectManager(client)
    
    if command == "setup-domains":
        domain_manager.setupDomains(restrict_to_existing=False)
    
    elif command == "list-domains":
        print("=" * 70)
        print("SparksBM Domains")
        print("=" * 70)
        domain_manager.listDomains()
    
    elif command == "delete-domain":
        print("=" * 70)
        print("Delete Domain")
        print("=" * 70)
        
        if len(sys.argv) >= 3:
            domain_id = sys.argv[2]
        else:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available.")
                return
            
            print("\nSelect domain to delete:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
        
        confirm = input(f"\n⚠️  Are you sure you want to delete domain {domain_id}? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Deletion cancelled")
            return
        
        if domain_manager.deleteDomain(domain_id):
            print("\n✅ Domain deleted successfully!")
        else:
            print("\n❌ Domain deletion failed")
    
    elif command == "list-templates":
        print("=" * 70)
        print("SparksBM Domain Templates")
        print("=" * 70)
        domain_manager.getDomainTemplates()
    
    elif command == "check-templates":
        print("=" * 70)
        print("Check Domain Template Completeness")
        print("=" * 70)
        results = domain_manager.checkAllTemplatesCompleteness()
        
        complete_count = sum(1 for r in results if r["is_complete"])
        print(f"\n📊 Summary:")
        print(f"   Total templates: {len(results)}")
        print(f"   Complete (with subTypes): {complete_count}")
        print(f"   Incomplete: {len(results) - complete_count}")
        
        if complete_count == 0:
            print(f"\n⚠️  No complete templates found!")
            print(f"   You need to import domain templates with full element type definitions.")
            print(f"   Use: python sparksbmMgmt.py import-template <template-file.json>")
    
    elif command == "import-template":
        print("=" * 70)
        print("Import Domain Template")
        print("=" * 70)
        
        if len(sys.argv) >= 3:
            template_file = sys.argv[2]
        else:
            template_file = input("\nTemplate file path: ").strip()
            if not template_file:
                print("❌ Template file path required")
                return
        
        print(f"\n📥 Importing template from: {template_file}")
        
        if domain_manager.importDomainTemplate(template_file):
            print("\n✅ Template imported successfully!")
            print("   You can now create domains from this template using option 1 (setup-domains)")
        else:
            print("\n❌ Template import failed")
            print("   Check:")
            print("   1. File exists and is valid JSON")
            print("   2. User has 'veo-content-creator' role")
            print("   3. Template structure is correct")
    
    elif command == "fix-all-domains":
        print("=" * 70)
        print("Fix All Domains - Ensure Complete subTypes")
        print("=" * 70)
        
        print("\n🔍 Checking domain template completeness...")
        results = domain_manager.checkAllTemplatesCompleteness()
        
        incomplete_templates = [r for r in results if not r["is_complete"]]
        complete_templates = [r for r in results if r["is_complete"]]
        
        if not incomplete_templates:
            print("\n✅ All domain templates are complete!")
            print("   All domains have subTypes defined.")
            return
        
        print(f"\n⚠️  Found {len(incomplete_templates)} incomplete template(s):")
        for result in incomplete_templates:
            print(f"   - {result.get('template_name', 'Unknown')} ({result['template_id']})")
        
        # Find complete ISO 27001 template
        complete_iso_template = None
        for result in complete_templates:
            if 'ISO' in result.get('template_name', '') or '27001' in result.get('template_name', ''):
                complete_iso_template = result
                break
        
        print("\n📋 Current Status:")
        for result in results:
            status = "✅" if result["is_complete"] else "❌"
            print(f"   {status} {result.get('template_name', 'Unknown')} template: {'Complete' if result['is_complete'] else 'Incomplete'}")
        
        if complete_iso_template:
            print(f"\n✅ Found complete ISO 27001 template: {complete_iso_template['template_id']}")
            print("\n💡 Solution:")
            print("   1. When creating new domains, use the COMPLETE template:")
            print(f"      Template ID: {complete_iso_template['template_id']}")
            print("   2. For existing domains created from incomplete template:")
            print("      - Delete the incomplete domain")
            print("      - Recreate it using the complete template")
            print("      - Or contact support to update existing domains")
        else:
            print("\n💡 To fix incomplete templates:")
            print("   1. Get complete domain template JSON files with full elementTypeDefinitions")
            print("   2. Import them using: python sparksbmMgmt.py import-template <file.json>")
            print("   3. Or update existing templates with complete definitions")
        
        print("\n🎯 Quick Fix:")
        print("   Use the COMPLETE ISO 27001 template when creating domains:")
        if complete_iso_template:
            print(f"   Template ID: {complete_iso_template['template_id']}")
        print("   Avoid using the incomplete template:")
        for result in incomplete_templates:
            if 'ISO' in result.get('template_name', '') or '27001' in result.get('template_name', ''):
                print(f"   Template ID: {result['template_id']} ❌")
    
    elif command == "list-units":
        print("=" * 70)
        print("SparksBM Units")
        print("=" * 70)
        unit_manager.listUnits()
    
    elif command == "check-limits":
        print("=" * 70)
        print("SparksBM License Limits")
        print("=" * 70)
        diagnosis = unit_manager.diagnoseUnitCreationIssue()
        print(f"\n📊 Unit Limit Status:")
        print(f"   Current units: {diagnosis['current_units']}")
        print(f"   max_units in token: {diagnosis['max_units_in_token']}")
        print(f"   total_units in token: {diagnosis['total_units_in_token']}")
        
        if diagnosis["issue"] == "total_units_missing":
            print(f"\n❌ CRITICAL: total_units claim is missing!")
            print(f"   This prevents unit creation.")
            print(f"\n💡 Fix: python sparksbmMgmt.py fix-total-units")
        elif diagnosis["issue"] == "total_units_zero":
            print(f"\n❌ total_units is 0 - prevents unit creation")
        elif diagnosis["issue"] == "limit_reached":
            print(f"\n⚠️  Limit reached! Cannot create more units.")
        else:
            remaining = (diagnosis['total_units_in_token'] or 0) - diagnosis['current_units']
            print(f"\n✅ You can create {remaining} more unit(s)")
    
    elif command == "create-unit":
        print("=" * 70)
        print("Create Unit")
        print("=" * 70)
        
        # Check if arguments provided (non-interactive mode)
        if len(sys.argv) >= 3:
            name = sys.argv[2]
            description = sys.argv[3] if len(sys.argv) >= 4 else ""
            domain_indices = sys.argv[4].split(',') if len(sys.argv) >= 5 else []
        else:
            # Interactive mode
            name = input("\nUnit name: ").strip()
            if not name:
                print("❌ Unit name is required")
                return
            
            description = input("Description (optional): ").strip()
            domain_indices = []
        
        # List domains for selection
        domains = domain_manager.listDomains()
        domain_ids = []
        
        if domains:
            if domain_indices:
                # Non-interactive: use provided indices
                try:
                    indices = [int(x.strip()) - 1 for x in domain_indices]
                    domain_ids = [domains[i].get('id') for i in indices if 0 <= i < len(domains)]
                except:
                    print("⚠️  Invalid domain selection, creating unit without domains")
            else:
                # Interactive: show list and ask
                print("\nAvailable domains:")
                for idx, domain in enumerate(domains, 1):
                    print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
                
                domain_input = input("\nEnter domain numbers (comma-separated, or press Enter for none): ").strip()
                if domain_input:
                    try:
                        indices = [int(x.strip()) - 1 for x in domain_input.split(',')]
                        domain_ids = [domains[i].get('id') for i in indices if 0 <= i < len(domains)]
                    except:
                        print("⚠️  Invalid domain selection, creating unit without domains")
        
        result = unit_manager.createUnit(name, description, domain_ids)
        
        if result:
            print("\n✅ Unit creation completed successfully!")
        else:
            print("\n❌ Unit creation failed. Check the error messages above.")
    
    elif command == "create-object":
        print("=" * 70)
        print("Create Object")
        print("=" * 70)
        
        # Get required info
        if len(sys.argv) >= 3:
            object_type = sys.argv[2]
            name = sys.argv[3] if len(sys.argv) >= 4 else ""
            domain_id = sys.argv[4] if len(sys.argv) >= 5 else ""
            unit_id = sys.argv[5] if len(sys.argv) >= 6 else ""
            description = sys.argv[6] if len(sys.argv) >= 7 else ""
        else:
            print("\nAvailable object types: scope, asset, control, process, person, scenario, incident, document")
            object_type = input("\nObject type: ").strip().lower()
            if not object_type:
                print("❌ Object type is required")
                return
            
            name = input("Object name: ").strip()
            if not name:
                print("❌ Object name is required")
                return
            
            description = input("Description (optional): ").strip()
        
        # Get domain if not provided
        if not domain_id:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available. Run 'setup-domains' first.")
                return
            
            print("\nSelect domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
        
        # Get unit if not provided
        if not unit_id:
            units = unit_manager.listUnits()
            if not units:
                print("❌ No units available. Create a unit first.")
                return
            
            print("\nSelect unit:")
            for idx, unit in enumerate(units, 1):
                print(f"  {idx}. {unit.get('name')} ({unit.get('id')})")
            
            unit_idx = input("\nUnit number: ").strip()
            try:
                unit_id = units[int(unit_idx) - 1].get('id')
            except:
                print("❌ Invalid unit selection")
                return
        
        result = object_manager.createObject(object_type, name, domain_id, unit_id, description, None, unit_manager)
        
        if result:
            print("\n✅ Object creation completed successfully!")
        else:
            print("\n❌ Object creation failed. Check the error messages above.")
    
    elif command == "show-subtypes":
        print("=" * 70)
        print("Show Valid subTypes")
        print("=" * 70)
        
        if len(sys.argv) >= 3:
            domain_id = sys.argv[2]
            object_type = sys.argv[3] if len(sys.argv) >= 4 else None
        else:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available.")
                return
            
            print("\nSelect domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
            
            print("\nAvailable object types: scope, asset, control, process, person, scenario, incident, document")
            object_type = input("Object type (or press Enter for all): ").strip() or None
        
        object_manager.showValidSubTypes(domain_id, object_type)
    
    elif command == "use-complete-domain":
        print("=" * 70)
        print("Use Domain with Complete subTypes")
        print("=" * 70)
        
        # Check which domains have subTypes
        domains = domain_manager.listDomains()
        print("\n🔍 Checking which domains have subTypes...")
        
        domains_with_subtypes = []
        for domain in domains:
            domain_id = domain.get('id')
            valid_subtypes = object_manager.getValidSubTypes(domain_id, "asset")
            if valid_subtypes:
                domains_with_subtypes.append((domain, valid_subtypes))
        
        if domains_with_subtypes:
            print(f"\n✅ Found {len(domains_with_subtypes)} domain(s) with subTypes:")
            for domain, subtypes in domains_with_subtypes:
                print(f"\n   {domain.get('name')} ({domain.get('id')})")
                print(f"   Asset subTypes: {', '.join(subtypes)}")
                print(f"\n   💡 You can create objects in this domain!")
                print(f"   Example:")
                print(f"   python sparksbmMgmt.py create-object asset 'My Asset' {domain.get('id')} <unit-id>")
        else:
            print("\n❌ No domains with subTypes found!")
            print("\n💡 Solutions:")
            print("   1. Check templates: python sparksbmMgmt.py check-templates")
            print("   2. Import complete template: python sparksbmMgmt.py import-template <file.json>")
            print("   3. Create domain from complete template (DS-GVO has subTypes)")
    
    elif command == "list-objects":
        print("=" * 70)
        print("List Objects")
        print("=" * 70)
        
        if len(sys.argv) >= 3:
            object_type = sys.argv[2]
            domain_id = sys.argv[3] if len(sys.argv) >= 4 else ""
        else:
            print("\nAvailable object types: scope, asset, control, process, person, scenario, incident, document")
            object_type = input("\nObject type: ").strip().lower()
            if not object_type:
                print("❌ Object type is required")
                return
        
        if not domain_id:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available.")
                return
            
            print("\nSelect domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
        
        object_manager.listObjects(domain_id, object_type)
    
    elif command == "test-scope":
        print("=" * 70)
        print("Test Scope Creation")
        print("=" * 70)
        
        if len(sys.argv) >= 3:
            domain_id = sys.argv[2]
            unit_id = sys.argv[3] if len(sys.argv) >= 4 else ""
        else:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available.")
                return
            
            print("\nSelect domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
            
            units = unit_manager.listUnits()
            if not units:
                print("❌ No units available. Create a unit first.")
                return
                
            print("\nSelect unit:")
            for idx, unit in enumerate(units, 1):
                print(f"  {idx}. {unit.get('name')} ({unit.get('id')})")
            
            unit_idx = input("\nUnit number: ").strip()
            try:
                unit_id = units[int(unit_idx) - 1].get('id')
            except:
                print("❌ Invalid unit selection")
                return
        
        object_manager.testScopeCreation(domain_id, unit_id, unit_manager)
    
    elif command == "list-catalog":
        print("=" * 70)
        print("List Catalog Items")
        print("=" * 70)
        
        if len(sys.argv) >= 3:
            domain_id = sys.argv[2]
        else:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available.")
                return
            
            print("\nSelect domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
        
        object_manager.listCatalogItems(domain_id)
    
    elif command == "list-reports":
        print("=" * 70)
        print("List Reports")
        print("=" * 70)
        
        if len(sys.argv) >= 3:
            domain_id = sys.argv[2]
        else:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available.")
                return
            
            print("\nSelect domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
        
        object_manager.listReports(domain_id)
    
    elif command == "list-risk-definitions":
        print("=" * 70)
        print("List Risk Definitions")
        print("=" * 70)
        
        if len(sys.argv) >= 3:
            domain_id = sys.argv[2]
        else:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available.")
                return
            
            print("\nSelect domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
        
        object_manager.listRiskDefinitions(domain_id)
    
    elif command == "list-profiles":
        print("=" * 70)
        print("List Profiles")
        print("=" * 70)
        
        if len(sys.argv) >= 3:
            domain_id = sys.argv[2]
        else:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available.")
                return
            
            print("\nSelect domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
        
        domain_manager.listProfiles(domain_id)
    
    elif command == "export-profile":
        print("=" * 70)
        print("Export Profile")
        print("=" * 70)
        
        if len(sys.argv) >= 4:
            domain_id = sys.argv[2]
            profile_id = sys.argv[3]
            output_file = sys.argv[4] if len(sys.argv) >= 5 else f"profile-{profile_id}.json"
        else:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available.")
                return
            
            print("\nSelect domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
            
            profiles = domain_manager.listProfiles(domain_id)
            if not profiles:
                print("❌ No profiles in this domain")
                return
            
            print("\nSelect profile:")
            for idx, profile in enumerate(profiles, 1):
                print(f"  {idx}. {profile.get('name')} ({profile.get('id')})")
            
            profile_idx = input("\nProfile number: ").strip()
            try:
                profile_id = profiles[int(profile_idx) - 1].get('id')
            except:
                print("❌ Invalid profile selection")
                return
            
            output_file = input("Output file (or press Enter for default): ").strip() or f"profile-{profile_id}.json"
        
        domain_manager.exportProfile(domain_id, profile_id, output_file)
    
    elif command == "import-profile":
        print("=" * 70)
        print("Import Profile")
        print("=" * 70)
        
        if len(sys.argv) >= 3:
            profile_file = sys.argv[2]
            domain_id = sys.argv[3] if len(sys.argv) >= 4 else ""
        else:
            profile_file = input("\nProfile file path: ").strip()
            if not profile_file:
                print("❌ Profile file path required")
                return
        
        if not domain_id:
            domains = domain_manager.listDomains()
            if not domains:
                print("❌ No domains available.")
                return
            
            print("\nSelect target domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            domain_idx = input("\nDomain number: ").strip()
            try:
                domain_id = domains[int(domain_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
        
        if domain_manager.importProfile(domain_id, profile_file):
            print("\n✅ Profile imported successfully!")
        else:
            print("\n❌ Profile import failed")
    
    elif command == "copy-profile":
        print("=" * 70)
        print("Copy Profile Between Domains")
        print("=" * 70)
        
        domains = domain_manager.listDomains()
        if len(domains) < 2:
            print("❌ Need at least 2 domains to copy profiles")
            return
        
        if len(sys.argv) >= 4:
            source_domain_id = sys.argv[2]
            profile_id = sys.argv[3]
            target_domain_id = sys.argv[4] if len(sys.argv) >= 5 else ""
        else:
            print("\nSelect source domain:")
            for idx, domain in enumerate(domains, 1):
                print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            source_idx = input("\nSource domain number: ").strip()
            try:
                source_domain_id = domains[int(source_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
            
            profiles = domain_manager.listProfiles(source_domain_id)
            if not profiles:
                print("❌ No profiles in source domain")
                return
            
            print("\nSelect profile to copy:")
            for idx, profile in enumerate(profiles, 1):
                print(f"  {idx}. {profile.get('name')} ({profile.get('id')})")
            
            profile_idx = input("\nProfile number: ").strip()
            try:
                profile_id = profiles[int(profile_idx) - 1].get('id')
            except:
                print("❌ Invalid profile selection")
                return
            
            print("\nSelect target domain:")
            for idx, domain in enumerate(domains, 1):
                if domain.get('id') != source_domain_id:
                    print(f"  {idx}. {domain.get('name')} ({domain.get('id')})")
            
            target_idx = input("\nTarget domain number: ").strip()
            try:
                target_domain_id = domains[int(target_idx) - 1].get('id')
            except:
                print("❌ Invalid domain selection")
                return
        
        if domain_manager.copyProfileBetweenDomains(source_domain_id, profile_id, target_domain_id):
            print("\n✅ Profile copied successfully!")
        else:
            print("\n❌ Profile copy failed")
    
    else:
        # Show help if command not recognized
        showMainMenu()
        print("\n💡 Tip: Run without arguments for interactive menu, or use:")
        print("   python sparksbmMgmt.py <command>")
        print("\n   Or use menu numbers: python sparksbmMgmt.py 1")


if __name__ == "__main__":
    main()
