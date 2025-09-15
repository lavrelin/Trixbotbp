from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
import secrets
import string

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with safe DB handling"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    
    # Пытаемся сохранить пользователя в БД, но не падаем если ошибка
    try:
        from services.db import db
        from models import User, Gender
        from sqlalchemy import select
        from datetime import datetime
        
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
                
    except Exception as e:
        logger.warning(f"Could not save user to DB: {e}")
        # Продолжаем работу без БД
    
    # Always show main menu
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu with updated order"""
    keyboard = [
        [InlineKeyboardButton("🗯️ Будапешт", callback_data="menu:budapest")],
        [InlineKeyboardButton("💼 Предложить услугу", callback_data="menu:services")],
        [InlineKeyboardButton("📚 Каталог", callback_data="menu:catalog")],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="menu:profile"),
            InlineKeyboardButton("ℹ️ Помощь", callback_data="menu:help")
        ]
    ]
    
    text = (
        "🏠 *Главное меню*\n\n"
        "Выберите раздел:\n\n"
        "🗯️ *Будапешт* - объявления, новости, подслушано\n"
        "💼 *Предложить услугу* - продвижение бизнеса\n"
        "📚 *Каталог* - каталог услуг и товаров\n"
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
        # Fallback без форматирования
        try:
            await update.effective_message.reply_text(
                "Главное меню\n\nВыберите раздел:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e2:
            logger.error(f"Fallback menu also failed: {e2}")
            # Последний fallback - простое текстовое сообщение
            await update.effective_message.reply_text(
                "Бот запущен! Используйте /start для перезапуска."
            )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command with links to community"""
    keyboard = [
        [InlineKeyboardButton("📺 Канал SNGHU", url="https://t.me/snghu")],
        [InlineKeyboardButton("💬 Чат для общения", url="https://t.me/tgchatxxx")],
        [InlineKeyboardButton("📚 Каталог услуг", url="https://t.me/trixvault")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="menu:back")]
    ]
    
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
        "• Все посты проходят модерацию\n\n"
        "*Наше сообщество:*\n"
        "📺 Главный канал для публикаций\n"
        "💬 Чат для живого общения\n"
        "📚 Каталог всех услуг и товаров"
    )
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.effective_message.reply_text(
                help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error showing help: {e}")
        # Fallback без форматирования
        await update.effective_message.reply_text(
            "Помощь по использованию бота\n\n"
            "Основные команды:\n"
            "/start - главное меню\n"
            "/help - эта помощь\n\n"
            "Все посты проходят модерацию.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

def generate_referral_code():
    """Generate unique referral code"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
