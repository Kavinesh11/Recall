"""
Simple HTTP proxy for Ollama (Mistral).

POST /mistral { "prompt": "..." }
Response: { "text": "model output" }

Run on the host when Recall is running in Docker so containers can call
host.docker.internal:5001/mistral to use local ollama.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import requests
import traceback

HOST = '0.0.0.0'
PORT = 5001

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(length)
        data = json.loads(body or b'{}')

        # /mistral -> run phi:latest (text generation) - using phi as fallback for GPU issues
        if self.path == '/mistral':
            prompt = data.get('prompt', '')
            max_tokens = data.get('max_tokens', 2000)
            try:
                payload = {
                    "model": "phi:latest",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens
                    }
                }
                r = requests.post('http://127.0.0.1:11434/api/generate', json=payload, timeout=60)
                r.raise_for_status()
                result = r.json()
                out = result.get('response', '')
                resp = {'text': out}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode('utf-8'))
            except Exception as e:
                print(f"Error in /mistral: {e}")
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            return

        # /phi_embed -> return embeddings from phi:latest
        if self.path == '/phi_embed':
            text = data.get('text', '')
            try:
                r = requests.post('http://127.0.0.1:11434/api/embed', json={"model": "phi:latest", "input": text}, timeout=30)
                r.raise_for_status()
                payload = r.json()
                # handle different response formats
                if isinstance(payload, dict) and 'embeddings' in payload:
                    embedding = payload['embeddings'][0] if isinstance(payload['embeddings'], list) else payload['embeddings']
                elif isinstance(payload, dict) and 'embedding' in payload:
                    embedding = payload['embedding']
                else:
                    embedding = payload
                resp = {'embedding': embedding}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode('utf-8'))
            except Exception as e:
                print(f"Error in /phi_embed: {e}")
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            return

        # /nomic_embed -> call Ollama HTTP API (suitable for embedding-only models like nomic-embed-text)
        if self.path == '/nomic_embed':
            text = data.get('text', '')
            try:
                r = requests.post('http://127.0.0.1:11434/api/embed', json={"model": "nomic-embed-text", "input": text}, timeout=30)
                r.raise_for_status()
                payload = r.json()
                # payload may be a list or an object containing 'embedding'
                if isinstance(payload, list):
                    embedding = payload
                elif isinstance(payload, dict) and 'embeddings' in payload and isinstance(payload['embeddings'], list):
                    embedding = payload['embeddings'][0]
                elif isinstance(payload, dict) and 'embedding' in payload:
                    embedding = payload['embedding']
                elif isinstance(payload, dict) and 'data' in payload and isinstance(payload['data'], list) and 'embedding' in payload['data'][0]:
                    embedding = payload['data'][0]['embedding']
                else:
                    embedding = payload
                resp = {'embedding': embedding}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode('utf-8'))
            except Exception as e:
                print(f"Error in /nomic_embed: {e}")
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            return

        # unknown path
        self.send_response(404)
        self.end_headers()
        return

def run():
    srv = HTTPServer((HOST, PORT), Handler)
    print(f'OLLAMA proxy listening on http://{HOST}:{PORT}')
    srv.serve_forever()

if __name__ == '__main__':
    run()
