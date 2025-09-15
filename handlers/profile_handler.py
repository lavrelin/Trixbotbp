from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.db import db
from models import User
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    try:
        # Получаем данные пользователя из БД
        async with db.get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            db_user = result.scalar_one_or_none()
        
        keyboard = [
            [InlineKeyboardButton("◀️ Главное меню", callback_data="menu:back")]
        ]
        
        profile_text = (
            f"👤 *Ваш профиль*\n\n"
            f"🆔 ID: {user.id}\n"
            f"👋 Имя: {user.first_name or 'Не указано'}\n"
        )
        
        if user.username:
            profile_text += f"📧 Username: @{user.username}\n"
        
        if db_user:
            profile_text += f"📅 Регистрация: {db_user.created_at.strftime('%d.%m.%Y')}\n"
            if hasattr(db_user, 'posts_count'):
                profile_text += f"📝 Публикаций: {db_user.posts_count or 0}\n"
        
        profile_text += f"\n💼 Статус: Активный пользователь"
        
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    profile_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await update.effective_message.reply_text(
                    profile_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error showing profile: {e}")
            await update.effective_message.reply_text(
                profile_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in show_profile: {e}")
        await update.effective_message.reply_text(
            "❌ Ошибка загрузки профиля. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Главное меню", callback_data="menu:back")]
            ])
        )

async def handle_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle profile callbacks"""
    query = update.callback_query
    await query.answer()
    
    # Пока только показываем профиль
    await show_profile(update, context)
