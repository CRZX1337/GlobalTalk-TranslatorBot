import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    ApplicationHandlerStop
)
import google.generativeai as genai
from gtts import gTTS
import speech_recognition as sr
from pydub import AudioSegment

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# Konfiguration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ADMIN_USER_IDS = [int(id) for id in os.getenv('ADMIN_USER_IDS').split(',')]
USER_SETTINGS_FILE = "user_settings.json"
USAGE_STATS_FILE = "usage_stats.json"
USER_INFO_FILE = "user_info.json"
VIP_USERS_FILE = "vip_users.json"

# Logging konfigurieren
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini API konfigurieren
genai.configure(api_key=GEMINI_API_KEY)

# --- Model Selection ---
# Use the best available model.  'gemini-pro' is generally a good choice for text.
# If you have access to 'gemini-1.5-pro-001' or later, use that.  Otherwise, stick with 'gemini-pro'.
# MODEL_NAME = 'gemini-1.5-pro-001'  # Uncomment if you have access
MODEL_NAME = 'gemini-pro'  # Comment out if using gemini-1.5-pro-001

model = genai.GenerativeModel(MODEL_NAME)
# --- End Model Selection ---

# Gültige Sprachcodes
VALID_LANGUAGE_CODES = {
    'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'it': 'Italian',
    'pt': 'Portuguese', 'ru': 'Russian', 'ja': 'Japanese', 'zh': 'Chinese (Simplified)',
    'ko': 'Korean', 'ar': 'Arabic', 'hi': 'Hindi', 'nl': 'Dutch', 'pl': 'Polish',
    'sv': 'Swedish', 'tr': 'Turkish', 'vi': 'Vietnamese', 'th': 'Thai'
}

# Hilfsfunktionen für Dateioperationen
def load_json(filename, default={}):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return default

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f)

# Lade Daten
user_settings = load_json(USER_SETTINGS_FILE)
usage_stats = load_json(USAGE_STATS_FILE, {"total_translations": 0, "daily_stats": {}})
user_info = load_json(USER_INFO_FILE)
vip_users = set(load_json(VIP_USERS_FILE, []))

def ensure_user_in_settings(user_id):
    user_id = str(user_id)
    if user_id not in user_settings:
        user_settings[user_id] = 'en'
        save_json(USER_SETTINGS_FILE, user_settings)

def get_user_language(user_id):
    return user_settings.get(str(user_id), 'en')

def set_user_language(user_id, language):
    user_settings[str(user_id)] = language
    save_json(USER_SETTINGS_FILE, user_settings)

def update_usage_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    usage_stats["total_translations"] += 1
    usage_stats["daily_stats"][today] = usage_stats["daily_stats"].get(today, 0) + 1
    save_json(USAGE_STATS_FILE, usage_stats)

