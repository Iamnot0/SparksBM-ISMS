#!/usr/bin/env python3
"""
Quality Evaluation Suite for SparksBM Agent
Implements 'LLM-as-a-Judge' to benchmark Accuracy, Latency, and Reasoning Quality.
"""

import sys
import os
import time
import requests
import json
import statistics
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path for direct imports if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Configuration
BASE_URL = "http://localhost:8000/api/agent"
SESSION_USER = "quality_evaluator"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("❌ Error: GEMINI_API_KEY environment variable not set. Cannot run LLM-as-a-Judge.")
    sys.exit(1)

import google.generativeai as genai
genai.configure(api_key=GEMINI_API_KEY)
judge_model = genai.GenerativeModel('gemini-2.5-flash')

# Test Dataset: Diverse queries testing different cognitive capabilities
TEST_CASES = [
    {
        "category": "Knowledge Base",
        "query": "What is ISO 27001? Provide a concise definition.",
        "expected_criteria": "Must mention 'Information Security Management System' (ISMS), 'standard', and 'risk management'. Should be complete sentences.",
        "complexity": "Low"
    },
    {
        "category": "Knowledge Base",
        "query": "Explain the difference between a Scope and an Asset in Verinice.",
        "expected_criteria": "Must explain Scope as a boundary/container and Asset as a protected item/resource. Must clarify the relationship.",
        "complexity": "Medium"
    },
    {
        "category": "Analysis",
        "query": "Analyze scope 'Alpha-Scope'.",
        "expected_criteria": "Must return a structured analysis report. Should not just say 'I need ID'. (Assumes Alpha-Scope exists from previous tests)",
        "complexity": "Medium"
    },
    {
        "category": "Reasoning (Complex)",
        "query": "I need to secure my 'Payment Gateway'. Create a scope for it and link it to the 'Financial Data' asset.",
        "expected_criteria": "Should perform two actions: Create Scope and Link Object. Should identify 'Payment Gateway' as name and 'Financial Data' as target.",
        "complexity": "High"
    },
    {
        "category": "Handling Ambiguity",
        "query": "Do the security thing.",
        "expected_criteria": "Should NOT hallucinate actions. Should ask for clarification or list capabilities. Should be polite.",
        "complexity": "High"
    }
]

class QualityEvaluator:
    def __init__(self):
        self.session_id = self._create_session()
        self.results = []

    def _create_session(self):
        try:
            res = requests.post(f"{BASE_URL}/session", params={"userId": SESSION_USER})
            if res.status_code == 200:
                return res.json().get("sessionId")
        except Exception as e:
            print(f"❌ Failed to create session: {e}")
            sys.exit(1)
        return None

    def judge_response(self, query: str, response: str, criteria: str) -> Dict[str, Any]:
        """Uses Gemini to grade the agent's response"""
        prompt = f"""
You are an expert AI Quality Assurance Judge. Evaluate the following AI response based on the user query and success criteria.

User Query: "{query}"
AI Response: "{response}"
Success Criteria: {criteria}

Evaluate on:
1. **Accuracy**: Is the information correct?
2. **Completeness**: Did it answer the whole prompt? (Check for truncation!)
3. **Relevance**: Is it on topic?

Output STRICT JSON:
{{
    "score": <integer 1-5>,
    "reasoning": "<brief explanation>",
    "is_truncated": <boolean>,
    "is_generic": <boolean (true if generic 'I dont know' or 'ISO' stub)>
}}
"""
        try:
            result = judge_model.generate_content(prompt)
            # Clean up markdown
            text = result.text.replace('```json', '').replace('```', '').strip()
            return json.loads(text)
        except Exception as e:
            return {"score": 0, "reasoning": f"Judge Error: {e}", "is_truncated": False, "is_generic": False}

    def run_tests(self):
        print(f"\n🚀 Starting Quality Evaluation on {len(TEST_CASES)} cases...\n")
        print(f"{ 'CATEGORY':<20} | {'LATENCY':<10} | {'SCORE':<5} | {'RESULT'}")
        print("-" * 80)

        for test in TEST_CASES:
            start_time = time.time()
            try:
                # Send query
                res = requests.post(f"{BASE_URL}/chat", json={"message": test["query"], "sessionId": self.session_id})
                duration = (time.time() - start_time) * 1000  # ms
                
                if res.status_code == 200:
                    data = res.json()
                    response_text = str(data.get("result", ""))
                    
                    # AI Judge
                    eval_result = self.judge_response(test["query"], response_text, test["expected_criteria"])
                    
                    self.results.append({
                        "test": test,
                        "response": response_text,
                        "latency": duration,
                        "evaluation": eval_result
                    })
                    
                    status = "✅" if eval_result["score"] >= 4 else "⚠️" if eval_result["score"] >= 2 else "❌"
                    print(f"{test['category']:<20} | {int(duration)}ms     | {eval_result['score']}/5 | {status} {eval_result['reasoning'][:40]}...")
                else:
                    print(f"{test['category']:<20} | FAIL       | 0/5 | ❌ HTTP {res.status_code}")
            except Exception as e:
                print(f"{test['category']:<20} | ERROR      | 0/5 | ❌ {str(e)[:40]}")

    def generate_report(self):
        if not self.results:
            print("No results to report.")
            return

        avg_latency = statistics.mean([r["latency"] for r in self.results])
        avg_score = statistics.mean([r["evaluation"]["score"] for r in self.results])
        truncated_count = sum(1 for r in self.results if r["evaluation"]["is_truncated"])
        generic_count = sum(1 for r in self.results if r["evaluation"]["is_generic"])

        print("\n" + "=" * 50)
        print("📊 QUALITY ASSURANCE REPORT")
        print("=" * 50)
        print(f"Overall Score:      {avg_score:.1f} / 5.0")
        print(f"Avg Latency:        {int(avg_latency)} ms")
        print(f"Truncated Responses: {truncated_count}")
        print(f"Generic Fallbacks:   {generic_count}")
        print("=" * 50)
        
        # Recommendations
        print("\n🔍 RECOMMENDATIONS:")
        if truncated_count > 0:
            print("  • [CRITICAL] Fix response truncation (increase max_tokens or relax concise mode).")
        if avg_latency > 2000:
            print("  • [PERFORMANCE] Optimize RAG retrieval or LLM inference speed.")
        if generic_count > 0:
            print("  • [TUNING] Improve Intent Classifier for ambiguous queries.")
        if avg_score < 4.0:
            print("  • [QUALITY] Review system prompts and context injection.")
            
        # Save Metrics to JSON
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "overall_score": round(avg_score, 2),
            "avg_latency_ms": int(avg_latency),
            "truncated_count": truncated_count,
            "generic_count": generic_count,
            "total_tests": len(self.results),
            "details": self.results
        }
        
        with open("metrics_report.json", "w") as f:
            json.dump(report_data, f, indent=2)
        print(f"\n💾 Metrics saved to 'metrics_report.json'")

if __name__ == "__main__":
    evaluator = QualityEvaluator()
    evaluator.run_tests()
    evaluator.generate_report()
