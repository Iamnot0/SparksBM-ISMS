# ISMS Object Types and Subtypes Mapping

## Main Object Types

The system supports the following **8 main object types** (from `ismsInstructions.json`):

| # | Object Type | Plural Form | Description |
|---|-------------|-------------|-------------|
| 1 | **scope** | scopes | Organizational scopes/contexts |
| 2 | **asset** | assets | Information assets (IT systems, data, etc.) |
| 3 | **control** | controls | Security controls (ISO 27001, etc.) |
| 4 | **process** | processes | Business processes |
| 5 | **person** | persons/people | People/roles in the organization |
| 6 | **scenario** | scenarios | Risk scenarios |
| 7 | **incident** | incidents | Security incidents |
| 8 | **document** | documents | Documents/reports |

## Subtypes by Object Type

### 1. SCOPE Subtypes

**Subtypes:**
1. **All** (shows all scopes)
2. **Scopes** (default scope type)
3. **Processors** (Data processors)
4. **Controllers** (Data controllers)
5. **Joint controllerships** (Joint controllers)
6. **Controllers, Art. 4 Nr.7** (Controllers per Article 4 Number 7)

**Subtype Names → Technical IDs:**
- "Scopes" → `SCP_Scope`
- "Processors" → `SCP_Processor`
- "Controllers" → `SCP_Controller`
- "Joint controllerships" / "Joint Controllerships" → `SCP_JointController`
- "Controllers, Art. 4 Nr.7" → `SCP_Controller` (with specific article reference)

**User Input Examples:**
- "create Controller named 'MFA for VPN'" → Creates scope with `SCP_Controller` subtype
- "create Controllers named 'X'" → Creates scope with `SCP_Controller` subtype
- "create Joint controllership named 'X'" → Creates scope with `SCP_JointController` subtype
- "create Processor named 'X'" → Creates scope with `SCP_Processor` subtype

**Subtype Mapping (from `ismsInstructions.json`):**
```json
{
  "controllers": "scope",
  "controller": "scope",
  "joint controllerships": "scope",
  "joint controllership": "scope"
}
```

**User Input Examples:**
- "create Controller named 'MFA for VPN'" → Creates scope with `SCP_Controller` subtype
- "create Controllers named 'X'" → Creates scope with `SCP_Controller` subtype
- "create Joint Controller named 'X'" → Creates scope with `SCP_JointController` subtype

---

### 2. ASSET Subtypes

**Subtypes:**
1. **All** (shows all assets)
2. **Datatypes** (Data type assets - confirmed in test: "DATA TYPE 01" uses this)
3. **IT-systems** (IT-System assets)
4. **Applications** (Application assets)

**Subtype Names → Technical IDs:**
- "Datatypes" / "Datatype" / "Data Type" / "DataType" → `AST_Datatype`
- "IT-systems" / "IT-System" / "IT System" / "IT-Systems" → `AST_IT-System`
- "Applications" / "Application" → `AST_Application`

**User Input Examples:**
- "create assets 'Data Type 01' in the Datatypes assets" → Creates asset with `AST_Datatype`
- "create IT-System asset 'Server1'" → Creates asset with `AST_IT-System`
- "link SCOPE1 with IT-System assets" → Links all `AST_IT-System` assets
- "create Application asset 'WebApp1'" → Creates asset with `AST_Application`

---

### 3. PERSON Subtypes

**Subtypes:**
1. **All** (shows all persons)
2. **Persons** (Generic person - default)
3. **Data protection officers** (Data Protection Officer / DPO)

**Subtype Names → Technical IDs:**
- "Persons" / "Person" → `PER_Person`
- "Data protection officers" / "Data Protection Officer" / "DPO" / "Data protection officer" → `PER_DataProtectionOfficer`

**User Input Examples:**
- "create person 'John'.assign his role to 'DPO'" → Creates person with `PER_DataProtectionOfficer` subtype
- "create a new Data Protection Officer 'John'" → Creates person with `PER_DataProtectionOfficer` subtype
- "add Toom in our isms person list and set his role to DPO" → Creates person with `PER_DataProtectionOfficer` subtype

---

### 4. CONTROL Subtypes

**Subtypes:**
1. **All** (shows all controls)
2. **TOMs** (Technical and Organizational Measures)

**Subtype Names → Technical IDs:**
- "TOMs" / "TOM" / "Technical and Organizational Measures" → `CTL_TOM`

**User Input Examples:**
- "create control TOM" → Creates control with `CTL_TOM` subtype
- "create TOM control 'Access Control'" → Creates control with `CTL_TOM` subtype

