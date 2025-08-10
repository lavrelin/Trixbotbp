from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.db import db
from models import User, Gender
from sqlalchemy import select
from datetime import datetime
import logging
import secrets
import string

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    
    async with db.get_session() as session:
        # Check if user exists
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Create new user immediately with default values
            new_user = User(
                id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                gender=Gender.UNKNOWN,
                referral_code=generate_referral_code(),
                created_at=datetime.utcnow()
            )
            session.add(new_user)
            await session.commit()
            logger.info(f"Created new user: {user_id}")
    
    # Always show main menu
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu"""
    keyboard = [
        [InlineKeyboardButton("🗯️ Будапешт", callback_data="menu:budapest")],
        [InlineKeyboardButton("🕵️ Поиск", callback_data="menu:search")],
        [InlineKeyboardButton("📚 Каталог", callback_data="menu:catalog")],
        [InlineKeyboardButton("⭐️ Пиар", callback_data="menu:piar")],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="menu:profile"),
            InlineKeyboardButton("ℹ️ Помощь", callback_data="menu:help")
        ]
    ]
    
    text = (
        "🏠 *Главное меню*\n\n"
        "Выберите раздел:\n\n"
        "🗯️ *Будапешт* - объявления, новости, подслушано\n"
        "🕵️ *Поиск* - поиск чего угодно\n"
        "📚 *Каталог* - каталог услуг и товаров\n"
        "⭐️ *Пиар* - продвижение бизнеса\n"
    )
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.effective_message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error showing main menu: {e}")
        # Если не можем отредактировать, отправим новое сообщение
        await update.effective_message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📖 *Помощь по использованию бота*\n\n"
        "🔸 /start - главное меню\n"
        "🔸 /profile - ваш профиль\n"
        "🔸 /help - эта помощь\n\n"
        "*Как опубликовать пост:*\n"
        "1. Выберите категорию в главном меню\n"
        "2. Выберите подкатегорию (если есть)\n"
        "3. Отправьте текст и/или медиа\n"
        "4. Проверьте предпросмотр\n"
        "5. Отправьте на модерацию\n\n"
        "*Правила:*\n"
        "• Между постами минимум 94 минуты\n"
        "• Запрещены ссылки\n"
        "• Все посты проходят модерацию\n"
    )
    
    await update.effective_message.reply_text(
        help_text,
        parse_mode='Markdown'
    )

def generate_referral_code():
    """Generate unique referral code"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
