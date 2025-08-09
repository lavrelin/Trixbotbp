from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from services.filter_service import FilterService
from models import User, Post
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# Piar form steps
PIAR_STEPS = [
    ('name', 'Имя', 'Введите ваше имя:'),
    ('profession', 'Профессия', 'Введите вашу профессию:'),
    ('districts', 'Районы', 'Введите районы (до 3, через запятую):'),
    ('phone', 'Телефон', 'Введите номер телефона (необязательно, отправьте "-" чтобы пропустить):'),
    ('contacts', 'Контакты', 'Введите контакты (Telegram или Instagram):'),
    ('price', 'Цена', 'Введите цену за услуги:'),
    ('description', 'Описание', 'Введите описание ваших услуг:')
]

async def handle_piar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle piar callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    
    if action == "preview":
        await show_piar_preview(update, context)
    elif action == "send":
        await send_piar_to_moderation(update, context)
    elif action == "edit":
        await restart_piar_form(update, context)
    elif action == "cancel":
        await cancel_piar(update, context)
    elif action == "add_photo":
        await request_piar_photo(update, context)

async def handle_piar_text(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           field: str, value: str):
    """Handle text input for piar form"""
    if 'piar_data' not in context.user_data:
        context.user_data['piar_data'] = {}
    
    filter_service = FilterService()
    
    # Validate and save field
    if field == 'name':
        if len(value) > 100:
            await update.message.reply_text("❌ Имя слишком длинное (макс. 100 символов)")
            return
        context.user_data['piar_data']['name'] = value
        next_step = 'profession'
        
    elif field == 'profession':
        if len(value) > 100:
            await update.message.reply_text("❌ Профессия слишком длинная (макс. 100 символов)")
            return
        context.user_data['piar_data']['profession'] = value
        next_step = 'districts'
        
    elif field == 'districts':
        districts = [d.strip() for d in value.split(',')][:3]
        if not districts:
            await update.message.reply_text("❌ Укажите хотя бы один район")
            return
        context.user_data['piar_data']['districts'] = districts
        next_step = 'phone'
        
    elif field == 'phone':
        if value != '-':
            if not filter_service.is_valid_phone(value):
                await update.message.reply_text("❌ Неверный формат телефона")
                return
            context.user_data['piar_data']['phone'] = value
        else:
            context.user_data['piar_data']['phone'] = None
        next_step = 'contacts'
        
    elif field == 'contacts':
        # Parse contacts (Telegram or Instagram)
        contacts = []
        for contact in value.split(','):
            contact = contact.strip()
            if contact.startswith('@'):
                if filter_service.is_valid_username(contact):
                    contacts.append(contact)
            elif 'instagram.com' in contact.lower() or contact.startswith('ig:'):
                contacts.append(contact)
            else:
                contacts.append(contact)
        
        if not contacts:
            await update.message.reply_text("❌ Укажите хотя бы один контакт")
            return
        
        context.user_data['piar_data']['contacts'] = contacts
        next_step = 'price'
        
    elif field == 'price':
        if len(value) > 100:
            await update.message.reply_text("❌ Цена слишком длинная (макс. 100 символов)")
            return
        context.user_data['piar_data']['price'] = value
        next_step = 'description'
        
    elif field == 'description':
        if len(value) > 1000:
            await update.message.reply_text("❌ Описание слишком длинное (макс. 1000 символов)")
            return
        context.user_data['piar_data']['description'] = value
        next_step = 'photos'
    
    else:
        return
    
    # Show next step or photo request
    if next_step == 'photos':
        context.user_data['piar_data']['photos'] = []
        context.user_data['waiting_for'] = 'piar_photo'
        
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data="piar:preview")],
            [InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")]
        ]
        
        await update.message.reply_text(
            "📷 *Фотографии*\n\n"
            "Отправьте до 3 фотографий для вашего объявления\n"
            "или нажмите 'Пропустить'",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        # Find next step info
        for i, (step_field, step_name, step_text) in enumerate(PIAR_STEPS):
            if step_field == next_step:
                step_num = i + 1
                break
        
        context.user_data['waiting_for'] = f'piar_{next_step}'
        
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")]]
        
        await update.message.reply_text(
            f"⭐️ *Пиар - Продвижение бизнеса*\n\n"
            f"Шаг {step_num} из 7\n"
            f"{step_text}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def handle_piar_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo input for piar"""
    if 'waiting_for' not in context.user_data or context.user_data['waiting_for'] != 'piar_photo':
        return
    
    if 'piar_data' not in context.user_data:
        return
    
    if 'photos' not in context.user_data['piar_data']:
        context.user_data['piar_data']['photos'] = []
    
    photos = context.user_data['piar_data']['photos']
    
    if len(photos) >= Config.MAX_PHOTOS_PIAR:
        await update.message.reply_text(
            f"❌ Максимум {Config.MAX_PHOTOS_PIAR} фотографии"
        )
        return
    
    if update.message.photo:
        photos.append(update.message.photo[-1].file_id)
        
        remaining = Config.MAX_PHOTOS_PIAR - len(photos)
        
        keyboard = [
            [InlineKeyboardButton("👁 Предпросмотр", callback_data="piar:preview")]
        ]
        
        if remaining > 0:
            keyboard.insert(0, [
                InlineKeyboardButton(f"📷 Добавить еще ({remaining})", 
                                   callback_data="piar:add_photo")
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")])
        
        await update.message.reply_text(
            f"✅ Фото добавлено! (Всего: {len(photos)})",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def request_piar_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request more photos"""
    context.user_data['waiting_for'] = 'piar_photo'
    
    photos_count = len(context.user_data.get('piar_data', {}).get('photos', []))
    remaining = Config.MAX_PHOTOS_PIAR - photos_count
    
    keyboard = [
        [InlineKeyboardButton("👁 Предпросмотр", callback_data="piar:preview")],
        [InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")]
    ]
    
    await update.callback_query.edit_message_text(
        f"📷 Отправьте еще фото (осталось: {remaining}):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_piar_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show piar preview"""
    if 'piar_data' not in context.user_data:
        await update.callback_query.edit_message_text("❌ Данные не найдены")
        return
    
    data = context.user_data['piar_data']
    
    # Build preview text
    text = "⭐️ *ПИАР - Предпросмотр*\n\n"
    text += f"👤 *Имя:* {data.get('name')}\n"
    text += f"💼 *Профессия:* {data.get('profession')}\n"
    text += f"📍 *Районы:* {', '.join(data.get('districts', []))}\n"
    
    if data.get('phone'):
        text += f"📞 *Телефон:* {data.get('phone')}\n"
    
    text += f"📱 *Контакты:* {', '.join(data.get('contacts', []))}\n"
    text += f"💰 *Цена:* {data.get('price')}\n\n"
    text += f"📝 *Описание:*\n{data.get('description')}\n\n"
    
    if data.get('photos'):
        text += f"📷 Фотографий: {len(data['photos'])}\n\n"
    
    text += "#Пиар #БизнесБудапешт\n\n"
    text += Config.DEFAULT_SIGNATURE
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Отправить на модерацию", callback_data="piar:send"),
            InlineKeyboardButton("✏️ Изменить", callback_data="piar:edit")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")]
    ]
    
    # Send photos if exist
    if data.get('photos'):
        for photo_id in data['photos']:
            await update.callback_query.message.reply_photo(photo_id)
    
    await update.callback_query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    if update.callback_query:
        await update.callback_query.delete_message()

async def send_piar_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send piar to moderation"""
    user_id = update.effective_user.id
    data = context.user_data.get('piar_data', {})
    
    async with db.get_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.callback_query.answer("❌ Ошибка: пользователь не найден", show_alert=True)
            return
        
        # Create piar post
        post = Post(
            user_id=user_id,
            category='⭐️ Пиар',
            text=data.get('description', ''),
            hashtags=['#Пиар', '#БизнесБудапешт'],
            is_piar=True,
            piar_name=data.get('name'),
            piar_profession=data.get('profession'),
            piar_districts=data.get('districts'),
            piar_phone=data.get('phone'),
            piar_contacts=data.get('contacts'),
            piar_price=data.get('price'),
            media=[{'type': 'photo', 'file_id': fid} for fid in data.get('photos', [])]
        )
        
        session.add(post)
        await session.commit()
        
        # Send to moderation group
        await send_piar_to_mod_group(update, context, post, user, data)
        
        # Clear user data
        context.user_data.pop('piar_data', None)
        context.user_data.pop('waiting_for', None)
        
        await update.callback_query.edit_message_text(
            "✅ *Отправлено на модерацию!*\n\n"
            "Ваша заявка на пиар будет рассмотрена модераторами.",
            parse_mode='Markdown'
        )

async def send_piar_to_mod_group(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 post: Post, user: User, data: dict):
    """Send piar to moderation group"""
    bot = context.bot
    
    text = (
        f"⭐️ *Новая заявка ПИАР*\n\n"
        f"👤 Автор: @{user.username or 'no_username'} (ID: {user.id})\n"
        f"📅 Дата: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"*Данные:*\n"
        f"👤 Имя: {data.get('name')}\n"
        f"💼 Профессия: {data.get('profession')}\n"
        f"📍 Районы: {', '.join(data.get('districts', []))}\n"
    )
    
    if data.get('phone'):
        text += f"📞 Телефон: {data.get('phone')}\n"
    
    text += (
        f"📱 Контакты: {', '.join(data.get('contacts', []))}\n"
        f"💰 Цена: {data.get('price')}\n\n"
        f"📝 Описание:\n{data.get('description')}"
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Ответить автору", url=f"tg://user?id={user.id}")]
    ]
    
    # Send to moderation group
    if data.get('photos'):
        for photo_id in data['photos']:
            await bot.send_photo(
                chat_id=Config.MODERATION_GROUP_ID,
                photo=photo_id
            )
    
    await bot.send_message(
        chat_id=Config.MODERATION_GROUP_ID,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def restart_piar_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart piar form from beginning"""
    context.user_data['piar_data'] = {}
    context.user_data['waiting_for'] = 'piar_name'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="menu:back")]]
    
    await update.callback_query.edit_message_text(
        "⭐️ *Пиар - Продвижение бизнеса*\n\n"
        "Шаг 1 из 7\n"
        "Введите ваше имя:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def cancel_piar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel piar creation"""
    context.user_data.pop('piar_data', None)
    context.user_data.pop('waiting_for', None)
    
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)