---

### 5. PROCESS Subtypes

**Subtypes:**
1. **All** (shows all processes)
2. **Data protection impact...** (Data Protection Impact Assessment - DPIA)
3. **Data transfers** (Data transfer processes)
4. **Data processings** (Data processing processes)

**Subtype Names → Technical IDs:**
- "Data protection impact" / "DPIA" / "Data Protection Impact Assessment" → `PRO_DPIA`
- "Data transfers" / "Data Transfer" → `PRO_DataTransfer`
- "Data processings" / "Data Processing" → `PRO_DataProcessing`

**User Input Examples:**
- "create process 'GDPR Assessment'" → May create process with `PRO_DPIA` subtype
- "create Data Transfer process 'X'" → Creates process with `PRO_DataTransfer` subtype
- "create Data processing process 'X'" → Creates process with `PRO_DataProcessing` subtype

---

### 6. INCIDENT Subtypes

**Subtypes:**
1. **All** (shows all incidents)
2. **Data privacy incidents** (Data privacy related incidents)

**Subtype Names → Technical IDs:**
- "Data privacy incidents" / "Data Privacy Incident" → `INC_Incident` (or specific privacy subtype)

**User Input Examples:**
- "create incident 'Phishing Attempt Jan-24'" → Creates incident with `INC_Incident` subtype
- "create Data privacy incident 'X'" → Creates incident with data privacy subtype

---

### 7. DOCUMENT Subtypes

**Subtypes:**
1. **All** (shows all documents)
2. **Contracts** (Contract documents)
3. **Documents** (Generic document)

**Subtype Names → Technical IDs:**
- "Contracts" / "Contract" → `DOC_Contract`
- "Documents" / "Document" (default) → `DOC_Document`

**User Input Examples:**
- "create Contract document 'Service Agreement'" → Creates document with `DOC_Contract` subtype
- "create document 'Policy X'" → Creates document with `DOC_Document` subtype

---

### 8. SCENARIO Subtypes

**Actual Subtypes (from DS-GVO and ISO 27001 domains):**
1. **SCN_Scenario** (Default scenario)

**User Input Examples:**
- "create scenario 'Data Breach Risk'" → Creates scenario with `SCN_Scenario` subtype

## Subtype Naming Conventions (ACTUAL FROM VERINICE)

**Technical Format Patterns (confirmed from actual system):**
- **Scopes**: `SCP_*` prefix (e.g., `SCP_Scope`, `SCP_Controller`, `SCP_Processor`)
- **Assets**: `AST_*` prefix (e.g., `AST_IT-System`, `AST_Datatype`, `AST_Application`)
- **Persons**: `PER_*` prefix (e.g., `PER_Person`, `PER_DataProtectionOfficer`)
- **Controls**: `CTL_*` prefix (e.g., `CTL_TOM`)
- **Processes**: `PRO_*` prefix (e.g., `PRO_DPIA`, `PRO_DataTransfer`, `PRO_DataProcessing`)
- **Incidents**: `INC_*` prefix (e.g., `INC_Incident`)
- **Documents**: `DOC_*` prefix (e.g., `DOC_Contract`, `DOC_Document`)
- **Scenarios**: `SCN_*` prefix (e.g., `SCN_Scenario`)

## Subtype Detection Logic

The system uses **intelligent pattern matching** to detect subtypes from user input:

### 1. Direct Subtype Detection
- "create Controller named 'X'" → Detects "Controller" as scope subtype
- "create assets 'X' in the Datatypes assets" → Detects "Datatypes" as asset subtype

### 2. Role/Subtype Assignment
- "assign his role to 'DPO'" → Maps to person DPO subtype
- "set his role to DPO" → Maps to person DPO subtype
- "as DPO" → Maps to person DPO subtype
- "for DPO" → Maps to person DPO subtype

### 3. User-Friendly Name Mapping
The system maps common user-friendly names to technical subtypes:
- "IT-System" / "IT System" → `AST_IT-System`
- "Datatype" / "Data Type" / "DataType" → `AST_Datatype`
- "DPO" / "Data Protection Officer" → `PER_DataProtectionOfficer` or `PER_DPO`
- "Controller" / "Controllers" → "Controllers" (scope subtype)

## Important Notes

1. **Subtypes are domain-specific**: Actual available subtypes are retrieved dynamically from the Verinice domain using `getDomainSubTypes(domainId, objectType)`. The subtypes listed above are common patterns but may vary by domain.

