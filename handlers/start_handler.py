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
                    # УБРАН updated_at - его нет в БД модели
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
    """Show new main menu design"""
    
    # Новые кнопки для главного меню
    keyboard = [
        [InlineKeyboardButton("🙅‍♂️ Будапешт - канал", url="https://t.me/snghu")],
        [InlineKeyboardButton("🙅‍♀️ Будапешт - чат", url="https://t.me/tgchatxxx")],
        [InlineKeyboardButton("🙅 Будапешт - каталог услуг", url="https://t.me/trixvault")],
        [InlineKeyboardButton("🚶‍♀️‍➡️ Писать", callback_data="menu:write")]
    ]
    
    # Новый текст главного меню с описанием
    text = (
        "🤖 *Добро пожаловать в TrixBot!*\n\n"
        "🎯 *Ваш помощник для публикаций в Будапеште*\n\n"
        
        "🧏🏻‍♀️ *Наши каналы и группы:*\n"
        "🙅‍♂️ *Канал* - основные публикации и новости\n"
        "🙅‍♀️ *Чат* - живое общение и обсуждения\n"
        "🙅 *Каталог* - поиск мастеров услуг\n\n"
        
        "✍️ *Хотите что-то опубликовать?*\n"
        "Нажмите 🚶‍♀️‍➡️ *Писать* и выберите тип публикации\n\n"
        
        "⚡️ Быстро • 🎯 Удобно • 🔒 Безопасно"
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
                "TrixBot - Ваш помощник для публикаций в Будапеште\n\n"
                "Нажмите 'Писать' чтобы создать публикацию",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e2:
            logger.error(f"Fallback menu also failed: {e2}")
            await update.effective_message.reply_text(
                "Бот запущен! Используйте /start для перезапуска."
            )

async def show_write_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show write menu with publication types"""
    
    keyboard = [
        [InlineKeyboardButton("🗯️ Пост в Будапешт", callback_data="menu:budapest")],
        [InlineKeyboardButton("💥 Заявка в каталог услуг", callback_data="menu:services")],
        [InlineKeyboardButton("⚡️ Актуальное", callback_data="menu:actual")],
        [InlineKeyboardButton("🚶‍♀️ Читать", callback_data="menu:read")]
    ]
    
    text = (
        "🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦\n"
        "#️⃣ *Выбор и описание разделов для создания поста на наши каналы:*\n"
        "🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦\n\n"
        
        "📌 *🗯️ Пост в 🙅‍♂️Будапешт/🕵🏼‍♀️КОП*\n"
        "💁‍♂️ Канал Будапешт: Объявления, новости, подслушанно, жалобы.\n"
        "🕵🏽‍♀️ Канал Куплю/Отдам/Продам: заявки на торги, обмены, раздачи и т.д.\n\n"
        
        "📌 *💥 Заявка в 🙅🏻‍♀️Каталог Услуг*\n"
        "📰 Список специалистов, отсортированный по #️⃣ направлениям для удобного поиска❕\n"
        "(Примеры: маникюр, репетитор английского, переводчик и т.д.)\n\n"
        
        "📌 *⚡️ Актуальное*\n"
        "Важные и срочные сообщения, публикуются в чат и закрепляются❕\n"
        "(Примеры: нужен стоматолог сегодня; Потерял 🐶 в 13 районе➕ фото; "
        "Ищу 🚐 для переезда; Нужен 👷🏽 на завтра — оплата в конце дня)\n\n"
        
        "📌 *🚶‍♀️ Читать*\n"
        "Вернуться в главное меню"
    )
    
    try:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error showing write menu: {e}")
        await update.callback_query.edit_message_text(
            "Выберите раздел публикации:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command - теперь показывает главное меню"""
    await show_main_menu(update, context)

def generate_referral_code():
    """Generate unique referral code"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
