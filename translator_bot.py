import os
import logging
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

from dotenv import load_dotenv

from utils import load_json, save_json
from translation_service import translate_text, text_to_speech, TranslationError, get_model # Import get_model
from user_management import ensure_user_in_settings, get_user_language, set_user_language, update_user_info, is_vip
from usage_stats import update_usage_stats
from admin_commands import admin_panel, button_callback, handle_admin_input
from chat_commands import chat, handle_chat_message, cancel
from constants import VALID_LANGUAGE_CODES, USER_SETTINGS_FILE, USAGE_STATS_FILE, USER_INFO_FILE, VIP_USERS_FILE, ADMIN_USER_IDS
from api_checker import API_Checker

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# Debug-Ausgabe, um sicherzustellen, dass ADMIN_USER_IDS geladen wird
print(f"ADMIN_USER_IDS from environment: {os.getenv('ADMIN_USER_IDS')}")  # Hinzugefügt

# Logging konfigurieren
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_USER_IDS = [int(id) for id in os.getenv('ADMIN_USER_IDS').split(',')]

# Daten laden
user_settings = load_json(USER_SETTINGS_FILE)
usage_stats = load_json(USAGE_STATS_FILE, {"total_translations": 0, "daily_stats": {}})
user_info = load_json(USER_INFO_FILE)
vip_users = set(load_json(VIP_USERS_FILE, []))

api_checker = API_Checker(GEMINI_API_KEY)
# Initialize the model here, after translation_service is imported
model = get_model()
api_checker.start()  # Startet den API-Checker-Thread
tts_command=None

