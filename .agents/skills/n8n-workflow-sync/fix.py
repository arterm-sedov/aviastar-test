"""Fix n8n workflow JSON stripped by UI auto-save (mode, language, options, parser schema)."""
import json, os, sys

WF_PATH = os.environ.get("N8N_WORKFLOW_PATH",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "n8n", "legal-rag.json")))

with open(WF_PATH, encoding="utf-8-sig") as f:
    wf = json.load(f)

repaired = 0
for n in wf['nodes']:
    if n['type'] == 'n8n-nodes-base.code':
        if n['parameters'].get('mode') != 'runOnceForAllItems':
            n['parameters']['mode'] = 'runOnceForAllItems'
            repaired += 1
        if 'language' not in n['parameters'] and 'jsCode' in n['parameters']:
            n['parameters']['language'] = 'javaScript'
    if n['type'] == '@n8n/n8n-nodes-langchain.outputParserStructured':
        if n['parameters'].get('schemaType') == 'manual' and 'inputSchema' not in n['parameters']:
            n['parameters']['inputSchema'] = json.dumps({
                'type': 'object',
                'properties': {
                    'score': {'type': 'number', 'minimum': 0, 'maximum': 1},
                    'reasoning': {'type': 'string', 'maxLength': 200}
                },
                'required': ['score']
            }, ensure_ascii=False, indent=2)
            repaired += 1
    if n['type'] == '@n8n/n8n-nodes-langchain.chainLlm' and 'options' not in n['parameters']:
        n['parameters']['options'] = {}
        repaired += 1

for key in ('id', 'meta', 'versionId', 'tags'):
    wf.pop(key, None)

with open(WF_PATH, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

print(f'Fixed {repaired} stripped field(s) in {WF_PATH}' if repaired else f'No fixes needed in {WF_PATH}')
