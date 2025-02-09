from typing import Dict, Any
from telegram import User

from utils import load_json, save_json
from constants import USER_SETTINGS_FILE, VIP_USERS_FILE, USER_INFO_FILE # Added USER_INFO_FILE
from datetime import datetime

user_settings = load_json(USER_SETTINGS_FILE)
vip_users = set(load_json(VIP_USERS_FILE, []))
user_info = load_json(USER_INFO_FILE)

def ensure_user_in_settings(user_id: int) -> None:
    """
    Ensures that a user is present in the user settings.

    Args:
        user_id: The ID of the user.
    """
    user_id_str = str(user_id)
    if user_id_str not in user_settings:
        user_settings[user_id_str] = 'en'
        save_json(USER_SETTINGS_FILE, user_settings)

def get_user_language(user_id: int) -> str:
    """
    Gets the preferred language of a user.

    Args:
        user_id: The ID of the user.

    Returns:
        The language code of the user's preferred language.
    """
    return user_settings.get(str(user_id), 'en')

def set_user_language(user_id: int, language: str) -> None:
    """
    Sets the preferred language of a user.

    Args:
        user_id: The ID of the user.
        language: The language code to set.
    """
    user_settings[str(user_id)] = language
    save_json(USER_SETTINGS_FILE, user_settings)

def update_user_info(user: User) -> None:
    """
    Updates the user information in the user info file.

    Args:
        user: The Telegram User object.
    """
    user_id = str(user.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user_id not in user_info:
        user_info[user_id] = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code,
            "last_activity": now,
            "translation_count": 0
        }
    else:
       user_info[user_id]["username"] = user.username
       user_info[user_id]["first_name"] = user.first_name
       user_info[user_id]["last_name"] = user.last_name
       user_info[user_id]["language_code"] = user.language_code
       user_info[user_id]["last_activity"] = now
       if "translation_count" not in user_info[user_id]:
            user_info[user_id]["translation_count"] = 0

    user_info[user_id]["translation_count"] += 1
    save_json(USER_INFO_FILE, user_info)

def is_vip(user_id: int) -> bool:
    """
    Checks if a user is a VIP user.

    Args:
        user_id: The ID of the user.

    Returns:
        True if the user is a VIP user, False otherwise.
    """
    return str(user_id) in vip_users