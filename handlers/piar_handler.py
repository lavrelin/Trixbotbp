from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from models import User, Post  # ИСПРАВЛЕНО: добавлен импорт моделей
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# Piar form steps - ИСПРАВЛЕНО: теперь 8 шагов
PIAR_STEPS = [
    ('name', 'Имя', 'Привет, чтобы попасть в наш каталог услуг заполните маленькую анкету о себе, укажите своё имя, псевдоним тд.:'),
    ('profession', 'Профессия', 'Какие услуги вы предоставляте:'),
    ('districts', 'Районы', 'В каких районах вы работаете? (до 3, через запятую):'),
    ('phone', 'Телефон', 'Добавьте номер телефона если используете в работе с клиентами (или отправьте "-" чтобы перейти дальше):'),
    ('instagram', 'Instagram', 'Введите ваш Instagram (разрешено ссылку, @, или просто username, или напишите "-" чтобы пропустить):'),
    ('telegram', 'Telegram', 'Введите ваш Telegram (также разрешается ссылка, @, или username,  "-" - чтобы не указывать):'),
    ('price', 'Цена', 'Цена за услуги, прайс лист если он есть:'),
    ('description', 'Описание', 'Сформулируйте описание ваших услуг, добавьте медиафайлы, используйте эмодзи, абзацы. Чем лучше описание - тем больше оно привлекает новых клиентов  :')
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
    elif action == "next_photo":
        await show_piar_preview(update, context)
    elif action == "back":
        await go_back_step(update, context)

async def handle_piar_text(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           field: str, value: str):
    """Handle text input for piar form"""
    if 'piar_data' not in context.user_data:
        context.user_data['piar_data'] = {}
    
    # Сохраняем текущий шаг для возможности возврата
    context.user_data['piar_step'] = field
    
    # Validate and save field - УБРАНА ПРОВЕРКА ССЫЛОК
    if field == 'name':
        if len(value) > 100:
            await update.message.reply_text("🛣️ Укажите как к вам обращаться не сломав язык (макс. 100 символов)")
            return
        context.user_data['piar_data']['name'] = value
        next_step = 'profession'
        
    elif field == 'profession':
        if len(value) > 100:
            await update.message.reply_text("😳 Чем это вы таким занимаетесь? Слишком много текста (макс. 100 символов)")
            return
        context.user_data['piar_data']['profession'] = value
        next_step = 'districts'
        
    elif field == 'districts':
        districts = [d.strip() for d in value.split(',')][:3]
        if not districts:
            await update.message.reply_text("🏢 Нужно указать хотя бы один район")
            return
        context.user_data['piar_data']['districts'] = districts
        next_step = 'phone'
        
    elif field == 'phone':
        if value != '-':
            # Простая валидация телефона - ССЫЛКИ РАЗРЕШЕНЫ
            phone = value.strip()
            if len(phone) < 7:
                await update.message.reply_text("📵 Абонент не доступен или номер не действителен. Укажите еще раз.")
                return
            context.user_data['piar_data']['phone'] = phone
        else:
            context.user_data['piar_data']['phone'] = None
        next_step = 'instagram'
        
    elif field == 'instagram':
        if value != '-':
            # ССЫЛКИ РАЗРЕШЕНЫ в Instagram
            instagram = value.strip()
            if instagram.startswith('@'):
                instagram = instagram[1:]
            context.user_data['piar_data']['instagram'] = instagram if instagram else None
        else:
            context.user_data['piar_data']['instagram'] = None
        next_step = 'telegram'
        
    elif field == 'telegram':
        if value != '-':
            # ССЫЛКИ РАЗРЕШЕНЫ в Telegram
            telegram = value.strip()
            if not telegram.startswith('@') and not telegram.startswith('https://t.me/'):
                telegram = f"@{telegram}"
            context.user_data['piar_data']['telegram'] = telegram
        else:
            context.user_data['piar_data']['telegram'] = None
        next_step = 'price'
        
    elif field == 'price':
        if len(value) > 100:
            await update.message.reply_text("🙇🏿‍♀️ Неприлично дорого (макс. 100 символов)")
            return
        context.user_data['piar_data']['price'] = value
        next_step = 'description'
        
    elif field == 'description':
        if len(value) > 1000:
            await update.message.reply_text("💻 Длинное описание это хорошо, но ненастолько же... (макс. 1000 символов)")
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
            [InlineKeyboardButton("🏃‍♂️‍➡️ Дальше", callback_data="piar:skip_photo")],
            [InlineKeyboardButton("🏃‍♂️ Вернуться", callback_data="piar:back")],
            [InlineKeyboardButton("🤷‍♂️ Отмена", callback_data="piar:cancel")]
        ]
        
        await update.message.reply_text(
            "📷 *Шаг 8 - Фотографии*\n\n"
            "Вы можете отправить до 3 фотографий или видео для вашего объявления\n"
            "или нажмите 'Дальше'",
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
            keyboard.append([InlineKeyboardButton("👨‍💻 Изменить предыдущий шаг", callback_data="piar:back")])
        keyboard.append([InlineKeyboardButton("🤷🏻‍♀️ Вернуться в главное меню", callback_data="piar:cancel")])
        
        await update.message.reply_text(
            f"🧏 *Заполнение данных в каталог услуг*\n\n"
            f"💥Выполнено {step_num} из 8\n"
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
            f"💿 Не вмещается, максимум {Config.MAX_PHOTOS_PIAR} фотографии"
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
        
        keyboard = []
        
        if remaining > 0:
            keyboard.append([
                InlineKeyboardButton(f"📸 Добавить еще ({remaining})", 
                                   callback_data="piar:add_photo")
            ])
        
        # Всегда показываем кнопку "Дальше"
        keyboard.append([
            InlineKeyboardButton("🏃‍♂️‍➡️ Продолжить", callback_data="piar:next_photo")
        ])
        
        keyboard.append([InlineKeyboardButton("🔙 Вернуться назад", callback_data="piar:back")])
        keyboard.append([InlineKeyboardButton("👹 Отмена", callback_data="piar:cancel")])
        
        await update.message.reply_text(
            f"📶 Медиа файлы получено! (Всего: {len(photos)})\n\n"
            f"➡️ Можно добавить еще или перейдём к предпросмотру?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def request_piar_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request more photos"""
    context.user_data['waiting_for'] = 'piar_photo'
    
    photos_count = len(context.user_data.get('piar_data', {}).get('photos', []))
    remaining = Config.MAX_PHOTOS_PIAR - photos_count
    
    keyboard = [
        [InlineKeyboardButton("▶️ Дальше", callback_data="piar:next_photo")],
        [InlineKeyboardButton("◀️ Назад", callback_data="piar:back")],
        [InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")]
    ]
    
    await update.callback_query.edit_message_text(
        f"📷 Отправьте еще фото/видео (осталось: {remaining}):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_piar_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show piar preview with media first, then buttons"""
    if 'piar_data' not in context.user_data:
        await update.callback_query.edit_message_text("❌ Данные не найдены")
        return
    
    data = context.user_data['piar_data']
    
    # Build preview text
    text = "💼 *Предложить услугу - Предпросмотр*\n\n"
    text += f"👤 *Имя:* {data.get('name')}\n"
    text += f"💼 *Профессия:* {data.get('profession')}\n"
    text += f"📍 *Районы:* {', '.join(data.get('districts', []))}\n"
    
    if data.get('phone'):
        text += f"📞 *Телефон:* {data.get('phone')}\n"
    
    # Новая обработка контактов
    contacts = []
    if data.get('instagram'):
        contacts.append(f"📷 Instagram: @{data.get('instagram')}")
    if data.get('telegram'):
        contacts.append(f"📱 Telegram: {data.get('telegram')}")
    
    if contacts:
        text += f"📞 *Контакты:*\n{chr(10).join(contacts)}\n"
    
    text += f"💰 *Цена:* {data.get('price')}\n\n"
    text += f"📝 *Описание:*\n{data.get('description')}\n\n"
    
    if data.get('photos'):
        text += f"📷 Медиа файлов: {len(data['photos'])}\n\n"
    
    text += "#Услуги #БизнесБудапешт\n\n"
    text += Config.DEFAULT_SIGNATURE
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Отправить на модерацию", callback_data="piar:send"),
            InlineKeyboardButton("✏️ Изменить", callback_data="piar:edit")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="piar:cancel")]
    ]
    
    # ИСПРАВЛЕНО: Сначала удаляем старое сообщение с кнопками
    try:
        if update.callback_query:
            await update.callback_query.delete_message()
    except:
        pass
    
    # ИСПРАВЛЕНО: Сначала показываем медиа, если есть
    if data.get('media'):
        try:
            for i, media_item in enumerate(data['media'][:3]):  # Показываем до 3 медиа
                caption = None
                if i == 0:  # Первое медиа с подписью
                    caption = f"📷 Медиа файлы ({len(data['media'])} шт.)"
                
                if media_item.get('type') == 'photo':
                    await update.effective_message.reply_photo(
                        photo=media_item['file_id'],
                        caption=caption
                    )
                elif media_item.get('type') == 'video':
                    await update.effective_message.reply_video(
                        video=media_item['file_id'],
                        caption=caption
                    )
        except Exception as e:
            logger.error(f"Error showing piar media preview: {e}")
    
    # ИСПРАВЛЕНО: Потом показываем текст с кнопками (последнее сообщение)
    try:
        await update.effective_message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error showing piar preview: {e}")
        await update.effective_message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def send_piar_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send piar to moderation with safe DB handling"""
    user_id = update.effective_user.id
    data = context.user_data.get('piar_data', {})
    
    try:
        async with db.get_session() as session:
            # Get user
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await update.callback_query.edit_message_text(
                    "🚨 Ошибка при отправке. Попробуйте еще раз /start При повторной неудаче обратитесь к администратору @trixilvebot 💥"
                )
                return
            
            # Create piar post without new fields first
            post_data = {
                'user_id': user_id,
                'category': '💼 Услуги',
                'text': data.get('description', ''),
                'hashtags': ['#Услуги', '#БизнесБудапешт'],
                'is_piar': True,
                'piar_name': data.get('name'),
                'piar_profession': data.get('profession'),
                'piar_districts': data.get('districts'),
                'piar_phone': data.get('phone'),
                'piar_price': data.get('price'),
                'media': data.get('media', [])
            }
            
            # Safely add new fields if they exist in DB
            try:
                post_data['piar_instagram'] = data.get('instagram')
                post_data['piar_telegram'] = data.get('telegram')
            except Exception as field_error:
                logger.warning(f"New piar fields not available: {field_error}")
                # Continue without new fields
            
            post = Post(**post_data)
            session.add(post)
            await session.commit()
            
            # Send to moderation group
            await send_piar_to_mod_group_safe(update, context, post, user, data)
            
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
            
            # Show success message with channel promotion
            success_keyboard = [
                [InlineKeyboardButton("📺 Наш канал", url="https://t.me/snghu")],
                [InlineKeyboardButton("📚 Каталог услуг", url="https://t.me/trixvault")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu:back")]
            ]
            
            await update.callback_query.edit_message_text(
                f"✅ *Отправлено на модерацию!*\n\n"
                f"Ваша заявка на услугу будет рассмотрена модераторами.\n\n"
                f"⏰ Следующую заявку можно отправить через {next_post_time}\n\n"
                f"🔔 *Не забудьте подписаться на наши каналы:*",
                reply_markup=InlineKeyboardMarkup(success_keyboard),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in send_piar_to_moderation: {e}")
        await update.callback_query.edit_message_text(
            "🚨 Ошибка при отправке. Попробуйте еще раз /start При повторной неудаче обратитесь к администратору @trixilvebot 💥"
        )

async def send_piar_to_mod_group_safe(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                     post: Post, user: User, data: dict):
    """Send piar to moderation group with safe text handling"""
    bot = context.bot
    
    def escape_markdown(text):
        """Экранирует специальные символы"""
        if not text:
            return text
        text = str(text)
        text = text.replace('*', '\\*')
        text = text.replace('_', '\\_')
        text = text.replace('[', '\\[')
        text = text.replace(']', '\\]')
        text = text.replace('`', '\\`')
        return text
    
    # Безопасное сообщение без markdown
    username = user.username or 'no_username'
    
    text = (
        f"💼 Новая заявка - Услуга\n\n"
        f"👤 Автор: @{username} (ID: {user.id})\n"
        f"📅 Дата: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"Данные:\n"
        f"👤 Имя: {escape_markdown(data.get('name', ''))}\n"
        f"💼 Профессия: {escape_markdown(data.get('profession', ''))}\n"
        f"📍 Районы: {escape_markdown(', '.join(data.get('districts', [])))}\n"
    )
    
    if data.get('phone'):
        text += f"📞 Телефон: {escape_markdown(data.get('phone'))}\n"
    
    # Новая обработка контактов для модерации
    contacts = []
    if data.get('instagram'):
        contacts.append(f"📷 Instagram: @{escape_markdown(data.get('instagram'))}")
    if data.get('telegram'):
        contacts.append(f"📱 Telegram: {escape_markdown(data.get('telegram'))}")
    
    if contacts:
        text += f"📞 Контакты:\n{chr(10).join(contacts)}\n"
    
    text += f"💰 Цена: {escape_markdown(data.get('price', ''))}\n"
    
    # Добавляем информацию о медиа
    if data.get('media') and len(data['media']) > 0:
        text += f"📎 Медиа: {len(data['media'])} файл(ов)\n"
    
    # Безопасно добавляем описание
    description = data.get('description', '')[:300]
    if len(data.get('description', '')) > 300:
        description += "..."
    text += f"\n📝 Описание:\n{escape_markdown(description)}"
    
    keyboard = [
        [InlineKeyboardButton("💬 Написать автору", url=f"tg://user?id={user.id}")],
        [
            InlineKeyboardButton("✅ Опубликовать", callback_data=f"mod:approve:{post.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")
        ]
    ]
    
    try:
        # Проверяем доступность группы модерации
        try:
            await bot.get_chat(Config.MODERATION_GROUP_ID)
        except Exception as e:
            logger.error(f"Cannot access moderation group {Config.MODERATION_GROUP_ID}: {e}")
            await bot.send_message(
                chat_id=user.id,
                text="⚠️ Группа модерации недоступна. Обратитесь к администратору."
            )
            return

        # Отправляем медиа с улучшенной обработкой ошибок
        media_sent = []
        if data.get('media') and len(data['media']) > 0:
            for i, media_item in enumerate(data['media']):
                try:
                    if media_item.get('type') == 'photo':
                        msg = await bot.send_photo(
                            chat_id=Config.MODERATION_GROUP_ID,
                            photo=media_item['file_id'],
                            caption=f"📷 Медиа {i+1}/{len(data['media'])}"
                        )
                        media_sent.append(msg.message_id)
                    elif media_item.get('type') == 'video':
                        msg = await bot.send_video(
                            chat_id=Config.MODERATION_GROUP_ID,
                            video=media_item['file_id'],
                            caption=f"🎥 Медиа {i+1}/{len(data['media'])}"
                        )
                        media_sent.append(msg.message_id)
                except Exception as media_error:
                    logger.error(f"Error sending piar media {i+1}: {media_error}")
                    continue
        
        # Отправляем основное сообщение с кнопками БЕЗ parse_mode
        try:
            message = await bot.send_message(
                chat_id=Config.MODERATION_GROUP_ID,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard)
                # УБРАН parse_mode='Markdown'
            )
            
            logger.info(f"Piar sent to moderation successfully. Post ID: {post.id}")
            
            # Сохраняем ID сообщения безопасно
            try:
                from sqlalchemy import text as sql_text
                async with db.get_session() as session:
                    await session.execute(
                        sql_text("UPDATE posts SET moderation_message_id = :msg_id WHERE id = :post_id"),
                        {"msg_id": message.message_id, "post_id": str(post.id)}
                    )
                    await session.commit()
            except Exception as save_error:
                logger.error(f"Error saving moderation_message_id for piar: {save_error}")
            
        except Exception as text_error:
            logger.error(f"Error sending piar text message: {text_error}")
            raise text_error
            
    except Exception as e:
        logger.error(f"Error sending piar to moderation: {e}")
        await bot.send_message(
            chat_id=user.id,
            text="⚠️ Ошибка отправки в группу модерации. Обратитесь к администратору."
        )

async def go_back_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to previous step in piar form"""
    current_step = context.user_data.get('piar_step')
    
    if not current_step:
        await restart_piar_form(update, context)
        return
    
    # Определяем предыдущий шаг
    step_order = ['name', 'profession', 'districts', 'phone', 'instagram', 'telegram', 'price', 'description']
    
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
                        f"💼 *Предложить услугу*\n\n"
                        f"Шаг {step_num} из 8\n"
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
        "💼 *Предложить услугу*\n\n"
        "Шаг 1 из 8\n"
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
