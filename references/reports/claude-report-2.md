## Полный пошаговый план реализации MVP

Предпосылки: у тебя работает first-MVP.json (embedding + LLM + Supabase + chat), значит credentials уже в n8n. Дальше строим поверх этого.

---

## PHASE 0 — Supabase Schema Setup
**Время:** 30 мин | **Делается один раз**

### 0.1 Таблица для документов (векторное хранилище)

Открой Supabase → SQL Editor, выполни:

```sql
-- Включи pgvector если не включён
create extension if not exists vector;

-- Основная таблица для чанков
create table documents (
  id bigint primary key generated always as identity,
  content text not null,
  metadata jsonb,
  embedding vector(1536)
);

-- Индекс для ускорения поиска
create index on documents 
using ivfflat (embedding vector_cosine_ops)
with (lists = 100);

-- Функция поиска (ОБЯЗАТЕЛЬНО для n8n Supabase Vector Store)
create or replace function match_documents(
  query_embedding vector(1536),
  match_count int default 5,
  filter jsonb default '{}'
)
returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    d.id,
    d.content,
    d.metadata,
    1 - (d.embedding <=> query_embedding) as similarity
  from documents d
  where d.metadata @> filter
  order by d.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

### 0.2 Таблица для логов запросов

```sql
create table request_log (
  id bigint primary key generated always as identity,
  created_at timestamptz default now(),
  user_id bigint,
  username text,
  query text,
  intent text,          -- 'normative' | 'template' | 'unknown'
  answer text,
  sources jsonb,        -- [{file, section, similarity}]
  confidence float,
  feedback smallint,    -- null | 1 (good) | -1 (bad)
  needs_review boolean default false,
  execution_id text
);
```

### ✅ CHECKPOINT 0
```sql
-- Проверка:
select count(*) from documents;
select count(*) from request_log;
-- Обе должны вернуть 0, без ошибок
```

---

## PHASE 1 — Подготовка документов
**Время:** 2–3 часа | **Python вне n8n**

### 1.1 Скачай документы (открытые источники)

Минимальный пакет для демо (5–7 документов):

| Документ | Источник | Формат |
|---|---|---|
| Трудовой кодекс РФ | [trudkodeks.ru](https://www.trudkodeks.ru/trudkodeks/trud/trudovoj_kodeks_rossijskoj_federacii.html) | HTML → txt |
| ФЗ №196 "О БДД" | [consultant.ru](https://www.consultant.ru/document/cons_doc_LAW_17585/) | txt |
| Правила перевозок грузов (ПП №2200) | [docs.cntd.ru](https://docs.cntd.ru/document/573464126) | txt |
| Типовой трудовой договор | [rosmintrud.ru](https://mintrud.gov.ru/) | docx/txt |
| Шаблон договора оказания услуг | любой открытый образец | txt |
| Политика удалённой работы (mock) | создай сам, 1–2 страницы | txt |
| FAQ онлайнинспекция.рф | [онлайнинспекция.рф/questions](https://онлайнинспекция.рф) | scrape |

Для FAQ онлайнинспекция.рф — это твой "внешний источник". Простой scraper:

```python
# scrape_oninspection.py
import requests
from bs4 import BeautifulSoup
import json, time

base_url = "https://онлайнинспекция.рф"
# Используй публичный раздел вопросов/ответов
# Сохраняй как txt файлы с метаданными
```

### 1.2 Чанкинг с метаданными (Python скрипт)

Запусти один раз локально, получишь JSONL для загрузки:

```python
# chunk_documents.py
import tiktoken
import json
from pathlib import Path
from datetime import datetime

def chunk_text(text, chunk_size=500, chunk_overlap=50, encoding_name="cl100k_base"):
    """TokenTextSplitter аналог через tiktoken"""
    enc = tiktoken.get_encoding(encoding_name)
    tokens = enc.encode(text)
    
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = enc.decode(chunk_tokens)
        chunks.append(chunk_text)
        if end == len(tokens):
            break
        start += chunk_size - chunk_overlap
    return chunks

def process_file(filepath: Path, source_name: str, section: str = ""):
    text = filepath.read_text(encoding='utf-8')
    chunks = chunk_text(text)
    
    records = []
    for i, chunk in enumerate(chunks):
        records.append({
            "content": chunk.strip(),
            "metadata": {
                "file": source_name,
                "section": section or f"chunk_{i+1}",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source_path": str(filepath)
            }
        })
    return records

