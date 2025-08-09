from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from services.db import db
from models import User, Gender
from sqlalchemy import select
from datetime import datetime
import logging
import secrets
import string

logger = logging.getLogger(__name__)

# Состояния для регистрации
GENDER, BIRTHDATE = range(2)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    
    # Check referral code
    referral_code = None
    if context.args and len(context.args) > 0:
        referral_code = context.args[0]
    
    async with db.get_session() as session:
        # Check if user exists
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # New user - request gender
            context.user_data['registration'] = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'referral_code': referral_code
            }
            
            keyboard = [
                [
                    InlineKeyboardButton("👨 Мужской", callback_data="profile:gender:M"),
                    InlineKeyboardButton("👩 Женский", callback_data="profile:gender:F")
                ],
                [InlineKeyboardButton("🤷 Другой", callback_data="profile:gender:other")]
            ]
            
            await update.effective_message.reply_text(
                f"Привет, {first_name}! 👋\n\n"
                "Добро пожаловать в бот TRIX!\n"
                "Для начала укажите ваш пол:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return GENDER
        else:
            # Existing user - show main menu
            await show_main_menu(update, context)
            return ConversationHandler.END

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu"""
    keyboard = [
        [InlineKeyboardButton("🗯️ Будапешт", callback_data="menu:budapest")],
        [InlineKeyboardButton("🕵️ Поиск", callback_data="menu:search")],
        [InlineKeyboardButton("📃 Предложения", callback_data="menu:offers")],
        [InlineKeyboardButton("⭐️ Пиар", callback_data="menu:piar")],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="menu:profile"),
            InlineKeyboardButton("ℹ️ Помощь", callback_data="menu:help")
        ]
    ]
    
    text = (
        "🏠 *Главное меню*\n\n"
        "Выберите раздел для публикации:\n\n"
        "🗯️ *Будапешт* - объявления, новости, подслушано\n"
        "🕵️ *Поиск* - поиск чего угодно\n"
        "📃 *Предложения* - услуги и помощь\n"
        "⭐️ *Пиар* - продвижение бизнеса\n"
    )
    
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📖 *Помощь по использованию бота*\n\n"
        "🔸 /start - главное меню\n"
        "🔸 /profile - ваш профиль\n"
        "🔸 /stats - статистика\n"
        "🔸 /top - топ пользователей\n\n"
        "*Как опубликовать пост:*\n"
        "1. Выберите категорию в главном меню\n"
        "2. Выберите подкатегорию (если есть)\n"
        "3. Отправьте текст и/или медиа\n"
        "4. Проверьте предпросмотр\n"
        "5. Отправьте на модерацию\n\n"
        "*Правила:*\n"
        "• Между постами должно пройти минимум 94 минуты\n"
        "• Запрещены ссылки (кроме официальных)\n"
        "• Все посты проходят модерацию\n\n"
        "По всем вопросам: @admin"
    )
    
    await update.effective_message.reply_text(
        help_text,
        parse_mode='Markdown'
    )

def generate_referral_code():
    """Generate unique referral code"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))