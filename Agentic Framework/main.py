#!/usr/bin/env python3
"""Main entry point for Agentic Framework"""
import sys
import os
import platform

# Clear screen for clean start (cross-platform)
def clearScreen():
    """Clear terminal screen"""
    if platform.system() == 'Windows':
        os.system('cls')
    else:
        os.system('clear')

# Clear screen before starting
clearScreen()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.mainAgent import MainAgent
from tools.llmTool import LLMTool
from tools.veriniceTool import VeriniceTool
from orchestrator.executor import AgentExecutor
from memory.memoryStore import MemoryStore
from config.settings import Settings


def setupAgent():
    """Setup and configure an ISMS agent"""
    
    agent = MainAgent("SparksBM DataProcessor")
    
    # Register tools
    
    # Register LLM - use Gemini
    try:
        llmTool = LLMTool(provider='gemini')
        
        # Register LLM tools for chat
        agent.registerTool('generate', llmTool.generate, 'Generate text using LLM')
        agent.registerTool('analyze', llmTool.analyze, 'Analyze data using LLM')
        agent.registerTool('extractEntities', llmTool.extractEntities, 'Extract entities from text')
        print("[+] LLM tools registered")
    except Exception as e:
        print(f"[!] LLM not available: {e}")
        # Continue without LLM - agent can still handle ISMS operations
    
    # Register Verinice tools (always try to initialize)
    try:
        veriniceTool = VeriniceTool()
        verinice_available = veriniceTool._checkClient()
        
        # Store reference for menu functions (even if client check fails, tools can be registered)
        agent._veriniceTool = veriniceTool
        
        # Register all CRUD operations (always register, let tool handle client check)
        agent.registerTool('createVeriniceObject', veriniceTool.createObject, 'Create any object in Verinice (scope, asset, control, process, person, scenario, incident, document)')
        agent.registerTool('listVeriniceObjects', veriniceTool.listObjects, 'List objects in Verinice by type and domain')
        agent.registerTool('getVeriniceObject', veriniceTool.getObject, 'Get object details from Verinice by ID')
        agent.registerTool('updateVeriniceObject', veriniceTool.updateObject, 'Update object in Verinice')
        agent.registerTool('deleteVeriniceObject', veriniceTool.deleteObject, 'Delete object from Verinice')
        agent.registerTool('listVeriniceReports', veriniceTool.listReports, 'List available reports in Verinice')
        agent.registerTool('generateVeriniceReport', veriniceTool.generateReport, 'Generate report in Verinice')
        agent.registerTool('listVeriniceDomains', veriniceTool.listDomains, 'List all domains in Verinice')
        agent.registerTool('listVeriniceUnits', veriniceTool.listUnits, 'List all units in Verinice')
        agent.registerTool('getVeriniceSubTypes', veriniceTool.getValidSubTypes, 'Get valid subTypes for object type')
        agent.registerTool('createVeriniceDomain', veriniceTool.createDomain, 'Create domain from template')
        agent.registerTool('deleteVeriniceDomain', veriniceTool.deleteDomain, 'Delete a domain')
        agent.registerTool('getVeriniceDomainTemplates', veriniceTool.getDomainTemplates, 'Get available domain templates')
        agent.registerTool('getVeriniceDomainSubTypes', veriniceTool.getDomainSubTypes, 'Get all subtypes for a domain')
        agent.registerTool('createVeriniceUnit', veriniceTool.createUnit, 'Create a new unit')
        agent.registerTool('listVeriniceRiskDefinitions', veriniceTool.listRiskDefinitions, 'List risk definitions in a domain')
        
        # Profile Management
        agent.registerTool('listVeriniceProfiles', veriniceTool.listProfiles, 'List profiles in a domain')
        
        # Catalog Management
        agent.registerTool('listVeriniceCatalogItems', veriniceTool.listCatalogItems, 'List catalog items in a domain')
        
        agent.registerTool('getVeriniceDomain', veriniceTool.getDomain, 'Get detailed information about a domain')
        agent.registerTool('getVeriniceUnit', veriniceTool.getUnit, 'Get detailed information about a unit')
        
        # Template Operations
        agent.registerTool('checkVeriniceTemplateCompleteness', veriniceTool.checkTemplateCompleteness, 'Check if a domain template is complete (has all subTypes)')
        
        if verinice_available:
            print("[+] Verinice tools registered and client authenticated")
        else:
            print("[!] Verinice tools registered but client not authenticated - check Keycloak/API configuration")
            print("   Tools will be available but may fail until authentication is configured")
    except Exception as e:
        print(f"[!] Verinice tool initialization error: {e}")
        print("   Note: Verinice features require sparksbm-scripts and proper configuration")
    
    return agent


def printMenu():
    """Print interactive menu"""
    print("\n" + "=" * 70)
    print("          SparksBM Agentic Framework")
    print("=" * 70)
    print("\n[fa-robot] INTELLIGENT AGENT:")
    print("   3. Chat with SparksBM Intelligent (LLM)")
    print("\n[fa-cube] OBJECT MANAGEMENT:")
    print("   4. Create Object (scope, asset, control, process, etc.)")
    print("   5. List Objects")
    print("   6. View Object Details")
    print("   7. Update Object")
    print("   8. Delete Object")
    print("\n[fa-building] DOMAIN MANAGEMENT:")
    print("  10. List Domains")
    print("  11. Create Domain from Template")
    print("  12. Delete Domain")
    print("  13. List Domain Templates")
    print("  14. Show Domain SubTypes")
    print("\n[fa-sitemap] UNIT MANAGEMENT:")
    print("  15. List Units")
    print("  16. Create Unit")
    print("\n[fa-chart-bar] REPORTS & RISK:")
    print("  17. List Reports")
    print("  18. Generate Report")
    print("  19. List Risk Definitions")
    print("\n[fa-cog] SYSTEM & CONFIGURATION:")
    print("  20. View Agent Capabilities")
    print("  21. View Agent State/History")
    print("  22. Test Workflow (Multi-step)")
    print("  23. Show System Logic Flow")
    print("  24. Check LLM Configuration Status")
    print("  25. Manage Agents (List/Create/Register)")
    print("\n   0. Exit")
    print("=" * 70)

def checkLLMStatus():
    """Check LLM configuration status"""
    print("\n" + "=" * 70)
    print("LLM Configuration Status")
    print("=" * 70)
    
    geminiKey = Settings.GEMINI_API_KEY
    
    print(f"\nGemini API:")
    if geminiKey:
        masked = geminiKey[:8] + "..." + geminiKey[-4:] if len(geminiKey) > 12 else "***"
        print(f"  [+] API Key: {masked}")
        print(f"  Current Model: {Settings.GEMINI_MODEL}")
        print(f"\n  Available Gemini Models:")
        models = Settings.getAvailableGeminiModels()
        for model, desc in models.items():
            marker = "← CURRENT" if model == Settings.GEMINI_MODEL else ""
            print(f"    • {model}: {desc} {marker}")
    else:
        print(f"  [-] Not configured (set GEMINI_API_KEY in .env)")
        print(f"\n  Available Gemini Models:")
        models = Settings.getAvailableGeminiModels()
        for model, desc in models.items():
            print(f"    • {model}: {desc}")
    
    print(f"\nLLM Configuration:")
    if geminiKey:
        print(f"  ✅ Using Gemini: {Settings.GEMINI_MODEL}")
    else:
        print(f"  ❌ No LLM provider configured")
    
    print("\nRecommendation:")
    if geminiKey:
        if Settings.GEMINI_MODEL == 'gemini-2.5-flash':
            print(f"  [+] Using gemini-2.5-flash (fast and cost-effective)")
        else:
            print(f"  [*] Consider gemini-2.5-flash for faster, cost-effective processing")
    else:
        print(f"  [*] Set GEMINI_API_KEY to use Gemini models")
    
    print("=" * 70)