# Обработай все файлы
all_records = []
docs_dir = Path("./docs")

file_map = {
    "trudovoy_kodeks.txt": ("Трудовой кодекс РФ", ""),
    "fz_196_bdd.txt": ("ФЗ №196 О безопасности дорожного движения", ""),
    "pp_2200_perevozki.txt": ("Правила перевозок грузов ПП №2200", ""),
    "tipovoy_trudovoy_dogovor.txt": ("Типовой трудовой договор Минтруда", "Шаблон"),
    "dogovor_uslug_shablon.txt": ("Шаблон договора оказания услуг", "Шаблон"),
    "politika_udalennoy_raboty.txt": ("Политика удалённой работы", "Внутренний регламент"),
    "oninspection_faq.txt": ("FAQ Онлайнинспекция.рф", "Внешний источник"),
}

for filename, (source_name, section) in file_map.items():
    filepath = docs_dir / filename
    if filepath.exists():
        records = process_file(filepath, source_name, section)
        all_records.extend(records)
        print(f"✓ {source_name}: {len(records)} чанков")

# Сохрани в JSONL
with open("chunks.jsonl", "w", encoding="utf-8") as f:
    for record in all_records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"\nИтого: {len(all_records)} чанков → chunks.jsonl")
```

```bash
pip install tiktoken
python chunk_documents.py
# Ожидаемый вывод: 150-600 чанков зависимо от объёма документов
```

### ✅ CHECKPOINT 1
```bash
wc -l chunks.jsonl
# Должно быть > 50 строк
head -n 2 chunks.jsonl | python -m json.tool
# Проверь структуру: content, metadata.file, metadata.section, metadata.date
```

---

## PHASE 2 — Workflow 1: Индексация документов
**Время:** 1–2 часа | **В n8n**

### 2.1 Создай новый workflow "01_Document_Indexing"

Структура нодов (слева → вправо):

```
Manual Trigger
    ↓
Read Binary File  (chunks.jsonl)
    ↓
Code: Parse JSONL
    ↓
[Split in Batches]  ← 10 записей за раз (rate limiting)
    ↓
Embeddings OpenAI ←─────────┐
    |                       |
Supabase Vector Store       |
(mode: insert)    ──────────┘
    ↓
Set: Log result
```

### 2.2 Конфигурация каждого нода

**Manual Trigger** — без настроек, просто trigger.

**Read Binary File:**
- File Path: `/home/node/.n8n/chunks.jsonl` (скопируй файл туда, или используй абсолютный путь)
- Альтернатива: если n8n в Docker, примонтируй папку и используй путь.

Если путь к файлу неудобен — используй **HTTP Request** для чтения файла из GitHub raw или любого URL.

**Code: Parse JSONL:**
```javascript
// Читаем binary данные и парсим каждую строку как JSON
const binaryData = $input.first().binary.data;
const text = Buffer.from(binaryData, 'base64').toString('utf-8');
const lines = text.split('\n').filter(line => line.trim());

const items = lines.map(line => {
  const parsed = JSON.parse(line);
  return {
    json: {
      content: parsed.content,
      metadata: parsed.metadata
    }
  };
});

return items;
```

**Split in Batches:**
- Batch Size: `10`
- (Это предотвращает rate limit на OpenAI Embeddings API)

**Embeddings OpenAI** (sub-node):
- Model: `text-embedding-3-small` (1536 dims, дешевле)
- Connect as: `ai_embedding` вход к Supabase Vector Store

**Supabase Vector Store:**
- Operation: `Insert Documents`
- Table Name: `documents`
- Query Name (for retrieval): `match_documents`
- Content Field: `content`
- Metadata Field: `metadata`

**Set: Log result:**
```javascript
// Просто чтобы видеть прогресс
return [{json: {status: "indexed", count: $input.all().length}}];
```

### 2.3 Запуск индексации

1. Нажми "Execute Workflow" на Manual Trigger
2. Наблюдай прогресс — каждый батч проходит через embedding
3. После завершения:

### ✅ CHECKPOINT 2
```sql
-- В Supabase SQL Editor:
select count(*) from documents;
-- Должно быть > 50

