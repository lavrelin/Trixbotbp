from datetime import datetime, timedelta
from services.db import db
from models import User
from sqlalchemy import select
from config import Config
import logging

logger = logging.getLogger(__name__)

class CooldownService:
    """Service for managing post cooldowns"""
    
    async def can_post(self, user_id: int) -> tuple[bool, int]:
        """
        Check if user can post
        Returns: (can_post: bool, remaining_seconds: int)
        """
        async with db.get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False, 0
            
            # Admins and moderators bypass cooldown
            if Config.is_moderator(user_id):
                return True, 0
            
            # Check if user is banned or muted
            if user.banned:
                return False, 999999
            
            if user.mute_until and user.mute_until > datetime.utcnow():
                remaining = int((user.mute_until - datetime.utcnow()).total_seconds())
                return False, remaining
            
            # Check cooldown
            if user.cooldown_expires_at:
                if user.cooldown_expires_at > datetime.utcnow():
                    remaining = int((user.cooldown_expires_at - datetime.utcnow()).total_seconds())
                    return False, remaining
            
            return True, 0
    
    async def update_cooldown(self, user_id: int):
        """Update user's cooldown after posting"""
        async with db.get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user and not Config.is_moderator(user_id):
                user.cooldown_expires_at = datetime.utcnow() + timedelta(seconds=Config.COOLDOWN_SECONDS)
                await session.commit()
                logger.info(f"Updated cooldown for user {user_id}")
    
    async def reset_cooldown(self, user_id: int) -> bool:
        """Reset user's cooldown (admin command)"""
        async with db.get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                user.cooldown_expires_at = None
                await session.commit()
                logger.info(f"Reset cooldown for user {user_id}")
                return True
            
            return False
    
    async def get_cooldown_info(self, user_id: int) -> dict:
        """Get cooldown information for user"""
        async with db.get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {'has_cooldown': False}
            
            if user.cooldown_expires_at and user.cooldown_expires_at > datetime.utcnow():
                remaining = int((user.cooldown_expires_at - datetime.utcnow()).total_seconds())
                return {
                    'has_cooldown': True,
                    'expires_at': user.cooldown_expires_at,
                    'remaining_seconds': remaining,
                    'remaining_minutes': remaining // 60
                }
            
            return {'has_cooldown': False}
