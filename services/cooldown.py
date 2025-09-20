from datetime import datetime, timedelta
from services.db import db
from models import User
from sqlalchemy import select
from config import Config
import logging

logger = logging.getLogger(__name__)

class CooldownService:
    """Service for managing post cooldowns"""
    
    def __init__(self):
        self._cache = {}  # Simple in-memory cache for performance
    
    async def can_post(self, user_id: int) -> tuple[bool, int]:
        """
        Check if user can post
        Returns: (can_post: bool, remaining_seconds: int)
        """
        try:
            # Admins and moderators bypass cooldown
            if Config.is_moderator(user_id):
                return True, 0
            
            async with db.get_session() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return False, 0
                
                # Check if user is banned or muted
                if hasattr(user, 'banned') and user.banned:
                    return False, 999999
                
                if hasattr(user, 'mute_until') and user.mute_until and user.mute_until > datetime.utcnow():
                    remaining = int((user.mute_until - datetime.utcnow()).total_seconds())
                    return False, remaining
                
                # Check cooldown
                if hasattr(user, 'cooldown_expires_at') and user.cooldown_expires_at:
                    if user.cooldown_expires_at > datetime.utcnow():
                        remaining = int((user.cooldown_expires_at - datetime.utcnow()).total_seconds())
                        return False, remaining
                
                return True, 0
                
        except Exception as e:
            logger.error(f"Error checking cooldown for user {user_id}: {e}")
            # В случае ошибки разрешаем постить (безопасный fallback)
            return True, 0
    
    async def update_cooldown(self, user_id: int):
        """Update user's cooldown after posting"""
        try:
            if Config.is_moderator(user_id):
                return  # Модераторы не имеют кулдауна
            
            async with db.get_session() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if user:
                    if hasattr(user, 'cooldown_expires_at'):
                        user.cooldown_expires_at = datetime.utcnow() + timedelta(seconds=Config.COOLDOWN_SECONDS)
                        await session.commit()
                        logger.info(f"Updated cooldown for user {user_id}")
                        
        except Exception as e:
            logger.error(f"Error updating cooldown for user {user_id}: {e}")
    
    async def reset_cooldown(self, user_id: int) -> bool:
        """Reset user's cooldown (admin command)"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if user and hasattr(user, 'cooldown_expires_at'):
                    user.cooldown_expires_at = None
                    await session.commit()
                    logger.info(f"Reset cooldown for user {user_id}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error resetting cooldown for user {user_id}: {e}")
            return False
    
    async def get_cooldown_info(self, user_id: int) -> dict:
        """Get cooldown information for user"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return {'has_cooldown': False}
                
                if (hasattr(user, 'cooldown_expires
