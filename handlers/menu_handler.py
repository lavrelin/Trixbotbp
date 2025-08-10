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
    
    logger.info(f"Menu callback action: {action}")
    
    if action == "budapest":
        await show_budapest_menu(update, context)
    elif action == "search":
        await start_search(update, context)
    elif action == "catalog":
        # Открываем каталог
        await show_catalog(update, context)
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
    else:
        logger.warning(f"Unknown menu action: {action}")
        await query.answer("Функция в разработке", show_alert=True)

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
        "🤐 *Подслушано* - анонимные истории\n"
        "🤮 *Жалобы* - анонимные жалобы\n"
    )
    
    try:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in show_budapest_menu: {e}")
        await update.callback_query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def show_announcements_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show announcements subcategories"""
    keyboard = [
        [
            InlineKeyboardButton("👷‍♀️ Работа", callback_data="pub:cat:work"),
            InlineKeyboardButton("🏠 Аренда", callback_data="pub:cat:rent")
        ],
        [
            InlineKeyboardButton("🔻 Куплю", callback_data="pub:cat:buy"),
            InlineKeyboardButton("🔺 Продам", callback_data="pub:cat:sell")
        ],
        [
            InlineKeyboardButton("🎉 События", callback_data="pub:cat:events"),
            InlineKeyboardButton("📦 Отдам даром", callback_data="pub:cat:free")
        ],
        [
            InlineKeyboardButton("🌪️ Важно", callback_data="pub:cat:important"),
            InlineKeyboardButton("❔ Другое", callback_data="pub:cat:other")
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu:budapest")]
    ]
    
    text = (
        "🗣️ *Объявления*\n\n"
        "Выберите подкатегорию:"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start search post creation"""
    context.user_data['post_data'] = {
        'category': '🕵️ Поиск',
        'subcategory': None,
        'anonymous': False
    }
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="menu:back")]]
    
    text = (
        "🕵️ *Поиск*\n\n"
        "Отправьте текст вашего поискового запроса.\n"
        "Что вы ищете? (вещи, работу, людей, услуги)"
    )
    
    try:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        context.user_data['waiting_for'] = 'post_text'
    except Exception as e:
        logger.error(f"Error in start_search: {e}")
        await update.callback_query.answer("Ошибка. Попробуйте позже", show_alert=True)

async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show catalog link"""
    keyboard = [
        [InlineKeyboardButton("📚 Открыть каталог", url="https://t.me/trixvault")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu:back")]
    ]
    
    text = (
        "📚 *Каталог TRIX*\n\n"
        "Полный каталог услуг, товаров и предложений\n"
        "от участников сообщества.\n\n"
        "Нажмите кнопку ниже, чтобы перейти в каталог:"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def start_piar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Piar form"""
    context.user_data['piar_data'] = {}
    context.user_data['waiting_for'] = 'piar_name'
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="menu:back")]]
    
    text = (
        "⭐️ *Пиар - Продвижение бизнеса*\n\n"
        "Шаг 1 из 7\n"
        "Введите ваше имя:"
    )
    
    try:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in start_piar: {e}")
        await update.callback_query.answer("Ошибка. Попробуйте позже", show_alert=True)

async def start_category_post(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              category: str, subcategory: str, anonymous: bool = False):
    """Start post creation for specific category"""
    context.user_data['post_data'] = {
        'category': category,
        'subcategory': subcategory,
        'anonymous': anonymous
    }
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="menu:budapest")]]
    
    anon_text = " (анонимно)" if anonymous else ""
    
    text = (
        f"{category} → {subcategory}{anon_text}\n\n"
        "Отправьте текст вашей публикации и/или фото/видео:"
    )
    
    try:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        context.user_data['waiting_for'] = 'post_text'
    except Exception as e:
        logger.error(f"Error in start_category_post: {e}")
        await update.callback_query.answer("Ошибка. Попробуйте позже", show_alert=True)
