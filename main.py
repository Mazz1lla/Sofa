# main.py (telebot-версия)
import telebot
import time
import threading
import json
import tempfile
import requests
import datetime
import openai  # Whisper API
import base64

from decision_engine import evaluate_response_timing, should_sofa_write_first
from responder import handle_incoming_message
from memory import update_short_memory, save_to_long_memory
from styler import split_message_to_chunks
from schedule_generator import generate_new_schedule
import pytz

moscow_tz = pytz.timezone("Europe/Moscow")

API_TOKEN = "8231992790:AAGiytsyqdj3QvTj7qIPbzYxRiUVm18fzFw"
USER_CHAT_ID = 1363075194  # Укажите свой chat_id

openai.api_key = "your_openai_key_here"  # 🔐 Укажи свой OpenAI ключ

bot = telebot.TeleBot(API_TOKEN)

sofa_should_reply_pending = False

# 📅 Плановая генерация расписания (в отдельном потоке)
def weekly_schedule_update_loop():
    while True:
        now = datetime.datetime.now(moscow_tz)
        if now.weekday() == 6 and now.hour == 22:  # Воскресенье 22:00
            with open("data/schedule.json", "r", encoding="utf-8") as f:
                old_schedule = json.load(f)
            new_schedule_json = generate_new_schedule(old_schedule)
            with open("data/schedule.json", "w", encoding="utf-8") as f:
                f.write(new_schedule_json)
            time.sleep(3600)
        time.sleep(60)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if message.chat.id != USER_CHAT_ID:
        bot.reply_to(message, "Извините, бот работает только с авторизованным пользователем.")
        return

    try:
        # Получаем файл
        file_info = bot.get_file(message.photo[-1].file_id)
        file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}"
        response = requests.get(file_url)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name

        # Загружаем в Gemini через OpenRouter
        from openai import OpenAI
        gemini = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key="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"
        )

        with open(temp_file_path, "rb") as img:
            image_data = base64.b64encode(img.read()).decode("utf-8")
            response = gemini.chat.completions.create(
                model="google/gemini-2.0-flash-001",
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": "Опиши изображение максимально подробно(например, укажи, если это скриншот из какого-то приложения или картинка, связанная с каким-либо аниме)."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                    ]}
                ]
            )

        description = response.choices[0].message.content.strip()
        summary = f"Партнёр прислал изображение: {description}"

        # Сохраняем в краткую память
        from memory import update_short_memory
        update_short_memory(summary, role="partner")

        # Софа отвечает как обычно
        from decision_engine import evaluate_response_timing
        from responder import handle_incoming_message
        from styler import split_message_to_chunks
        from memory import save_to_long_memory

        delay, reason = evaluate_response_timing()
        should_reply = True
        global sofa_should_reply_pending
        sofa_should_reply_pending = should_reply
        if should_reply:
            time.sleep(delay)
            reply_text = handle_incoming_message(reason_activity=reason, delay_seconds=delay)
            chunks = split_message_to_chunks(reply_text)

            for chunk in chunks:
                if chunk["type"] == "text":
                    bot.send_chat_action(message.chat.id, "typing")
                    time.sleep(len(chunk["content"]) * 0.04)
                    bot.send_message(message.chat.id, chunk["content"])
                    sofa_should_reply_pending = False
                    update_short_memory(chunk["content"], role="sofa")
                elif chunk["type"] == "sticker":
                    bot.send_sticker(message.chat.id, chunk["sticker_id"])
                    sofa_should_reply_pending = False
                    update_short_memory("", role="sofa", is_sticker=True, sticker_description=chunk["description"])

            save_to_long_memory()

    except Exception as e:
        print("[⚠️ Ошибка при обработке фото]", e)
        bot.reply_to(message, "Не получилось обработать изображение 😢")

# 🎤 Обработка голосовых сообщений
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    if message.chat.id != USER_CHAT_ID:
        bot.reply_to(message, "Извините, бот работает только с авторизованным пользователем.")
        return

    try:
        file_info = bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}"
        response = requests.get(file_url)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name

        with open(temp_file_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)

        text = transcript["text"]
        display_text = f"🎤 Голосовое сообщение: {text}"
        update_short_memory(display_text, role="partner")

        delay, reason = evaluate_response_timing()
        should_reply = True
        global sofa_should_reply_pending
        sofa_should_reply_pending = should_reply
        if should_reply:
            time.sleep(delay)
            response = handle_incoming_message(reason_activity=reason, delay_seconds=delay)
            chunks = split_message_to_chunks(response)

            for chunk in chunks:
                if chunk["type"] == "text":
                    bot.send_chat_action(message.chat.id, "typing")
                    time.sleep(len(chunk["content"]) * 0.04)
                    bot.send_message(message.chat.id, chunk["content"])
                    sofa_should_reply_pending = False
                    update_short_memory(chunk["content"], role="sofa")
                elif chunk["type"] == "sticker":
                    bot.send_sticker(message.chat.id, chunk["sticker_id"])
                    sofa_should_reply_pending = False
                    update_short_memory("", role="sofa", is_sticker=True, sticker_description=chunk["description"])

            save_to_long_memory()

    except Exception as e:
        print("[⚠️ Ошибка при обработке голосового сообщения]", e)
        bot.reply_to(message, "Не удалось расшифровать голосовое сообщение.")

# 💬 Обработка текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.chat.id != USER_CHAT_ID:
        bot.reply_to(message, "Извините, бот работает только с авторизованным пользователем.")
        return

    if message.text.startswith("/"):
        return

    reply_to_content = None
    if message.reply_to_message:
        reply_to_content = message.reply_to_message.text

    update_short_memory(message.text, role="partner", reply_to_content=reply_to_content)

    delay, reason = evaluate_response_timing()
    should_reply = True
    global sofa_should_reply_pending
    sofa_should_reply_pending = should_reply
    print("Ответ:", should_reply, delay, reason)
    if should_reply:
        time.sleep(delay)
        response = handle_incoming_message(reason_activity=reason, delay_seconds=delay)
        chunks = split_message_to_chunks(response)

        for chunk in chunks:
            if chunk["type"] == "text":
                bot.send_chat_action(message.chat.id, "typing")
                time.sleep(len(chunk["content"]) * 0.04)
                bot.send_message(message.chat.id, chunk["content"])
                sofa_should_reply_pending = False
                update_short_memory(chunk["content"], role="sofa")
            elif chunk["type"] == "sticker":
                bot.send_sticker(message.chat.id, chunk["sticker_id"])
                sofa_should_reply_pending = False
                update_short_memory("", role="sofa", is_sticker=True, sticker_description=chunk["description"])

        save_to_long_memory()

# 🤖 Проактивная Софа
def proactive_sofa_loop():
    while True:
        time.sleep(1800)
        try:
            global sofa_should_reply_pending
            if sofa_should_reply_pending:
                continue  # Софа должна сначала ответить — не пишет сама
            
            if should_sofa_write_first():
                text = handle_incoming_message(reason_activity="спонтанное желание написать 💬", delay_seconds=0, is_proactive=True)
                chunks = split_message_to_chunks(text)
                for chunk in chunks:
                    if chunk["type"] == "text":
                        bot.send_chat_action(USER_CHAT_ID, "typing")
                        time.sleep(len(chunk["content"]) * 0.04)
                        bot.send_message(USER_CHAT_ID, chunk["content"])
                        update_short_memory(chunk["content"], role="sofa")
                    elif chunk["type"] == "sticker":
                        bot.send_sticker(USER_CHAT_ID, chunk["sticker_id"])
                        update_short_memory("", role="sofa", is_sticker=True, sticker_description=chunk["description"])
        except Exception as e:
            print("[⚠️ Ошибка в proactive_sofa_loop]", e)

# 🧵 Запуск в потоках
threading.Thread(target=proactive_sofa_loop, daemon=True).start()
threading.Thread(target=weekly_schedule_update_loop, daemon=True).start()

# 🚀 Основной цикл
while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except Exception as e:
        print(f"[⚠️ Бот упал с ошибкой] {e}")
        time.sleep(5)
