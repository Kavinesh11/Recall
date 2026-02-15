"""Local Mistral (Ollama) demo client.

This is a lightweight shim that calls the `ollama` CLI installed on the host
and returns the model output as a string. Intended for local demos only.
"""
from __future__ import annotations
import os
import shlex
import subprocess
from typing import Optional


def generate_text_from_mistral(prompt: str, timeout: int = 15) -> str:
    """Run `ollama run mistral:latest` and return the stdout text.

    Raises RuntimeError when ollama is not available or when the process
    returns a non-zero exit code.
    """
    cmd = ["ollama", "run", "mistral:latest", prompt]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        # ollama not available inside container; fall back to host proxy at
        # http://host.docker.internal:5001/mistral (host must run the proxy)
        import requests
        proxy_url = os.getenv("OLLAMA_PROXY_URL", "http://host.docker.internal:5001/mistral")
        try:
            r = requests.post(proxy_url, json={"prompt": prompt}, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            text = data.get("text") or data.get("output")
            if text:
                return text
            raise RuntimeError("No text returned from OLLAMA proxy")
        except Exception as e:
            raise RuntimeError("ollama CLI not found and OLLAMA proxy unavailable") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("mistral call timed out") from e

    if proc.returncode != 0:
        raise RuntimeError(f"mistral (ollama) error {proc.returncode}: {proc.stderr.strip()}")

    out = proc.stdout.strip()
    if not out:
        # Some versions write to stderr; include stderr in error message
        raise RuntimeError(f"mistral produced no output. stderr: {proc.stderr.strip()}")

    return out