select metadata->>'file' as source, count(*) as chunks
from documents
group by metadata->>'file'
order by chunks desc;
-- Покажет сколько чанков с каждого документа

-- Тест поиска вручную:
select content, metadata, 
       1 - (embedding <=> (select embedding from documents limit 1)) as sim
from documents
order by sim desc
limit 3;
-- Должен вернуть похожие чанки
```

---

## PHASE 3 — Workflow 2: Основной RAG Pipeline (Telegram)
**Время:** 3–4 часа | **Ключевой workflow**

### 3.1 Структура workflow "02_Main_RAG_Bot"

```
Telegram Trigger
    ↓
IF: Auth Check (whitelist)
    ├── FALSE → Telegram: "Доступ запрещён" → STOP
    └── TRUE ↓
Code: Normalize Input
    ↓
Code: Classify Intent
    ├── "template" → [Template Branch] (Phase 4)
    ├── "unknown"  → Telegram: "Уточните запрос" → Log → STOP
    └── "normative" ↓
HTTP Request: match_documents RPC  ← напрямую через REST, получаем scores
    ↓
Code: Confidence Gate
    ├── LOW → Telegram: "Нет данных" → Log → STOP
    └── HIGH ↓
LLM Chain (с контекстом)
    ↓
Code: Format Answer + Sources
    ↓
Telegram: Send Message (+ inline keyboard 👍/👎)
    ↓
Supabase: Insert to request_log
```

### 3.2 Конфигурация каждого нода

**Telegram Trigger:**
- Bot Token: из credentials (уже настроено)
- Events: `message`
- Дополнительно: НЕ используй встроенный whitelist Trigger'а — делай его в следующем IF node (больше гибкости)

**IF: Auth Check:**
- Condition type: `String`
- Value 1: `{{ $json.message.from.id.toString() }}`
- Operation: `Contains`
- Value 2: `{{ $env.TELEGRAM_WHITELIST }}`

В n8n → Settings → Environment Variables добавь:
```
TELEGRAM_WHITELIST = 123456789,987654321
```
(telegram user IDs через запятую, без пробелов)

Если FALSE — подключи **Telegram** node:
- Operation: `Send Message`
- Chat ID: `{{ $json.message.chat.id }}`
- Text: `⛔ Доступ запрещён. Обратитесь к администратору.`

**Code: Normalize Input:**
```javascript
const msg = $input.first().json;
return [{
  json: {
    user_id: msg.message.from.id,
    username: msg.message.from.username || msg.message.from.first_name,
    chat_id: msg.message.chat.id,
    message_id: msg.message.message_id,
    query: msg.message.text?.trim() || "",
    raw: msg
  }
}];
```

**Code: Classify Intent:**
```javascript
const query = $input.first().json.query.toLowerCase();

// Ключевые слова для классификации
const templateKeywords = [
  'шаблон', 'договор', 'составь договор', 'черновик', 'образец',
  'бланк', 'заявление', 'приказ о', 'трудовой договор с'
];
const normativeKeywords = [
  'сколько', 'когда', 'можно ли', 'обязан', 'требования',
  'порядок', 'срок', 'закон', 'статья', 'нарушение', 'штраф',
  'отпуск', 'увольнение', 'зарплата', 'компенсация', 'перевозк'
];

let intent = 'normative'; // default

for (const kw of templateKeywords) {
  if (query.includes(kw)) { intent = 'template'; break; }
}

// Если запрос слишком короткий или непонятный
if (query.length < 10) { intent = 'unknown'; }

const input = $input.first().json;
return [{
  json: { ...input, intent }
}];
```

**HTTP Request: match_documents RPC:**

Используй HTTP Request вместо Vector Store node — так получаешь `similarity` score:

- Method: `POST`
- URL: `{{ $env.SUPABASE_URL }}/rest/v1/rpc/match_documents`
- Headers:
  - `apikey`: `{{ $env.SUPABASE_SERVICE_KEY }}`
  - `Authorization`: `Bearer {{ $env.SUPABASE_SERVICE_KEY }}`
  - `Content-Type`: `application/json`
- Body (JSON):
```json
{
  "query_embedding": "={{ $json.embedding }}",
  "match_count": 5,
  "filter": {}
}
```

НО — перед этим нужно получить embedding запроса. Вставь нод до HTTP Request:

**OpenAI: Create Embedding** (или HTTP Request к OpenAI):
- Model: `text-embedding-3-small`
- Input: `{{ $json.query }}`
- Это вернёт `data[0].embedding`

После получения embedding — передаём в match_documents.

На практике чище сделать через два HTTP Request:

**HTTP Request: Get Embedding:**
- URL: `https://api.openai.com/v1/embeddings`
- Method: POST
- Headers: `Authorization: Bearer {{ $env.OPENAI_API_KEY }}`
- Body:
```json
{
  "model": "text-embedding-3-small",
  "input": "={{ $json.query }}"
}
```

