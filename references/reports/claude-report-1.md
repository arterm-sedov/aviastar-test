Here's a comprehensive primer for this project, followed by the swimlane diagram.

---

## Project primer: MVP RAG AI assistant for Legal/HR

### Your situation in one paragraph
You have a working LangChain/Python RAG engine. The task requires wrapping it in n8n as the orchestration layer with Supabase pgvector as the vector store and a Telegram bot as the UI. Your Python instincts are an asset — n8n lets you run Python (or JS) code nodes, so you can port your existing chunking/embedding logic as-is and wire it together visually.

### Architecture decisions to lock in first

**Vector DB:** Use Supabase (pgvector) as specified. It's free tier is sufficient for demo, and the TZ explicitly names it. Pinecone is mentioned as an alternative but Supabase gives you both the vector store and a logging table in one service.

**LLM:** OpenAI (`text-embedding-ada-002` for embeddings, `gpt-4o-mini` for generation) or Anthropic Claude via API. The TZ doesn't specify — either is fine for the demo.

**n8n deployment path:** Self-host via Docker/WSL first (works offline, fast iteration), then push to HuggingFace Spaces via the Docker Space SDK. The self-hosted-ai-starter-kit repo you found is the right starting point — it gives you n8n + Qdrant (swap Qdrant for Supabase).

**Telegram auth:** n8n has a native Telegram trigger node. Whitelist check = compare `message.from.id` against a hardcoded array (or a Supabase `allowed_users` table) in the first node of every workflow.

---

### Day-by-day plan (4–5 working days)

**Day 1 — Infrastructure**
- Spin up n8n locally via Docker Compose (use the self-hosted-ai-starter-kit as base, add Supabase env vars instead of Qdrant)
- Create Supabase project, enable pgvector extension, create `documents` table with `content text`, `embedding vector(1536)`, `metadata jsonb` columns
- Create `request_log` table: `id`, `user_id`, `question`, `answer`, `sources`, `score`, `confidence`, `created_at`, `bad_flag`
- Set up Telegram bot via BotFather, get token, store in `.env`

**Day 2 — Document indexing pipeline**
- Build n8n workflow: Manual trigger → Read files (PDFs/DOCX from folder) → Code node (Python/JS to chunk with 500-token chunks, 50-token overlap) → OpenAI Embeddings node → Supabase insert
- Demo documents: grab 3–5 Labor Code PDFs from `consultant.ru` open access, 1–2 HR policy templates from open GitHub repos, 1 transport regulation PDF
- External source: use the Russian Federal Labour Inspection site (онлайнинспекция.рф) — its FAQ pages are scrapable and HR-relevant
- Test: run indexing, verify vectors in Supabase with `SELECT count(*) FROM documents`

**Day 3 — RAG pipeline in n8n**
- Build the main Q&A workflow (see swimlane diagram below):
  - Telegram trigger → whitelist check → request classification (Code node with simple keyword matching: "договор/шаблон" → template route, everything else → normative Q route)
  - Normative route: embed query (OpenAI) → Supabase similarity search (`match_documents` RPC) → confidence check (use cosine similarity score, reject if max score < 0.75) → LLM node with prompt "Answer using ONLY these sources, cite each fact" → format response with source list
  - Template route: Code node that fills a DOCX/text template with extracted entities (no LLM for final output — LLM only extracts field values from the question)
- Add rating buttons using Telegram inline keyboard (👍/👎 callback)

**Day 4 — Logging, error handling, polish**
- Log every request to Supabase `request_log` table
- On 👎 callback: set `bad_flag=true` → triggers a separate n8n workflow that posts to a dedicated "review" Telegram group or Google Sheet
- Handle edge cases: no chunks found → "Недостаточно данных в базе" message; LLM timeout → retry once
- Add basic analytics: a second workflow triggered daily that counts requests, top questions, avg confidence — posts summary to a private channel

**Day 5 — HuggingFace Spaces deployment + demo prep**
- Create HF Space with Docker SDK (see the `tomowang/n8n` Space you found as a reference)
- Key HF Spaces gotcha: persistent storage via `/data` volume, set `N8N_USER_FOLDER=/data` in Dockerfile
- All secrets go in HF Space "Repository secrets" (not hardcoded)
- Export n8n workflows as JSON, import on the HF instance
- Prepare 3 demo questions: one normative (трудовое право), one template request, one that triggers the "low confidence" path to show the guard works

---

### n8n specifics for a Python developer

n8n workflows are JSON files. You can absolutely write them by hand or generate them programmatically — each node has an `id`, `type`, `parameters`, and `position`. The GUI is essentially a visual editor for that JSON. Useful pattern: build one workflow in the GUI, export it, then edit the JSON directly for repetitive nodes.

The **Code node** runs JS by default but supports Python if you check "Python" in the language dropdown. Your existing chunking logic from `cmw-rag` can paste almost directly into a Code node. The node receives input as `$input.all()` and returns objects in an array.

For Supabase vector search, use the **HTTP Request node** to call Supabase's REST API with the `match_documents` RPC function (a stored procedure you create in Supabase that runs `<=>` cosine similarity). Alternatively, n8n has a community Supabase node — check if it supports pgvector RPC calls before relying on it.

---

### Key risks to mention in your submission

The TZ has a "Риски / Опишите риски" section. Flag these: (1) LLM hallucination on legal content is mitigated by the confidence threshold and source-citation requirement, but not eliminated — human review of all template outputs is mandatory; (2) the external source integration (КонсультантПлюс) has no official API — demo uses public scraping which may break; (3) HuggingFace Spaces has cold-start latency (up to 30s) which conflicts with the "1–2 minute response" SLA — production would need a always-on VPS.

---

Now the swimlane diagram:

The dashed red arrows show the two guard rails: (1) unauthorized users get rejected immediately at the Telegram Bot layer, and (2) low-confidence results never reach the LLM — the pipeline drops the request with a "нет данных" message. The dashed gray audit-log arrow at the bottom shows that every conversation gets persisted regardless of outcome. Click any node to drill into that step.

---

### What to answer in "ЧТО НУЖНО ОТ ЗАКАЗЧИКА"

Before you build, send back these questions to the recruiter/ZGD:

1. Which LLM provider is approved — OpenAI, Anthropic, or a self-hosted model? (Affects cost and data privacy)
2. Is there a sample pack of real internal documents (even with PII redacted) to test against, or do you build entirely on open sources?
3. Who are the 3–5 pilot users for the Telegram whitelist?
4. For the template generation step — which 1–2 specific templates (договор найма, приказ, etc.) should be demonstrated?
5. Is HuggingFace Spaces acceptable as a demo host, or does the company require the instance to run on their infrastructure?

