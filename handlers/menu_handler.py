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
    
    if action == "write":
        from handlers.start_handler import show_write_menu
        await show_write_menu(update, context)
    elif action == "read":
        from handlers.start_handler import show_main_menu
        await show_main_menu(update, context)
    elif action == "budapest":
        await show_budapest_menu(update, context)
    elif action == "catalog":
        await show_catalog(update, context)
    elif action == "services":  # Заявка в каталог услуг (бывший пиар)
        await start_piar(update, context)
    elif action == "actual":  # НОВЫЙ РАЗДЕЛ
        await start_actual_post(update, context)
    elif action == "back":
        from handlers.start_handler import show_main_menu
        await show_main_menu(update, context)
    elif action == "announcements":
        await show_announcements_menu(update, context)
    elif action == "news":
        await start_category_post(update, context, "🗯️ Будапешт", "🆕 Новости")
    elif action == "overheard":
        await start_category_post(update, context, "🗯️ Будапешт", "😈 Подслушано", anonymous=True)
    elif action == "complaints":
        await start_category_post(update, context, "🗯️ Будапешт", "🌚 Жалобы", anonymous=True)
    else:
        logger.warning(f"Unknown menu action: {action}")
        await query.answer("Функция в разработке", show_alert=True)

async def show_budapest_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Budapest category menu"""
    keyboard = [
        [InlineKeyboardButton("🎙️ Объявления", callback_data="menu:announcements")],
        [InlineKeyboardButton("🗞️ Новости", callback_data="menu:news")],
        [InlineKeyboardButton("😈 Подслушано (анонимно)", callback_data="menu:overheard")],
        [InlineKeyboardButton("🌚 Жалобы (анонимно)", callback_data="menu:complaints")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu:write")]
    ]
    
    text = (
        "🙅‍♂️ *Пост в Будапешт*\n\n"
        "Выберите тип публикации:\n\n"
        "🎙️ *Объявления* - товары, услуги, поиски и предложения. \n"
        "🗞️ *Новости* - новая актуальная информация\n"
        "😈 *Подслушано* - анонимные истории, сплетни, ситуации\n"
        "🌚 *Жалобы* - анонимные недовольства и проблемы\n"
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
            InlineKeyboardButton("🏢 Аренда", callback_data="pub:cat:rent")
        ],
        [
            InlineKeyboardButton("🕵🏻‍♀️ Куплю", callback_data="pub:cat:buy"),
            InlineKeyboardButton("🕵🏻‍♂️ Продам", callback_data="pub:cat:sell")
        ],
        [
            InlineKeyboardButton("🎉 События", callback_data="pub:cat:events"),
            InlineKeyboardButton("🕵🏼 Отдам даром", callback_data="pub:cat:free")
        ],
        [
            InlineKeyboardButton("🪙 Криптовалюта", callback_data="pub:cat:important"),
            InlineKeyboardButton("❔ Другое", callback_data="pub:cat:other")
        ],
        [InlineKeyboardButton("↩️ Выйти", callback_data="menu:budapest")]
    ]
    
    text = (
        "🎙️ *Объявления*\n\n"
        "Выберите подкатегорию:"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show catalog link"""
    keyboard = [
        [InlineKeyboardButton("📂 Открыть каталог", url="https://t.me/trixvault")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu:write")]
    ]
    
    text = (
        "🙅 *Каталог Услуг Будапешта от бота Трикса*\n\n"
        "Полный каталог услуг, товаров и предложений\n"
        "от участников сообщества.\n\n"
        "⤵️ Нажмите кнопку ниже, чтобы перейти в каталог:"
    )
    
    await update.callback_query. edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def start_piar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Services form (renamed from Piar)"""
    context.user_data['piar_data'] = {}
    context.user_data['waiting_for'] = 'piar_name'
    context.user_data['piar_step'] = 'name'
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="menu:write")]]

    text = (
        "🪄 *Подайте заявку на добавление в каталог Будапешта и всей Венгрии.*\n"
        "Это не просто перечень контактов — это динамичное сообщество, где соединяются специалисты, клиенты и партнёры.\n"
        "Мы создаём единое пространство, в котором можно найти всё необходимое: от частных услуг до профессиональных решений.\n\n"
        
        "🧲 *Цель каталога — сделать жизнь удобнее для каждого:*\n"
        "🧞- Вам — эффективнее находить клиентов,\n"
        "🧞‍♀️- людям — быстрее получать нужные услуги,\n"
        "🧞‍♂️- сообществу — активно развиваться и расширяться.\n\n"
        
        "🧬*Важно:* участники каталога — это Ваши будущие клиенты и партнёры. Каждая деталь, которую Вы укажете в заявке, имеет значение. От Вашей внимательности и креативности зависит, насколько быстро и легко Вас смогут найти те, кому нужны именно Ваши услуги.\n\n"
        "После подачи Ваша заявка будет проверена и откорректирована модераторами.\n"
        " О результате Вы получите персональное уведомление.\n\n"
        
        "*Приступим к первому шагу подачи заявки в Каталог Услуг:*\n"
        "💭 *Укажите своё имя, псевдоним или то, как к Вам обращаться:*"
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
    
    try:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in start_piar: {e}")
        await update.callback_query.answer("Ошибка. Попробуйте позже", show_alert=True)

async def start_actual_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Actual post creation - НОВЫЙ РАЗДЕЛ"""
    context.user_data['post_data'] = {
        'category': '⚡️Актуальное',
        'subcategory': None,
        'anonymous': False,
        'is_actual': True  # Специальный флаг для актуального
    }
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="menu:write")]]
    
    text = (
        "⚡️*Актуальное*\n\n"
        "🫧*Подробнее:*\n"
        "Этот раздел предназначен для важных и срочных сообщений, "
        "которые будут опубликованы в чате Будапешта и закреплены администраторами.\n\n"
        
        "🎯 *Подходит для:*\n"
        "• Срочные объявления\n"
        "• Важная информация\n"
        "• Экстренные сообщения\n"
        "• Актуальные новости\n\n"
        
        "📝 Отправьте текст вашего сообщения и/или до 3 медиа файлов:"
    )
    
    try:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        context.user_data['waiting_for'] = 'post_text'
    except Exception as e:
        logger.error(f"Error in start_actual_post: {e}")
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
        "📝 Отправьте текст вашей публикации и/или фото/видео:"
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
