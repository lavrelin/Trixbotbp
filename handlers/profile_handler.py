from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile with safe DB handling"""
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("◀️ Главное меню", callback_data="menu:back")]
    ]
    
    # Базовая информация профиля без БД
    profile_text = (
        f"👤 *Ваш профиль*\n\n"
        f"🆔 ID: {user.id}\n"
        f"👋 Имя: {user.first_name or 'Не указано'}\n"
    )
    
    if user.username:
        profile_text += f"📧 Username: @{user.username}\n"
    
    # Пытаемся получить данные из БД, но не падаем если ошибка
    try:
        from services.db import db
        from models import User
        from sqlalchemy import select
        
        async with db.get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user.id)
            )
            db_user = result.scalar_one_or_none()
            
            if db_user:
                profile_text += f"📅 Регистрация: {db_user.created_at.strftime('%d.%m.%Y')}\n"
            
    except Exception as e:
        logger.warning(f"Could not load profile data from DB: {e}")
        # Продолжаем показывать профиль без данных из БД
    
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
        # Fallback без форматирования
        await update.effective_message.reply_text(
            f"Ваш профиль\n\nID: {user.id}\nИмя: {user.first_name or 'Не указано'}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle profile callbacks"""
    query = update.callback_query
    await query.answer()
    
    await show_profile(update, context)
