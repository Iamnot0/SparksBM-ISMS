#!/usr/bin/env python3
"""
Test deployed Render services (health / reachability).

Usage:
  # Set your Render URLs (get them from Render dashboard → each service → URL)
  export KEYCLOAK_URL=https://keycloak-server.onrender.com
  export SPARKSBM_WEB_URL=https://sparksbm-web.onrender.com
  export SPARKSBM_API_URL=https://sparksbm.onrender.com
  export NOTEBOOKLLM_API_URL=https://sparksbm-agent.onrender.com
  export NOTEBOOKLLM_UI_URL=https://notebookllm-w3w7.onrender.com
  python dev/test/test_render_services.py

  # Or pass base URL to test only NotebookLLM API (for prompt tests)
  python dev/test/test_render_services.py --api-url https://sparksbm-agent.onrender.com

Free-tier services spin down after ~15 min inactivity; first request can take 50–90s.
"""

import os
import sys
import time
import argparse
import requests
from typing import Tuple

# Default slugs (Render: service name → https://<slug>.onrender.com; slug is set at creation)
DEFAULTS = {
    "keycloak": os.environ.get("KEYCLOAK_URL", "https://keycloak-server.onrender.com"),
    "sparksbm_web": os.environ.get("SPARKSBM_WEB_URL", "https://sparksbm-web.onrender.com"),
    "sparksbm_api": os.environ.get("SPARKSBM_API_URL", "https://sparksbm.onrender.com"),
    "notebookllm_api": os.environ.get("NOTEBOOKLLM_API_URL", "https://sparksbm-agent.onrender.com"),
    "notebookllm_ui": os.environ.get("NOTEBOOKLLM_UI_URL", "https://notebookllm-w3w7.onrender.com"),
}

CONNECT_TIMEOUT = 10
DEFAULT_TOTAL_TIMEOUT = 90  # Cold start on free tier can be 50–90s


def test_url(name: str, url: str, path: str = "/", method: str = "GET", total_timeout: int = DEFAULT_TOTAL_TIMEOUT) -> Tuple[bool, int, float, str]:
    """Return (ok, status_code, elapsed, message)."""
    full = url.rstrip("/") + path
    start = time.time()
    try:
        r = requests.request(method, full, timeout=(CONNECT_TIMEOUT, total_timeout))
        elapsed = time.time() - start
        ok = r.status_code < 400
        return ok, r.status_code, elapsed, r.reason or ""
    except requests.exceptions.Timeout as e:
        elapsed = time.time() - start
        return False, 0, elapsed, f"Timeout: {e}"
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start
        return False, 0, elapsed, str(e)


def main():
    parser = argparse.ArgumentParser(description="Test Render service URLs")
    parser.add_argument("--api-url", default=None, help="NotebookLLM API base URL (for quick single test)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TOTAL_TIMEOUT, help="Request timeout (default 90)")
    args = parser.parse_args()
    timeout = args.timeout

    if args.api_url:
        print(f"Testing NotebookLLM API: {args.api_url}")
        ok, code, elapsed, msg = test_url("NotebookLLM API", args.api_url, "/api/agent/tools", total_timeout=timeout)
        status = "OK" if ok else "FAIL"
        print(f"  {status}  {code}  {elapsed:.1f}s  {msg}")
        return 0 if ok else 1

    services = [
        ("Keycloak", DEFAULTS["keycloak"], "/"),
        ("SparksBM-Web", DEFAULTS["sparksbm_web"], "/"),
        ("SparksBM-API", DEFAULTS["sparksbm_api"], "/"),
        ("NotebookLLM-API", DEFAULTS["notebookllm_api"], "/api/agent/tools"),
        ("NotebookLLM-UI", DEFAULTS["notebookllm_ui"], "/"),
    ]
    print("Testing Render services (first request may take 50–90s if instance was sleeping)...\n")
    failed = []
    for name, base, path in services:
        ok, code, elapsed, msg = test_url(name, base, path, total_timeout=timeout)
        status = "✅" if ok else "❌"
        print(f"{status} {name:20} {base}  →  {code}  {elapsed:.1f}s  {msg}")
        if not ok:
            failed.append(name)
    if failed:
        print(f"\nFailed: {', '.join(failed)}")
        return 1
    print("\nAll reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
