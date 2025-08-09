import os
from dotenv import load_dotenv
from typing import List, Set

load_dotenv()

class Config:
    # Telegram
    BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
    
    # Channels and groups
    TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "-1002743668534"))
    MODERATION_GROUP_ID = int(os.getenv("MODERATION_GROUP_ID", "-1002734837434"))
    CHAT_FOR_ADS = os.getenv("CHAT_FOR_ADS", "https://t.me/tgchatxxx")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/trixbot")
    
    # Admins and moderators
    ADMIN_IDS: Set[int] = set(map(int, filter(None, os.getenv("ADMIN_IDS", "").split(","))))
    MODERATOR_IDS: Set[int] = set(map(int, filter(None, os.getenv("MODERATOR_IDS", "").split(","))))
    
    # Cooldown
    COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "5666"))
    
    # Scheduler
    SCHEDULER_MIN_INTERVAL = int(os.getenv("SCHEDULER_MIN", "120"))
    SCHEDULER_MAX_INTERVAL = int(os.getenv("SCHEDULER_MAX", "160"))
    SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"
    
    # Default messages
    DEFAULT_SIGNATURE = os.getenv("DEFAULT_SIGNATURE", "🗯️ Бот для ваших публикаций — https://t.me/Trixlivebot")
    DEFAULT_PROMO_MESSAGE = os.getenv("DEFAULT_PROMO_MESSAGE", 
                                      "Сделать публикацию: https://t.me/Trixlivebot\n"
                                      "Топ канал Будапешта - @snghu")
    
    # XP System
    XP_MESSAGE = 1
    XP_MEDIA = 2
    XP_REACTION = 1
    XP_VOTE = 5
    XP_REFERRAL = 10
    XP_HOURLY_LIMIT = 50
    
    # XP Levels
    XP_LEVELS = {
        1: (0, "🪨 Я"),
        2: (50, "🪰 Турист"),
        3: (150, "🐜 Работающий"),
        4: (300, "🐢 Интегрированный"),
        5: (600, "🐬 Коренной"),
        6: (1000, "🐳 Свой")
    }
    
    # Filters
    BANNED_DOMAINS = [
        "http://", "https://", "t.me/", "www.",
        "bit.ly", "tinyurl.com", "cutt.ly", "goo.gl",
        "shorturl.at", "ow.ly", "is.gd", "buff.ly"
    ]
    
    # Media limits
    MAX_PHOTOS_PIAR = 3
    MAX_DISTRICTS_PIAR = 3
    
    # Categories
    CATEGORIES = {
        "🗯️ Будапешт": {
            "🗣️ Объявления": [
                "👷‍♀️ Работа",
                "🏠 Аренда", 
                "🔻 Куплю",
                "🔺 Продам",
                "🎉 События",
                "📦 Отдам даром",
                "🌪️ Важно",
                "❔ Другое"
            ],
            "📺 Новости": [],
            "🤐 Подслушано": [],
            "🤮 Жалобы": []
        },
        "🕵️ Поиск": [],
        "📃 Предложения": [],
        "⭐️ Пиар": []
    }
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        return user_id in cls.ADMIN_IDS
    
    @classmethod
    def is_moderator(cls, user_id: int) -> bool:
        return user_id in cls.MODERATOR_IDS or cls.is_admin(user_id)
    
    @classmethod
    def get_level_info(cls, xp: int) -> tuple[int, str]:
        level = 1
        level_name = cls.XP_LEVELS[1][1]
        
        for lvl, (min_xp, name) in cls.XP_LEVELS.items():
            if xp >= min_xp:
                level = lvl
                level_name = name
        
        return level, level_name