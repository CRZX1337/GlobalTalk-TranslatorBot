import os

VALID_LANGUAGE_CODES = {
    'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'it': 'Italian',
    'pt': 'Portuguese', 'ru': 'Russian', 'ja': 'Japanese', 'zh': 'Chinese (Simplified)',
    'ko': 'Korean', 'ar': 'Arabic', 'hi': 'Hindi', 'nl': 'Dutch', 'pl': 'Polish',
    'sv': 'Swedish', 'tr': 'Turkish', 'vi': 'Vietnamese', 'th': 'Thai'
}

USER_SETTINGS_FILE = "user_settings.json"
USAGE_STATS_FILE = "usage_stats.json"
USER_INFO_FILE = "user_info.json"
VIP_USERS_FILE = "vip_users.json"

ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv('ADMIN_USER_IDS', '').split(',')]