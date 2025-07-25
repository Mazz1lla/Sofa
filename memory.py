# memory.py
import json
import os
import datetime
from openai import OpenAI
import pytz

moscow_tz = pytz.timezone("Europe/Moscow")

SHORT_TERM_PATH = "data/short_term_memory.json"
LONG_TERM_PATH = "data/long_term_memory.json"
PERSONA_PATH = "data/persona.json"
MAX_SHORT_TERM_LENGTH = 4000

client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key="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",  # 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
            default_headers={
                "HTTP-Referer": "http://localhost",  # Например: http://localhost
                "X-Title": "Beta v0 NSFW Client",
            }
        )

def _get_current_context():
    now = datetime.datetime.now(moscow_tz)
    day = now.strftime("%A").lower()
    time = now.strftime("%H:%M")
    return day, time, now

def update_short_memory(content: str, role: str = "partner", is_sticker: bool = False, sticker_description: str = "", reply_to_content: str = None):
    """
    Обновляет кратковременную память.

    Args:
        content (str): Содержание сообщения.
        role (str, optional): Роль автора сообщения ("sofa" или "partner"). Defaults to "partner".
        is_sticker (bool, optional): Является ли сообщение стикером. Defaults to False.
        sticker_description (str, optional): Описание стикера. Defaults to "".
        reply_to_content (str, optional): Содержание сообщения, на которое ответили (если есть). Defaults to None.
    """
    if not os.path.exists(SHORT_TERM_PATH):
        memory = []
    else:
        with open(SHORT_TERM_PATH, "r", encoding="utf-8") as f:
            memory = json.load(f)

    if is_sticker:
        content = f"*Стикер: {sticker_description}*"

    now = datetime.datetime.now(moscow_tz).strftime("%Y-%m-%d %H:%M:%S")
    author = "Софа" if role == "sofa" else "Партнёр"
    message = {
        "role": role,
        "author": author,
        "timestamp": now,
        "content": content
    }
    if reply_to_content:
        message["reply_to"] = reply_to_content  # Добавляем информацию об ответе

    memory.append(message)

    total = 0
    pruned = []
    for msg in reversed(memory):
        total += len(msg['content'])
        if total > MAX_SHORT_TERM_LENGTH:
            break
        pruned.insert(0, msg)

    with open(SHORT_TERM_PATH, "w", encoding="utf-8") as f:
        json.dump(pruned, f, ensure_ascii=False, indent=2)

def save_to_long_memory():
    if not os.path.exists(SHORT_TERM_PATH):
        return
    with open(SHORT_TERM_PATH, "r", encoding="utf-8") as f:
        short = json.load(f)
    if not short:
        return

    with open(LONG_TERM_PATH, "r", encoding="utf-8") as f:
        long_memory = json.load(f) if os.path.getsize(LONG_TERM_PATH) > 0 else []

    with open(PERSONA_PATH, "r", encoding="utf-8") as f:
        persona = json.load(f)

    history_text = "\n".join([
        f"[{m.get('timestamp', '???')}] {m.get('author', '???')}: {m['content']} " + (f"(Ответ на: {m['reply_to']})" if m.get("reply_to") else "") # Добавляем информацию об ответе в историю
        for m in short
    ])
    memory_text = json.dumps(long_memory, ensure_ascii=False, indent=2)

    day, time, now = _get_current_context()
    date_formatted = now.strftime("%d.%m.%Y")

    prompt = f"""
Сегодня {day}, {time}, дата: {date_formatted}.

Ты — помощник, который помогает девочке-подростку Софе запоминать важные факты из переписки со своим парнем.
Вот кто такая Софа:
{json.dumps(persona, ensure_ascii=False, indent=2)}

Вот текущая история общения:
{history_text}

Вот что она уже помнит:
{memory_text}

Учитывай, что в данный момент Софа общается со своим парнем в Telegram, а не в реальной жизни.

Выдели только те ФАКТЫ, которые реально стоит запомнить.
Если ничего значимого не произошло — верни пустой список [].

В фактах должны быть факты о собеседнике или самой Софе, иногда краткое описание их диалога(если этот диалог был важным)

Формат:
[
  {{"fact": "...", "date": "YYYY-MM-DD"}},
  ...
]

Если что-то уже есть в памяти, предложи обновление, а не дублирование.
"""

    response = client.chat.completions.create(
        model="openai/gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    print(response.choices[0].message.content)

    try:
        extracted = json.loads(response.choices[0].message.content)
        if not isinstance(extracted, list) or not extracted:
            return  # ничего не сохраняем

# Обновляем память: заменяем похожие по смыслу
        updated_memory = long_memory.copy()
        for new_item in extracted:
            replaced = False
            for i, existing in enumerate(updated_memory):
                if new_item["fact"] in existing["fact"] or existing["fact"] in new_item["fact"]:
                    updated_memory[i] = new_item
                    replaced = True
                    break
            if not replaced:
                updated_memory.append(new_item)

        with open(LONG_TERM_PATH, "w", encoding="utf-8") as f:
            json.dump(updated_memory, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print("[Memory Error]", e)
