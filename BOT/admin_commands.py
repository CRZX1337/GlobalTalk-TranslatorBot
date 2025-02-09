from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

from user_management import set_user_language, is_vip
from utils import save_json, load_json
from translation_service import translate_text
from constants import VALID_LANGUAGE_CODES, USER_SETTINGS_FILE, VIP_USERS_FILE, USER_INFO_FILE, ADMIN_USER_IDS
# Import von usage_stats
from usage_stats import usage_stats

logger = logging.getLogger(__name__)

# Daten laden
user_settings = load_json(USER_SETTINGS_FILE)
vip_users = set(load_json(VIP_USERS_FILE, []))
user_info = load_json(USER_INFO_FILE)

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
        # Translate the confirmation message
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