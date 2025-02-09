import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from user_management import is_vip
from constants import ADMIN_USER_IDS
# from translator_bot import model # Absoluter Import wieder verwenden <- REMOVED

logger = logging.getLogger(__name__)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Startet die Chat-Konversation."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS and not is_vip(user_id):
        await update.message.reply_text("🚫 This feature is only available for VIP users and admins.")
        return ConversationHandler.END

    await update.message.reply_text("You can now start chatting with the AI. Send /endchat to end the conversation.")
    return 1


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE, model) -> int: # Added model as argument
    """Verarbeitet Nachrichten im Chat-Modus."""
    print("HANDLE_CHAT_MESSAGE WIRD AUFGERUFEN")  # DEBUG-AUSGABE
    import sys
    print(f"Python sys.path: {sys.path}")  # DEBUG-AUSGABE: Python Path ausgeben
    user_message = update.message.text
    if user_message.lower() == '/endchat':
        await update.message.reply_text("Chat session ended. Thank you for using our service!")
        return ConversationHandler.END

    try:
        # Verwende das importierte Model-Objekt für Gemini-Anfragen
        response = model.generate_content(user_message)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error in chat: {e}") # Logging hinzugefügt
        await update.message.reply_text(f"An error occurred: {str(e)}")
    return 1  # Behalte den Chat-Status bei


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bricht die Konversation ab und beendet sie."""
    user = update.message.from_user
    logger.info(f"User {user.first_name} canceled the conversation.") # Logging verbessert
    await update.message.reply_text(
        "Bye! I hope we can talk again some day."
    )
    return ConversationHandler.END