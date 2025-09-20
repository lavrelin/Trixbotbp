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
    CHAT_FOR_ACTUAL = int(os.getenv("CHAT_FOR_ACTUAL", "-1002734837434"))  # ID чата для актуальных постов (временно = модерации)
    CHAT_FOR_ADS = os.getenv("CHAT_FOR_ADS", "https://t.me/tgchatxxx")
    
    # Новый канал для барахолки
    TRADE_CHANNEL_ID = int(os.getenv("TRADE_CHANNEL_ID", "-1003033694255"))  # https://t.me/hungarytrade
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/trixbot")
    
    # Admins and moderators
    ADMIN_IDS: Set[int] = set(map(int, filter(None, os.getenv("ADMIN_IDS", "7811593067").split(","))))
    MODERATOR_IDS: Set[int] = set(map(int, filter(None, os.getenv("MODERATOR_IDS", "7811593067").split(","))))
    
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
    
    # Categories (updated without Search)
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
        "💼 Услуги": []
    }
    
    # Hashtags
    HASHTAGS = {
        "🗯️ Будапешт": {
            "🗣️ Объявления": {
                "👷‍♀️ Работа": ["#Работа", "#ВакансииБудапешт"],
                "🏠 Аренда": ["#Аренда", "#НедвижимостьБудапешт"],
                "🔻 Куплю": ["#Куплю", "#ПокупкаБудапешт"],
                "🔺 Продам": ["#Продам", "#ПродажаБудапешт"],
                "🎉 События": ["#События", "#МероприятияБудапешт"],
                "📦 Отдам даром": ["#ОтдамДаром", "#БесплатноБудапешт"],
                "🌪️ Важно": ["#Важно", "#СрочноБудапешт"],
                "❔ Другое": ["#Объявления", "#РазноеБудапешт"]
            },
            "📺 Новости": ["#Новости", "#НовостиБудапешт"],
            "🤐 Подслушано": ["#Подслушано", "#ИсторииБудапешт"],
            "🤮 Жалобы": ["#Жалобы", "#ПроблемыБудапешт"]
        },
        "💼 Услуги": ["#Услуги", "#БизнесБудапешт"]
    }
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in cls.ADMIN_IDS
    
    @classmethod
    def is_moderator(cls, user_id: int) -> bool:
        """Check if user is moderator or admin"""
        return user_id in cls.MODERATOR_IDS or cls.is_admin(user_id)
    
    @classmethod
    def get_all_moderators(cls) -> Set[int]:
        """Get all moderators and admins"""
        return cls.ADMIN_IDS.union(cls.MODERATOR_IDS)
    
    @classmethod
    def get_xp_level(cls, xp: int) -> tuple:
        """Get level info by XP amount"""
        for level in range(len(cls.XP_LEVELS), 0, -1):
            if xp >= cls.XP_LEVELS[level][0]:
                return level, cls.XP_LEVELS[level][1]
        return 1, cls.XP_LEVELS[1][1]
    
    @classmethod
    def get_next_level_xp(cls, current_xp: int) -> int:
        """Get XP needed for next level"""
        current_level, _ = cls.get_xp_level(current_xp)
        
        if current_level >= len(cls.XP_LEVELS):
            return 0  # Max level reached
        
        next_level = current_level + 1
        return cls.XP_LEVELS[next_level][0] - current_xp