def update_user_info(user):
    user_id = str(user.id)
    if user_id not in user_info:
        user_info[user_id] = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code,
            "last_activity": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "translation_count": 0
        }
    else:
       user_info[user_id]["username"] = user.username
       user_info[user_id]["first_name"] = user.first_name
       user_info[user_id]["last_name"] = user.last_name
       user_info[user_id]["language_code"] = user.language_code
       user_info[user_id]["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
       if "translation_count" not in user_info[user_id]:
            user_info[user_id]["translation_count"] = 0

    user_info[user_id]["translation_count"] += 1
    save_json(USER_INFO_FILE, user_info)

def is_vip(user_id):
    return str(user_id) in vip_users

def translate_text(text, target_language, source_language=None):
    if not source_language:
        prompt_detect = f"""
        Task: Detect the language of the following text.

        Instructions:
        1. Analyze the text thoroughly to identify the language used.
        2. Respond with the language code of the detected language.

        Text:
        "{text}"

        Language code:
        """
        response_detect = model.generate_content(prompt_detect)
        source_language = response_detect.text.strip()

    if source_language not in VALID_LANGUAGE_CODES:
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

def text_to_speech(text, lang):
    try:

        prompt_improve = f"""
        Task: Improve the text for text to speech.

        Instructions:
        1. Analyze the text thoroughly to understand its full context, tone, and intent.
        2. Correct any grammar issues to make the text perfect for a text to speech application.
        3. If the text contains humor, wordplay, or cultural references make sure that these are also present when reading it out loud.
        4. Remove all Anführungszeichen und sonderzeichen wie ! " # $ % & / ( ) = ? ~ etc. die eine korrekte Text zu Sprache ausgabe behindern.

        Text:
        "{text}"

        Improved Text:
        """
        response_improve = model.generate_content(prompt_improve)
        improved_text = response_improve.text.strip()

        #Ersetzen von unerwünschten Sonderzeichen

        characters_to_remove = ['"', "'", '!', '#', '$', '%', '&', '/', '(', ')', '=', '?', '~', '<', '>', ',', '.']
        for char in characters_to_remove:
            improved_text = improved_text.replace(char, '')

        tts = gTTS(text=improved_text, lang=lang)
        temp_file = "temp.mp3"
        tts.save(temp_file)
        return temp_file
    except Exception as e:
        logger.error(f"Error generating TTS: {e}")
        return None

async def tts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_vip(user.id) and user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("🚫 This feature is only available for VIP users and admins.")
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
    welcome_message = translate_text(
        "🌟 Welcome to GlobalTalk-TranslatorBot! 🌍✨\n\n"
        "I'm here to help you translate forwarded messages into various languages. "
        "Simply forward me a message, and I'll translate it to your preferred language.\n\n"
        "To get started, use  to choose your language, or just start forwarding messages!\n\n"
        "Need help?",
        language
    )
    welcome_message = welcome_message.replace("use", "use /setlanguage")
    welcome_message += "\n\nNeed help? Just type /help for more information."
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    ensure_user_in_settings(user_id)
    language = get_user_language(user_id)
    help_message = translate_text(
        "🤖 Bot Commands:\n\n"
        "🌟 /start - Start the bot and see the welcome message\n"
        "🔤 /setlanguage - Set your preferred language\n"
        "ℹ️ /help - Show this help message\n"
        "🌍 /languagecodes - View available language codes\n"
        "👨‍💼 /admin - Access admin panel (only for authorized users)\n"
         "🎧 /tts [text] - Convert text to speech (VIP only)\n"
        "💬 /chat - Start a chat session (for VIP users and admins)\n\n"
        "To translate, simply forward a message to me. Enjoy translating! 🎉",
        language
    )
    await update.message.reply_text(help_message)

async def language_codes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    ensure_user_in_settings(user_id)
    language = get_user_language(user_id)
    codes_message = "🌐 Available Language Codes:\n\n"
    for code, lang_name in VALID_LANGUAGE_CODES.items():
        codes_message += f"{code}: {lang_name}\n"
    codes_message += "\nUse the /setlanguage command to set your preferred language."
    translated_message = translate_text(codes_message, language)
    await update.message.reply_text(translated_message)

async def translate_forwarded(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    ensure_user_in_settings(user.id)
    message = update.message
    if message.voice:
        return  # If voice message, do not translate

    text = message.text or message.caption or ""
    target_language = get_user_language(user.id)

    # Determine source language and original sender based on forward_origin type
    if message.forward_origin.type == "user":
        source_language = message.forward_origin.sender_user.language_code if message.forward_origin.sender_user else None
        original_sender = f"@{message.forward_origin.sender_user.username}" if message.forward_origin.sender_user.username else message.forward_origin.sender_user.first_name
    elif message.forward_origin.type == "chat":
        source_language = None  # Language code not available for chat forwards
        original_sender = message.forward_origin.chat.title or "Channel"
    elif message.forward_origin.type == "hidden_user":
        source_language = None # Language code not directly available
        original_sender = message.forward_origin.sender_user_name
    else:
        source_language = None
        original_sender = "Unknown"


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

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    ensure_user_in_settings(user.id)

    keyboard = []
    for code, name in VALID_LANGUAGE_CODES.items():
        keyboard.append([InlineKeyboardButton(name, callback_data=f'setlang_{code}')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("🌐 Please choose your language:", reply_markup=reply_markup)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("🚫 You are not authorized to access the admin panel.")
        return

    keyboard = [
        [InlineKeyboardButton("👥 User Count", callback_data='user_count')],
        [InlineKeyboardButton("📊 Language Statistics", callback_data='language_stats')],
        [InlineKeyboardButton("🔄 Reset All User Settings", callback_data='reset_settings')],
        [InlineKeyboardButton("📈 Usage Statistics", callback_data='usage_stats')],
        [InlineKeyboardButton("🔍 Search User", callback_data='search_user')],
        [InlineKeyboardButton("📣 Broadcast Message", callback_data='broadcast')],
        [InlineKeyboardButton("👤 User Info", callback_data='user_info')],
         [InlineKeyboardButton("👤 Change User Language", callback_data='change_user_lang')],
        [InlineKeyboardButton("🌟 Add VIP User", callback_data='add_vip_user')],
        [InlineKeyboardButton("🔽 Remove VIP User", callback_data='remove_vip_user')],
        [InlineKeyboardButton("📋 List All Users", callback_data='list_users')],
        [InlineKeyboardButton("📋 List User Translations", callback_data='list_user_translations')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👨‍💼 Admin Panel:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data.startswith('setlang_'):
        language = query.data[8:]
        set_user_language(query.from_user.id, language)
        confirmation = translate_text(f"🌟 Language successfully set to: {VALID_LANGUAGE_CODES[language]}", language)
        await query.edit_message_text(confirmation)
        return

    if query.data == 'user_count':
        count = len(user_settings)
        await query.edit_message_text(f"👥 Total users: {count}")
    elif query.data == 'language_stats':
        stats = {}
        for lang in user_settings.values():
            stats[lang] = stats.get(lang, 0) + 1
        text = "📊 Language statistics:\n" + "\n".join([f"{VALID_LANGUAGE_CODES.get(lang, lang)}: {count}" for lang, count in stats.items()])
        await query.edit_message_text(text)
    elif query.data == 'reset_settings':
        user_settings.clear()
        save_json(USER_SETTINGS_FILE, user_settings)
        await query.edit_message_text("🔄 All user settings have been reset.")
    elif query.data == 'usage_stats':
        total = usage_stats["total_translations"]
        daily = usage_stats["daily_stats"]
        text = f"📈 Total translations: {total}\n\nDaily statistics:\n"
        for date, count in daily.items():
            text += f"{date}: {count} translations\n"
        await query.edit_message_text(text)
    elif query.data == 'search_user':
        await query.edit_message_text("🔍 Please enter the user ID you want to search for:")
        context.user_data['admin_state'] = 'waiting_for_user_id'
    elif query.data == 'broadcast':
        await query.edit_message_text("📣 Please enter the message you want to broadcast to all users:")
        context.user_data['admin_state'] = 'waiting_for_broadcast'
    elif query.data == 'user_info':
        await query.edit_message_text("👤 Please enter the user ID to get detailed information:")
        context.user_data['admin_state'] = 'waiting_for_user_info'
    elif query.data == 'change_user_lang':
        await query.edit_message_text("👤 Please enter the user ID to change the language for:")
        context.user_data['admin_state'] = 'waiting_for_user_id_lang_change'
    elif query.data == 'add_vip_user':
        await query.edit_message_text("🌟 Please enter the user ID to add as a VIP user:")
        context.user_data['admin_state'] = 'waiting_for_vip_user_id'
    elif query.data == 'remove_vip_user':
        await query.edit_message_text("🔽 Please enter the user ID to remove from VIP users:")
        context.user_data['admin_state'] = 'waiting_for_remove_vip_user_id'
    elif query.data == 'list_users':
        users_list = "📋 List of all users:\n\n"
        for user_id, language in user_settings.items():
            vip_status = "🌟 VIP" if user_id in vip_users else "Regular"
            users_list += f"User ID: {user_id}, Language: {language}, Status: {vip_status}\n"
        await query.edit_message_text(users_list[:4096])  # Telegram message limit is 4096 characters
    elif query.data == 'list_user_translations':
        await query.edit_message_text("👤 Please enter the user ID to get the translation history:")
        context.user_data['admin_state'] = 'waiting_for_user_translations'

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        return

    state = context.user_data.get('admin_state')
    if state == 'waiting_for_user_id':
        search_user_id = update.message.text
        if search_user_id in user_settings:
            lang = user_settings[search_user_id]
            await update.message.reply_text(f"User {search_user_id} has language set to: {VALID_LANGUAGE_CODES.get(lang, lang)}")
        else:
            await update.message.reply_text("User not found in bot settings.")
        del context.user_data['admin_state']
    elif state == 'waiting_for_broadcast':
        broadcast_message = update.message.text
        success_count = 0
        for user_id in user_settings.keys():
            try:
                await context.bot.send_message(chat_id=int(user_id), text=broadcast_message)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user_id}: {e}")
        await update.message.reply_text(f"Broadcast sent successfully to {success_count} out of {len(user_settings)} users.")
        del context.user_data['admin_state']
    elif state == 'waiting_for_user_info':
        user_id = update.message.text
        try:
            if user_id in user_info:
                user = user_info[user_id]
                language = user_settings.get(str(user_id), "Not set")
                message = f"User Information for ID {user_id}:\n"
                message += f"Username: @{user['username']}\n" if user['username'] else "Username: Not set\n"
                message += f"First Name: {user['first_name']}\n"
                message += f"Last Name: {user['last_name']}\n" if user['last_name'] else "Last Name: Not set\n"
                message += f"Language Code: {user['language_code']}\n" if user['language_code'] else "Language Code: Not set\n"
                message += f"Last Activity: {user['last_activity']}\n"
                message += f"Translation Count: {user['translation_count']}\n"
                message += f"Preferred Language: {VALID_LANGUAGE_CODES.get(language, language)}\n"
                message += f"VIP Status: {'Yes' if str(user_id) in vip_users else 'No'}"
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("User not found in bot settings.")
        except Exception as e:
            await update.message.reply_text(f"Error retrieving user information: {str(e)}")
        del context.user_data['admin_state']
    elif state == 'waiting_for_user_id_lang_change':
       user_id = update.message.text
       if user_id in user_settings:
           keyboard = []
           for code, name in VALID_LANGUAGE_CODES.items():
                keyboard.append([InlineKeyboardButton(name, callback_data=f'setlang_{code}')])
           reply_markup = InlineKeyboardMarkup(keyboard)
           await update.message.reply_text("🌐 Please choose the new language:", reply_markup=reply_markup)
           context.user_data['admin_state'] = 'waiting_for_lang_change'
           context.user_data['lang_change_user_id'] = user_id
       else:
           await update.message.reply_text("User not found in bot settings.")
           del context.user_data['admin_state']
    elif state == 'waiting_for_lang_change':
        if update.message.text.startswith('setlang_'):
           language = update.message.text[8:]
           set_user_language(context.user_data['lang_change_user_id'], language)
           await update.message.reply_text(f"Language of user with the ID {context.user_data['lang_change_user_id']} has been set to: {VALID_LANGUAGE_CODES[language]}.")
        del context.user_data['admin_state']
        del context.user_data['lang_change_user_id']
    elif state == 'waiting_for_vip_user_id':
        vip_user_id = str(update.message.text)
        vip_users.add(vip_user_id)
        save_json(VIP_USERS_FILE, list(vip_users))
        await update.message.reply_text(f"User {vip_user_id} has been added to VIP users.")
        del context.user_data['admin_state']
    elif state == 'waiting_for_remove_vip_user_id':
        vip_user_id = str(update.message.text)
        if vip_user_id in vip_users:
            vip_users.remove(vip_user_id)
            save_json(VIP_USERS_FILE, list(vip_users))
            await update.message.reply_text(f"User {vip_user_id} has been removed from VIP users.")
        else:
            await update.message.reply_text(f"User {vip_user_id} is not a VIP user.")
        del context.user_data['admin_state']
    elif state == 'waiting_for_user_translations':
        user_id = update.message.text
        if user_id in user_info:
            translation_history = user_info[user_id].get("translation_history", [])
            if translation_history:
                history_text = f"📋 Translation history for user ID {user_id}:\n\n"
                for i, translation in enumerate(translation_history):
                    history_text += f"{i+1}. Original: {translation['original_text']}\n   Translation: {translation['translated_text']}\n"
                    if len(history_text) > 4000:
                        await update.message.reply_text(history_text)
                        history_text = ""
                if len(history_text) > 0:
                   await update.message.reply_text(history_text)
            else:
               await update.message.reply_text(f"No translation history found for user ID {user_id}.")
        else:
            await update.message.reply_text(f"User with ID {user_id} not found")
        del context.user_data['admin_state']

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS and not is_vip(user_id):
        await update.message.reply_text("🚫 This feature is only available for VIP users and admins.")
        return ConversationHandler.END

    await update.message.reply_text("You can now start chatting with the AI. Send /endchat to end the conversation.")
    return 1

async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_message = update.message.text
    if user_message.lower() == '/endchat':
        await update.message.reply_text("Chat session ended. Thank you for using our service!")
        return ConversationHandler.END

    try:
        response = model.generate_content(user_message)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}")
    return 1 # Keep same state

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Bye! I hope we can talk again some day."
    )
    return ConversationHandler.END

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

    chat_handler = ConversationHandler(
        entry_points=[CommandHandler('chat', chat)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message)], # Use integer state
        },
        fallbacks=[CommandHandler('endchat', cancel), CommandHandler("cancel", cancel)],
        #allow_reentry = True # REMOVE THIS LINE

    )
    app.add_handler(chat_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))

    # Use the application's run_polling method
    app.run_polling()

if __name__ == '__main__':
    main()