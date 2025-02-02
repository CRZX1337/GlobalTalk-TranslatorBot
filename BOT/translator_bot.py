import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import google.generativeai as genai

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# Konfiguration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_USER_IDS = [int(id) for id in os.getenv('ADMIN_USER_IDS').split(',')]
USER_SETTINGS_FILE = "user_settings.json"
USAGE_STATS_FILE = "usage_stats.json"
USER_INFO_FILE = "user_info.json"

# Logging konfigurieren
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini API konfigurieren
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Gültige Sprachcodes
VALID_LANGUAGE_CODES = {
    'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'it': 'Italian',
    'pt': 'Portuguese', 'ru': 'Russian', 'ja': 'Japanese', 'zh': 'Chinese (Simplified)',
    'ko': 'Korean', 'ar': 'Arabic', 'hi': 'Hindi', 'nl': 'Dutch', 'pl': 'Polish',
    'sv': 'Swedish', 'tr': 'Turkish', 'vi': 'Vietnamese', 'th': 'Thai'
}

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

# Nutzungsstatistiken laden oder erstellen
def load_usage_stats():
    if os.path.exists(USAGE_STATS_FILE):
        with open(USAGE_STATS_FILE, 'r') as f:
            return json.load(f)
    return {"total_translations": 0, "daily_stats": {}}

def save_usage_stats(stats):
    with open(USAGE_STATS_FILE, 'w') as f:
        json.dump(stats, f)

usage_stats = load_usage_stats()

