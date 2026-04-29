import telebot
import os
from telebot import types
from flask import Flask
from threading import Thread

# ================= НАСТРОЙКИ =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))  # ID группы

bot = telebot.TeleBot(BOT_TOKEN)

PROJECT_NAME = "TSUL Law Arena"
CHANNEL_LINK = "https://t.me/tsul_law_arena"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POLOZHENIE_PATH = os.path.join(BASE_DIR, "TSUL_Law_Arena_Polozhenie.pdf")
GUIDE_PATH = os.path.join(BASE_DIR, "TSUL_Law_Arena_Guide.pdf")

# ================= ХРАНИЛИЩА =================

user_language = {}
waiting_for_message = {}
active_requests = {}  # message_id -> coordinator_id
subscribers = set()

# ================= МЕНЮ =================

def send_main_menu(chat_id, lang):
    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(types.InlineKeyboardButton(
        "📩 Связаться с координаторами" if lang == "ru"
        else "📩 Koordinatorlar bilan bog'lanish",
        callback_data="contact"
    ))

    keyboard.add(types.InlineKeyboardButton(
        "📘 Критерии оценивания" if lang == "ru"
        else "📘 Baholash mezonlari",
        callback_data="guide"
    ))

    keyboard.add(types.InlineKeyboardButton(
        f"📄 Положение {PROJECT_NAME}" if lang == "ru"
        else f"📄 {PROJECT_NAME} nizomi",
        callback_data="polozhenie"
    ))

    keyboard.add(types.InlineKeyboardButton(
        "📣 Канал проекта" if lang == "ru"
        else "📣 Kanal",
        url=CHANNEL_LINK
    ))

    bot.send_message(
        chat_id,
        f"Добро пожаловать в {PROJECT_NAME}!" if lang == "ru"
        else f"{PROJECT_NAME} ga xush kelibsiz!",
        reply_markup=keyboard
    )

# ================= START =================

@bot.message_handler(commands=["start"])
def start(message):
    subscribers.add(message.chat.id)

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz")
    )

    bot.send_message(message.chat.id, "Выберите язык / Tilni tanlang:", reply_markup=keyboard)

# ================= ЯЗЫК =================

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def set_lang(call):
    lang = call.data.split("_")[1]
    user_language[call.from_user.id] = lang

    bot.edit_message_text("✅", call.message.chat.id, call.message.message_id)
    send_main_menu(call.message.chat.id, lang)

# ================= PDF =================

def send_pdf(chat_id, path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            bot.send_document(chat_id, f)
    else:
        bot.send_message(chat_id, "❌ Файл не найден")

# ================= КНОПКИ =================

@bot.callback_query_handler(func=lambda call: call.data in ["contact", "guide", "polozhenie"])
def menu_handler(call):
    user_id = call.from_user.id

    if call.data == "contact":
        waiting_for_message[user_id] = True
        bot.send_message(call.message.chat.id, "Напишите сообщение:")

    elif call.data == "guide":
        send_pdf(call.message.chat.id, GUIDE_PATH)

    elif call.data == "polozhenie":
        send_pdf(call.message.chat.id, POLOZHENIE_PATH)

# ================= ПОЛЬЗОВАТЕЛЬ =================

@bot.message_handler(func=lambda msg: msg.chat.id != GROUP_ID)
def user_message(message):
    user_id = message.from_user.id

    if waiting_for_message.get(user_id):
        text = f"📩 Обращение\n👤 @{message.from_user.username}\n🆔 ID: {user_id}\n\n{message.text}"

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(
            "🟢 Взять обращение",
            callback_data=f"take_{user_id}"
        ))

        sent = bot.send_message(GROUP_ID, text, reply_markup=keyboard)
        active_requests[sent.message_id] = None

        bot.send_message(message.chat.id, "✅ Отправлено!")
        waiting_for_message[user_id] = False

# ================= ВЗЯТЬ ОБРАЩЕНИЕ =================

@bot.callback_query_handler(func=lambda call: call.data.startswith("take_"))
def take(call):
    msg_id = call.message.message_id

    if active_requests.get(msg_id):
        bot.answer_callback_query(call.id, "❌ Уже занято")
        return

    active_requests[msg_id] = call.from_user.id

    bot.send_message(GROUP_ID, f"🟢 Взял: {call.from_user.first_name}")

# ================= ОТВЕТ ИЗ ГРУППЫ =================

@bot.message_handler(func=lambda msg: msg.chat.id == GROUP_ID and msg.reply_to_message)
def reply_handler(message):
    msg_id = message.reply_to_message.message_id
    owner = active_requests.get(msg_id)

    if owner and owner != message.from_user.id:
        return bot.reply_to(message, "❌ Не ваше обращение")

    # ищем user_id
    for line in message.reply_to_message.text.split("\n"):
        if "ID:" in line:
            user_id = int(line.split("ID:")[1].strip())
            bot.send_message(user_id, f"💬 Ответ:\n\n{message.text}")
            return

# ================= РАССЫЛКА =================

@bot.message_handler(commands=["notify"])
def notify(message):
    if message.chat.id != GROUP_ID:
        return

    text = message.text.replace("/notify", "").strip()
    sent = 0

    for user in list(subscribers):
        try:
            bot.send_message(user, f"📢 {text}")
            sent += 1
        except:
            subscribers.discard(user)

    bot.send_message(GROUP_ID, f"Отправлено: {sent}")

# ================= FLASK =================

app = Flask(__name__)

@app.route("/")
def home():
    return "OK"

def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ================= ЗАПУСК =================

if __name__ == "__main__":
    Thread(target=run).start()
    bot.infinity_polling(skip_pending=True)
