from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
import logging

logger = logging.getLogger(__name__)

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    
    if action == "budapest":
        await show_budapest_menu(update, context)
    elif action == "search":
        await start_search(update, context)
    elif action == "offers":
        await start_offers(update, context)
    elif action == "piar":
        await start_piar(update, context)
    elif action == "profile":
        from handlers.profile_handler import show_profile
        await show_profile(update, context)
    elif action == "help":
        from handlers.start_handler import help_command
        await help_command(update, context)
    elif action == "back":
        from handlers.start_handler import show_main_menu
        await show_main_menu(update, context)
    elif action == "announcements":
        await show_announcements_menu(update, context)
    elif action == "news":
        await start_category_post(update, context, "🗯️ Будапешт", "📺 Новости")
    elif action == "overheard":
        await start_category_post(update, context, "🗯️ Будапешт", "🤐 Подслушано", anonymous=True)
    elif action == "complaints":
        await start_category_post(update, context, "🗯️ Будапешт", "🤮 Жалобы", anonymous=True)

async def show_budapest_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Budapest category menu"""
    keyboard = [
        [InlineKeyboardButton("🗣️ Объявления", callback_data="menu:announcements")],
        [InlineKeyboardButton("📺 Новости", callback_data="menu:news")],
        [InlineKeyboardButton("🤐 Подслушано (анонимно)", callback_data="menu:overheard")],
        [InlineKeyboardButton("🤮 Жалобы (анонимно)", callback_data="menu:complaints")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu:back")]
    ]
    
    text = (
        "🗯️ *Будапешт*\n\n"
        "Выберите тип публикации:\n\n"
        "🗣️ *Объявления* - работа, аренда, купля/продажа\n"
        "📺 *Новости* - актуальная информация\n"
        "🤐 *Подслушано* - анонимные истории\n