2. **Subtype Matching**: The system uses fuzzy matching to handle variations:
   - Case-insensitive matching
   - Handles spaces, hyphens, underscores
   - Handles singular/plural forms
   - Handles acronyms (DPO, CIO, CTO, CFO, CISO)

3. **Subtype Priority**: When multiple subtypes match, the system:
   - Prefers exact matches
   - Falls back to contains matching
   - Uses intelligent synonym matching

## How to Query Available Subtypes

**Via Chat:**
- "how many subtypes assets"
- "show me all subtypes of scopes"
- "what subtypes are available for assets"
- "list subtypes for asset"

**Via API:**
```python
veriniceTool.getDomainSubTypes(domainId, objectType)
```

## Current Subtype Mappings in Code

From `ismsInstructions.json`:
```json
"subtype_mappings": {
  "controllers": "scope",
  "controller": "scope",
  "joint controllerships": "scope",
  "joint controllership": "scope"
}
```

**Purpose**: These mappings tell the system that when a user says "create Controller", they mean "create a scope with Controller subtype", NOT "create a control object".

## Summary Table

| Object Type | Subtypes | Technical IDs | Mapping |
|-------------|----------|----------------|---------|
| **scope** | Scopes, Processors, Controllers, Joint controllerships, Controllers Art. 4 Nr.7 | SCP_Scope, SCP_Processor, SCP_Controller, SCP_JointController | Subtype names map to technical IDs |
| **asset** | Datatypes, IT-systems, Applications | AST_Datatype, AST_IT-System, AST_Application | Subtype names map to technical IDs |
| **person** | Persons, Data protection officers | PER_Person, PER_DataProtectionOfficer | Subtype names map to technical IDs |
| **control** | TOMs | CTL_TOM | Subtype name maps to technical ID |
| **process** | Data protection impact assessment, Data transfers, Data processings | PRO_DPIA, PRO_DataTransfer, PRO_DataProcessing | Subtype names map to technical IDs |
| **incident** | Data privacy incidents | INC_Incident | Subtype name maps to technical ID |
| **document** | Contracts, Documents | DOC_Contract, DOC_Document | Subtype names map to technical IDs |
| **scenario** | Scenarios | SCN_Scenario | Subtype name maps to technical ID |

## Critical Understanding

**Main Objects vs Subtypes:**
- **Main Objects**: scope, asset, control, process, person, scenario, incident, document (8 total)
- **Subtypes**: The items shown under each main object (e.g., "Controllers", "Datatypes", "Data protection officers")

**When user asks:**
- "how many subtypes assets" → User wants to know subtypes of **asset** main object
- "show me all subtypes of Scopes" → User wants to know subtypes of **scope** main object
- "what subtypes are available for persons" → User wants to know subtypes of **person** main object

**Agent must:**
1. Recognize main object type (scope, asset, person, etc.)
2. Extract the question is about subtypes (not about creating/list the main object)
3. Query actual subtypes from domain using `getDomainSubTypes(domainId, objectType)`
4. Return the subtypes in the format shown in the ISMS system

## Complete Subtype List

**Subtype Names → Technical IDs:**

- **SCOPE:**
  - All → (shows all, not a subtype)
  - Scopes → `SCP_Scope`
  - Processors → `SCP_Processor`
  - Controllers → `SCP_Controller`
  - Joint controllerships → `SCP_JointController`
  - Controllers, Art. 4 Nr.7 → `SCP_Controller` (with article reference)

- **ASSET:**
  - All → (shows all, not a subtype)
  - Datatypes → `AST_Datatype`
  - IT-systems → `AST_IT-System`
  - Applications → `AST_Application`

- **CONTROL:**
  - All → (shows all, not a subtype)
  - TOMs → `CTL_TOM`

- **PROCESS:**
  - All → (shows all, not a subtype)
  - Data protection impact assessment → `PRO_DPIA`
  - Data transfers → `PRO_DataTransfer`
  - Data processings → `PRO_DataProcessing`

- **PERSON:**
  - All → (shows all, not a subtype)
  - Persons → `PER_Person`
  - Data protection officers → `PER_DataProtectionOfficer`

- **INCIDENT:**
  - All → (shows all, not a subtype)
  - Data privacy incidents → `INC_Incident`

- **DOCUMENT:**
  - All → (shows all, not a subtype)
  - Contracts → `DOC_Contract`
  - Documents → `DOC_Document`

- **SCENARIO:**
  - Scenarios → `SCN_Scenario`
