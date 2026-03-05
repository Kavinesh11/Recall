"""Lightweight Gemini demo client (shim)

This module provides a tolerant HTTP shim for demo purposes only.
- Reads GEMINI_API_KEY and optional GEMINI_API_ENDPOINT/GEMINI_MODEL from env
- Sends a POST to the configured endpoint and returns the first text-like
  string found in the JSON response.

Notes:
- This is a demo shim (no official SDK). For production, use Google's
  official client libraries or an official agno model integration.
"""
from __future__ import annotations
import os
import requests
from typing import Optional, Any


def _first_string(obj: Any) -> Optional[str]:
    if isinstance(obj, str) and obj.strip():
        return obj.strip()
    if isinstance(obj, dict):
        for v in obj.values():
            s = _first_string(v)
            if s:
                return s
    if isinstance(obj, list):
        for item in obj:
            s = _first_string(item)
            if s:
                return s
    return None


def generate_text_from_gemini(prompt: str, timeout: int = 15) -> str:
    """Call Gemini-style endpoint and return text for demo use.

    Environment variables used:
    - GEMINI_API_KEY (required)
    - GEMINI_API_ENDPOINT (optional) — default targets Generative Language REST path
    - GEMINI_MODEL (optional) — default `gemini-1.5`
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = os.getenv(
        "GEMINI_API_ENDPOINT",
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"prompt": prompt}

    # Primary attempt: Authorization Bearer (OAuth token)
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)

    # Fallback for API keys (Google API key strings often start with 'AIza')
    if resp.status_code >= 400 and api_key.startswith("AIza"):
        # Retry using `key=` query parameter (no Authorization header)
        params = {"key": api_key}
        resp = requests.post(endpoint, headers={"Content-Type": "application/json"}, params=params, json=payload, timeout=timeout)

    if resp.status_code >= 400:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")

    data = resp.json()
    text = _first_string(data)
    return text or ""
