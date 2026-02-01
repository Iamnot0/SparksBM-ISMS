# QA Test Plan: SparksBM Agent - ISMS Operations

**Document Version:** 1.0
**Date:** January 25, 2026
**Author:** Gemini CLI Agent

---

## 1. Introduction

This document outlines a series of end-to-end test cases for the SparksBM Agent, focusing on its capabilities related to Information Security Management System (ISMS) operations, particularly reconciliation and compliance. The test cases are derived from advanced natural language prompts found in `promptEngineering.txt`, designed to stress-test the agent's natural language understanding, tool orchestration, and backend integration via `veriniceTool.py`.

**Objective:** To verify the SparksBM agent's ability to:
*   Accurately interpret complex, multi-clause natural language prompts.
*   Correctly map user intent to appropriate sequences of `veriniceTool.py` calls.
*   Perform ISMS operations (listing, getting, comparing, updating, reporting) with correct parameters.
*   Synthesize information from multiple backend calls into a coherent and meaningful response for the user.
*   Handle and report errors gracefully.

---

## 2. Test Environment

*   **Agent:** SparksBM Agentic Framework (Python-based, running locally).
*   **Backend:** Verinice ISMS instance (expected to be running and accessible via `http://localhost:8070`).
*   **Authentication:** Keycloak (expected to be running and accessible via `http://localhost:8080`).
*   **Tools:** `veriniceTool.py` (for ISMS backend interaction), `LLMTool` (for general reasoning/text generation).

---

## 3. Test Cases

### 3.1. Test Case: Cross-Domain Drift Detection

*   **Test ID:** ISMS-CRD-001
*   **Category:** ISMS Reconciliation & Compliance
*   **Priority:** High
*   **Prompt (User Input):**
    ```
    "Compare the 'Production' domain against the 'Disaster Recovery' domain. Goal: Identify any 'Critical' assets in Production that are missing in DR. For each missing asset, generate a 'Gap Analysis' report item."
    ```
*   **Expected Agent Behavior (Internal Logic Flow):**
    1.  **NLP/Intent Recognition:** Agent identifies intent as "domain comparison" and "asset reconciliation with filtering."
    2.  **Entity Extraction:** Extracts "Production" and "Disaster Recovery" as domain names, and "Critical" as an asset property/tag.
    3.  **Tool Selection:** Selects `veriniceTool.py`.
    4.  **Orchestration:**
        *   Calls `veriniceTool.listDomains()` to resolve "Production" and "Disaster Recovery" domain names to their respective `domainId`s.
        *   Calls `veriniceTool.compareDomains(domainId_Production, domainId_DR, objectType='asset')`.
        *   Processes the `compareDomains` result to identify assets found "only_in_domain1" (Production).
        *   For each asset identified as "only in Production," it calls `veriniceTool.getObject('asset', domainId_Production, assetId)` to retrieve its full details and verify the "Critical" status or tag. (Alternatively, if `listObjects` supported advanced filtering, it could have been used upfront).
        *   For each "Critical" asset missing in DR, the agent internally constructs a "Gap Analysis report item" (this might involve an `LLMTool` call for formatting or interaction with a dedicated reporting tool if available).
        *   Synthesizes findings into a coherent natural language summary.

*   **Expected Backend Interactions (Verinice API):**
    *   `GET /domains` (to retrieve all domains for name-to-ID mapping).
    *   `GET /domains/{domainId_Production}/assets` (to list assets in Production).
    *   `GET /domains/{domainId_DR}/assets` (to list assets in Disaster Recovery).
    *   `GET /assets/{assetId}` (for each identified asset in Production to check its full details/tags).
    *   (Potential `POST` to a reporting API endpoint, if "generate report item" maps to one).

*   **Expected Agent Output (User-facing):**
    ```
    "Comparing Production and Disaster Recovery domains... Found X 'Critical' assets in Production that are missing from Disaster Recovery: [list asset names/IDs]. Gap analysis report items have been generated."
    ```
    *   **Success Condition:** Agent provides correct count and list of assets, confirms report item generation. All underlying `veriniceTool.py` calls return `success: True`.
    *   **Failure Condition:** Incorrect asset identification, failure to resolve domains, `veriniceTool.py` returns errors (e.g., `'Domain {domainId} not found'`, `'{objectType} not found'`), or agent fails to generate report items.

---

### 3.2. Test Case: Policy vs. Reality Check

*   **Test ID:** ISMS-PLC-002
*   **Category:** ISMS Reconciliation & Compliance
*   **Priority:** High
*   **Prompt (User Input):**
    ```
    "Check the 'Access Control' policy document. It requires MFA on all external-facing assets. Scan the 'Asset Inventory' for assets tagged 'External' that do not have the 'MFA' control linked. List the non-compliant assets."
    ```
*   **Expected Agent Behavior (Internal Logic Flow):**
    1.  **NLP/Intent Recognition:** Agent identifies intent as "compliance check," "policy enforcement," "asset scanning."
    2.  **Entity Extraction:** Extracts "Access Control policy document" (implies the agent has internal knowledge of this policy or accesses it), "MFA" (control), "external-facing assets" (asset property/tag).
    3.  **Tool Selection:** Selects `veriniceTool.py` (and potentially `LLMTool` if dynamic policy interpretation is needed, though static policy rules are more likely here).
    4.  **Orchestration:**
        *   Retrieves policy rules for "Access Control" and "MFA" (either from internal knowledge base or by processing a document via LLM, assuming such capability exists or was pre-processed).
        *   Calls `veriniceTool.listObjects('asset', domainId=relevant_domain_id, filters={'tags': 'External'})` (assuming tag filtering is directly supported by the API, otherwise, fetches all assets and filters client-side).
        *   For each 'External' asset, it calls `veriniceTool.getObject('asset', relevant_domain_id, assetId)` to get its detailed properties, specifically looking for linked controls.
        *   Compares the linked controls of each asset against the "MFA" control requirement.
        *   Identifies assets that are 'External' but do not have 'MFA' control linked as non-compliant.
        *   Synthesizes non-compliant assets into a user-friendly list.

