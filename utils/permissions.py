from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from config import Config
import logging

logger = logging.getLogger(__name__)

def admin_only(func):
    """Decorator to restrict command to admins only"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not Config.is_admin(user_id):
            await update.message.reply_text(
                "❌ Эта команда доступна только администраторам"
            )
            logger.warning(f"User {user_id} tried to use admin command {func.__name__}")
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def moderator_only(func):
    """Decorator to restrict command to moderators and admins"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not Config.is_moderator(user_id):
            await update.message.reply_text(
                "❌ Эта команда доступна только модераторам"
            )
            logger.warning(f"User {user_id} tried to use moderator command {func.__name__}")
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def check_user_banned(func):
    """Decorator to check if user is banned"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from services.db import db
        from models import User
        from sqlalchemy import select
        
        user_id = update.effective_user.id
        
        async with db.get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user and user.banned:
                await update.message.reply_text(
                    "❌ Вы заблокированы и не можете использовать бота"
                )
                return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def check_user_muted(func):
    """Decorator to check if user is muted"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from services.db import db
        from models import User
        from sqlalchemy import select
        from datetime import datetime
        
        user_id = update.effective_user.id
        
        async with db.get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user and user.mute_until and user.mute_until > datetime.utcnow():
                remaining = int((user.mute_until - datetime.utcnow()).total_seconds())
                minutes = remaining // 60
                
                await update.message.reply_text(
                    f"🔇 Вы замучены еще на {minutes} минут"
                )
                return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper
