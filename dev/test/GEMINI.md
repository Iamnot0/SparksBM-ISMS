# GEMINI Project Context: Agentic ISMS Framework

## Project Overview

This project is an **Agentic AI Framework** designed to provide a natural language interface for an **Information Security Management System (ISMS)**. The core of the project is a Python-based backend that exposes a REST API (running on `http://localhost:8000`).

The agent is built to understand and process both structured commands and conversational, human-like queries. It can perform complex operations on various ISMS objects, including:

*   **CRUD Operations:** Create, Read, Update, and Delete.
*   **Object Linking:** Connecting different ISMS objects (e.g., linking an `asset` to a `scope`).
*   **Comparison/Reconciliation:** Analyzing the differences between two objects.
*   **Analysis:** Providing detailed information about a specific object.

The supported ISMS object types include `scope`, `asset`, `person`, `process`, `document`, `incident`, `control`, and `scenario`.

The ultimate goal is to create a robust and intuitive conversational AI that can assist users, likely security professionals, in managing the ISMS without needing to learn a rigid set of commands.

## Building and Running

The project consists of a backend agent and multiple testing scripts.

### Backend Agent (Agentic Framework)

The backend agent is a Python application. To set up and run it:

1.  **Install dependencies:**
    ```bash
    pip install -r Agentic\ Framework/requirements.txt
    ```
2.  **Run the agent:**
    ```bash
    python Agentic\ Framework/main.py
    ```

The agent will then be running and listening on `http://localhost:8000`.

### Testing Scripts

The testing scripts are located in the `dev/test/` directory. They are used to validate the functionality and natural language capabilities of the agent.

1.  **Natural Language Understanding Tests:**
    *   This suite validates the agent's ability to handle typos, varied phrasing, and conversational queries.
    *   **To Run:**
        ```bash
        python natural_language_test.py --all
        ```
    *   **Interactive Mode:**
        ```bash
        python natural_language_test.py --interactive
        ```

2.  **Structured Command Tests:**
    *   This provides an interactive shell for manual QA testing using structured commands.
    *   **To Run:**
        ```bash
        python ismsTesting.py
        ```
    *   **Automated Scenarios:** The script also supports running predefined test suites (e.g., for CRUD, linking).
        ```bash
        # Run all automated ISMS tests
        python ismsTesting.py --all

        # Run a quick CRUD test for the 'asset' object type
        python ismsTesting.py --quick --type asset
        ```

## Development Conventions

*   **Testing is Key:** The project has a strong emphasis on testing, with two distinct and comprehensive test suites: one for structured commands (`ismsTesting.py`) and one for natural language processing (`natural_language_test.py`).
*   **Component-Based:** The system is decoupled, with the agent running as a separate service that the testing scripts communicate with via a REST API.
*   **Natural Language Focus:** Significant effort is dedicated to making the agent's responses feel natural and conversational, and to correctly interpreting a wide range of user inputs. The evaluation metrics in `natural_language_test.py` (scoring based on "conversational markers" and penalizing "generic responses") highlight this priority.
*   **ISMS Domain:** All functionality is centered around the specific domain of Information Security Management Systems.
