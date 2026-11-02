"""
Quản lý cấu hình (Config Manager) cho Tool Leech Manga & Pixiv.
Lưu trữ các cài đặt như Pixiv Cookie (PHPSESSID), số luồng mặc định, thư mục tải.
"""

import json
import os
from typing import Any, Dict

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "pixiv_cookie": "",
    "default_threads": 6,
    "default_output_dir": "downloads",
}


def load_config() -> Dict[str, Any]:
    """Tải cấu hình từ file config.json."""
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            config = DEFAULT_CONFIG.copy()
            config.update(data)
            return config
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> bool:
    """Lưu cấu hình vào file config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_pixiv_cookie() -> str:
    """Lấy Pixiv Cookie (PHPSESSID)."""
    cfg = load_config()
    return cfg.get("pixiv_cookie", "").strip()


def set_pixiv_cookie(cookie: str) -> bool:
    """Cập nhật Pixiv Cookie (PHPSESSID)."""
    cfg = load_config()
    cfg["pixiv_cookie"] = cookie.strip()
    return save_config(cfg)