После этого в следующем Code node:
```javascript
const prev = $input.first().json;
const embedding = prev.data[0].embedding;
// Передаём embedding дальше вместе с остальными данными
const context = $('Code: Classify Intent').first().json;
return [{ json: { ...context, embedding } }];
```

Затем **HTTP Request: Supabase match_documents:**
```json
{
  "query_embedding": "={{ $json.embedding }}",
  "match_count": 5,
  "filter": {}
}
```

**Code: Confidence Gate:**
```javascript
const chunks = $input.all(); // массив результатов от Supabase
const context = $('Code: Normalize Input').first().json; // исходный контекст

// Порог уверенности (настрой под свой датасет, начни с 0.70)
const CONFIDENCE_THRESHOLD = 0.70;
const MIN_CHUNKS = 1;

// Фильтруем чанки выше порога
const relevantChunks = chunks.filter(c => c.json.similarity >= CONFIDENCE_THRESHOLD);

if (relevantChunks.length < MIN_CHUNKS) {
  return [{
    json: {
      ...context,
      confidence_ok: false,
      max_similarity: chunks.length > 0 ? Math.max(...chunks.map(c => c.json.similarity)) : 0,
      message: "⚠️ В базе знаний недостаточно информации по этому вопросу.\n\nПожалуйста, уточните запрос или обратитесь к специалисту."
    }
  }];
}

// Формируем контекст для LLM
const contextText = relevantChunks.map((c, i) => 
  `[${i+1}] ${c.json.content}\n(Источник: ${c.json.metadata?.file}, раздел: ${c.json.metadata?.section})`
).join('\n\n---\n\n');

const sources = relevantChunks.map(c => ({
  file: c.json.metadata?.file,
  section: c.json.metadata?.section,
  similarity: Math.round(c.json.similarity * 100) / 100
}));

return [{
  json: {
    ...context,
    confidence_ok: true,
    max_similarity: Math.max(...relevantChunks.map(c => c.json.similarity)),
    context_text: contextText,
    sources
  }
}];
```

Добавь **IF: confidence_ok:**
- Value 1: `{{ $json.confidence_ok }}`
- Operation: `Equal`
- Value 2: `true` (boolean)

FALSE → Telegram: отправить `{{ $json.message }}` → Log → STOP

**LLM Chain (OpenAI Chat Model):**

Используй нод **OpenAI Chat Model** или **LLM Chain**. Промпт через Code node перед ним:

**Code: Build Prompt:**
```javascript
const data = $input.first().json;

const systemPrompt = `Ты — AI-ассистент юридического и HR отдела. 
Отвечай ТОЛЬКО на основе предоставленного контекста.
Если ответ не найден в контексте — скажи об этом прямо.
Всегда указывай источник каждого утверждения в формате [Источник: название документа].
Не выдумывай факты. Не цитируй законы, которых нет в контексте.`;

const userPrompt = `КОНТЕКСТ:
${data.context_text}

ВОПРОС СОТРУДНИКА:
${data.query}

Дай развёрнутый ответ со ссылками на конкретные источники.`;

return [{
  json: {
    ...data,
    system_prompt: systemPrompt,
    user_prompt: userPrompt
  }
}];
```

**OpenAI Chat Model** (или HTTP Request к OpenAI):
- Model: `gpt-4o-mini` (дешевле для демо)
- System Message: `{{ $json.system_prompt }}`
- User Message: `{{ $json.user_prompt }}`
- Max Tokens: 800

