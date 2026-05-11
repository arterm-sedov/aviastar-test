"""Push n8n workflow JSON via REST API or n8n CLI (docker exec).

Modes:
  python push.py          REST API (default, supports update)
  python push.py --cli    n8n CLI via docker exec (no API key needed, creates new)

Env vars / Windows registry: N8N_API_KEY, N8N_API_URL, N8N_WORKFLOW_ID, N8N_WORKFLOW_PATH
"""
import json, os, sys, subprocess, urllib.request, urllib.error

def _env(key, default=None):
    for src in [os.environ.get(key), _from_winreg(key)]:
        if src: return src
    return default

def _from_winreg(key):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, key)[0]
    except Exception:
        return None

N8N_URL = _env("N8N_API_URL", "http://localhost:5678")
N8N_KEY = _env("N8N_API_KEY")
WF_PATH = os.environ.get("N8N_WORKFLOW_PATH",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "n8n", "legal-rag.json")))
WF_ID = _env("N8N_WORKFLOW_ID", "")
USE_CLI = "--cli" in sys.argv

with open(WF_PATH, encoding="utf-8-sig") as f:
    wf = json.load(f)

# --- Auto-repair: restore fields stripped by n8n UI auto-save ---
repaired = 0
for n in wf['nodes']:
    if n['type'] == 'n8n-nodes-base.code':
        if n['parameters'].get('mode') != 'runOnceForAllItems':
            n['parameters']['mode'] = 'runOnceForAllItems'
            repaired += 1
        if 'language' not in n['parameters'] and 'jsCode' in n['parameters']:
            n['parameters']['language'] = 'javaScript'
    # Structured Output Parser: restore schema if stripped
    if n['type'] == '@n8n/n8n-nodes-langchain.outputParserStructured':
        if n['parameters'].get('schemaType') == 'manual':
            if 'inputSchema' not in n['parameters']:
                n['parameters']['inputSchema'] = json.dumps({
                    'type': 'object',
                    'properties': {
                        'score': {'type': 'number', 'minimum': 0, 'maximum': 1},
                        'reasoning': {'type': 'string', 'maxLength': 200}
                    },
                    'required': ['score']
                }, ensure_ascii=False, indent=2)
                repaired += 1
    # Chain LLM: restore options
    if n['type'] == '@n8n/n8n-nodes-langchain.chainLlm':
        if 'options' not in n['parameters']:
            n['parameters']['options'] = {}
if repaired:
    print(f'Auto-repaired {repaired} stripped field(s) — n8n UI auto-save')

if USE_CLI:
    # n8n CLI: docker cp → docker exec import:workflow (creates only, no update)
    subprocess.run(["docker", "cp", WF_PATH, "n8n:/tmp/wf.json"], check=True)
    result = subprocess.run(
        ["docker", "exec", "n8n", "n8n", "import:workflow", "--input=/tmp/wf.json"],
        capture_output=True, text=True
    )
    print(result.stdout or result.stderr)
    sys.exit(0)

if not N8N_KEY:
    print("ERROR: N8N_API_KEY not set in environment", file=sys.stderr)
    sys.exit(1)

# Strip ID fields so PUT/POST payload is clean
for key in ("id", "versionId", "meta", "tags"):
    wf.pop(key, None)

body = json.dumps({
    "name": wf["name"],
    "nodes": wf["nodes"],
    "connections": wf["connections"],
    "settings": {"executionOrder": "v1"}
}).encode()

url = f"{N8N_URL}/api/v1/workflows"
method = "POST"
if WF_ID:
    url = f"{url}/{WF_ID}"
    method = "PUT"
    print(f"Updating workflow {WF_ID}...")
else:
    print(f"Creating '{wf['name']}'...")

req = urllib.request.Request(url, data=body, method=method)
req.add_header("X-N8N-API-KEY", N8N_KEY)
req.add_header("Content-Type", "application/json")

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        print(f"Done: {result['id']} - {result['name']}")
        if not WF_ID:
            print(f"Set N8N_WORKFLOW_ID={result['id']} for future pushes")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body}", file=sys.stderr)
    sys.exit(1)