# Benutzerinformationen laden oder erstellen
def load_user_info():
    if os.path.exists(USER_INFO_FILE):
        with open(USER_INFO_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_info(info):
    with open(USER_INFO_FILE, 'w') as f:
        json.dump(info, f)

user_info = load_user_info()

def ensure_user_in_settings(user_id):
    if str(user_id) not in user_settings:
        user_settings[str(user_id)] = 'en'  # Standardsprache auf Englisch setzen
        save_user_settings(user_settings)

def get_user_language(user_id):
    return user_settings.get(str(user_id), 'en')

def set_user_language(user_id, language):
    user_settings[str(user_id)] = language
    save_user_settings(user_settings)

def update_usage_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    usage_stats["total_translations"] += 1
    usage_stats["daily_stats"][today] = usage_stats["daily_stats"].get(today, 0) + 1
    save_usage_stats(usage_stats)

def update_user_info(user):
    user_id = str(user.id)
    user_info[user_id] = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code,
        "last_activity": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_user_info(user_info)

def translate_text(text, target_language, source_language=None):
    if not source_language:
        source_language = "the source language"
    
    prompt = f"""
    Task: Translate the following text from {source_language} to {target_language} with extreme precision and accuracy.

    Instructions:
    1. Analyze the text thoroughly to understand its full context, tone, and intent.
    2. Consider any cultural nuances, idioms, or specific terminology in the source text.
    3. Translate the text maintaining the original meaning, tone, and style as closely as possible.
    4. Ensure proper grammar, punctuation, and formatting in the target language.
    5. If there are multiple possible interpretations, choose the most appropriate one based on context.
    6. For any ambiguous terms or phrases, provide the most likely translation and include a brief explanation in parentheses if necessary.
    7. Double-check the translation for accuracy, paying special attention to:
       - Correct use of tenses
       - Proper noun translations (names, places, etc.)
       - Numerical values and units of measurement
       - Technical or specialized vocabulary
    8. Verify that no part of the original text has been omitted in the translation.
    9. Ensure that the translation reads naturally in the target language.
    10. If the text contains humor, wordplay, or cultural references, adapt them appropriately for the target language and culture.

    Original text:
    "{text}"

    Translated text (in {target_language}):
    """
    
    response = model.generate_content(prompt)
    translated_text = response.text.strip()
    
    # Additional verification step
    verification_prompt = f"""
    Verify the accuracy of the following translation from {source_language} to {target_language}:

    Original: "{text}"
    Translation: "{translated_text}"

    Instructions:
    1. Check for any mistranslations or inaccuracies.
    2. Verify that the tone and style are preserved.
    3. Ensure all content from the original is included in the translation.
    4. Check for proper grammar and natural flow in the target language.

    If any issues are found, provide a corrected version. If no issues are found, respond with "Translation is accurate."

    Verification result:
    """
    
    verification_response = model.generate_content(verification_prompt)
    verification_result = verification_response.text.strip()
    
    if verification_result != "Translation is accurate.":
        # If issues were found, use the corrected version
        translated_text = verification_result.split("\n")[-1]  # Get the last line of the response
    
    return translated_text

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    ensure_user_in_settings(user.id)
    language = get_user_language(user.id)
    update_user_info(user)
    welcome_message = translate_text(
        "🌟 Welcome to GlobalTalk-TranslatorBot! 🌍✨\n\n"
        "I'm here to help you translate forwarded messages into various languages. "
        "Simply forward me a message, and I'll translate it to your preferred language.\n\n"
        "To get started, use /setlanguage to choose your language, or just start forwarding messages!\n\n"
        "Need help? Just type /help for more information.",
        language
    )
    update.message.reply_text(welcome_message)

def help_command(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    ensure_user_in_settings(user_id)
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
    ensure_user_in_settings(user_id)
    language = get_user_language(user_id)
    codes_message = "🌐 Available Language Codes:\n\n"
    for code, lang_name in VALID_LANGUAGE_CODES.items():
        codes_message += f"{code}: {lang_name}\n"
    codes_message += "\nUse these codes with the /setlanguage command to set your preferred language."
    translated_message = translate_text(codes_message, language)
    update.message.reply_text(translated_message)

def translate_forwarded(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    ensure_user_in_settings(user.id)
    message = update.message
    text = message.text or message.caption or ""
    target_language = get_user_language(user.id)
    source_language = message.from_user.language_code if message.from_user else None
    translated_text = translate_text(text, target_language, source_language)
    
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
    update_usage_stats()
    update_user_info(user)

def set_language(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    ensure_user_in_settings(user.id)
    if not context.args:
        update.message.reply_text("⚠️ Please provide a valid language code. Use /languagecodes to see available options.")
        return
    language = context.args[0].lower()
    if language not in VALID_LANGUAGE_CODES:
        update.message.reply_text("⚠️ Invalid language code. Use /languagecodes to see available options.")
        return
    set_user_language(user.id, language)
    update_user_info(user)
    confirmation = translate_text(f"🌟 Language successfully set to: {VALID_LANGUAGE_CODES[language]}", language)
    update.message.reply_text(confirmation)

def admin_panel(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        update.message.reply_text("🚫 You are not authorized to access the admin panel.")
        return
    
    keyboard = [
        [InlineKeyboardButton("👥 User Count", callback_data='user_count')],
        [InlineKeyboardButton("📊 Language Statistics", callback_data='language_stats')],
        [InlineKeyboardButton("🔄 Reset All User Settings", callback_data='reset_settings')],
        [InlineKeyboardButton("📈 Usage Statistics", callback_data='usage_stats')],
        [InlineKeyboardButton("🔍 Search User", callback_data='search_user')],
        [InlineKeyboardButton("📣 Broadcast Message", callback_data='broadcast')],
        [InlineKeyboardButton("👤 User Info", callback_data='user_info')]
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
        text = "📊 Language statistics:\n" + "\n".join([f"{VALID_LANGUAGE_CODES.get(lang, lang)}: {count}" for lang, count in stats.items()])
        query.edit_message_text(text)
    elif query.data == 'reset_settings':
        user_settings.clear()
        save_user_settings(user_settings)
        query.edit_message_text("🔄 All user settings have been reset.")
    elif query.data == 'usage_stats':
        total = usage_stats["total_translations"]
        daily = usage_stats["daily_stats"]
        text = f"📈 Total translations: {total}\n\nDaily statistics:\n"
        for date, count in daily.items():
            text += f"{date}: {count} translations\n"
        query.edit_message_text(text)
    elif query.data == 'search_user':
        query.edit_message_text("🔍 Please enter the user ID you want to search for:")
        context.user_data['admin_state'] = 'waiting_for_user_id'
    elif query.data == 'broadcast':
        query.edit_message_text("📣 Please enter the message you want to broadcast to all users:")
        context.user_data['admin_state'] = 'waiting_for_broadcast'
    elif query.data == 'user_info':
        query.edit_message_text("👤 Please enter the user ID to get detailed information:")
        context.user_data['admin_state'] = 'waiting_for_user_info'

def handle_admin_input(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        return

    state = context.user_data.get('admin_state')
    if state == 'waiting_for_user_id':
        search_user_id = update.message.text
        if search_user_id in user_settings:
            lang = user_settings[search_user_id]
            update.message.reply_text(f"User {search_user_id} has language set to: {VALID_LANGUAGE_CODES.get(lang, lang)}")
        else:
            update.message.reply_text("User not found in bot settings.")
        del context.user_data['admin_state']
    elif state == 'waiting_for_broadcast':
        broadcast_message = update.message.text
        success_count = 0
        for user_id in user_settings.keys():
            try:
                context.bot.send_message(chat_id=int(user_id), text=broadcast_message)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user_id}: {e}")
        update.message.reply_text(f"Broadcast sent successfully to {success_count} out of {len(user_settings)} users.")
        del context.user_data['admin_state']
    elif state == 'waiting_for_user_info':
        user_id = update.message.text
        try:
            chat_member = context.bot.get_chat_member(user_id, user_id)
            user = chat_member.user
            language = user_settings.get(str(user_id), "Not set")
            message = f"User Information for ID {user_id}:\n"
            message += f"Username: @{user.username}\n" if user.username else "Username: Not set\n"
            message += f"First Name: {user.first_name}\n"
            message += f"Last Name: {user.last_name}\n" if user.last_name else "Last Name: Not set\n"
            message += f"Language Code: {user.language_code}\n" if user.language_code else "Language Code: Not set\n"
            message += f"Is Bot: {'Yes' if user.is_bot else 'No'}\n"
            message += f"Preferred Language: {VALID_LANGUAGE_CODES.get(language, language)}"
            update.message.reply_text(message)
        except Exception as e:
            update.message.reply_text(f"Error retrieving user information: {str(e)}")
        del context.user_data['admin_state']

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
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_admin_input))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