**Code: Format Answer + Sources:**
```javascript
const data = $input.first().json;
const llmResponse = data.text || data.choices?.[0]?.message?.content || "";

// Формируем список источников
const sourcesText = data.sources
  .map(s => `📄 ${s.file}${s.section ? ` / ${s.section}` : ''} (${Math.round(s.similarity * 100)}%)`)
  .join('\n');

const fullMessage = `${llmResponse}\n\n──────────────\n📚 *Источники:*\n${sourcesText}`;

return [{
  json: {
    ...data,
    llm_answer: llmResponse,
    formatted_answer: fullMessage,
    // execution_id для привязки фидбека
    execution_id: $execution.id
  }
}];
```

**Telegram: Send Message (с кнопками оценки):**
- Chat ID: `{{ $json.chat_id }}`
- Text: `{{ $json.formatted_answer }}`
- Parse Mode: `Markdown`
- Additional Fields → Reply Markup:
```json
{
  "inline_keyboard": [[
    {"text": "👍 Полезно", "callback_data": "feedback:up:{{ $json.execution_id }}"},
    {"text": "👎 Не помогло", "callback_data": "feedback:down:{{ $json.execution_id }}"}
  ]]
}
```

**Supabase: Insert to request_log:**
- Operation: `Create`
- Table: `request_log`
- Columns:
  - `user_id`: `{{ $json.user_id }}`
  - `username`: `{{ $json.username }}`
  - `query`: `{{ $json.query }}`
  - `intent`: `{{ $json.intent }}`
  - `answer`: `{{ $json.llm_answer }}`
  - `sources`: `{{ JSON.stringify($json.sources) }}`
  - `confidence`: `{{ $json.max_similarity }}`
  - `execution_id`: `{{ $json.execution_id }}`

### ✅ CHECKPOINT 3
Протестируй в Telegram:
1. Напиши боту с авторизованного ID: `"Сколько дней отпуска положено по ТК РФ?"`  
   → Должен ответить с источниками и кнопками 👍/👎
2. Напиши с неавторизованного ID  
   → `"Доступ запрещён"`
3. Напиши что-то случайное: `"ааа"`  
   → Либо `"Уточните запрос"` (если < 10 символов), либо ответ с низким confidence

Проверь в Supabase:
```sql
select user_id, query, intent, confidence, created_at 
from request_log 
order by created_at desc 
limit 5;
```

---

## PHASE 4 — Template Branch
**Время:** 1–2 часа

### 4.1 Шаблоны документов

Создай два шаблонных файла и положи их в n8n или в Supabase Storage:

**template_trudovoy_dogovor.txt:**
```
ТРУДОВОЙ ДОГОВОР №{{НОМЕР_ДОГОВОРА}}

г. {{ГОРОД}}, {{ДАТА}}

{{РАБОТОДАТЕЛЬ_НАЗВАНИЕ}}, в лице {{ДИРЕКТОР_ФИО}}, действующего на основании {{ОСНОВАНИЕ}},
именуемое в дальнейшем «Работодатель», и гражданин(ка) {{РАБОТНИК_ФИО}},
именуемый(ая) в дальнейшем «Работник», заключили настоящий договор о следующем:

1. ПРЕДМЕТ ДОГОВОРА
1.1. Работник принимается на должность: {{ДОЛЖНОСТЬ}}
1.2. Место работы: {{МЕСТО_РАБОТЫ}}
1.3. Дата начала работы: {{ДАТА_НАЧАЛА}}

2. ОПЛАТА ТРУДА
2.1. Должностной оклад: {{ОКЛАД}} рублей в месяц

⚠️ ЧЕРНОВИК. Требует проверки юриста перед подписанием.
```

**template_dogovor_uslug.txt:**
```
ДОГОВОР ОКАЗАНИЯ УСЛУГ №{{НОМЕР_ДОГОВОРА}}

г. {{ГОРОД}}, {{ДАТА}}

{{ЗАКАЗЧИК_НАЗВАНИЕ}} (Заказчик) и {{ИСПОЛНИТЕЛЬ_НАЗВАНИЕ}} (Исполнитель)
заключили настоящий договор:

1. ПРЕДМЕТ
1.1. Исполнитель обязуется оказать услуги: {{ОПИСАНИЕ_УСЛУГ}}
1.2. Срок: с {{ДАТА_НАЧАЛА}} по {{ДАТА_ОКОНЧАНИЯ}}

2. СТОИМОСТЬ
2.1. Стоимость услуг: {{СТОИМОСТЬ}} рублей

⚠️ ЧЕРНОВИК. Требует проверки юриста перед подписанием.
```

