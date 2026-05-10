# AGENTS.md - Aviastar n8n RAG AI Assistant

n8n workflow automation for Legal/HR RAG pipeline. Supabase pgvector + Gemini LLM.

**Implementations follow:** SDD, lean, DRY, non-breaking, 12-factor. Always research before coding.

## Research & Planning

- Research n8n node configs with `get_node` MCP tool before adding nodes.
- Reference n8n source at `C:\Repos\n8n` for node implementations.
- Plan workflow changes before editing JSON — validate after each change.
- Deep web research for n8n docs: https://docs.n8n.io, GitHub issues.

## Engineering Baseline

- **Non-breaking:** Never break existing functionality. Test after each push.
- **Lean:** Remove dead nodes, unused connections, unnecessary complexity.
- **DRY:** Reuse patterns (embedding pipeline, metadata preparation).
- **SDD:** Spec-driven — the PDF spec at `references/docs/ТЗ_AI ассистент_HR_ЮрО.md` is the contract.
- **12-factor:** API keys in env vars, never in JSON/workflow. Backing services as attached resources.

## Dev Commands

```powershell
# Validate workflow JSON before pushing
# (uses n8n-mcp validate_workflow tool)

# Push to local n8n (requires N8N_API_KEY env var)
.\n8n\push.ps1

# Pull from local n8n
.\n8n\pull.ps1 -WorkflowId "QwHk77OeKJzgsxpU"

# Verify n8n container
docker ps --filter "name=n8n"
docker logs n8n --tail 10

# Direct API test
$env:N8N_API_KEY="<key>"; $headers=@{"X-N8N-API-KEY"=$env:N8N_API_KEY}
Invoke-RestMethod -Uri "http://localhost:5678/api/v1/workflows" -Headers $headers
```

## Project Structure

- **`n8n/legal-rag.json`** — Main RAG workflow (source of truth, git-versioned)
- **`n8n/push.ps1`** — Deploy JSON to local n8n via REST API
- **`n8n/pull.ps1`** — Pull current state from n8n back to JSON
- **`sample-docs/`** — PDF documents for RAG indexing (mounted to n8n at `/docs`)
- **`references/`** — Reference workflows, AI research reports, URL bookmarks
- **`.agents/skills/`** — n8n skills for this repo

## Workflow Architecture

**Chat flow:** RAG Chatbot → Text Classifier (AI) → Gemini AI Agent → Supabase Vector Store → Confidence Check → Response

**Indexing flow:** Local Files (`/docs/*`) + Web (trudkod.ru) → Extract Text → Embeddings → Supabase Vector Store

**Key rules (from spec):**
- No answer without source or insufficient confidence (threshold: 0.6)
- No final legal docs through LLM without human verification
- LLM for search + answers; templates filled via code, not LLM
- Telegram bot with authorization (MVP phase 2)

## Security

- N8N_API_KEY in Windows user env var, never committed.
- Google Gemini API key in n8n credentials, not in workflow JSON.
- .gitignore excludes `.mcp.json`, `.env`, `*.log`, secrets.

## Commit Guidelines

- Only commit when explicitly asked.
- Keep messages concise: `"section: what changed"`.
- Generated message only — don't add/stage/push unless requested.

## n8n-Specific Notes

- Docker volume `n8n_data` persists workflows/credentials across container rebuilds.
- `docker volume rm n8n_data` = data loss. Never run without explicit user request.
- n8n v2.19.5 (stable tag = `docker.n8n.io/n8nio/n8n:latest`).
- API: `POST /api/v1/workflows` accepts `{name, nodes, connections, settings}`.
- Read/Write Files node looks relative to n8n container install path; use absolute paths.
- Text Classifier needs `ai_languageModel` connection to a model node.
