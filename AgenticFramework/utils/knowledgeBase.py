"""
Knowledge Base Fallback System

Provides accurate, friendly responses for common ISMS questions when LLM is unavailable.
"""

from typing import Dict, Optional, List
import re
import logging

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Fallback knowledge base for ISMS questions"""
    
    def __init__(self):
        self.knowledge = self._load_knowledge()
    
    def _load_knowledge(self) -> Dict:
        """Load knowledge base"""
        return {
            # ISO 27001 questions
            'iso27001': {
                'patterns': [
                    r'what\s+is\s+iso\s*27001',
                    r'what\s+is\s+iso27001',
                    r'iso\s*27001',
                    r'iso27001\s+standard'
                ],
                'response': """ISO 27001 is an international standard for Information Security Management Systems (ISMS).

**Key Points:**
• Provides a framework for establishing, implementing, maintaining, and continually improving an ISMS
• Helps organizations manage information security risks
• Includes requirements for risk assessment, security controls, and continuous improvement
• Can be certified by third-party auditors

**In this ISMS system, you can:**
• Create and manage scopes (organizational boundaries)
• Link assets, controls, and processes to scopes
• Track compliance and generate reports
• Manage risks and security measures

Try: `list scopes` to see your current ISMS structure."""
            },
            
            # How to create scope
            'create_scope': {
                'patterns': [
                    r'how\s+to\s+create\s+scope',
                    r'how\s+do\s+i\s+create\s+scope',
                    r'create\s+scope\s+in\s+isms',
                    r'how\s+can\s+i\s+create\s+scope'
                ],
                'response': """To create a scope in the ISMS system, use this command:

**Command Format:**
```
create scope <Name> <Abbreviation> "<Description>"
```

**Example:**
```
create scope ProductionEnvironment PROD "Production environment scope"
```

**What you need:**
• **Name**: The full name of the scope (e.g., "Production Environment")
• **Abbreviation**: Short code (e.g., "PROD")
• **Description**: Brief description of what this scope covers

**After creating a scope, you can:**
• Link assets to it: `link DesktopComputer to ProductionEnvironment`
• Link controls: `link A.8.1.1 to ProductionEnvironment`
• Link people: `link JohnDoe to ProductionEnvironment`
• View it: `get scope ProductionEnvironment`

Try it now: `create scope TestScope TS "Test scope"`"""
            },
            
            # How to create asset
            'create_asset': {
                'patterns': [
                    r'how\s+to\s+create\s+asset',
                    r'how\s+do\s+i\s+create\s+asset',
                    r'create\s+asset\s+in\s+isms'
                ],
                'response': """To create an asset in the ISMS system:

**Command Format:**
```
create asset <Name> <Abbreviation> "<Description>" subType <SubType>
```

**Example:**
```
create asset Server01 SRV01 "Production server" subType AST_IT-System
```

**Available Asset Subtypes:**
• `AST_IT-System` - IT Systems (servers, workstations)
• `AST_Datatype` - Data types
• `AST_Application` - Applications
• `AST_Process` - Business processes
• `AST_Service` - Services
• `AST_Building` - Buildings/facilities

**After creating an asset, you can:**
• Link it to a scope: `link Server01 to ProductionEnvironment`
• View it: `get asset Server01`
• List all assets: `list assets`

Try: `create asset MyServer MS "My server" subType AST_IT-System`"""
            },
            
            # How to link objects
            'link_objects': {
                'patterns': [
                    r'how\s+to\s+link',
                    r'how\s+do\s+i\s+link',
                    r'how\s+can\s+i\s+link',
                    r'link\s+objects\s+in\s+isms'
                ],
                'response': """To link objects in the ISMS system, you can use friendly commands:

**Friendly Commands (Recommended):**
• `add DesktopComputer to MyScope`
• `make Server01 part of ProductionScope`
• `put AssetName in ScopeName`
• `assign PersonName to ScopeName`

**Traditional Commands:**
• `link DesktopComputer to MyScope`
• `connect AssetName with ScopeName`

**Examples:**
```
add DesktopComputer to ProductionScope
make Server01 part of MyScope
link ControlA.8.1.1 to ProductionScope
```

**What can be linked:**
• Assets → Scopes
• Controls → Scopes
• Persons → Scopes
• Processes → Scopes
• Documents → Scopes

**Bulk Linking:**
• Link all IT-System assets: `link ProductionScope with IT-System assets`
• Link all Datatype assets: `link ProductionScope with Datatype assets`

Try: `add DesktopComputer to MyScope`"""
            },
            
            # What is ISMS
            'isms': {
                'patterns': [
                    r'what\s+is\s+isms',
                    r'what\s+is\s+an\s+isms',
                    r'information\s+security\s+management\s+system'
                ],
                'response': """ISMS stands for **Information Security Management System**.

**Definition:**
An ISMS is a systematic approach to managing sensitive company information so it remains secure. It includes people, processes, and IT systems.

