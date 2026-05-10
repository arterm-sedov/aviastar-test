Here is a complete execution primer for your 4–5 day MVP. I have broken it into a **roadmap**, a **Python → n8n architecture map**, **deployment notes for Docker/WSL → Hugging Face Spaces**, and the **Swimlane BPMN diagram** you need as a deliverable.

---

## 1. Swimlane BPMN Diagram (Deliverable)

This covers the full MVP flow: User → Telegram → n8n RAG Orchestrator → Data Storage, including the feedback loop and template-generation safety branch.

![MVP Swimlane BPMN](sandbox:///mnt/agents/output/swimlane_bpmn_rag.png)

**Lane walkthrough:**
- **Пользователь** — initiates the query and provides thumbs-up/down feedback.
- **Telegram-бот** — receives messages, sends answers with inline rating buttons, and captures callbacks.
- **n8n RAG Orchestrator** — runs whitelist auth, classifies the query (legal / HR / template), retrieves chunks from Supabase pgvector, scores confidence, generates an answer via LLM (with sources), logs the interaction, and flags bad answers for review.
- **Хранилище данных** — Supabase pgvector for semantic search; Supabase/Google Sheets for logs and analytics.

---

## 2. Your LangChain/Python → n8n Translation Map

Since you already built [`cmw-rag`](https://github.com/arterm-sedov/cmw-rag), you are not starting from zero. You are *porting* your logic from imperative Python to declarative n8n nodes (with JSON under the hood).

| Your Python / LangChain Stack | n8n MVP Equivalent | Practical Note |
|---|---|---|
| `PyPDFLoader`, `Unstructured` | **Read Binary Files** → **Extract from File** (or pre-convert to `.txt`/`.md`) | For 4–5 days, pre-convert docs to text outside n8n to avoid parser dependencies inside the container. |
| `TokenTextSplitter(chunk_size=500, overlap=50)` | **Code node** (JavaScript or Python) | n8n has no native token splitter. The standard n8n image is Node-based, so **JS in a Code node** is the path of least resistance. If you absolutely need Python inside n8n, you must extend the Dockerfile (see Docker section). |
| `OpenAIEmbeddings` | **Embeddings OpenAI** node | Native AI node. |
| `SupabaseVectorStore.from_documents()` | **Supabase Vector Store** node (insert) | Native AI node. |
| `similarity_search_with_score()` | **Vector Store Retriever** node | Returns documents. Scores are not always exposed in the UI node; implement a confidence gate with a downstream **Code** or **IF** node. |
| `RetrievalQAChain` + custom prompt | **LLM Chain** node OR **Code** node + **OpenAI** node | I recommend a **Code** node to assemble the prompt with citations, then call OpenAI via an **OpenAI Chat Model** node. This gives you exact control over source attribution. |
| `python-telegram-bot` | **Telegram Trigger** + **Telegram** nodes | Native and robust. Use **Polling** for HF Spaces (webhooks break when the Space sleeps). |
| Custom analytics DB | **Supabase** node or **Google Sheets** node | Zero-code logging. |

**Key mental model:** n8n workflows are JSON. Every node you drag in the GUI is an entry in a `nodes[]` array, and every connection is an entry in a `connections{}` object. You can export the JSON, edit it in VS Code, and re-import it. This is perfect for your background.

---

## 3. 5-Day Execution Roadmap

### Day 1 — Infrastructure & Document Indexing
**Goal:** Vector DB is live and documents are indexed.

1. **Local stack (WSL/Docker):**
   ```yaml
   # docker-compose.yml (minimal)
   services:
     n8n:
       image: n8nio/n8n
       ports:
         - "5678:5678"
       environment:
         - N8N_BASIC_AUTH_ACTIVE=true
         - N8N_BASIC_AUTH_USER=admin
         - N8N_BASIC_AUTH_PASSWORD=strongpass
         - WEBHOOK_URL=http://localhost:5678/
       volumes:
         - ~/.n8n:/home/node/.n8n
   ```
   *Run with `docker compose up`.*

2. **Supabase project:** Create a new project, enable the `vector` extension, and create a table:
   ```sql
   create table documents (
     id bigint primary key generated always as identity,
     content text,
     metadata jsonb,
     embedding vector(1536)
   );
   ```

3. **Document package (open source):**
   - Трудовой кодекс РФ (txt)
   - ФЗ № 259-ФЗ "О безопасности дорожного движения" (for transport law)
   - Типовой трудовой договор (from Минтруда)
   - 2–3 mocked "internal" policies (e.g., "Политика удаленной работы", "Регламент командировок")
   - One external legal source of your choice (e.g., ГК РФ excerpts)

4. **Chunking strategy:** Because the task specifies `TokenTextSplitter(chunk_size=500, chunk_overlap=50)`, run this **once** in your local Python environment (your `cmw-rag` repo) to generate a JSONL/CSV of chunks with metadata (`{file, section, date}`). Then use n8n only for the *embedding* and *insert* steps.
   - *Why?* Avoids installing Python inside the n8n container for the MVP, saving you hours.

5. **Indexing workflow in n8n:** `Manual Trigger` → `Read Binary Files` → `Spreadsheet File` (or `Code` node to read JSONL) → `Embeddings OpenAI` → `Supabase Vector Store` (insert).

### Day 2 — Core RAG Pipeline
**Goal:** A workflow that takes a question and returns a cited answer.

Workflow: `Telegram Trigger` → `Auth Check (IF)` → `Set` (normalize query) → `Vector Store Retriever` (Supabase, topK=4) → `Code: Confidence Gate` → `LLM Chain` → `Code: Format Answer` → `Telegram: Send Message`.

- **Confidence gate:** If the retriever returns zero documents, route to a fallback message: *"В базе знаний недостаточно информации. Обратитесь к юристу."* Do not call the LLM.
- **Prompt template (in Code node):**
  ```
  Контекст:
  {context}

  Вопрос сотрудника: {question}

  Инструкция: Ответь строго на основе контекста. Укажи источники [файл, раздел]. 
  Если ответ не найден в контексте, скажи "Недостаточно данных".
  ```
- **Citations:** Append source metadata from the retriever to the final Telegram message.

### Day 3 — Telegram Bot, Auth & Template Branch
**Goal:** Whitelist security and 1–2 document templates.

1. **Auth:** In the `IF` node after `Telegram Trigger`:
   - Left value: `{{ $json.message.from.id }}`
   - Operation: `IN` (or string equals list check via Code node)
   - Right value: your whitelist from env var `TELEGRAM_WHITELIST` (e.g., `123456,789012`).
   - If unauthorized → `Telegram: Send Message` ("Access denied") → Stop.

2. **Classifier:** Use a small `LLM Chain` or `Code` node to classify intent: `legal_question`, `hr_question`, `template_request`. For MVP, a keyword-based Code node is acceptable and faster.

3. **Template branch (safety-critical):**
   - If `template_request` → retrieve the template from vector store → `Code` node does string replacement (do **not** let the LLM invent clauses) → return a **draft** with a mandatory disclaimer: *"Черновик. Требует проверки юриста перед подписанием."*

### Day 4 — Logging, Feedback & Analytics
**Goal:** Every interaction is stored and rated.

1. **Logging workflow:** After the answer is sent, insert a row into Supabase (or Google Sheets):
   - `user_id`, `query`, `classified_intent`, `retrieved_sources`, `answer_text`, `timestamp`, `feedback` (null).

2. **Feedback buttons:** In the `Telegram: Send Message` node, add `reply_markup` JSON for an inline keyboard:
   ```json
   {"inline_keyboard": [[{"text":"👍","callback_data":"up:{{ $run.executionId }}"},{"text":"👎","callback_data":"down:{{ $run.executionId }}"}]]}
   ```

3. **Feedback handler workflow:** `Telegram Trigger` (set to `callback_query`) → parse `callback_data` → `Supabase` (update row, set `feedback='up'`/`'down'`) → if `down`, set `needs_review=true`.

### Day 5 — BPMN Polish, Testing & HF Spaces Packaging
**Goal:** Working demo + deployable artifact.

- Run the swimlane diagram (delivered above).
- Test: unauthorized user, empty retrieval, template request, thumbs-down callback.
- Package for HF Spaces.

---

## 4. Docker & HF Spaces Deployment

You mentioned self-hosting in WSL first, then pushing to HF Spaces. Here is the critical path.

### Local (WSL)
The `docker-compose.yml` above is sufficient. Access n8n at `http://localhost:5678`.

### HF Spaces Docker Deployment
HF Spaces expects a `Dockerfile` and exposes port `7860` by default.

**Key constraints:**
- **Ephemeral filesystem:** When the Space sleeps, local files disappear. You **must** store all state in Supabase (vector DB + logs). n8n’s internal SQLite will reset on sleep, which means workflow definitions disappear unless you use an external Postgres DB or re-import workflows on startup.
- **Pragmatic MVP fix:** Keep `N8N_BASIC_AUTH_*` env vars, and after the Space wakes up, re-import your workflow JSON via n8n’s REST API if needed. For a 30-minute demo call, this is acceptable; just mention it as a "Stage 2" requirement to move n8n’s DB to external Postgres.

**Sample Dockerfile for HF Spaces:**
```dockerfile
FROM n8nio/n8n:latest
ENV N8N_PORT=7860
ENV N8N_PROTOCOL=https
ENV N8N_HOST=0.0.0.0
# Force basic auth so the public Space isn't wide open
ENV N8N_BASIC_AUTH_ACTIVE=true
ENV N8N_BASIC_AUTH_USER=admin
ENV N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
# All secrets via HF Space env vars (never hardcoded)
ENV TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
ENV OPENAI_API_KEY=${OPENAI_API_KEY}
ENV SUPABASE_URL=${SUPABASE_URL}
ENV SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
ENV TELEGRAM_WHITELIST=${TELEGRAM_WHITELIST}
EXPOSE 7860
CMD ["n8n", "start"]
```

**Telegram on HF Spaces:** Use **polling**, not webhooks. HF Spaces sleep after inactivity, which breaks webhook endpoints. Polling resumes automatically when the container restarts.

---

## 5. n8n Workflow as JSON (Leverage Your Strength)

Since you are comfortable coding JSON, use the GUI to prototype, then **export the JSON** and refine it in your IDE. The structure is:

```json
{
  "name": "RAG_HR_Legal_MVP",
  "nodes": [
    {
      "parameters": { "events": ["message"] },
      "id": "telegram-trigger-1",
      "name": "Telegram Trigger",
      "type": "n8n-nodes-base.telegramTrigger",
      "typeVersion": 1.1,
      "position": [250, 300],
      "webhookId": "webhook-telegram"
    },
    {
      "parameters": {
        "conditions": {
          "options": { "caseSensitive": true },
          "conditions": [
            {
              "id": "auth-check",
              "leftValue": "={{ $json.message.from.id }}",
              "rightValue": "={{ $env.TELEGRAM_WHITELIST }}",
              "operator": { "type": "string", "operation": "contains" }
            }
          ]
        }
      },
      "name": "Auth Check",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [450, 300]
    }
  ],
  "connections": {
    "Telegram Trigger": {
      "main": [[{ "node": "Auth Check", "type": "main", "index": 0 }]]
    }
  }
}
```

You can version-control this JSON in GitHub and load it via n8n’s `/rest/workflows` API.

---

## 6. Risk & Compliance Checklist (Required in Deliverables)

The task explicitly asks you to address risks. Bake these into your demo narrative:

| Риск | Митигация в MVP |
|---|---|
| **Галлюцинация LLM в договоре** | Финальные документы не генерируются LLM. Шаблоны заполняются через Code-ноду (string replacement). Выводится дисклеймер: *"Черновик, требует проверки юриста."* |
| **Устаревшие нормы** | Для MVP используем открытые источники. В интервью озвучить, что Stage 2 включает автообновление через API КонсультантПлюс/Гарант. |
| **Несанкционированный доступ** | Whitelist Telegram ID + базовая авторизация n8n (Basic Auth) на HF Spaces. |
| **Утечка данных** | API-ключи только в env vars. Ни одного хардкода в workflow JSON. |
| **Низкая точность ответа** | Скоринг уверенности + fallback. Если релевантных чанков нет — отказ от генерации. |

---

## 7. What to Show on the Demo Call

1. **BPMN diagram** (swimlane) — explain lanes and data flow.
2. **Live Telegram bot** — ask a legal question, get an answer with citations.
3. **Template path** — request a contract draft, show code-based filling + disclaimer.
4. **Security** — show rejection from an unauthorized Telegram ID.
5. **Feedback loop** — press 👎, show the log updating in Supabase/GSheets with `needs_review=true`.
6. **Architecture summary** — 4-5 day timeline, n8n + Supabase pgvector, env-var security, HF Spaces deployment.

---

## 8. Quick-Start Command Cheat Sheet

```bash
# 1. Local n8n
mkdir ~/n8n-rag && cd ~/n8n-rag
# paste the docker-compose.yml above
docker compose up -d

# 2. Open n8n
# http://localhost:5678 (admin / strongpass)

# 3. Export workflow JSON for version control
# Settings (in GUI) → Export JSON

# 4. HF Spaces push (after creating Space with Docker SDK)
git init
git add Dockerfile docker-compose.yml workflow.json
git commit -m "mvp"
git push
```

---

**Bottom line:** Treat n8n as a visual workflow orchestrator where your Python logic lives in **Code nodes** and your LangChain primitives (embeddings, vector store) are replaced by native **AI nodes**. Your existing RAG knowledge is 80% of the work; the remaining 20% is learning n8n’s node wiring and JSON schema. The diagram above is your BPMN deliverable, and the 5-day roadmap keeps you inside the recruiter’s deadline.