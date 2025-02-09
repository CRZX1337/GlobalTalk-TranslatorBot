import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in constants.ADMIN_USER_IDS and not is_vip(user_id):
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
    return 1  # Keep same state


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Bye! I hope we can talk again some day."
    )
    return ConversationHandler.END
