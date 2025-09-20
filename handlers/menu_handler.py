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
        await start_category_post(update, context, "🗯️ Будапешт", "🔔 Новости")
    elif action == "overheard":
        await start_category_post(update, context, "🗯️ Будапешт", "🔕 Подслушано", anonymous=True)
    elif action == "complaints":
        await start_category_post(update, context, "🗯️ Будапешт", "👸🏼 Жалобы", anonymous=True)
    else:
        logger.warning(f"Unknown menu action: {action}")
        await query.answer("Функция в разработке", show_alert=True)

async def show_budapest_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Budapest category menu"""
    keyboard = [
        [InlineKeyboardButton("📣 Объявления", callback_data="menu:announcements")],
        [InlineKeyboardButton("🔔 Новости", callback_data="menu:news")],
        [InlineKeyboardButton("🔕 Подслушано (анонимно)", callback_data="menu:overheard")],
        [InlineKeyboardButton("👸🏼 Жалобы (анонимно)", callback_data="menu:complaints")],
        [InlineKeyboardButton("🙅‍♂️ Назад", callback_data="menu:write")]
    ]
    
    text = (
        "🙅‍♂️ *Пост в Будапешт*\n\n"
        "Выберите тип публикации:\n\n"
        "📣 *Объявления* - товары, услуги, поиски и предложения. \n"
        "🔔 *Новости* - новая актуальная информация\n"
        "🔕 *Подслушано* - анонимные истории, сплетни, ситуации\n"
        "👑 *Жалобы* - анонимные недовольства и проблемы\n"
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
            InlineKeyboardButton("🕵🏻‍♀️ Куплю", callback_data="pub:cat:buy"),
            InlineKeyboardButton("👷‍♀️ Работа", callback_data="pub:cat:work")
        ],
        [
            InlineKeyboardButton("🕵🏼 Отдам", callback_data="pub:cat:free"),
            InlineKeyboardButton("🏢 Аренда", callback_data="pub:cat:rent")
        ],
        [
            InlineKeyboardButton("🕵🏻‍♂️ Продам", callback_data="pub:cat:sell"),
            InlineKeyboardButton("🪙 Криптовалюта", callback_data="pub:cat:crypto")
        ],
        [
            InlineKeyboardButton("🫧 Ищу ", callback_data="pub:cat:other"),
            InlineKeyboardButton("⭐️ О себе", callback_data="pub:cat:events")
        ],
        [InlineKeyboardButton("🔑 Назад", callback_data="menu:budapest")]
    ]
    
    text = (
        "📣 *Объявления*\n\n"
        "Выберите подкатегорию:"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
async def start_piar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Services form (renamed from Piar)"""
    context.user_data['piar_data'] = {}
    context.user_data['waiting_for'] = 'piar_name'
    context.user_data['piar_step'] = 'name'
    
    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="menu:write")]]

    text = (
        "🪄 *Подайте заявку на добавление в каталог Будапешта и всей Венгрии.*\n"
        
        "🧲 *Цель каталога — сделать жизнь в Будапеште проще для каждого:*\n"
        "🧞• Мастерам — эффективнее находить клиентов,\n"
        "🧞‍♀️• Участникам — быстрее получать нужные услуги,\n"
        "🧞‍♂️• Сообществу — активно развиваться и расширяться.\n"
        "🧬*Важно:* участники каталога — это Ваши будущие клиенты и партнёры. Каждая деталь, которую Вы укажете в заявке, имеет значение. От Вашей внимательности и креативности зависит, насколько быстро и легко Вас смогут найти те, кому нужны именно Ваши услуги.\n\n"
        "После подачи Ваша заявка будет проверена и откорректирована модераторами.\n"
        " О результате Вы получите персональное уведомление.\n\n"
        "*Приступим к 1 из 8 шагу подачи заявки в Каталог Услуг:*\n\n"
        "💭 *Напишите своё имя, псевдоним, никнейм - как к Вам обращаться:*"
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
        "⚡️ *Актуальное*\n"
        "💡 *Подробнее:*\n"
        "Этот раздел предназначен для важных и срочных сообщений.\n"
        "Посты закрепляются в чате для общения и имеют ограниченный срок актуальности.\n\n"
        "🫧 *Примеры сообщений для этого раздела:*\n"
        "- Болит зуб — ищу стоматолога, который примет сегодня\n"
        "- Срочно нужен перевозчик по Будапешту\n"
        "- Требуются люди на подработку на завтра\n"
        "- Потерял паспорт на вокзале Келети, имя Триксов.Т.Т., 1986 года рождения\n"
        "- Требуются волонтёры на мероприятие сегодня\n"
        "- Район Келенфольд — учусь стричь, нужна практика, делаю стрижки бесплатно с 10:00 до 18:00\n"
        "🆘 *Связь с администрацией*\n"
        "Обратиться к нашей команде можно через этот раздел.\n"
        "⚠️ Указывайте, что сообщение предназначено для администрации❗️\n"
        "*P.S.* Все неадекватные вопросы, предложения и т.д. останутся без ответа.\n"
        "🚩 Пользователи, нарушающие правила, будут забанены.\n\n"
        "🛎️ *Заключение*\n"
        "👺 Отправляйте текст только после тщательного ознакомления с инструкцией.\n"
        "🔥 Публикуются исключительно *актуальные* и корректные сообщения❗️\n\n"
        "⚡️ *Введите свой текст ниже:*"
    )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
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
    
    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="menu:budapest")]]
    
    anon_text = " (анонимно)" if anonymous else ""
    
    text = (
        f"{category} → {subcategory}{anon_text}\n\n"
       "✏️ Отправьте текст вашей публикации. Добавьте фото или видео файлы.\n"
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
