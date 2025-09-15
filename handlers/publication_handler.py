# -*- coding: utf-8 -*-
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from services.cooldown import CooldownService
from services.hashtags import HashtagService
from services.filter_service import FilterService
from models import User, Post, PostStatus
from sqlalchemy import select
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def handle_publication_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle publication callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    
    if action == "cat":
        # Subcategory selected
        subcategory = data[2] if len(data) > 2 else None
        await start_post_creation(update, context, subcategory)
    elif action == "preview":
        await show_preview(update, context)
    elif action == "send":
        await send_to_moderation(update, context)
    elif action == "edit":
        await edit_post(update, context)
    elif action == "cancel":
        await cancel_post_with_reason(update, context)
    elif action == "cancel_confirm":
        await cancel_post(update, context)
    elif action == "add_media":
        await request_media(update, context)
    elif action == "back":
        # Возврат к предпросмотру
        await show_preview(update, context)

async def start_post_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, subcategory: str):
    """Start creating a post with selected subcategory"""
    subcategory_names = {
        'work': '👷‍♀️ Работа',
        'rent': '🏠 Аренда',
        'buy': '🔻 Куплю',
        'sell': '🔺 Продам',
        'events': '🎉 События',
        'free': '📦 Отдам даром',
        'important': '🌪️ Важно',
        'other': '❔ Другое'
    }
    
    # Сохраняем данные поста
    context.user_data['post_data'] = {
        'category': '🗯️ Будапешт',
        'subcategory': subcategory_names.get(subcategory, '❔ Другое'),
        'anonymous': False
    }

    keyboard = [[InlineKeyboardButton("🔙 Вернуться", callback_data="menu:announcements")]]
    
    await update.callback_query.edit_message_text(
        f"🗯️ Будапешт → 🗣️ Объявления → {subcategory_names.get(subcategory)}\n\n"
        "📝 Отправьте текст вашего объявления и/или фото/видео:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['waiting_for'] = 'post_text'

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста от пользователя"""
    
    # Проверяем, есть ли медиа вместе с текстом
    has_media = update.message.photo or update.message.video or update.message.document
    
    # Если медиа и текст одновременно (caption)
    if has_media and update.message.caption:
        text = update.message.caption
        
        # Если ждём текст поста
        if context.user_data.get('waiting_for') == 'post_text':
            # Проверяем на запрещённые ссылки
            filter_service = FilterService()
            if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
                await handle_link_violation(update, context)
                return
            
            # Сохраняем текст
            if 'post_data' not in context.user_data:
                context.user_data['post_data'] = {}
            
            context.user_data['post_data']['text'] = text
            context.user_data['post_data']['media'] = []
            
            # Сохраняем медиа
            if update.message.photo:
                context.user_data['post_data']['media'].append({
                    'type': 'photo',
                    'file_id': update.message.photo[-1].file_id
                })
            elif update.message.video:
                context.user_data['post_data']['media'].append({
                    'type': 'video',
                    'file_id': update.message.video.file_id
                })
            elif update.message.document:
                context.user_data['post_data']['media'].append({
                    'type': 'document',
                    'file_id': update.message.document.file_id
                })
            
            keyboard = [
                [
                    InlineKeyboardButton("🖼️ Добавить еще медиа", callback_data="pub:add_media"),
                    InlineKeyboardButton("👀 Предпросмотр", callback_data="pub:preview")
                ],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu:back")]
            ]
            
            await update.message.reply_text(
                "🎯 Супер! Текст и медиа сохранены!\n\n"
                "🎨 Хотите добавить еще медиа или перейти к предпросмотру?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            context.user_data['waiting_for'] = None
            return
    
    # Если только текст без медиа
    if 'waiting_for' not in context.user_data:
        return
    
    waiting_for = context.user_data['waiting_for']
    text = update.message.text if update.message.text else update.message.caption
    
    if not text:
        return
    
    logger.info(f"Text input received. waiting_for: {waiting_for}")
    
    if waiting_for == 'post_text':
        # Check for links
        filter_service = FilterService()
        if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
            await handle_link_violation(update, context)
            return
        
        if 'post_data' not in context.user_data:
            await update.message.reply_text(
                "🤔 Упс! Данные поста потерялись.\n"
                "Давайте начнем заново с /start"
            )
            context.user_data.pop('waiting_for', None)
            return
        
        context.user_data['post_data']['text'] = text
        context.user_data['post_data']['media'] = []
        
        keyboard = [
            [
                InlineKeyboardButton("🎬 Добавить медиа", callback_data="pub:add_media"),
                InlineKeyboardButton("👀 Предпросмотр", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            "🎉 Отлично! Текст сохранен!\n\n"
            "🎭 Хотите добавить фото/видео или сразу перейти к предпросмотру?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data['waiting_for'] = None
        
    elif waiting_for == 'cancel_reason':
        context.user_data['cancel_reason'] = text
        await cancel_post(update, context)
        
    elif waiting_for.startswith('piar_'):
        from handlers.piar_handler import handle_piar_text
        field = waiting_for.replace('piar_', '')
        await handle_piar_text(update, context, field, text)

async def handle_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media input from user"""
    # Проверяем, что пользователь в процессе добавления медиа
    if 'post_data' not in context.user_data:
        return
    
    # Принимаем медиа даже если waiting_for не установлен
    if 'media' not in context.user_data['post_data']:
        context.user_data['post_data']['media'] = []
    
    media_added = False
    
    if update.message.photo:
        # Get highest quality photo
        context.user_data['post_data']['media'].append({
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        })
        media_added = True
        logger.info(f"Added photo: {update.message.photo[-1].file_id}")
        
    elif update.message.video:
        context.user_data['post_data']['media'].append({
            'type': 'video',
            'file_id': update.message.video.file_id
        })
        media_added = True
        logger.info(f"Added video: {update.message.video.file_id}")
        
    elif update.message.document:
        context.user_data['post_data']['media'].append({
            'type': 'document',
            'file_id': update.message.document.file_id
        })
        media_added = True
        logger.info(f"Added document: {update.message.document.file_id}")
    
    if media_added:
        total_media = len(context.user_data['post_data']['media'])
        
        keyboard = [
            [
                InlineKeyboardButton(f"➕ Добавить еще", callback_data="pub:add_media"),
                InlineKeyboardButton("🔍 Предпросмотр", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            f"🔥 Медиа добавлено! (Всего: {total_media})\n\n"
            "🎪 Добавить еще или перейти к предпросмотру?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data['waiting_for'] = None

async def request_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request media from user"""
    context.user_data['waiting_for'] = 'post_media'
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "📸 Отправьте фото, видео или документ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show post preview with media"""
    if 'post_data' not in context.user_data:
        await update.callback_query.edit_message_text("😵 Ошибка: данные поста не найдены")
        return
    
    post_data = context.user_data['post_data']
    
    # Generate hashtags
    hashtag_service = HashtagService()
    hashtags = hashtag_service.generate_hashtags(
        post_data.get('category'),
        post_data.get('subcategory')
    )
    
    # Build preview text
    preview_text = f"{post_data.get('text', '')}\n\n"
    preview_text += f"{' '.join(hashtags)}\n\n"
    preview_text += Config.DEFAULT_SIGNATURE
    
    keyboard = [
        [
            InlineKeyboardButton("🚀 Отправить на модерацию", callback_data="pub:send"),
            InlineKeyboardButton("✏️ Редактировать", callback_data="pub:edit")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="pub:cancel")]
    ]
    
    # Send media preview first if exists
    media = post_data.get('media', [])
    if media:
        try:
            for media_item in media[:5]:  # Показываем до 5 медиа файлов
                if media_item.get('type') == 'photo':
                    await update.effective_message.reply_photo(
                        photo=media_item['file_id'],
                        caption="📷 Прикрепленное фото" if len(media) == 1 else None
                    )
                elif media_item.get('type') == 'video':
                    await update.effective_message.reply_video(
                        video=media_item['file_id'],
                        caption="🎥 Прикрепленное видео" if len(media) == 1 else None
                    )
                elif media_item.get('type') == 'document':
                    await update.effective_message.reply_document(
                        document=media_item['file_id'],
                        caption="📄 Прикрепленный документ" if len(media) == 1 else None
                    )
        except Exception as e:
            logger.error(f"Error showing media preview: {e}")
    
    # Send preview text
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"🎭 *Предпросмотр поста:*\n\n{preview_text}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.effective_message.reply_text(
                f"🎭 *Предпросмотр поста:*\n\n{preview_text}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    except:
        await update.effective_message.reply_text(
            f"🎭 *Предпросмотр поста:*\n\n{preview_text}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def send_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send post to moderation with safe DB handling"""
    user_id = update.effective_user.id
    
    try:
        # Check cooldown
        from services.cooldown import CooldownService
        cooldown_service = CooldownService()
        can_post, remaining = await cooldown_service.can_post(user_id)
        
        if not can_post:
            minutes = remaining // 60
            hours = minutes // 60
            mins = minutes % 60
            
            if hours > 0:
                time_str = f"{hours} ч. {mins} мин."
            else:
                time_str = f"{minutes} мин."
                
            await update.callback_query.answer(
                f"⏰ Подождите еще {time_str} перед следующей публикацией",
                show_alert=True
            )
            return
    except Exception as e:
        logger.warning(f"Cooldown check failed: {e}")
        # Продолжаем без проверки кулдауна
    
    post_data = context.user_data.get('post_data', {})
    
    # Save to database with error handling
    try:
        from services.db import db
        from models import User, Post, PostStatus
        from services.hashtags import HashtagService
        from sqlalchemy import select
        
        async with db.get_session() as session:
            # Get user
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await update.callback_query.answer("❌ Ошибка: пользователь не найден", show_alert=True)
                return
            
            # Create post
            hashtag_service = HashtagService()
            hashtags = hashtag_service.generate_hashtags(
                post_data.get('category'),
                post_data.get('subcategory')
            )
            
            post = Post(
                user_id=user_id,
                category=post_data.get('category'),
                subcategory=post_data.get('subcategory'),
                text=post_data.get('text', ''),
                media=post_data.get('media', []),
                hashtags=hashtags,
                anonymous=post_data.get('anonymous', False),
                status=PostStatus.PENDING
            )
            
            session.add(post)
            await session.commit()
            
            # Send to moderation group
            await send_to_moderation_group(update, context, post, user)
            
            # Update cooldown
            try:
                from services.cooldown import CooldownService
                cooldown_service = CooldownService()
                await cooldown_service.update_cooldown(user_id)
            except Exception as e:
                logger.warning(f"Cooldown update failed: {e}")
            
            # Clear user data
            context.user_data.pop('post_data', None)
            context.user_data.pop('waiting_for', None)
            
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
                [InlineKeyboardButton("📺 Топ канал Будапешта", url="https://t.me/snghu")],
                [InlineKeyboardButton("📚 Каталог услуг", url="https://t.me/trixvault")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu:back")]
            ]
            
            # =========================
            # Сообщение пользователю после отправки на модерацию
            # =========================
            await update.callback_query.edit_message_text(
                f"🤳 *Поздравляю, ваша публикация успешно отправлена*\n\n"
                f"📝 Этот шедевр уже в руках модераторов!\n"
                f"📬 После проверки и коррекции вы будете уведомлены о результате\n\n"
                f"😴 Следующий пост можно отправить через {next_post_time}\n\n"
                f"🧑‍✈️ *Загляните в наши каналы, там каждый найдет то что ищет :*",
                reply_markup=InlineKeyboardMarkup(success_keyboard),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in send_to_moderation: {e}")
        await update.callback_query.edit_message_text(
            "❌ Произошла ошибка при отправке поста.\n"
            "Попробуйте позже или обратитесь к администратору."
        )

async def send_to_moderation_group(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   post: Post, user: User):
    """Send post to moderation group with media"""
    bot = context.bot
    
    # =========================
    # Сообщение для модерации
    # =========================
    mod_text = (
        f"🚨 *Заявочка залетела*\n\n"
        f"💌 от: @{user.username or 'no_username'} (ID: {user.id})\n"
        f"💥 Примерно в: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📚 Из раздела: {post.category}"
    )
    
    if post.subcategory:
        mod_text += f" → {post.subcategory}"
    
    if post.anonymous:
        mod_text += "\n🎭 *Анонимно*"
    
    # Добавляем информацию о медиа
    if post.media and len(post.media) > 0:
        mod_text += f"\n📎 Медиа: {len(post.media)} файл(ов)"
    
    mod_text += f"\n\n📝 Текст:\n{post.text}\n\n"
    mod_text += f"🏷 Хештеги: {' '.join(post.hashtags)}"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Опубликовать", callback_data=f"mod:approve:{post.id}"),
            InlineKeyboardButton("✏️ Редактировать", callback_data=f"mod:edit:{post.id}")
        ],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")]
    ]
    
    try:
        # Сначала отправляем медиа, если есть - ИСПРАВЛЕНО
        media_messages = []
        if post.media and len(post.media) > 0:
            # Отправляем каждое медиа отдельно для лучшего отображения
            for i, media_item in enumerate(post.media):
                try:
                    if media_item.get('type') == 'photo':
                        msg = await bot.send_photo(
                            chat_id=Config.MODERATION_GROUP_ID,
                            photo=media_item['file_id'],
                            caption=f"📷 Медиа {i+1}/{len(post.media)}"
                        )
                        media_messages.append(msg.message_id)
                    elif media_item.get('type') == 'video':
                        msg = await bot.send_video(
                            chat_id=Config.MODERATION_GROUP_ID,
                            video=media_item['file_id'],
                            caption=f"🎥 Медиа {i+1}/{len(post.media)}"
                        )
                        media_messages.append(msg.message_id)
                    elif media_item.get('type') == 'document':
                        msg = await bot.send_document(
                            chat_id=Config.MODERATION_GROUP_ID,
                            document=media_item['file_id'],
                            caption=f"📄 Медиа {i+1}/{len(post.media)}"
                        )
                        media_messages.append(msg.message_id)
                except Exception as e:
                    logger.error(f"Error sending media {i+1}: {e}")
        
        # Затем отправляем текст с кнопками
        message = await bot.send_message(
            chat_id=Config.MODERATION_GROUP_ID,
            text=mod_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Сохраняем ID сообщения
        async with db.get_session() as session:
            await session.execute(
                f"UPDATE posts SET moderation_message_id = {message.message_id} WHERE id = {post.id}"
            )
            await session.commit()
        
        logger.info(f"Post {post.id} sent to moderation with {len(media_messages)} media files")
            
    except Exception as e:
        logger.error(f"Error sending to moderation group: {e}")
        # Отправляем подробное сообщение об ошибке
        error_details = str(e)[:200] + "..." if len(str(e)) > 200 else str(e)
        
        await bot.send_message(
            chat_id=user.id,
            text=(
                f"⚠️ Ошибка отправки в группу модерации\n\n"
                f"Детали ошибки:\n`{error_details}`\n\n"
                f"Проверьте:\n"
                f"• Бот добавлен в группу модерации?\n"
                f"• Бот является администратором группы?\n"
                f"• ID группы: {Config.MODERATION_GROUP_ID}\n\n"
                f"Обратитесь к администратору."
            ),
            parse_mode='Markdown'
        )

async def cancel_post_with_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for cancellation reason"""
    keyboard = [
        [InlineKeyboardButton("🤷 Передумал", callback_data="pub:cancel_confirm")],
        [InlineKeyboardButton("✏️ Ошибка в тексте", callback_data="pub:cancel_confirm")],
        [InlineKeyboardButton("🔙 Назад", callback_data="pub:preview")]
    ]
    
    await update.callback_query.edit_message_text(
        "🤔 Укажите причину отмены:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_link_violation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle link violation"""
    await update.message.reply_text(
        "🚫 Обнаружена запрещенная ссылка!\n"
        "Ссылки запрещены в публикациях."
    )
    context.user_data.pop('waiting_for', None)

async def edit_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit post before sending"""
    context.user_data['waiting_for'] = 'post_text'
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "✏️ Отправьте новый текст для поста:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel post creation"""
    context.user_data.pop('post_data', None)
    context.user_data.pop('waiting_for', None)
    context.user_data.pop('cancel_reason', None)
    
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)
