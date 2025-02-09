from datetime import datetime
from utils import load_json, save_json
from constants import USAGE_STATS_FILE

usage_stats = load_json(USAGE_STATS_FILE, {"total_translations": 0, "daily_stats": {}})

def update_usage_stats() -> None:
    """
    Updates the usage statistics.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    usage_stats["total_translations"] += 1
    usage_stats["daily_stats"][today] = usage_stats["daily_stats"].get(today, 0) + 1
    save_json(USAGE_STATS_FILE, usage_stats)