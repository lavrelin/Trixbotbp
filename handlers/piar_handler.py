from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
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
    elif action == "skip_photo":
        await show_piar_preview(update, context)
    elif action == "back":
        # Возврат на предыдущий шаг
        await go_back_step(update, context)

async def handle_piar_text(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           field: str, value: str):
    """Handle text input for piar form"""
    if 'piar_data' not in context.user_data:
        context.user_data['piar_data'] = {}
    
    filter_service = FilterService()
    
    # Сохраняем текущий шаг для возможности возврата
    context.user_data['piar_step'] = field
    
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
        context.user_data['piar_data']['media'] = []
        context.user_data['waiting_for'] = 'piar_photo'
        
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data="piar:skip_photo")],
            [InlineKeyboardButton("◀️ Назад", callback_data="piar:back")],
            [InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")]
        ]
        
        await update.message.reply_text(
            "📷 *Фотографии*\n\n"
            "Отправьте до 3 фотографий или видео для вашего объявления\n"
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
        
        # Добавляем кнопку "Назад" начиная со второго шага
        keyboard = []
        if step_num > 1:
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="piar:back")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")])
        
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
    
    if 'media' not in context.user_data['piar_data']:
        context.user_data['piar_data']['media'] = []
    
    photos = context.user_data['piar_data']['photos']
    media = context.user_data['piar_data']['media']
    
    if len(photos) >= Config.MAX_PHOTOS_PIAR:
        await update.message.reply_text(
            f"❌ Максимум {Config.MAX_PHOTOS_PIAR} фотографии"
        )
        return
    
    media_added = False
    if update.message.photo:
        photos.append(update.message.photo[-1].file_id)
        media.append({'type': 'photo', 'file_id': update.message.photo[-1].file_id})
        media_added = True
    elif update.message.video:
        photos.append(update.message.video.file_id)
        media.append({'type': 'video', 'file_id': update.message.video.file_id})
        media_added = True
    
    if media_added:
        remaining = Config.MAX_PHOTOS_PIAR - len(photos)
        
        keyboard = [
            [InlineKeyboardButton("👁 Предпросмотр", callback_data="piar:preview")]
        ]
        
        if remaining > 0:
            keyboard.insert(0, [
                InlineKeyboardButton(f"📷 Добавить еще ({remaining})", 
                                   callback_data="piar:add_photo")
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="piar:back")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")])
        
        await update.message.reply_text(
            f"✅ Медиа добавлено! (Всего: {len(photos)})",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def request_piar_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request more photos"""
    context.user_data['waiting_for'] = 'piar_photo'
    
    photos_count = len(context.user_data.get('piar_data', {}).get('photos', []))
    remaining = Config.MAX_PHOTOS_PIAR - photos_count
    
    keyboard = [
        [InlineKeyboardButton("👁 Предпросмотр", callback_data="piar:preview")],
        [InlineKeyboardButton("◀️ Назад", callback_data="piar:back")],
        [InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")]
    ]
    
    await update.callback_query.edit_message_text(
        f"📷 Отправьте еще фото/видео (осталось: {remaining}):",
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
        text += f"📷 Медиа файлов: {len(data['photos'])}\n\n"
    
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
            try:
                await update.callback_query.message.reply_photo(photo_id)
            except:
                pass
    
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except:
            await update.callback_query.message.reply_text(
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
            media=data.get('media', [])
        )
        
        session.add(post)
        await session.commit()
        
        # Send to moderation group
        await send_piar_to_mod_group(update, context, post, user, data)
        
        # Clear user data
        context.user_data.pop('piar_data', None)
        context.user_data.pop('waiting_for', None)
        context.user_data.pop('piar_step', None)
        
        # Calculate next post time
        cooldown_minutes = Config.COOLDOWN_SECONDS // 60
        hours = cooldown_minutes // 60
        mins = cooldown_minutes % 60
        
        if hours > 0:
            next_post_time = f"{hours} часа {mins} минут"
        else:
            next_post_time = f"{cooldown_minutes} минут"
        
        await update.callback_query.edit_message_text(
            f"✅ *Отправлено на модерацию!*\n\n"
            f"Ваша заявка на пиар будет рассмотрена модераторами.\n\n"
            f"⏰ Следующую заявку можно отправить через {next_post_time}",
            parse_mode='Markdown'
        )

async def send_piar_to_mod_group(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 post: Post, user: User, data: dict):
    """Send piar to moderation group with media"""
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
        f"💰 Цена: {data.get('price')}\n"
    )
    
    # Добавляем информацию о медиа
    if data.get('media') and len(data['media']) > 0:
        text += f"📎 Медиа: {len(data['media'])} файл(ов)\n"
    
    text += f"\n📝 Описание:\n{data.get('description')}"
    
    keyboard = [
        [InlineKeyboardButton("💬 Написать автору", url=f"tg://user?id={user.id}")],
        [
            InlineKeyboardButton("✅ Опубликовать", callback_data=f"mod:approve:{post.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")
        ]
    ]
    
    try:
        # Сначала отправляем все медиа по отдельности
        if data.get('media') and len(data['media']) > 0:
            for media_item in data['media']:
                try:
                    if media_item.get('type') == 'photo':
                        await bot.send_photo(
                            chat_id=Config.MODERATION_GROUP_ID,
                            photo=media_item['file_id']
                        )
                    elif media_item.get('type') == 'video':
                        await bot.send_video(
                            chat_id=Config.MODERATION_GROUP_ID,
                            video=media_item['file_id']
                        )
                except Exception as e:
                    logger.error(f"Error sending piar media: {e}")
        
        # Затем отправляем текст с кнопками
        await bot.send_message(
            chat_id=Config.MODERATION_GROUP_ID,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
            
    except Exception as e:
        logger.error(f"Error sending piar to moderation: {e}")
        await bot.send_message(
            chat_id=user.id,
            text="⚠️ Ошибка отправки в группу модерации.\nОбратитесь к администратору."
        )

async def go_back_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to previous step in piar form"""
    current_step = context.user_data.get('piar_step')
    
    if not current_step:
        await restart_piar_form(update, context)
        return
    
    # Определяем предыдущий шаг
    step_order = ['name', 'profession', 'districts', 'phone', 'contacts', 'price', 'description']
    
    try:
        current_index = step_order.index(current_step)
        if current_index > 0:
            prev_step = step_order[current_index - 1]
            
            # Находим информацию о предыдущем шаге
            for i, (step_field, step_name, step_text) in enumerate(PIAR_STEPS):
                if step_field == prev_step:
                    step_num = i + 1
                    
                    context.user_data['waiting_for'] = f'piar_{prev_step}'
                    context.user_data['piar_step'] = prev_step
                    
                    keyboard = []
                    if step_num > 1:
                        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="piar:back")])
                    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")])
                    
                    await update.callback_query.edit_message_text(
                        f"⭐️ *Пиар - Продвижение бизнеса*\n\n"
                        f"Шаг {step_num} из 7\n"
                        f"{step_text}",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                    break
        else:
            await restart_piar_form(update, context)
    except:
        await restart_piar_form(update, context)

async def restart_piar_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart piar form from beginning"""
    context.user_data['piar_data'] = {}
    context.user_data['waiting_for'] = 'piar_name'
    context.user_data['piar_step'] = 'name'
    
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
    context.user_data.pop('piar_step', None)
    
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)