async def tts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_vip(user.id) and user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("🚫 This feature is only available for VIP users and admins!!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Please provide text for text-to-speech.")
        return

    text = " ".join(context.args)
    target_language = get_user_language(user.id)
    translated_text = translate_text(text, target_language)
    audio_file = text_to_speech(translated_text, target_language)
    if audio_file:
        try:
            with open(audio_file, 'rb') as f:
               await update.message.reply_audio(audio=InputFile(f), title="Text to Speech")
            os.remove(audio_file)
        except Exception as e:
            await update.message.reply_text(f"An error occurred while sending audio: {e}")
    else:
        await update.message.reply_text("An error occurred while generating audio.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    ensure_user_in_settings(user.id)
    language = get_user_language(user.id)
    update_user_info(user)
    welcome_message_en = "🌟 Welcome to GlobalTalk-TranslatorBot! 🌍✨\n\n" \
                           "I'm here to help you translate forwarded messages into various languages. " \
                           "Simply forward me a message, and I'll translate it to your preferred language.\n\n" \
                           "To get started, use /setlanguage to choose your language, or just start forwarding messages!\n\n" \
                           "Need help? Just type /help for more information."

    await update.message.reply_text(welcome_message_en)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user # Hinzugefügt
    user_id = user.id # Hier den richtigen user definieren
    ensure_user_in_settings(user_id)
    language = get_user_language(user.id)
    help_message_en = "🤖 Bot Commands:\n\n" \
                      "🌟 /start - Start the bot and see the welcome message\n" \
                      "🔤 /setlanguage - Set your preferred language\n" \
                      "ℹ️ /help - Show this help message\n" \
                      "🌍 /languagecodes - View available language codes\n" \
                      "👨‍💼 /admin - Access admin panel (only for authorized users)\n" \
                      "🎧 /tts [text] - Convert text to speech (VIP only)\n" \
                      "💬 /chat - Start a chat session (for VIP users and admins)\n\n" \
                      "To translate, simply forward a message to me. Enjoy translating! 🎉"

    await update.message.reply_text(help_message_en)


async def language_codes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id # Hier den richtigen user definieren
    ensure_user_in_settings(user_id)
    language = get_user_language(user.id)
    codes_message = "🌐 Available Language Codes:\n\n"
    for code, lang_name in VALID_LANGUAGE_CODES.items():
        codes_message += f"{code}: {lang_name}\n"
    codes_message += "\nUse the /setlanguage command to set your preferred language."
    try:
        translated_message = translate_text(codes_message, language)
        await update.message.reply_text(translated_message)
    except TranslationError as e:
        logger.error(f"Translation error in language_codes command: {e}")
        await update.message.reply_text("Error: Could not translate language codes message.  Please try again later.")
    except Exception as e:
        logger.exception(f"Unexpected error in language_codes command: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again later.")


async def translate_forwarded(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles forwarded messages and translates them to the user's preferred language.
    """
    user = update.effective_user
    ensure_user_in_settings(user.id)
    message = update.message

    if message.voice:
        return  # If voice message, do not translate

    if not message.forward_origin:
        await update.message.reply_text("This message is not a forwarded message.")
        return

    text = message.text or message.caption or ""
    target_language = get_user_language(user.id)

    # Determine source language and original sender based on forward_origin type
    source_language = None
    original_sender = "Unknown"

    try:
        if message.forward_origin.type == "user":
            source_language = message.forward_origin.sender_user.language_code if message.forward_origin.sender_user else None
            original_sender = f"@{message.forward_origin.sender_user.username}" if message.forward_origin.sender_user.username else message.forward_origin.sender_user.first_name
        elif message.forward_origin.type == "chat":
            original_sender = message.forward_origin.chat.title or "Channel"
        elif message.forward_origin.type == "hidden_user":
            original_sender = message.forward_origin.sender_user_name
        else:
            original_sender = "Unknown"
    except Exception as e:
        logger.error(f"Error determining sender info: {e}")

    try:
        translated_text = translate_text(text, target_language, source_language)

        if str(user.id) in user_info:
            if "translation_history" not in user_info[str(user.id)]:
               user_info[str(user.id)]["translation_history"] = []
            user_info[str(user.id)]["translation_history"].append({"original_text": text, "translated_text": translated_text})
            if len(user_info[str(user.id)]["translation_history"]) > 10:
                user_info[str(user.id)]["translation_history"].pop(0)
            save_json(USER_INFO_FILE, user_info)

        response = f"Original sender: {original_sender}\n\n🔤 Translation:\n\n{translated_text}"
        await update.message.reply_text(response)
        update_usage_stats()
        update_user_info(user)

    except TranslationError as e:
        logger.error(f"Translation error: {e}")
        await update.message.reply_text(f"Error: Translation failed. Please try again later. {e}")  #User friendly message
    except Exception as e:
        logger.exception(f"Unexpected error in translation: {e}") #Logs full stacktrace
        await update.message.reply_text("An unexpected error occurred. Please try again later.") #Simple user message

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    ensure_user_in_settings(user.id)

    keyboard = []
    for code, name in VALID_LANGUAGE_CODES.items():
        keyboard.append([InlineKeyboardButton(name, callback_data=f'setlang_{code}')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("🌐 Please choose your language:", reply_markup=reply_markup)

def main() -> None:
    # Use ApplicationBuilder for a more modern approach
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers using the application object
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("languagecodes", language_codes))
    app.add_handler(CommandHandler("setlanguage", set_language))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.FORWARDED, translate_forwarded))
    app.add_handler(CommandHandler("tts", tts_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Define the wrapper function BEFORE it is used in the ConversationHandler
    async def handle_chat_message_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE): # Wrapper function
        return await handle_chat_message(update, context, model) # Pass model here


    chat_handler = ConversationHandler(
        entry_points=[CommandHandler('chat', chat)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message_wrapper)], # Use integer state, use wrapper
        },
        fallbacks=[CommandHandler('endchat', cancel), CommandHandler("cancel", cancel)],
    )


    app.add_handler(chat_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))

    # Use the application's run_polling method
    app.run_polling()

if __name__ == '__main__':
    main()