def showCapabilities(agent, executor):
    """Show what the agent can do"""
    print("\n" + "=" * 70)
    print("Agent Capabilities")
    print("=" * 70)
    print(f"Agent Name: {agent.name}")
    print(f"Agent Role: {agent.role}")
    print(f"Goals: {', '.join(agent.goals)}")
    print(f"\nAvailable Tools ({len(agent.tools)}):")
    
    # Group tools by category
    llm_tools = []
    verinice_tools = []
    
    for toolName, toolInfo in agent.tools.items():
        desc = toolInfo.get('description', 'No description')
        if 'Verinice' in desc or 'verinice' in toolName.lower():
            verinice_tools.append((toolName, desc))
        elif toolName in ['generate', 'analyze', 'extractEntities']:
            llm_tools.append((toolName, desc))
        else:
            # Assume other tools are doc tools for now, this can be improved
            pass
    
    if llm_tools:
        print("\n  [fa-brain] LLM Tools:")
        for toolName, desc in llm_tools:
            print(f"    • {toolName}: {desc}")
    
    if verinice_tools:
        print("\n  [fa-database] VERINICE ISMS:")
        # Group by category - hierarchical organization like dashboard
        object_tools = [t for t in verinice_tools if 'Object' in t[0] or 'object' in t[0].lower()]
        domain_tools = [t for t in verinice_tools if 'Domain' in t[0] or 'domain' in t[0].lower()]
        unit_tools = [t for t in verinice_tools if 'Unit' in t[0] or 'unit' in t[0].lower()]
        report_tools = [t for t in verinice_tools if 'Report' in t[0] or 'report' in t[0].lower()]
        risk_tools = [t for t in verinice_tools if 'Risk' in t[0] or 'risk' in t[0].lower()]
        profile_tools = [t for t in verinice_tools if 'Profile' in t[0] or 'profile' in t[0].lower()]
        catalog_tools = [t for t in verinice_tools if 'Catalog' in t[0] or 'catalog' in t[0].lower()]
        template_tools = [t for t in verinice_tools if 'Template' in t[0] or 'template' in t[0].lower()]
        helper_tools = [t for t in verinice_tools if t not in object_tools + domain_tools + unit_tools + report_tools + risk_tools + profile_tools + catalog_tools + template_tools]
        
        if object_tools:
            print("\n    [fa-cube] Objects:")
            for toolName, desc in object_tools:
                print(f"      • {toolName}: {desc}")
        if domain_tools:
            print("\n    [fa-building] Domains:")
            for toolName, desc in domain_tools:
                print(f"      • {toolName}: {desc}")
        if unit_tools:
            print("\n    [fa-sitemap] Units:")
            for toolName, desc in unit_tools:
                print(f"      • {toolName}: {desc}")
        if report_tools:
            print("\n    [fa-chart-bar] Reports:")
            for toolName, desc in report_tools:
                print(f"      • {toolName}: {desc}")
        if risk_tools:
            print("\n    [fa-shield-alt] Risk Definitions:")
            for toolName, desc in risk_tools:
                print(f"      • {toolName}: {desc}")
        if profile_tools:
            print("\n    [fa-user-circle] Profiles:")
            for toolName, desc in profile_tools:
                print(f"      • {toolName}: {desc}")
        if catalog_tools:
            print("\n    [fa-book] Catalog:")
            for toolName, desc in catalog_tools:
                print(f"      • {toolName}: {desc}")
        if template_tools:
            print("\n    [fa-file-alt] Templates:")
            for toolName, desc in template_tools:
                print(f"      • {toolName}: {desc}")
        if helper_tools:
            print("\n    [fa-tools] Helpers:")
            for toolName, desc in helper_tools:
                print(f"      • {toolName}: {desc}")
    
    print(f"\nExecution History: {len(executor.executionHistory)} tasks completed")
    print("=" * 70)

def manageAgents(executor):
    """Manage agents - list, create, register"""
    print("\n" + "=" * 70)
    print("Agent Management")
    print("=" * 70)
    
    print(f"\nRegistered Agents ({len(executor.agents)}):")
    for i, agent in enumerate(executor.agents, 1):
        print(f"  {i}. {agent.name} ({agent.role})")
        print(f"     Tools: {len(agent.tools)}, Goals: {len(agent.goals)}")
    
    print("\nOptions:")
    print("  1. Create new agent")
    print("  2. Register existing agent")
    print("  3. Back to main menu")
    
    choice = input("\nSelect option: ").strip()
    
    if choice == '1':
        print("\nCreating new agent...")
        name = input("Agent name: ").strip() or "NewAgent"
        role = input("Agent role: ").strip() or "Agent"
        
        goals = []
        print("Enter goals (press Enter with empty line to finish):")
        while True:
            goal = input(f"  Goal {len(goals) + 1}: ").strip()
            if not goal:
                break
            goals.append(goal)
        
        if not goals:
            goals = ["Process tasks"]
        
        instructions = input("Instructions (optional): ").strip() or f"You are a {role} agent."
        
        from agents.baseAgent import BaseAgent
        class CustomAgent(BaseAgent):
            def process(self, inputData):
                return {
                    'status': 'success',
                    'result': f"Agent {self.name} processed: {inputData}",
                    'message': 'This is a custom agent. Override process() method for custom behavior.'
                }
        
        newAgent = CustomAgent(name, role, goals, instructions)
        
        # Register some basic tools
        print("\nRegistering basic tools...")
        try:
            llmTool = LLMTool(provider='gemini')
            newAgent.registerTool('generate', llmTool.generate, 'Generate text using LLM')
            print("  [+] Registered generate")
        except:
            pass
        
        executor.registerAgent(newAgent)
        print(f"\n[+] Agent '{name}' created and registered!")
        print(f"  Total agents: {len(executor.agents)}")
    
    elif choice == '2':
        print("\nTo register an existing agent, modify main.py setupAgent() function")
        print("or create a new agent class in agents/ directory.")
    
    print("=" * 70)

# ==================== VERINICE MENU FUNCTIONS ====================