### 4.2 Template Branch Workflow

После **Code: Classify Intent** (if intent == 'template'), подключи:

**Code: Extract Template Fields (LLM):**
```javascript
// LLM используем ТОЛЬКО для извлечения полей из запроса
// НЕ для генерации финального документа
const data = $input.first().json;
return [{
  json: {
    ...data,
    extraction_prompt: `Из следующего запроса извлеки данные для заполнения договора.
Верни ТОЛЬКО JSON без объяснений.

Запрос: "${data.query}"

Формат ответа:
{
  "template_type": "trudovoy" или "uslug",
  "fields": {
    "НОМЕР_ДОГОВОРА": "значение или null",
    "ДАТА": "значение или null",
    "ГОРОД": "значение или null",
    "РАБОТНИК_ФИО": "значение или null",
    "ДОЛЖНОСТЬ": "значение или null",
    "ОКЛАД": "значение или null",
    "ЗАКАЗЧИК_НАЗВАНИЕ": "значение или null",
    "ИСПОЛНИТЕЛЬ_НАЗВАНИЕ": "значение или null",
    "ОПИСАНИЕ_УСЛУГ": "значение или null"
  }
}`
  }
}];
```

Подключи **OpenAI** для экстракции, потом:

**Code: Fill Template:**
```javascript
const data = $input.first().json;
let extractedJson;

try {
  // Парсим JSON ответ LLM
  const raw = data.text || data.choices?.[0]?.message?.content || "{}";
  const cleaned = raw.replace(/```json|```/g, '').trim();
  extractedJson = JSON.parse(cleaned);
} catch(e) {
  extractedJson = { template_type: "trudovoy", fields: {} };
}

// Шаблоны (в продакшне — читать из файлов/Supabase)
const templates = {
  trudovoy: `ТРУДОВОЙ ДОГОВОР №{{НОМЕР_ДОГОВОРА}}

г. {{ГОРОД}}, {{ДАТА}}

...работник {{РАБОТНИК_ФИО}} на должность {{ДОЛЖНОСТЬ}}, оклад {{ОКЛАД}} руб.

⚠️ ЧЕРНОВИК. Требует проверки юриста перед подписанием.`,

  uslug: `ДОГОВОР ОКАЗАНИЯ УСЛУГ №{{НОМЕР_ДОГОВОРА}}

г. {{ГОРОД}}, {{ДАТА}}

Заказчик: {{ЗАКАЗЧИК_НАЗВАНИЕ}}
Исполнитель: {{ИСПОЛНИТЕЛЬ_НАЗВАНИЕ}}
Услуги: {{ОПИСАНИЕ_УСЛУГ}}

⚠️ ЧЕРНОВИК. Требует проверки юриста перед подписанием.`
};

const templateType = extractedJson.template_type || "trudovoy";
let result = templates[templateType] || templates.trudovoy;

// String replacement (НЕ LLM!)
const fields = extractedJson.fields || {};
const defaultDate = new Date().toLocaleDateString('ru-RU');

// Заполняем поля или оставляем placeholder
for (const [key, value] of Object.entries(fields)) {
  const replacement = value || `[${key}: заполнить]`;
  result = result.replaceAll(`{{${key}}}`, replacement);
}

// Остаток незаполненных полей помечаем явно
result = result.replace(/{{(\w+)}}/g, (_, field) => `[${field}: заполнить]`);

return [{
  json: {
    ...data,
    template_result: result,
    template_type: templateType,
    filled_fields: fields
  }
}];
```

Затем **Telegram: Send Message** с `{{ $json.template_result }}` и логирование.

### ✅ CHECKPOINT 4
Напиши в Telegram: `"составь черновик трудового договора для Иванова Ивана Ивановича, должность менеджер, оклад 80000 рублей, Москва"`
→ Должен вернуть заполненный черновик договора с ⚠️ дисклеймером

---

## PHASE 5 — Workflow 3: Feedback Handler + Logging
**Время:** 1 час

### 5.1 Создай новый workflow "03_Feedback_Handler"