**Key Components:**
• **Scopes**: Organizational boundaries where the ISMS applies
• **Assets**: Information assets (servers, data, applications)
• **Controls**: Security controls (ISO 27001 Annex A controls)
• **Risks**: Security risks and their treatment
• **Processes**: Business processes that handle information
• **Persons**: People responsible for security

**In this system:**
• Create scopes to define your organizational boundaries
• Link assets, controls, and processes to scopes
• Track compliance and generate reports
• Manage your security posture

Try: `list scopes` to see your current ISMS structure."""
            },
            
            # GDPR questions
            'gdpr': {
                'patterns': [
                    r'what\s+is\s+gdpr',
                    r'gdpr',
                    r'general\s+data\s+protection\s+regulation'
                ],
                'response': """GDPR stands for **General Data Protection Regulation**.

**Key Points:**
• EU regulation for data protection and privacy
• Applies to organizations processing EU citizens' personal data
• Requires data protection by design and by default
• Includes rights for data subjects (access, erasure, portability)
• Requires data breach notifications within 72 hours

**In ISMS context:**
GDPR compliance can be managed through:
• Data protection controls in your ISMS
• Privacy impact assessments
• Data processing records
• Breach management procedures

**Related ISMS Operations:**
• Create assets for personal data: `create asset PersonalData PD "Personal data asset" subType AST_Datatype`
• Link to scopes: `add PersonalData to EUOperationsScope`
• Track controls: `list controls`

For more specific GDPR questions, please check official GDPR documentation."""
            },
            
            # List operations
            'list_help': {
                'patterns': [
                    r'how\s+to\s+list',
                    r'how\s+do\s+i\s+list',
                    r'show\s+me\s+all',
                    r'what\s+scopes\s+do\s+i\s+have',
                    r'what\s+assets\s+do\s+i\s+have'
                ],
                'response': """To list objects in the ISMS system:

**Basic Commands:**
• `list scopes` - Show all scopes
• `list assets` - Show all assets
• `list persons` - Show all persons
• `list controls` - Show all controls
• `list processes` - Show all processes
• `list documents` - Show all documents

**Friendly Alternatives:**
• `show me all scopes`
• `display assets`
• `what scopes do I have`

**Filtered Lists:**
• `list assets subType AST_IT-System` - Only IT-System assets
• `list assets subType AST_Datatype` - Only Datatype assets

**Examples:**
```
list scopes
list assets
show me all controls
list assets subType AST_IT-System
```

Try: `list scopes` to see what you have."""
            },
            
            'get_object': {
                'patterns': [
                    r'how\s+to\s+view',
                    r'how\s+do\s+i\s+view',
                    r'how\s+to\s+get\s+details',
                    r'show\s+me\s+details\s+of'
                ],
                'response': """To view details of an object:

**Command Format:**
```
get <objectType> <Name>
```

**Examples:**
• `get scope MyScope`
• `get asset DesktopComputer`
• `get person JohnDoe`
• `get control A.8.1.1`

**What you'll see:**
• Object name and description
• Subtype (if applicable)
• Linked objects (what's connected to it)
• Creation date and other metadata

**Examples:**
```
get scope ProductionScope
get asset Server01
get person DataProtectionOfficer
```

Try: `get scope MyScope` to see details."""
            }
        }
    
    def find_answer(self, question: str) -> Optional[str]:
        """
        Find answer for a knowledge question.
        
        Args:
            question: User's question
            
        Returns:
            Answer string if found, None otherwise
        """
        question_lower = question.lower().strip()
        
        for key, entry in self.knowledge.items():
            patterns = entry.get('patterns', [])
            for pattern in patterns:
                if re.search(pattern, question_lower, re.IGNORECASE):
                    logger.info(f"Knowledge base match: {key} for question: {question[:50]}")
                    return entry.get('response')
        
        return None
    
    def is_operational_question(self, question: str) -> bool:
        """
        Check if question is about how to perform operations.
        
        Args:
            question: User's question
            
        Returns:
            True if it's an operational question
        """
        operational_patterns = [
            r'how\s+to\s+create',
            r'how\s+do\s+i\s+create',
            r'how\s+to\s+link',
            r'how\s+do\s+i\s+link',
            r'how\s+to\s+list',
            r'how\s+do\s+i\s+list',
            r'how\s+to\s+view',
            r'how\s+do\s+i\s+view',
            r'how\s+to\s+get',
            r'how\s+do\s+i\s+get',
            r'how\s+to\s+update',
            r'how\s+do\s+i\s+update',
            r'how\s+to\s+delete',
            r'how\s+do\s+i\s+delete',
            r'can\s+you\s+tell\s+me\s+how\s+to',
            r'can\s+you\s+show\s+me\s+how\s+to'
        ]
        
        question_lower = question.lower().strip()
        return any(re.search(pattern, question_lower, re.IGNORECASE) for pattern in operational_patterns)
    
    def get_operational_help(self, question: str) -> Optional[str]:
        """
        Get operational help based on question.
        
        Args:
            question: User's question
            
        Returns:
            Help text if available
        """
        # This will be enhanced to use ISMS coordinator for actual examples
        return self.find_answer(question)