def createVeriniceObject(executor, agent, objectType=None):
    """Create a Verinice object"""
    print("\n" + "=" * 70)
    print("Create Verinice Object")
    print("=" * 70)
    
    veriniceTool = None
    if hasattr(agent, '_veriniceTool') and agent._veriniceTool and agent._veriniceTool._checkClient():
        veriniceTool = agent._veriniceTool
    else:
        # Try to create new instance as fallback
        try:
            from tools.veriniceTool import VeriniceTool
            veriniceTool = VeriniceTool()
            if not veriniceTool._checkClient():
                print("[-] Verinice client not available. Check configuration.")
                return
        except Exception as e:
            print(f"[-] Verinice tool not available: {e}")
            return
    
    if not objectType:
        print("\nAvailable object types: scope, asset, control, process, person, scenario, incident, document")
        objectType = input("Object type: ").strip().lower()
    
    if not objectType or objectType not in ['scope', 'asset', 'control', 'process', 'person', 'scenario', 'incident', 'document']:
        print("[-] Invalid object type")
        return
    
    domainsResult = veriniceTool.listDomains()
    if not domainsResult.get('success') or not domainsResult.get('domains'):
        print("[-] No domains available")
        return
    
    domains = domainsResult['domains']
    print("\nAvailable domains:")
    for idx, domain in enumerate(domains, 1):
        name = domain.get('name', 'Unknown')
        domainId = domain.get('id')
        templateVersion = domain.get('templateVersion', 'N/A')
        authority = domain.get('authority', 'N/A')
        createdAt = domain.get('createdAt', '')
        if createdAt:
            # Extract date part (YYYY-MM-DD)
            datePart = createdAt.split('T')[0] if 'T' in createdAt else createdAt[:10]
        else:
            datePart = 'N/A'
        
        hasSubTypes = False
        if 'elementTypeDefinitions' in domain:
            etd = domain['elementTypeDefinitions']
            if objectType in etd and 'subTypes' in etd[objectType]:
                subTypes = etd[objectType]['subTypes']
                hasSubTypes = bool(subTypes) if isinstance(subTypes, dict) else bool(subTypes)
        
        subTypeStatus = "[+] Has subTypes" if hasSubTypes else "[!] No subTypes"
        print(f"  {idx}. {name} (v{templateVersion}, {authority}, created: {datePart})")
        print(f"      ID: {domainId}")
        print(f"      {subTypeStatus} for {objectType}")
    
    domainIdx = input("\nDomain number: ").strip()
    try:
        domainId = domains[int(domainIdx) - 1].get('id')
    except:
        print("[-] Invalid domain selection")
        return
    
    unitsResult = veriniceTool.listUnits()
    if not unitsResult.get('success') or not unitsResult.get('units'):
        print("[-] No units available")
        return
    
    units = unitsResult['units']
    print("\nAvailable units:")
    for idx, unit in enumerate(units, 1):
        print(f"  {idx}. {unit.get('name', 'Unknown')} ({unit.get('id')})")
    
    unitIdx = input("\nUnit number: ").strip()
    try:
        unitId = units[int(unitIdx) - 1].get('id')
    except:
        print("[-] Invalid unit selection")
        return
    
    name = input(f"\n{objectType.capitalize()} name: ").strip()
    if not name:
        print("[-] Name is required")
        return
    
    description = input("Description (optional): ").strip()
    
    print(f"\nFetching valid subTypes for {objectType}...")
    subTypesResult = veriniceTool.getValidSubTypes(domainId, objectType)
    subType = None
    
    # If API call fails or returns empty, try to extract from domain data
    if not subTypesResult.get('success') or not subTypesResult.get('subTypes'):
        # Try to get subTypes from domain's elementTypeDefinitions
        selectedDomain = [d for d in domains if d.get('id') == domainId]
        if selectedDomain:
            domainData = selectedDomain[0]
            if 'elementTypeDefinitions' in domainData:
                etd = domainData['elementTypeDefinitions']
                if objectType in etd:
                    typeDef = etd[objectType]
                    if 'subTypes' in typeDef and typeDef['subTypes']:
                        subTypesDict = typeDef['subTypes']
                        if isinstance(subTypesDict, dict) and subTypesDict:
                            subTypes = list(subTypesDict.keys())
                            subTypesResult = {'success': True, 'subTypes': subTypes}
    
    if subTypesResult.get('success') and subTypesResult.get('subTypes'):
        subTypes = subTypesResult['subTypes']
        if isinstance(subTypes, dict):
            subTypes = list(subTypes.keys())
        
        if subTypes:
            print(f"\nAvailable subTypes:")
            for idx, st in enumerate(subTypes, 1):
                print(f"  {idx}. {st}")
            
            subTypeChoice = input(f"\nSubType number (or Enter for first: {subTypes[0]}): ").strip()
            if subTypeChoice:
                try:
                    subType = subTypes[int(subTypeChoice) - 1]
                except:
                    print(f"[!] Invalid selection, using first: {subTypes[0]}")
                    subType = subTypes[0]
            else:
                subType = subTypes[0]
            print(f"   Using subType: {subType}")
        else:
            print(f"\n[!] Domain has no subTypes defined for {objectType}!")
            print(f"   This domain template may be incomplete.")
            print(f"   Recommendation: Use Domain 2 (DS-GVO) or Domain 3 (ISO 27001 v1.0.1)")
            print(f"   which have subTypes configured.")
            print(f"\n   Attempting to create without subType (will likely fail)...")
            confirm = input("   Continue anyway? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("   Creation cancelled.")
                return
    else:
        print(f"\n[!] Domain has no subTypes defined for {objectType}!")
        print(f"   Error: {subTypesResult.get('error', 'No subTypes in domain template')}")
        print(f"   This domain template may be incomplete.")
        print(f"   Recommendation: Use Domain 2 (DS-GVO) or Domain 3 (ISO 27001 v1.0.1)")
        print(f"   which have subTypes configured.")
        print(f"\n   Attempting to create without subType (will likely fail)...")
        confirm = input("   Continue anyway? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("   Creation cancelled.")
            return
    
    print(f"\nCreating {objectType}...")
    result = veriniceTool.createObject(objectType, domainId, unitId, name, subType=subType, description=description)
    
    if result.get('success'):
        print(f"\n[+] Successfully created {objectType}: {name}")
        if result.get('objectId'):
            print(f"   Object ID: {result['objectId']}")
    else:
        print(f"\n[-] Failed to create {objectType}: {result.get('error', 'Unknown error')}")

def listVeriniceObjects(executor, agent, objectType=None):
    """List Verinice objects"""
    print("\n" + "=" * 70)
    print("List Verinice Objects")
    print("=" * 70)
    
    veriniceTool = None
    try:
        from tools.veriniceTool import VeriniceTool
        veriniceTool = VeriniceTool()
        if not veriniceTool._checkClient():
            print("[-] Verinice client not available. Check configuration.")
            return
    except Exception as e:
        print(f"[-] Verinice tool not available: {e}")
        return
    
    if not objectType:
        print("\nAvailable object types: scope, asset, control, process, person, scenario, incident, document")
        objectType = input("Object type: ").strip().lower()
    
    if not objectType or objectType not in ['scope', 'asset', 'control', 'process', 'person', 'scenario', 'incident', 'document']:
        print("[-] Invalid object type")
        return
    
    domainsResult = veriniceTool.listDomains()
    if not domainsResult.get('success') or not domainsResult.get('domains'):
        print("[-] No domains available")
        return
    
    domains = domainsResult.get('domains', [])
    if not domains:
        print("[-] No domains available")
        return
    
    print("\nAvailable domains:")
    for idx, domain in enumerate(domains, 1):
        name = domain.get('name', 'Unknown')
        domainId = domain.get('id')
        templateVersion = domain.get('templateVersion', 'N/A')
        authority = domain.get('authority', 'N/A')
        createdAt = domain.get('createdAt', '')
        if createdAt:
            # Extract date part (YYYY-MM-DD)
            datePart = createdAt.split('T')[0] if 'T' in createdAt else createdAt[:10]
        else:
            datePart = 'N/A'
        print(f"  {idx}. {name} (v{templateVersion}, {authority}, created: {datePart})")
        print(f"      ID: {domainId}")
    
    domainIdx = input("\nDomain number: ").strip()
    try:
        idx = int(domainIdx) - 1
        if idx < 0 or idx >= len(domains):
            print("[-] Invalid domain selection: index out of range")
            return
        domainId = domains[idx].get('id')
        if not domainId:
            print("[-] Invalid domain selection: domain ID not found")
            return
    except ValueError:
        print("[-] Invalid domain selection: please enter a number")
        return
    except (IndexError, KeyError, AttributeError) as e:
        print(f"[-] Invalid domain selection: {str(e)}")
        return
    
    # List objects
    print(f"\nFetching {objectType}s...")
    result = veriniceTool.listObjects(objectType, domainId)
    
    if result.get('success'):
        objects = result.get('objects', [])
        print(f"\n[+] Found {len(objects)} {objectType}(s)")
        for obj in objects:
            print(f"   - {obj.get('name', 'Unknown')} (ID: {obj.get('id')})")
    else:
        print(f"\n[-] Failed to list {objectType}s: {result.get('error', 'Unknown error')}")

def viewVeriniceObject(executor, agent, objectType=None):
    """View Verinice object details"""
    print("\n" + "=" * 70)
    print("View Verinice Object Details")
    print("=" * 70)
    
    veriniceTool = None
    try:
        from tools.veriniceTool import VeriniceTool
        veriniceTool = VeriniceTool()
        if not veriniceTool._checkClient():
            print("[-] Verinice client not available. Check configuration.")
            return
    except Exception as e:
        print(f"[-] Verinice tool not available: {e}")
        return
    
    if not objectType:
        print("\nAvailable object types: scope, asset, control, process, person, scenario, incident, document")
        objectType = input("Object type: ").strip().lower()
    
    if not objectType or objectType not in ['scope', 'asset', 'control', 'process', 'person', 'scenario', 'incident', 'document']:
        print("[-] Invalid object type")
        return
    
    domainsResult = veriniceTool.listDomains()
    if not domainsResult.get('success') or not domainsResult.get('domains'):
        print("[-] No domains available")
        return
    
    domains = domainsResult['domains']
    print("\nAvailable domains:")
    for idx, domain in enumerate(domains, 1):
        name = domain.get('name', 'Unknown')
        domainId = domain.get('id')
        templateVersion = domain.get('templateVersion', 'N/A')
        authority = domain.get('authority', 'N/A')
        createdAt = domain.get('createdAt', '')
        if createdAt:
            # Extract date part (YYYY-MM-DD)
            datePart = createdAt.split('T')[0] if 'T' in createdAt else createdAt[:10]
        else:
            datePart = 'N/A'
        print(f"  {idx}. {name} (v{templateVersion}, {authority}, created: {datePart})")
        print(f"      ID: {domainId}")
    
    domainIdx = input("\nDomain number: ").strip()
    try:
        domainId = domains[int(domainIdx) - 1].get('id')
    except:
        print("[-] Invalid domain selection")
        return
    
    objectId = input(f"\n{objectType.capitalize()} ID: ").strip()
    if not objectId:
        print("[-] Object ID is required")
        return
    
    print(f"\nFetching {objectType} details...")
    result = veriniceTool.getObject(objectType, domainId, objectId)
    
    if result.get('success'):
        obj = result.get('data', {})
        print(f"\n[+] Object Details:")
        print(f"   Name: {obj.get('name', 'Unknown')}")
        print(f"   ID: {obj.get('id', 'Unknown')}")
        if obj.get('description'):
            print(f"   Description: {obj.get('description')}")
        if obj.get('subType'):
            print(f"   SubType: {obj.get('subType')}")
        if obj.get('status'):
            print(f"   Status: {obj.get('status')}")
    else:
        print(f"\n[-] Failed to get object: {result.get('error', 'Unknown error')}")

def updateVeriniceObject(executor, agent, objectType=None):
    """Update a Verinice object"""
    print("\n" + "=" * 70)
    print("Update Verinice Object")
    print("=" * 70)
    print("[!]️  Update functionality - use chat mode for interactive updates")
    print("   Or use: 'update <objectType> <objectId> <field> <value>' in chat")

def deleteVeriniceObject(executor, agent, objectType=None):
    """Delete a Verinice object"""
    print("\n" + "=" * 70)
    print("Delete Verinice Object")
    print("=" * 70)
    
    veriniceTool = None
    try:
        from tools.veriniceTool import VeriniceTool
        veriniceTool = VeriniceTool()
        if not veriniceTool._checkClient():
            print("[-] Verinice client not available. Check configuration.")
            return
    except Exception as e:
        print(f"[-] Verinice tool not available: {e}")
        return
    
    if not objectType:
        print("\nAvailable object types: scope, asset, control, process, person, scenario, incident, document")
        objectType = input("Object type: ").strip().lower()
    
    if not objectType or objectType not in ['scope', 'asset', 'control', 'process', 'person', 'scenario', 'incident', 'document']:
        print("[-] Invalid object type")
        return
    
    domainsResult = veriniceTool.listDomains()
    if not domainsResult.get('success') or not domainsResult.get('domains'):
        print("[-] No domains available")
        return
    
    domains = domainsResult['domains']
    print("\nAvailable domains:")
    for idx, domain in enumerate(domains, 1):
        name = domain.get('name', 'Unknown')
        domainId = domain.get('id')
        templateVersion = domain.get('templateVersion', 'N/A')
        authority = domain.get('authority', 'N/A')
        createdAt = domain.get('createdAt', '')
        if createdAt:
            # Extract date part (YYYY-MM-DD)
            datePart = createdAt.split('T')[0] if 'T' in createdAt else createdAt[:10]
        else:
            datePart = 'N/A'
        print(f"  {idx}. {name} (v{templateVersion}, {authority}, created: {datePart})")
        print(f"      ID: {domainId}")
    
    domainIdx = input("\nDomain number: ").strip()
    try:
        domainId = domains[int(domainIdx) - 1].get('id')
    except:
        print("[-] Invalid domain selection")
        return
    
    objectId = input(f"\n{objectType.capitalize()} ID to delete: ").strip()
    if not objectId:
        print("[-] Object ID is required")
        return
    
    confirm = input(f"\n[!]️  Are you sure you want to delete {objectType} {objectId}? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("[-] Deletion cancelled")
        return
    
    print(f"\nDeleting {objectType}...")
    result = veriniceTool.deleteObject(objectType, domainId, objectId)
    
    if result.get('success'):
        print(f"\n[+] Successfully deleted {objectType}: {objectId}")
    else:
        print(f"\n[-] Failed to delete {objectType}: {result.get('error', 'Unknown error')}")

def generateVeriniceReport(executor, agent):
    """Generate a Verinice report"""
    print("\n" + "=" * 70)
    print("Generate Verinice Report")
    print("=" * 70)
    
    veriniceTool = None
    try:
        from tools.veriniceTool import VeriniceTool
        veriniceTool = VeriniceTool()
        if not veriniceTool._checkClient():
            print("[-] Verinice client not available. Check configuration.")
            return
    except Exception as e:
        print(f"[-] Verinice tool not available: {e}")
        return
    
    domainsResult = veriniceTool.listDomains()
    if not domainsResult.get('success') or not domainsResult.get('domains'):
        print("[-] No domains available")
        return
    
    domains = domainsResult['domains']
    print("\nAvailable domains:")
    for idx, domain in enumerate(domains, 1):
        name = domain.get('name', 'Unknown')
        domainId = domain.get('id')
        templateVersion = domain.get('templateVersion', 'N/A')
        authority = domain.get('authority', 'N/A')
        createdAt = domain.get('createdAt', '')
        if createdAt:
            # Extract date part (YYYY-MM-DD)
            datePart = createdAt.split('T')[0] if 'T' in createdAt else createdAt[:10]
        else:
            datePart = 'N/A'
        print(f"  {idx}. {name} (v{templateVersion}, {authority}, created: {datePart})")
        print(f"      ID: {domainId}")
    
    domainIdx = input("\nDomain number: ").strip()
    try:
        domainId = domains[int(domainIdx) - 1].get('id')
    except:
        print("[-] Invalid domain selection")
        return
    
    # List reports
    print("\nFetching available reports...")
    reportsResult = veriniceTool.listReports(domainId)
    
    if not reportsResult.get('success') or not reportsResult.get('reports'):
        print("[-] No reports available")
        return
    
    reports = reportsResult['reports']
    print("\nAvailable reports:")
    for idx, report in enumerate(reports, 1):
        name = report.get('name', {})
        if isinstance(name, dict):
            name = name.get('en', name.get('de', 'Unknown'))
        print(f"  {idx}. {name} (ID: {report.get('id')})")
    
    reportIdx = input("\nReport number: ").strip()
    try:
        reportId = reports[int(reportIdx) - 1].get('id')
    except:
        print("[-] Invalid report selection")
        return
    
    # Generate report
    print(f"\nGenerating report...")
    result = veriniceTool.generateReport(domainId, reportId)
    
    if result.get('success'):
        print(f"\n[+] Report generated successfully")
        print(f"   Report ID: {reportId}")
    else:
        print(f"\n[-] Failed to generate report: {result.get('error', 'Unknown error')}")

def listVeriniceReports(executor, agent):
    """List Verinice reports"""
    print("\n" + "=" * 70)
    print("List Verinice Reports")
    print("=" * 70)
    
    veriniceTool = None
    try:
        from tools.veriniceTool import VeriniceTool
        veriniceTool = VeriniceTool()
        if not veriniceTool._checkClient():
            print("[-] Verinice client not available. Check configuration.")
            return
    except Exception as e:
        print(f"[-] Verinice tool not available: {e}")
        return
    
    domainsResult = veriniceTool.listDomains()
    if not domainsResult.get('success') or not domainsResult.get('domains'):
        print("[-] No domains available")
        return
    
    domains = domainsResult['domains']
    print("\nAvailable domains:")
    for idx, domain in enumerate(domains, 1):
        name = domain.get('name', 'Unknown')
        domainId = domain.get('id')
        templateVersion = domain.get('templateVersion', 'N/A')
        authority = domain.get('authority', 'N/A')
        createdAt = domain.get('createdAt', '')
        if createdAt:
            # Extract date part (YYYY-MM-DD)
            datePart = createdAt.split('T')[0] if 'T' in createdAt else createdAt[:10]
        else:
            datePart = 'N/A'
        print(f"  {idx}. {name} (v{templateVersion}, {authority}, created: {datePart})")
        print(f"      ID: {domainId}")
    
    domainIdx = input("\nDomain number: ").strip()
    try:
        domainId = domains[int(domainIdx) - 1].get('id')
    except:
        print("[-] Invalid domain selection")
        return
    
    # List reports
    print(f"\nFetching reports...")
    result = veriniceTool.listReports(domainId)
    
    if result.get('success'):
        reports = result.get('reports', [])
        print(f"\n[+] Found {len(reports)} report(s)")
        for report in reports:
            name = report.get('name', {})
            if isinstance(name, dict):
                name = name.get('en', name.get('de', 'Unknown'))
            print(f"   - {name} (ID: {report.get('id')})")
    else:
        print(f"\n[-] Failed to list reports: {result.get('error', 'Unknown error')}")


def listVeriniceDomains(executor, agent):
    """List Verinice domains"""
    print("\n" + "=" * 70)
    print("List Verinice Domains")
    print("=" * 70)
    
    veriniceTool = None
    try:
        from tools.veriniceTool import VeriniceTool
        veriniceTool = VeriniceTool()
        if not veriniceTool._checkClient():
            print("[-] Verinice client not available. Check configuration.")
            return
    except Exception as e:
        print(f"[-] Verinice tool not available: {e}")
        return
    
    print("\nFetching domains...")
    result = veriniceTool.listDomains()
    
    if result.get('success'):
        domains = result.get('domains', [])
        print(f"\n[+] Found {len(domains)} domain(s)")
        for domain in domains:
            name = domain.get('name', 'Unknown')
            domainId = domain.get('id')
            templateVersion = domain.get('templateVersion', 'N/A')
            authority = domain.get('authority', 'N/A')
            createdAt = domain.get('createdAt', '')
            if createdAt:
                datePart = createdAt.split('T')[0] if 'T' in createdAt else createdAt[:10]
            else:
                datePart = 'N/A'
            print(f"   - {name} (v{templateVersion}, {authority}, created: {datePart})")
            print(f"     ID: {domainId}")
            if domain.get('abbreviation'):
                print(f"     Abbreviation: {domain.get('abbreviation')}")
            if domain.get('description'):
                desc = domain.get('description', '')[:80]
                print(f"     Description: {desc}...")
    else:
        print(f"\n[-] Failed to list domains: {result.get('error', 'Unknown error')}")

def listVeriniceUnits(executor, agent):
    """List Verinice units"""
    print("\n" + "=" * 70)
    print("List Verinice Units")
    print("=" * 70)
    
    veriniceTool = None
    try:
        from tools.veriniceTool import VeriniceTool
        veriniceTool = VeriniceTool()
        if not veriniceTool._checkClient():
            print("[-] Verinice client not available. Check configuration.")
            return
    except Exception as e:
        print(f"[-] Verinice tool not available: {e}")
        return
    
    print("\nFetching units...")
    result = veriniceTool.listUnits()
    
    if result.get('success'):
        units = result.get('units', [])
        print(f"\n[+] Found {len(units)} unit(s)")
        for unit in units:
            print(f"   - {unit.get('name', 'Unknown')} (ID: {unit.get('id')})")
            if unit.get('description'):
                print(f"     Description: {unit.get('description')[:100]}...")
    else:
        print(f"\n[-] Failed to list units: {result.get('error', 'Unknown error')}")

def createVeriniceDomain(executor, agent):
    """Create domain from template"""
    print("\n" + "=" * 70)
    print("Create Domain from Template")
    print("=" * 70)
    
    veriniceTool = None
    if hasattr(agent, '_veriniceTool') and agent._veriniceTool and agent._veriniceTool._checkClient():
        veriniceTool = agent._veriniceTool
    else:
        try:
            from tools.veriniceTool import VeriniceTool
            veriniceTool = VeriniceTool()
            if not veriniceTool._checkClient():
                print("[-] Verinice client not available. Check configuration.")
                return
        except Exception as e:
            print(f"[-] Verinice tool not available: {e}")
            return
    
    print("\nFetching domain templates...")
    templatesResult = veriniceTool.getDomainTemplates()
    
    if not templatesResult.get('success') or not templatesResult.get('templates'):
        print("[-] No templates available")
        return
    
    templates = templatesResult['templates']
    print(f"\n[+] Found {len(templates)} template(s):")
    for idx, template in enumerate(templates, 1):
        name = template.get('name', 'Unknown')
        templateId = template.get('id')
        version = template.get('templateVersion', 'N/A')
        authority = template.get('authority', 'N/A')
        print(f"  {idx}. {name} (v{version}, {authority})")
        print(f"      ID: {templateId}")
    
    templateIdx = input("\nTemplate number: ").strip()
    try:
        templateId = templates[int(templateIdx) - 1].get('id')
    except:
        print("[-] Invalid template selection")
        return
    
    print(f"\nCreating domain from template...")
    result = veriniceTool.createDomain(templateId)
    
    if result.get('success'):
        domain = result.get('domain', {})
        print(f"\n[+] Successfully created domain!")
        print(f"   Domain ID: {result.get('domainId')}")
        print(f"   Name: {domain.get('name', 'N/A')}")
    else:
        print(f"\n[-] Failed to create domain: {result.get('error', 'Unknown error')}")

def deleteVeriniceDomain(executor, agent):
    """Delete a domain"""
    print("\n" + "=" * 70)
    print("Delete Domain")
    print("=" * 70)
    
    veriniceTool = None
    if hasattr(agent, '_veriniceTool') and agent._veriniceTool and agent._veriniceTool._checkClient():
        veriniceTool = agent._veriniceTool
    else:
        try:
            from tools.veriniceTool import VeriniceTool
            veriniceTool = VeriniceTool()
            if not veriniceTool._checkClient():
                print("[-] Verinice client not available. Check configuration.")
                return
        except Exception as e:
            print(f"[-] Verinice tool not available: {e}")
            return
    
    # List domains
    domainsResult = veriniceTool.listDomains()
    if not domainsResult.get('success') or not domainsResult.get('domains'):
        print("[-] No domains available")
        return
    
    domains = domainsResult['domains']
    print("\nAvailable domains:")
    for idx, domain in enumerate(domains, 1):
        name = domain.get('name', 'Unknown')
        domainId = domain.get('id')
        print(f"  {idx}. {name} (ID: {domainId})")
    
    domainIdx = input("\nDomain number: ").strip()
    try:
        domainId = domains[int(domainIdx) - 1].get('id')
        domainName = domains[int(domainIdx) - 1].get('name', 'Unknown')
    except:
        print("[-] Invalid domain selection")
        return
    
    confirm = input(f"\n⚠️  Are you sure you want to delete domain '{domainName}' ({domainId})? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("[-] Deletion cancelled")
        return
    
    print(f"\nDeleting domain...")
    result = veriniceTool.deleteDomain(domainId)
    
    if result.get('success'):
        print(f"\n[+] Successfully deleted domain: {domainName}")
    else:
        print(f"\n[-] Failed to delete domain: {result.get('error', 'Unknown error')}")

def listVeriniceDomainTemplates(executor, agent):
    """List domain templates"""
    print("\n" + "=" * 70)
    print("List Domain Templates")
    print("=" * 70)
    
    veriniceTool = None
    if hasattr(agent, '_veriniceTool') and agent._veriniceTool and agent._veriniceTool._checkClient():
        veriniceTool = agent._veriniceTool
    else:
        try:
            from tools.veriniceTool import VeriniceTool
            veriniceTool = VeriniceTool()
            if not veriniceTool._checkClient():
                print("[-] Verinice client not available. Check configuration.")
                return
        except Exception as e:
            print(f"[-] Verinice tool not available: {e}")
            return
    
    print("\nFetching templates...")
    result = veriniceTool.getDomainTemplates()
    
    if result.get('success'):
        templates = result.get('templates', [])
        print(f"\n[+] Found {len(templates)} template(s):")
        for template in templates:
            name = template.get('name', 'Unknown')
            templateId = template.get('id')
            version = template.get('templateVersion', 'N/A')
            authority = template.get('authority', 'N/A')
            print(f"   - {name} (v{version}, {authority})")
            print(f"     ID: {templateId}")
            if template.get('description'):
                desc = template.get('description', '')[:80]
                print(f"     Description: {desc}...")
    else:
        print(f"\n[-] Failed to list templates: {result.get('error', 'Unknown error')}")

def showVeriniceDomainSubTypes(executor, agent):
    """Show subtypes for a domain"""
    print("\n" + "=" * 70)
    print("Show Domain SubTypes")
    print("=" * 70)
    
    veriniceTool = None
    if hasattr(agent, '_veriniceTool') and agent._veriniceTool and agent._veriniceTool._checkClient():
        veriniceTool = agent._veriniceTool
    else:
        try:
            from tools.veriniceTool import VeriniceTool
            veriniceTool = VeriniceTool()
            if not veriniceTool._checkClient():
                print("[-] Verinice client not available. Check configuration.")
                return
        except Exception as e:
            print(f"[-] Verinice tool not available: {e}")
            return
    
    domainsResult = veriniceTool.listDomains()
    if not domainsResult.get('success') or not domainsResult.get('domains'):
        print("[-] No domains available")
        return
    
    domains = domainsResult['domains']
    print("\nAvailable domains:")
    for idx, domain in enumerate(domains, 1):
        name = domain.get('name', 'Unknown')
        domainId = domain.get('id')
        print(f"  {idx}. {name} (ID: {domainId})")
    
    domainIdx = input("\nDomain number: ").strip()
    try:
        domainId = domains[int(domainIdx) - 1].get('id')
        domainName = domains[int(domainIdx) - 1].get('name', 'Unknown')
    except:
        print("[-] Invalid domain selection")
        return
    
    print(f"\nFetching subtypes for {domainName}...")
    result = veriniceTool.getDomainSubTypes(domainId)
    
    if result.get('success'):
        subtypes = result.get('subTypes', {})
        total = result.get('totalCount', 0)
        print(f"\n[+] Found {total} subtype(s) across all object types:")
        for objType, typeSubtypes in subtypes.items():
            if typeSubtypes:
                print(f"\n   {objType.upper()}: {len(typeSubtypes)} subtype(s)")
                for st in typeSubtypes:
                    print(f"      - {st}")
    else:
        print(f"\n[-] Failed to get subtypes: {result.get('error', 'Unknown error')}")

def createVeriniceUnit(executor, agent):
    """Create a new unit"""
    print("\n" + "=" * 70)
    print("Create Unit")
    print("=" * 70)
    
    veriniceTool = None
    if hasattr(agent, '_veriniceTool') and agent._veriniceTool and agent._veriniceTool._checkClient():
        veriniceTool = agent._veriniceTool
    else:
        try:
            from tools.veriniceTool import VeriniceTool
            veriniceTool = VeriniceTool()
            if not veriniceTool._checkClient():
                print("[-] Verinice client not available. Check configuration.")
                return
        except Exception as e:
            print(f"[-] Verinice tool not available: {e}")
            return
    
    name = input("\nUnit name: ").strip()
    if not name:
        print("[-] Name is required")
        return
    
    description = input("Description (optional): ").strip()
    
    domainIds = []
    domainsResult = veriniceTool.listDomains()
    if domainsResult.get('success') and domainsResult.get('domains'):
        domains = domainsResult['domains']
        print("\nAvailable domains (optional - press Enter to skip):")
        for idx, domain in enumerate(domains, 1):
            print(f"  {idx}. {domain.get('name', 'Unknown')} (ID: {domain.get('id')})")
        
        domainInput = input("\nDomain numbers (comma-separated, or Enter for none): ").strip()
        if domainInput:
            try:
                indices = [int(x.strip()) - 1 for x in domainInput.split(',')]
                domainIds = [domains[i].get('id') for i in indices if 0 <= i < len(domains)]
            except:
                print("[!] Invalid domain selection, creating unit without domains")
    
    print(f"\nCreating unit...")
    result = veriniceTool.createUnit(name, description, domainIds if domainIds else None)
    
    if result.get('success'):
        print(f"\n[+] Successfully created unit: {name}")
        print(f"   Unit ID: {result.get('unitId')}")
    else:
        print(f"\n[-] Failed to create unit: {result.get('error', 'Unknown error')}")

def listVeriniceRiskDefinitions(executor, agent):
    """List risk definitions in a domain"""
    print("\n" + "=" * 70)
    print("List Risk Definitions")
    print("=" * 70)
    
    veriniceTool = None
    if hasattr(agent, '_veriniceTool') and agent._veriniceTool and agent._veriniceTool._checkClient():
        veriniceTool = agent._veriniceTool
    else:
        try:
            from tools.veriniceTool import VeriniceTool
            veriniceTool = VeriniceTool()
            if not veriniceTool._checkClient():
                print("[-] Verinice client not available. Check configuration.")
                return
        except Exception as e:
            print(f"[-] Verinice tool not available: {e}")
            return
    
    domainsResult = veriniceTool.listDomains()
    if not domainsResult.get('success') or not domainsResult.get('domains'):
        print("[-] No domains available")
        return
    
    domains = domainsResult['domains']
    print("\nAvailable domains:")
    for idx, domain in enumerate(domains, 1):
        name = domain.get('name', 'Unknown')
        domainId = domain.get('id')
        print(f"  {idx}. {name} (ID: {domainId})")
    
    domainIdx = input("\nDomain number: ").strip()
    try:
        domainId = domains[int(domainIdx) - 1].get('id')
        domainName = domains[int(domainIdx) - 1].get('name', 'Unknown')
    except:
        print("[-] Invalid domain selection")
        return
    
    print(f"\nFetching risk definitions for {domainName}...")
    result = veriniceTool.listRiskDefinitions(domainId)
    
    if result.get('success'):
        riskDefs = result.get('riskDefinitions', [])
        print(f"\n[+] Found {len(riskDefs)} risk definition(s):")
        for rd in riskDefs:
            rdId = rd.get('id', 'Unknown')
            print(f"   - {rdId}")
    else:
        print(f"\n[-] Failed to list risk definitions: {result.get('error', 'Unknown error')}")
        print("   Note: Domain may not have risk definitions configured")

def showSystemFlow():
    """Explain the system logic flow"""
    print("\n" + "=" * 70)
    print("System Logic Flow")
    print("=" * 70)
    print("""
1. User Input → Agent Executor
   └─> Executor receives task and input data

2. Agent Executor → ISMS Agent
   └─> Executor selects agent and calls agent.process()

3. ISMS Agent analyzes input:
   └─> If text message → _processChatMessage()
       └─> Routes to appropriate ISMS operation handler

4. Tool Execution
   └─> Tool performs operation and returns result

5. Result Formatting
   └─> Agent formats result with status and data

6. Return to Executor
   └─> Logs execution and returns to user
""")
    print("=" * 70)

def chatWithLLM(executor, agent):
    """Chat with LLM in continuous conversation mode with action execution"""
    clearScreen()
    print("=" * 70)
    print("Chat Mode - Type 'exit' or 'back' to return to menu")
    print("You can ask questions or give commands like 'show capabilities', 'list scopes', etc.")
    print("=" * 70)
    print()
    
    while True:
        message = input("# ").strip()
        
        if not message:
            continue
        
        if message.lower() in ['exit', 'back', 'quit', 'q']:
            print("\nExiting chat mode...")
            break
        
        # Send to agent
        try:
            result = executor.execute(
                task="Chat message",
                inputData=message
            )
            
            if result.get('success'):
                resultData = result.get('result', {})
                if isinstance(resultData, dict):
                    if resultData.get('type') == 'action':
                        action = resultData.get('action', {})
                        actionType = action.get('action')
                        # Extract objectType from action dict if available
                        detectedObjectType = action.get('objectType')
                        # Store action data for later use
                        actionData = action
                        
                        if actionType == 'show_capabilities':
                            print()
                            showCapabilities(agent, executor)
                            print()
                        elif actionType == 'check_llm_status':
                            print()
                            checkLLMStatus()
                            print()
                        elif actionType == 'show_state':
                            print()
                            showAgentState(agent, executor)
                            print()
                        elif actionType == 'test_workflow':
                            print()
                            testWorkflow(executor)
                            print()
                        elif actionType == 'show_system_flow':
                            print()
                            showSystemFlow()
                            print()
                        elif actionType == 'manage_agents':
                            print()
                            manageAgents(executor)
                            print()
                        elif actionType.startswith('verinice_'):
                            print(f">>> Executing Verinice operation: {actionType}\n")
                            if detectedObjectType:
                                print(f">>> Detected object type: {detectedObjectType}\n")
                            if not hasattr(agent, '_veriniceTool') or not agent._veriniceTool or not agent._veriniceTool._checkClient():
                                print(f">>> [-] Verinice client not available. Check Keycloak/API configuration.\n")
                                print(f">>> Make sure Verinice server is running and properly configured.\n")
                            else:
                                try:
                                    if actionType == 'verinice_create':
                                        createVeriniceObject(executor, agent, objectType=detectedObjectType)
                                    elif actionType == 'verinice_list':
                                        listVeriniceObjects(executor, agent, objectType=detectedObjectType)
                                    elif actionType == 'verinice_view':
                                        viewVeriniceObject(executor, agent, objectType=detectedObjectType)
                                    elif actionType == 'verinice_update':
                                        updateVeriniceObject(executor, agent, objectType=detectedObjectType)
                                    elif actionType == 'verinice_delete':
                                        deleteVeriniceObject(executor, agent, objectType=detectedObjectType)
                                    elif actionType == 'verinice_generate_report':
                                        generateVeriniceReport(executor, agent)
                                    elif actionType == 'verinice_list_reports':
                                        listVeriniceReports(executor, agent)
                                    elif actionType == 'verinice_list_domains':
                                        listVeriniceDomains(executor, agent)
                                    elif actionType == 'verinice_list_units':
                                        listVeriniceUnits(executor, agent)
                                    else:
                                        print(f">>> Unknown Verinice action: {actionType}\n")
                                        print(f">>> Available: create, list, view, update, delete, generate report, list reports, list domains, list units\n")
                                except Exception as e:
                                    print(f">>> Error executing Verinice operation: {str(e)}\n")
                        else:
                            print(f">>> Unknown action: {actionType}\n")
                    
                    # Regular chat response
                    elif resultData.get('status') == 'success':
                        response = resultData.get('result', '')
                        print(f">>> {response}\n")
                    else:
                        errorMsg = resultData.get('error', 'Unknown error')
                        # Clean error display - don't show verbose LLM errors
                        if "LLM" in errorMsg and ("quota" in errorMsg.lower() or "404" in errorMsg or "unavailable" in errorMsg.lower()):
                            print(f">>> {errorMsg}\n")
                        else:
                            print(f">>> Error: {errorMsg}\n")
                else:
                    if isinstance(resultData, dict):
                        print(f">>> {resultData}\n")
                    else:
                        print(f">>> {resultData}\n")
            else:
                errorMsg = result.get('error')
                if errorMsg is None or errorMsg == 'Unknown error':
                    # Try to get more info from result
                    resultData = result.get('result', {})
                    if isinstance(resultData, dict):
                        if resultData.get('status') == 'error':
                            errorMsg = resultData.get('error', 'Unknown error')
                        else:
                            # Maybe result structure is different
                            print(f">>> Debug: result keys = {list(result.keys())}")
                            print(f">>> Debug: resultData keys = {list(resultData.keys()) if isinstance(resultData, dict) else 'not a dict'}")
                            errorMsg = 'Unknown error - check debug output above'
                
                # Clean error display with helpful suggestions
                if not errorMsg or errorMsg == 'Unknown error':
                    print(f">>> I'm not sure how to respond to that. Try:\n")
                    print(f">>>   - 'show capabilities' to see what I can do\n")
                    print(f">>>   - 'yes' if I asked you something\n")
                elif "LLM" in errorMsg:
                    print(f">>> LLM service unavailable. I can still help with ISMS operations!\n")
                    print(f">>> Try: 'show capabilities' or 'check LLM status'\n")
                else:
                    print(f">>> {errorMsg}\n")
        except Exception as e:
            import traceback
            errorMsg = str(e)
            print(f">>> Exception occurred: {errorMsg}\n")
            # Only show traceback in debug mode - for now just show helpful message
            print(f">>> Sorry boss, something went wrong. Try: 'show capabilities'\n")
    
    print("=" * 70)

def showAgentState(agent, executor):
    """Show agent state and history"""
    print("\n" + "=" * 70)
    print("Agent State & History")
    print("=" * 70)
    print(f"\nAgent State:")
    for key, value in agent.state.items():
        if key == 'lastProcessed':
            if isinstance(value, dict):
                if 'sheets' in value:
                    print(f"  {key}: {len(value.get('sheets', {}))} sheets")
                else:
                    print(f"  {key}: {len(value.get('data', []))} rows")
            else:
                print(f"  {key}: {value}")
        else:
            print(f"  {key}: {value}")
    
    print(f"\nAgent History ({len(agent.history)} actions):")
    for i, action in enumerate(agent.history[-5:], 1):  # Show last 5
        print(f"  {i}. {action.get('action', 'unknown')} - {action.get('tool', 'N/A')}")
    
    print(f"\nExecution History ({len(executor.executionHistory)} tasks):")
    for i, record in enumerate(executor.executionHistory[-5:], 1):  # Show last 5
        print(f"  {i}. {record.get('task', 'N/A')} - Status: {record.get('status', 'unknown')}")
    print("=" * 70)

def testWorkflow(executor):
    """Test multi-step workflow"""
    print("\n" + "=" * 70)
    print("Testing Multi-Step Workflow")
    print("=" * 70)
    

def main():
    """Main execution with interactive menu"""
    # Clear screen for clean interface
    clearScreen()
    
    print("=" * 70)
    print("Agentic Framework - ISMS Agent")
    print("=" * 70)
    
    configStatus = Settings.validate()
    if not configStatus['valid']:
        print("[-] Configuration errors:")
        for error in configStatus['errors']:
            print(f"  - {error}")
        return
    
    if configStatus['warnings']:
        print("[!] Warnings:")
        for warning in configStatus['warnings']:
            print(f"  - {warning}")
    
    # Setup agent
    print("\nSetting up agent...")
    agent = setupAgent()
    
    executor = AgentExecutor([agent])
    
    # Link executor to agent for state awareness
    agent.executor = executor
    
    # Interactive mode only
    
    print("\n" + "=" * 70)
    print("Agent setup complete. Ready for use.")
    print("=" * 70)
    
    # Interactive mode
    print("\n[+] Agent ready! Entering interactive mode...")
    
    while True:
        printMenu()
        choice = input("\nSelect an option (0-25): ").strip()
        
        if choice == '0':
            print("\nExiting... Goodbye!")
            break
        elif choice == '3':
            chatWithLLM(executor, agent)
        elif choice == '4':
            createVeriniceObject(executor, agent)
        elif choice == '5':
            listVeriniceObjects(executor, agent)
        elif choice == '6':
            viewVeriniceObject(executor, agent)
        elif choice == '7':
            updateVeriniceObject(executor, agent)
        elif choice == '8':
            deleteVeriniceObject(executor, agent)
        elif choice == '10':
            listVeriniceDomains(executor, agent)
        elif choice == '11':
            createVeriniceDomain(executor, agent)
        elif choice == '12':
            deleteVeriniceDomain(executor, agent)
        elif choice == '13':
            listVeriniceDomainTemplates(executor, agent)
        elif choice == '14':
            showVeriniceDomainSubTypes(executor, agent)
        elif choice == '15':
            listVeriniceUnits(executor, agent)
        elif choice == '16':
            createVeriniceUnit(executor, agent)
        elif choice == '17':
            listVeriniceReports(executor, agent)
        elif choice == '18':
            generateVeriniceReport(executor, agent)
        elif choice == '19':
            listVeriniceRiskDefinitions(executor, agent)
        elif choice == '20':
            try:
                showCapabilities(agent, executor)
            except Exception as e:
                print(f"\n[-] Error: {e}")
                import traceback
                traceback.print_exc()
        elif choice == '21':
            try:
                showAgentState(agent, executor)
            except Exception as e:
                print(f"\n[-] Error: {e}")
                import traceback
                traceback.print_exc()
        elif choice == '22':
            try:
                testWorkflow(executor)
            except Exception as e:
                print(f"\n[-] Error: {e}")
                import traceback
                traceback.print_exc()
        elif choice == '23':
            try:
                showSystemFlow()
            except Exception as e:
                print(f"\n[-] Error: {e}")
                import traceback
                traceback.print_exc()
        elif choice == '24':
            try:
                checkLLMStatus()
            except Exception as e:
                print(f"\n[-] Error: {e}")
                import traceback
                traceback.print_exc()
        elif choice == '25':
            try:
                manageAgents(executor)
            except Exception as e:
                print(f"\n[-] Error: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("[!] Invalid option. Please select 0-25.")


if __name__ == "__main__":
    main()