*   **Expected Backend Interactions (Verinice API):**
    *   `GET /assets` (potentially with query parameters for filtering by tag).
    *   `GET /assets/{assetId}` (for each relevant asset to check linked controls).
    *   (Potential `LLMTool` calls if dynamic policy document analysis is required).

*   **Expected Agent Output (User-facing):**
    ```
    "Policy check complete. The following external-facing assets are not compliant with the 'MFA' control requirement: [list non-compliant asset names/IDs]."
    ```
    *   **Success Condition:** Agent accurately identifies and lists all non-compliant assets based on the defined policy. All underlying `veriniceTool.py` calls return `success: True`.
    *   **Failure Condition:** Misses non-compliant assets, incorrectly flags compliant assets, fails to retrieve policy/asset data, or `veriniceTool.py` returns errors.

---

### 3.3. Test Case: Automated Compliance Evidence Generation

*   **Test ID:** ISMS-ACE-003
*   **Category:** ISMS Reconciliation & Compliance
*   **Priority:** High
*   **Prompt (User Input):**
    ```
    "Generate a 'Statement of Applicability' (SoA) for ISO 27001 Annex A. For A.12.1 (Operations Security), verify if we have linked 'Change Management' processes. If yes, mark as 'Implemented'; if no, mark as 'Pending' and add a comment 'Evidence missing'."
    ```
*   **Expected Agent Behavior (Internal Logic Flow):**
    1.  **NLP/Intent Recognition:** Agent identifies intent as "report generation," "compliance verification," "process linking evaluation."
    2.  **Entity Extraction:** Extracts "Statement of Applicability" (report type), "ISO 27001 Annex A" (standard/template context), "A.12.1 (Operations Security)" (specific control identifier), "Change Management processes."
    3.  **Tool Selection:** Selects `veriniceTool.py`.
    4.  **Orchestration:**
        *   Calls `veriniceTool.listObjects('process', domainId=relevant_domain_id, filters={'name': 'Change Management'})` to verify the existence and linkage of "Change Management" processes within the relevant domain.
        *   Evaluates the result:
            *   **If "Change Management" processes are found/linked to the control:** Sets control A.12.1 status to "Implemented."
            *   **If not found/linked:** Sets control A.12.1 status to "Pending" and sets a comment "Evidence missing."
        *   Calls `veriniceTool.generateReport(reportId='statement-of-applicability', domainId=relevant_domain_id, params={'control_A.12.1_status': 'Implemented/Pending', 'comment_A.12.1': '...'}`. This is a critical assumption about the backend's `generateReport` capabilities to accept dynamic control status updates and comments.

*   **Expected Backend Interactions (Verinice API):**
    *   `GET /processes` (potentially with filters for "Change Management").
    *   (Optional `GET /controls/A.12.1` if direct linkage needs verification).
    *   `POST /api/reporting/reports/statement-of-applicability` with a JSON payload that includes dynamic parameters for control A.12.1's status and comment.

*   **Expected Agent Output (User-facing):**
    ```
    "Generating Statement of Applicability... For control A.12.1, 'Change Management' processes were [found/not found], setting status to '[Implemented/Pending]'. Report generated successfully."
    ```
    *   **Success Condition:** Agent correctly determines the control status, generates the report with the updated information, and confirms successful generation. All underlying `veriniceTool.py` calls return `success: True`.
    *   **Failure Condition:** Fails to find processes, incorrectly determines status, `generateReport` fails due to unsupported dynamic parameters, or `veriniceTool.py` returns errors.

---

## 4. Conclusion and Recommendations

These test cases highlight the advanced capabilities expected from the SparksBM Agent in handling complex ISMS-related queries. They rely heavily on the agent's ability to:
*   **Deconstruct complex natural language:** Break down multi-clause, conditional statements.
*   **Orchestrate multiple tool calls:** Sequence `listObjects`, `getObject`, `compareDomains`, and `generateReport` effectively.
*   **Apply domain logic:** Understand ISMS concepts like "Critical assets," "MFA controls," and "Change Management processes" within the Verinice data model.
*   **Handle dynamic report generation:** Specifically for Test Case 3, the ability to dynamically inject control statuses and comments into a report template is a critical and potentially challenging requirement for the `generateReport` functionality.

**Recommendations:**
*   **Verify Dynamic Reporting:** Confirm with the backend team or through direct API testing if the `generateReport` endpoint (`POST /api/reporting/reports/{reportId}`) truly supports dynamic injection of control statuses and comments via its `params` payload, as implied by Test Case 3. If not, the agent's logic for this prompt would need to be re-evaluated (e.g., retrieving a static report and then performing post-processing/modification on the agent side).
*   **Refine Filter Capabilities:** Investigate if `listObjects` can leverage more advanced filtering directly at the API level (e.g., filtering by asset tags like "External" or "Critical") to reduce client-side processing by the agent.
*   **Policy Document Integration:** If policy documents are intended to be interpreted dynamically by the agent, ensure the `LLMTool` or a specialized document processing tool is robust enough for this task.

This test plan provides a rigorous framework for validating the agent's end-to-end performance on critical ISMS reconciliation and compliance tasks.

---