Отвечаю по всем пунктам с упором на скорость (вечер вместо недели).

---

## 1. Готовые узлы n8n vs ваш Python-код

**Правило для MVP за вечер: используйте готовые узлы везде, где возможно.** Code Node берите только для 2–3 узких мест, где готового решения нет.

| Задача | Что использовать | Зачем |
|---|---|---|
| Приём/отправка в Telegram | **Telegram Trigger** + **Telegram** | Нативно, без кода  |
| Эмбеддинги | **Embeddings OpenAI** | Нативный AI-узел |
| Векторный поиск | **Vector Store Retriever (Supabase)** | Нативный, но см. важное предупреждение ниже |
| Генерация ответа | **OpenAI Chat Model** | Нативный |
| Проверка whitelist | **IF** или **Switch** | Мышью, без кода |
| Логирование | **Supabase** (Insert) или **Google Sheets** | Мышью |
| Скоринг уверенности | **Code** (JavaScript) | Нет готового узла |
| Сборка prompt с источниками | **Code** (JavaScript) | Нужно склеить чанки + вопрос |
| Заполнение шаблона | **Code** (JavaScript) | Простой `string.replace()` |
| Inline keyboard (динамическая) | **HTTP Request** → Telegram API | Нативный Telegram-узел не поддерживает динамические inline-кнопки  |

**Важное предупреждение:** Не используйте новый **AI Agent (v3.1)** с Supabase Vector Store — есть подтверждённый баг: агент не вызывает инструмент поиска . Делайте RAG вручную: `Vector Store Retriever` → `Code` (сборка контекста) → `OpenAI Chat Model`. Это надёжнее и вы контролируете процесс.

---

## 2. План на 1 вечер (4–6 часов)

| Час | Действие |
|---|---|
| **0:00–0:30** | Docker: `docker run -it --rm -p 5678:5678 -v ~/.n8n:/home/node/.n8n n8nio/n8n` |
| **0:30–1:00** | Supabase: новый проект, SQL Editor → `create extension vector;` + создать таблицу `documents` |
| **1:00–1:30** | Загрузка 3–5 открытых документов (ТК РФ, ГК РФ, ФЗ о грузоперевозках) |
| **1:30–2:30** | **Ingest-воркфлоу** в n8n: Read Binary → Split → Embeddings OpenAI → Supabase Vector Store (Insert) |
| **2:30–4:00** | **Main-воркфлоу** в n8n: Telegram Trigger → IF (whitelist) → Vector Store Retriever → Code (prompt) → OpenAI Chat → Code (format + sources) → Telegram Send + Inline Keyboard |
| **4:00–5:00** | **Feedback-воркфлоу**: Telegram Trigger (callback_query) → Supabase (Update) |
| **5:00–6:00** | Тестирование, правка prompt, экспорт JSON workflow |

---

## 3. Что в белом списке Telegram?

**Telegram Chat ID** — это числовой идентификатор чата (обычно 9–10 цифр). Не username, не токен.

- Запустите бота, отправьте сообщение.
- В n8n поставьте **Telegram Trigger** → подключите бота → отправьте тестовое сообщение.
- В выводе триггера найдёте `{{ $json.message.chat.id }}` — это и есть whitelist-значение.
- Сохраните несколько таких ID в переменной окружения `TELEGRAM_WHITELIST` через запятую: `123456789,987654321`.

Проверка в n8n (узел **IF**):
- Left: `{{ $json.message.chat.id }}`
- Operation: **String → Contains**
- Right: `{{ $env.TELEGRAM_WHITELIST }}`

---

## 4. Что за шаблоны? Как делать в n8n?

В ТЗ сказано: *«LLM для поиска и ответов, шаблоны — через код с заполнением»*. Это значит:

**Шаблон = обычный текстовый файл с плейсхолдерами**, который вы храните в Supabase или прямо в n8n (в узле **Set**).

Пример шаблона трудового договора (хранится в Supabase как текст):
```
ТРУДОВОЙ ДОГОВОР № {{номер}}
г. {{город}}                                                                 "{{дата}}"

Работодатель: {{работодатель}}, в лице {{должность_представителя}} ...
```

**Заполнение в n8n (Code Node, JavaScript):**
```javascript
let template = $input.first().json.content; // шаблон из Supabase
const data = {
  номер: "123",
  город: "Москва",
  дата: new Date().toLocaleDateString('ru-RU'),
  работодатель: "ООО Ромашка",
  должность_представителя: "Генерального директора Иванова И.И."
};

for (const [key, value] of Object.entries(data)) {
  template = template.replaceAll(`{{${key}}}`, value);
}

return [{ json: { draft: template } }];
```

**Почему не DOCX/PDF?** Есть community node `n8n-nodes-fill-docx` , но для вечера это лишняя зависимость. Текстовый черновик с дисклеймером *«Требует проверки юриста»* — это MVP.

---

## 5. Диаграмма в swimlanes.io (Sequence Diagram)

