import os
import json
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import google.generativeai as genai

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# Konfiguration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_USER_IDS = [int(id) for id in os.getenv('ADMIN_USER_IDS').split(',')]
USER_SETTINGS_FILE = "user_settings.json"

# Logging konfigurieren
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini API konfigurieren
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Benutzereinstellungen laden oder erstellen
def load_user_settings():
    if os.path.exists(USER_SETTINGS_FILE):
        with open(USER_SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_settings(settings):
    with open(USER_SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

user_settings = load_user_settings()

def get_user_language(user_id):
    return user_settings.get(str(user_id), 'en')

def set_user_language(user_id, language):
    user_settings[str(user_id)] = language
    save_user_settings(user_settings)

def translate_text(text, target_language):
    prompt = f"Translate the following text to {target_language}: {text}"
    response = model.generate_content(prompt)
    return response.text

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    language = get_user_language(user.id)
    welcome_message = translate_text(
        "🌟 Welcome to EasyTranslatorPro! 🌍✨\n\n"
        "I'm here to help you translate forwarded messages into various languages. "
        "Simply forward me a message, and I'll translate it to your preferred language.\n\n"
        "To get started, use /setlanguage to choose your language, or just start forwarding messages!\n\n"
        "Need help? Just type /help for more information.",
        language
    )
    update.message.reply_text(welcome_message)

def help_command(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    language = get_user_language(user_id)
    help_message = translate_text(
        "🤖 Bot Commands:\n\n"
        "🌟 /start - Start the bot and see the welcome message\n"
        "🔤 /setlanguage [code] - Set your preferred language (e.g., /setlanguage es for Spanish)\n"
        "ℹ️ /help - Show this help message\n"
        "🌍 /languagecodes - View available language codes\n"
        "👨‍💼 /admin - Access admin panel (only for authorized users)\n\n"
        "To translate, simply forward a message to me. Enjoy translating! 🎉",
        language
    )
    update.message.reply_text(help_message)

def language_codes(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    language = get_user_language(user_id)
    codes_message = translate_text(
        "🌐 Available Language Codes:\n\n"
        "🇬🇧 English: en\n"
        "🇪🇸 Spanish: es\n"
        "🇫🇷 French: fr\n"
        "🇩🇪 German: de\n"
        "🇮🇹 Italian: it\n"
        "🇵🇹 Portuguese: pt\n"
        "🇷🇺 Russian: ru\n"
        "🇯🇵 Japanese: ja\n"
        "🇨🇳 Chinese (Simplified): zh\n"
        "🇰🇷 Korean: ko\n\n"
        "Use these codes with the /setlanguage command to set your preferred language.",
        language
    )
    update.message.reply_text(codes_message)

def translate_forwarded(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    message = update.message
    text = message.text or message.caption or ""
    target_language = get_user_language(user_id)
    translated_text = translate_text(text, target_language)
    
    # Versuche, den Absender zu identifizieren
    if message.forward_from:
        original_sender = f"@{message.forward_from.username}" if message.forward_from.username else message.forward_from.first_name
    elif message.forward_sender_name:
        original_sender = message.forward_sender_name
    elif message.forward_from_chat:
        original_sender = message.forward_from_chat.title or "Channel"
    else:
        original_sender = "Unknown"
    
    response = f"Original sender: {original_sender}\n\n🔤 Translation:\n\n{translated_text}"
    update.message.reply_text(response)

def set_language(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if not context.args:
        update.message.reply_text("⚠️ Please provide a language code. Use /languagecodes to see available options.")
        return
    language = context.args[0].lower()
    set_user_language(user_id, language)
    confirmation = translate_text(f"🌟 Language successfully set to: {language}", language)
    update.message.reply_text(confirmation)

def admin_panel(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        update.message.reply_text("🚫 You are not authorized to access the admin panel.")
        return
    
    keyboard = [
        [InlineKeyboardButton("👥 User Count", callback_data='user_count')],
        [InlineKeyboardButton("📊 Language Statistics", callback_data='language_stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("👨‍💼 Admin Panel:", reply_markup=reply_markup)

def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    if query.data == 'user_count':
        count = len(user_settings)
        query.edit_message_text(f"👥 Total users: {count}")
    elif query.data == 'language_stats':
        stats = {}
        for lang in user_settings.values():
            stats[lang] = stats.get(lang, 0) + 1
        text = "📊 Language statistics:\n" + "\n".join([f"{lang}: {count}" for lang, count in stats.items()])
        query.edit_message_text(text)

def main() -> None:
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("languagecodes", language_codes))
    dp.add_handler(CommandHandler("setlanguage", set_language))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(MessageHandler(Filters.forwarded, translate_forwarded))
    dp.add_handler(CallbackQueryHandler(button_callback))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