```
Telegram Trigger (callback_query)
    ↓
Code: Parse Callback
    ↓
Supabase: Update request_log
    ↓
IF: feedback == 'down'
    ├── TRUE → Supabase: needs_review = true
    │          + Telegram: answer callback ("Спасибо, передано на ревью")
    └── FALSE → Telegram: answer callback ("Спасибо за оценку!")
```

**Telegram Trigger (Workflow 3):**
- Events: `callback_query`
- (Отдельный Trigger нод, отдельный workflow)

**Code: Parse Callback:**
```javascript
const msg = $input.first().json;
const callbackData = msg.callback_query.data; // "feedback:up:exec_id"
const [, feedbackType, executionId] = callbackData.split(':');

return [{
  json: {
    callback_query_id: msg.callback_query.id,
    chat_id: msg.callback_query.message.chat.id,
    user_id: msg.callback_query.from.id,
    feedback: feedbackType, // 'up' или 'down'
    execution_id: executionId,
    feedback_value: feedbackType === 'up' ? 1 : -1,
    needs_review: feedbackType === 'down'
  }
}];
```

**Supabase: Update request_log:**
- Operation: `Update`
- Table: `request_log`
- Filter: `execution_id = {{ $json.execution_id }}`
- Update:
  - `feedback`: `{{ $json.feedback_value }}`
  - `needs_review`: `{{ $json.needs_review }}`

**Telegram: Answer Callback Query** (убирает "часики" с кнопки):
- Operation: `Answer Callback Query`
- Callback Query ID: `{{ $json.callback_query_id }}`
- Text: `{{ $json.feedback === 'up' ? 'Спасибо! 👍' : 'Спасибо! Передано на ревью.' }}`

### 5.2 Опциональная очередь плохих ответов

Добавь в IF TRUE ветку ещё один нод — **Telegram: Send Message** в отдельный чат администратора:
- Chat ID: `{{ $env.ADMIN_CHAT_ID }}`
- Text: 
```
🚨 Плохой ответ (needs review)

Запрос: {{ $('Code: Parse Callback').first().json.execution_id }}
Проверь в Supabase: 
SELECT * FROM request_log WHERE execution_id = '{{ $json.execution_id }}';
```

### ✅ CHECKPOINT 5
1. Нажми 👎 в боте → в Supabase: `needs_review = true`, `feedback = -1`
2. Нажми 👍 → `feedback = 1`
```sql
select query, feedback, needs_review 
from request_log 
where feedback is not null
order by created_at desc;
```

---

## PHASE 6 — Workflow 4: Базовая аналитика
**Время:** 30–45 мин

### 6.1 Создай "04_Analytics_Daily"

```
Schedule Trigger (каждый день в 9:00)
    ↓
Supabase: Run SQL (аналитика)
    ↓
Code: Format Report
    ↓
Telegram: Send to Admin
```

**Supabase: Run SQL** (через HTTP Request):
```sql
select 
  date_trunc('day', created_at) as day,
  count(*) as total_queries,
  count(case when intent = 'normative' then 1 end) as normative,
  count(case when intent = 'template' then 1 end) as template,
  count(case when feedback = 1 then 1 end) as thumbs_up,
  count(case when feedback = -1 then 1 end) as thumbs_down,
  count(case when needs_review then 1 end) as needs_review,
  round(avg(confidence)::numeric, 2) as avg_confidence
from request_log
where created_at > now() - interval '7 days'
group by 1
order by 1 desc;
```

**Code: Format Report:**
```javascript
const rows = $input.all();

if (rows.length === 0) {
  return [{ json: { report: "📊 За последние 7 дней запросов не было." } }];
}

const total = rows.reduce((sum, r) => sum + parseInt(r.json.total_queries), 0);
const thumbsUp = rows.reduce((sum, r) => sum + parseInt(r.json.thumbs_up || 0), 0);
const thumbsDown = rows.reduce((sum, r) => sum + parseInt(r.json.thumbs_down || 0), 0);
const reviews = rows.reduce((sum, r) => sum + parseInt(r.json.needs_review || 0), 0);

const report = `📊 *Аналитика за 7 дней*

Всего запросов: ${total}
├ Нормативные: ${rows.reduce((s,r) => s + parseInt(r.json.normative||0), 0)}
└ Шаблоны: ${rows.reduce((s,r) => s + parseInt(r.json.template||0), 0)}

