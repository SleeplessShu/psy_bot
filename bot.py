from telegram.ext import ApplicationBuilder, MessageHandler, filters, CallbackQueryHandler, CommandHandler
import asyncio
import os

from pathlib import Path
from gpt import *
from util import *
from datetime import datetime

# Путь к директории для логов
THIS_FOLDER = Path(__file__).parent.resolve()
log_path = THIS_FOLDER / "logs"
tokenPath = THIS_FOLDER / "tokens"

def read_token(tokenName):
    with open(f'{tokenPath}/{tokenName}.txt', 'r') as file:
        return file.read().strip()

gptToken = read_token('gptToken')
appToken = read_token('appToken')
print(f"GPT Token: {gptToken}")
print(f"App Token: {appToken}")
# Функция для отправки сообщений с кнопками
async def send_text_buttons(update, context, text, buttons):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [[InlineKeyboardButton(button_text, callback_data=callback_data)] for callback_data, button_text in buttons.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        msg = await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        msg = await update.callback_query.message.reply_text(text, reply_markup=reply_markup)

    await track_message(msg, context)
    return msg  # Возвращаем объект сообщения

# Функция для удаления всех сообщений
async def delete_all_messages(chat_id, context):
    message_ids = context.user_data.get("message_ids", [])
    for message_id in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            print(f"Ошибка при удалении сообщения {message_id}: {e}")

    context.user_data["message_ids"] = []

# Отслеживание сообщений и сохранение их идентификаторов
async def track_message(message, context):
    if message:  # Проверка на None
        message_ids = context.user_data.get("message_ids", [])
        message_ids.append(message.message_id)
        context.user_data["message_ids"] = message_ids

# Функция для добавления сообщения в историю
def update_dialog_history(dialog, role, message):
    dialog.history.append({"role": role, "content": message})

# Функция для записи сообщения в лог-файл
def log_message_to_file(user_nickname, role, message):
    message_length = len(message)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Форматирование даты и времени
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    log_file_path = f'{log_path}/{user_nickname}_fast_dialog.txt'
    with open(log_file_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"\n\n[{timestamp}] {role}: (Текст длинной: {message_length})\n")

async def start(update, context):
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
    await delete_all_messages(chat_id, context)

    dialog.mode = "main"
    dialog.history = []

    user = update.message.from_user if update.message else update.callback_query.from_user
    user_nickname = user.username if user.username else "unknown_user"
    log_file_path = f'{log_path}/{user_nickname}_fast_dialog.txt'

    # Создаем или очищаем файл при начале нового диалога
    with open(log_file_path, "w", encoding="utf-8") as log_file:
        log_file.write("New dialog started\n")

    text = load_message("main")
    photo_msg = await send_photo(update, context, "main")
    await track_message(photo_msg, context)
    text_msg = await send_text_buttons(update, context, text, {
        "start_restart": "главное меню бота",
        "start_fast": "быстрый диалог",
        "start_create": "настроить психолога",
        "start_contacts": "контакты действующих психологов",
        "start_rules": "общая информация о боте",
        "start_clear": "стереть полностью историю переписки"
    })
    await track_message(text_msg, context)

async def start_button(update, context):
    query = update.callback_query.data
    await update.callback_query.answer()
    if query == "start_restart":
        await start(update, context)
    elif query == "start_fast":
        await fast(update, context)
    elif query == "start_rules":
        rules_msg = await send_text(update.callback_query.message, context, "Здесь будет информация о правилах.")
        await track_message(rules_msg, context)
    elif query == "start_clear":
        chat_id = update.callback_query.message.chat_id
        await delete_all_messages(chat_id, context)

async def fast(update, context):
    dialog.mode = "fast"
    dialog.history = []  # Очистка истории диалога при старте новой сессии

    user = update.message.from_user if update.message else update.callback_query.from_user
    user_nickname = user.username if user.username else "unknown_user"
    log_file_path = os.path.join(log_path, f"{user_nickname}_fast_dialog.txt")
    # Создаем или очищаем файл при начале нового диалога
    with open(log_file_path, "w", encoding="utf-8") as log_file:
        log_file.write("Fast dialog started\n")

    text1 = load_message("fast1")
    msg1 = await send_text(update, context, text1)
    await track_message(msg1, context)
    photo_msg = await send_photo(update, context, "fast")
    await track_message(photo_msg, context)
    text2 = load_message("fast2")
    msg2 = await send_text(update, context, text2)
    await track_message(msg2, context)

async def fast_dialog(update, context):
    if dialog.mode != "fast":
        return

    user_message = update.message.text
    await track_message(update.message, context)  # Отслеживание сообщений пользователя
    update_dialog_history(dialog, "user", user_message)

    user_nickname = update.message.from_user.username if update.message.from_user.username else "unknown_user"

    log_message_to_file(user_nickname, "user", user_message)


    my_message = await send_text(update, context, "Твой собеседник думает над ответом...")
    await track_message(my_message, context)

    # Формирование полного текста диалога для отправки в GPT
    full_dialog_text = "\n".join([f"{entry['role']}: {entry['content']}" for entry in dialog.history])

    prompt = load_prompt("fast")
    answer = await chatgpt.send_question(prompt, full_dialog_text)
    log_message_to_file(user_nickname, "assistant", answer)


    update_dialog_history(dialog, "assistant", answer)

    await my_message.edit_text(answer)

async def dialogEngage(update, context):
    if dialog.mode == "fast":
        await fast_dialog(update, context)




dialog = Dialog()
dialog.mode = None
dialog.list = []
dialog.count = 0
dialog.user = {}
dialog.history = []

chatgpt = ChatGptService(gptToken)

app = ApplicationBuilder().token(appToken).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("fast", fast))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dialogEngage))
app.add_handler(CallbackQueryHandler(start_button, pattern="^start_.*"))

app.run_polling()
