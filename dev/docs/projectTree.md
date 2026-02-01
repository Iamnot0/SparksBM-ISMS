.
├── Agentic Framework
│   ├── agents
│   │   ├── coordinators
│   │   ├── baseAgent.py
│   │   ├── helpers.py
│   │   ├── instructions.py
│   │   ├── ismsAgent.py
│   │   ├── ismsController.py
│   │   ├── ismsFastPath.py
│   │   ├── ismsHandler.py
│   │   ├── ismsTools.py
│   │   └── mainAgent.py
│   ├── config
│   │   └── settings.py
│   ├── mcp
│   │   ├── prompts
│   │   ├── tools
│   │   │   ├── analyze.py
│   │   │   ├── compare.py
│   │   │   └── linking.py
│   │   └── server.py
│   ├── memory
│   │   ├── conversation.py
│   │   ├── enhancedContextManager.py
│   │   ├── memoryStore.py
│   │   ├── selections.py
│   │   └── uiState.py
│   ├── orchestrator
│   │   ├── advancedPatternMatcher.py
│   │   ├── chatRouter.py
│   │   ├── executor.py
│   │   ├── intentClassifier.py
│   │   ├── reasoningEngine.py
│   │   └── toolChain.py
│   ├── presenters
│   │   ├── base.py
│   │   ├── error.py
│   │   ├── list.py
│   │   ├── report.py
│   │   ├── table.py
│   │   └── text.py
│   ├── prompts
│   │   └── templates.py
│   ├── tools
│   │   ├── llmTool.py
│   │   └── veriniceTool.py
│   ├── utils
│   │   ├── prompt_versions
│   │   ├── commonInstructions.json
│   │   ├── errorsBase.json
│   │   ├── ismsInstructions.json
│   │   ├── knowledgeBase.py
│   │   ├── pathUtils.py
│   │   ├── promptVersioning.py
│   │   └── reconciliationUtils.py
│   ├── config.py
│   ├── main.py
│   └── requirements.txt
├── NotebookLLM
│   ├── api
│   │   ├── middleware
│   │   ├── models
│   │   ├── routers
│   │   ├── services
│   │   │   ├── agentService.py
│   │   │   ├── eventQueue.py
│   │   │   └── sessionService.py
│   │   ├── uploads
│   │   ├── utils
│   │   ├── workspace
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── config
│   │   ├── notebookllm.env
│   │   └── notebookllm.env.example
│   ├── frontend
│   │   ├── components
│   │   ├── composables
│   │   ├── layouts
│   │   ├── pages
│   │   ├── plugins
│   │   ├── public
│   │   ├── types
│   │   ├── app.vue
│   │   ├── nuxt.config.ts
│   │   └── package.json
│   ├── integration
│   │   ├── agentBridge.py
│   │   ├── contextMapper.py
│   │   └── responseFormatter.py
│   └── start.sh
├── SparksbmISMS
│   ├── config
│   ├── keycloak
│   ├── scripts
│   ├── verinice-veo
│   ├── start-sparksbm.sh
│   └── stop-sparksbm.sh
├── agent.log
├── dev
│   ├── docs
│   │   ├── projectTree.md
│   │   ├── systemArchitecture.md
│   │   └── todo.md
│   ├── scripts
│   │   └── asset_drift_audit.py
│   └── test
│       ├── evaluate_quality.py
│       ├── ismsHandler.py
│       ├── ismsTesting.py
│       ├── linking.py
│       ├── mainAgent.py
│       ├── quick_test.py
│       ├── test_gemini_integration.py
│       ├── test_promptEngineering.py
│       └── verify_capabilities.py
├── metrics_report.json
└── test_gemini_integration.py