Вот готовый код. Скопируйте в [swimlanes.io](https://swimlanes.io):

```swimlanes-io
title: MVP RAG AI-ассистент HR/Юр (n8n + Supabase)

actor Пользователь
participant Telegram
participant n8n
database Supabase

Пользователь -> Telegram: Отправляет вопрос
Telegram -> n8n: Polling / webhook (message.text)

n8n -> n8n: Проверка whitelist (chat_id)

alt chat_id не в whitelist
  n8n -> Telegram: "Доступ запрещён"
else chat_id в whitelist
  n8n -> n8n: Классификация (юр / HR / шаблон)
  
  alt Запрос шаблона
    n8n -> Supabase: Получить текстовый шаблон
    Supabase --> n8n: Шаблон с плейсхолдерами
    n8n -> n8n: Заполнение через Code Node
    n8n -> Telegram: Черновик документа + дисклеймер
  else Нормативный вопрос
    n8n -> Supabase: Semantic search (pgvector)
    Supabase --> n8n: Релевантные чанки + metadata
    
    n8n -> n8n: Скоринг уверенности (Code)
    
    alt Уверенность < порога
      n8n -> Telegram: "Недостаточно данных в базе знаний"
    else Уверенность >= порога
      n8n -> n8n: Сборка prompt (контекст + вопрос)
      n8n -> n8n: Генерация ответа (OpenAI Chat Model)
      n8n -> Supabase: Логирование (запрос, ответ, sources)
      n8n -> Telegram: Ответ с источниками + кнопки 👍 / 👎
    end
  end
end

Пользователь -> Telegram: Нажимает оценку
Telegram -> n8n: Callback query (callback_data)

alt Оценка 👎
  n8n -> Supabase: Обновить feedback = down, flag = review
else Оценка 👍
  n8n -> Supabase: Обновить feedback = up
end

n8n -> Telegram: Подтверждение ("Спасибо за оценку")
```

Это **Sequence Diagram** в нотации swimlanes.io, а не BPMN. Акторы — swimlanes по вертикали, стрелки — сообщения во времени.

---

## 6. Конкретные узлы n8n: что и зачем

### Входящий поток
| Узел | Настройка |
|---|---|
| **Telegram Trigger** | Event: `message` (для текстов), отдельный триггер на `callback_query` (для кнопок). Используйте **Polling** для HF Spaces. |
| **IF** (или **Switch**) | Проверка `chat.id` по whitelist. |
| **Vector Store Retriever** | Supabase, topK=4. Возвращает массив документов с `pageContent` и `metadata`. |
| **Code** (JS) | Склеивает чанки в строку `context`, считает скор (например, средняя косинусная близость). |
| **OpenAI Chat Model** | Модель: `gpt-4o-mini` (дешево и быстро). System prompt: *«Отвечай строго по контексту. Укажи источник [файл, раздел]. Если нет в контексте — скажи "Недостаточно данных"»*. |
| **Code** (JS) | Форматирует финальный текст: ответ + список источников из metadata. |
| **Telegram** | Operation: `Send Message`. Chat ID из триггера. |

### Исходящий поток (кнопки)
Проблема: нативный узел **Telegram** поддерживает Inline Keyboard, но **не динамическую генерацию** кнопок из предыдущего узла . 

**Решение для MVP:** Используйте узел **HTTP Request**:
- Method: `POST`
- URL: `https://api.telegram.org/bot{{$env.TELEGRAM_BOT_TOKEN}}/sendMessage`
- Body (JSON):
```json
{
  "chat_id": "{{ $json.message.chat.id }}",
  "text": "{{ $json.formatted_answer }}",
  "parse_mode": "HTML",
  "reply_markup": {
    "inline_keyboard": [
      [
        {"text": "👍", "callback_data": "up:{{ $run.executionId }}"},
        {"text": "👎", "callback_data": "down:{{ $run.executionId }}"}
      ]
    ]
  }
}
```

### Логирование
| Узел | Настройка |
|---|---|
| **Supabase** | Operation: `Insert` или `Update`. Таблица `logs` с полями: `chat_id`, `query`, `answer`, `sources`, `feedback`, `created_at`. |

---

## 7. Мышь vs AI-ассистенты (Claude Code, Cursor, Codex)

**Оптимальный подход для скорости:**

1. **Скелет собирайте мышью** в n8n GUI (30 минут):
   - Перетащите Telegram Trigger, IF, Vector Store Retriever, OpenAI, Supabase.
   - Соедините стрелками.
   - Заполните credentials (Supabase, OpenAI, Telegram).

2. **Сложную логику делайте через JSON**:
   - `Settings → Export JSON` → откройте в Cursor/VS Code.
   - AI-ассистенты отлично пишут **JavaScript для Code Node** и **JSON-тела для HTTP Request**.
   - Но n8n workflow JSON очень многословен (координаты X/Y узлов, ID соединений). AI плохо генерирует его с нуля — проще поправить существующий.

3. **Code Node пишите AI:**
   ```javascript
   // Попросите Cursor/Claude написать:
   // "Напиши n8n Code Node на JS, который берёт массив документов 
   // из Vector Store Retriever, склеивает их в context и добавляет 
   // источники [файл: раздел] в конец"
   ```

**Итог:** Мышь для topology (какие узлы и в каком порядке), AI для содержимого Code Node и prompt-инжиниринга.

---

## 8. HF Spaces: критические нюансы

- **Polling вместо webhook:** HF Spaces засыпают. Webhook сломается. В Telegram Trigger выберите **Polling**.
- **n8n теряет workflow при сне:** Файловая система эфемерна. Сделайте `Export JSON` workflow и храните его в репозитории. При обновлении Space просто re-import.
- **Секреты:** В HF Space → Settings → Secrets добавьте:
  - `TELEGRAM_BOT_TOKEN`
  - `OPENAI_API_KEY`
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_KEY`
  - `TELEGRAM_WHITELIST`

---

**Краткий итог для старта:** Не тащите Python. Соберите мышью цепочку `Telegram → IF → Retriever → OpenAI → Telegram`, два раза используйте Code Node (для prompt и для скоринга), шаблоны делайте текстовыми через `replaceAll`, а диаграмму скопируйте в swimlanes.io из блока выше. На всё уйдёт один вечер.