Оценки: 👍 ${thumbsUp} / 👎 ${thumbsDown}
На ревью: ${reviews}
Средний confidence: ${(rows.reduce((s,r) => s + parseFloat(r.json.avg_confidence||0), 0) / rows.length).toFixed(2)}

_По дням:_
${rows.map(r => `${r.json.day?.split('T')[0]}: ${r.json.total_queries} запросов`).join('\n')}`;

return [{ json: { report } }];
```

### ✅ CHECKPOINT 6
Запусти вручную (кнопка Test) → должен отправить отчёт в Telegram.

---

## PHASE 7 — Финальная проверка и упаковка
**Время:** 1–2 часа

### 7.1 Чеклист переменных окружения

В n8n → Settings → Variables (или в `.env` файле):

```
TELEGRAM_BOT_TOKEN=         # от BotFather
TELEGRAM_WHITELIST=         # "123456,789012" — user IDs
ADMIN_CHAT_ID=              # чат для уведомлений об ошибках
OPENAI_API_KEY=             # для embeddings и LLM
SUPABASE_URL=               # https://xxx.supabase.co
SUPABASE_SERVICE_KEY=       # service_role key (не anon!)
```

**Проверь**: нигде в нодах нет хардкода ключей — все через `{{ $env.VAR_NAME }}`.

### 7.2 Три сценария для демо

| Сценарий | Запрос | Ожидаемый результат |
|---|---|---|
| Нормативный | `"Сколько дней ежегодного оплачиваемого отпуска положено работнику?"` | Ответ + источники (ТК РФ) + кнопки |
| Шаблон | `"Составь черновик договора услуг для ООО Ромашка, исполнитель ИП Петров"` | Заполненный черновик + ⚠️ дисклеймер |
| Защита | Написать с незарегистрированного аккаунта | `"Доступ запрещён"` |
| Low confidence | `"Какой рецепт борща?"` | `"Недостаточно информации"` |

### 7.3 Экспорт workflow JSON

Для передачи на демо/HuggingFace: n8n GUI → каждый workflow → ⋮ → Export → JSON. Сохрани 4 файла:
- `01_Document_Indexing.json`
- `02_Main_RAG_Bot.json`  
- `03_Feedback_Handler.json`
- `04_Analytics_Daily.json`

### 7.4 HuggingFace Spaces (если требуется)

Минимальный `Dockerfile` для HF:
```dockerfile
FROM n8nio/n8n:latest

ENV N8N_PORT=7860
ENV N8N_PROTOCOL=https
ENV N8N_HOST=0.0.0.0
ENV N8N_BASIC_AUTH_ACTIVE=true
ENV N8N_BASIC_AUTH_USER=admin
# Все секреты — через HF Space "Repository secrets"
# НЕ прописывать здесь

EXPOSE 7860
ENTRYPOINT ["n8n"]
CMD ["start"]
```

**Важно для HF Spaces:** Telegram работает в polling режиме (не webhook), потому что Space "засыпает". Polling автоматически возобновляется при пробуждении — ничего дополнительно делать не нужно.

### ✅ ФИНАЛЬНЫЙ CHECKPOINT

```sql
-- Итоговая проверка всей системы
select 
  (select count(*) from documents) as indexed_chunks,
  (select count(distinct metadata->>'file') from documents) as unique_sources,
  (select count(*) from request_log) as total_requests,
  (select count(*) from request_log where feedback is not null) as rated_requests;
```

Ожидаемый результат после демо-сессии:
- `indexed_chunks` > 100
- `unique_sources` ≥ 5
- `total_requests` ≥ 4 (три тестовых + разные)
- `rated_requests` ≥ 1

---

## Порядок выполнения по дням

| День | Фазы | Результат |
|---|---|---|
| День 1 (суб) | Phase 0 + Phase 1 | Supabase готов, чанки нарезаны |
| День 2 (вос) | Phase 2 + Phase 3 начало | Документы проиндексированы, RAG отвечает |
| День 3 (пн/вт) | Phase 3 завершение + Phase 4 | Полный Q&A + шаблоны работают |
| День 4 | Phase 5 + Phase 6 | Логирование + аналитика |
| День 5 | Phase 7 | Демо-сценарии, экспорт JSON, HF если нужно |