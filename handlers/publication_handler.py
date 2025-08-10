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
        await cancel_post(update, context)
    elif action == "add_media":
        await request_media(update, context)

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
    
    context.user_data['post_data'] = {
        'category': '🗯️ Будапешт',
        'subcategory': subcategory_names.get(subcategory, '❔ Другое'),
        'anonymous': False
    }
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="menu:back")]]
    
    await update.callback_query.edit_message_text(
        f"🗯️ Будапешт → 🗣️ Объявления → {subcategory_names.get(subcategory)}\n\n"
        "Отправьте текст вашего объявления и/или фото/видео:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['waiting_for'] = 'post_text'

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input from user"""
    # Логируем для отладки
    logger.info(f"Text input received. waiting_for: {context.user_data.get('waiting_for')}")
    logger.info(f"User data: {context.user_data}")
    
    if 'waiting_for' not in context.user_data:
        # Если нет состояния ожидания, игнорируем
        return
    
    waiting_for = context.user_data['waiting_for']
    text = update.message.text
    
    # Handle different input types
    if waiting_for == 'post_text':
        # Check for links
        filter_service = FilterService()
        if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
            await handle_link_violation(update, context)
            return
        
        if 'post_data' not in context.user_data:
            await update.message.reply_text(
                "❌ Ошибка: данные поста не найдены.\n"
                "Пожалуйста, начните заново с /start"
            )
            context.user_data.pop('waiting_for', None)
            return
        
        context.user_data['post_data']['text'] = text
        context.user_data['post_data']['media'] = []
        
        # Ask for media or show preview
        keyboard = [
            [
                InlineKeyboardButton("📷 Добавить медиа", callback_data="pub:add_media"),
                InlineKeyboardButton("👁 Предпросмотр", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("❌ Отмена", callback_data="pub:cancel")]
        ]
        
        await update.message.reply_text(
            "✅ Текст сохранен!\n\n"
            "Хотите добавить фото/видео или сразу перейти к предпросмотру?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Очищаем состояние ожидания
        context.user_data['waiting_for'] = None
        
    elif waiting_for == 'piar_name':
        from handlers.piar_handler import handle_piar_text
        await handle_piar_text(update, context, 'name', text)
    elif waiting_for == 'piar_profession':
        from handlers.piar_handler import handle_piar_text
        await handle_piar_text(update, context, 'profession', text)
    elif waiting_for == 'piar_districts':
        from handlers.piar_handler import handle_piar_text
        await handle_piar_text(update, context, 'districts', text)
    elif waiting_for == 'piar_phone':
        from handlers.piar_handler import handle_piar_text
        await handle_piar_text(update, context, 'phone', text)
    elif waiting_for == 'piar_contacts':
        from handlers.piar_handler import handle_piar_text
        await handle_piar_text(update, context, 'contacts', text)
    elif waiting_for == 'piar_price':
        from handlers.piar_handler import handle_piar_text
        await handle_piar_text(update, context, 'price', text)
    elif waiting_for == 'piar_description':
        from handlers.piar_handler import handle_piar_text
        await handle_piar_text(update, context, 'description', text)
    else:
        logger.warning(f"Unknown waiting_for state: {waiting_for}")

async def handle_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media input from user"""
    if 'waiting_for' not in context.user_data or context.user_data['waiting_for'] != 'post_media':
        return
    
    if 'post_data' not in context.user_data:
        context.user_data['post_data'] = {'media': []}
    
    media = []
    
    if update.message.photo:
        # Get highest quality photo
        media.append({
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        })
    elif update.message.video:
        media.append({
            'type': 'video',
            'file_id': update.message.video.file_id
        })
    elif update.message.document:
        media.append({
            'type': 'document',
            'file_id': update.message.document.file_id
        })
    
    context.user_data['post_data']['media'].extend(media)
    
    keyboard = [
        [
            InlineKeyboardButton("📷 Добавить еще", callback_data="pub:add_media"),
            InlineKeyboardButton("👁 Предпросмотр", callback_data="pub:preview")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="pub:cancel")]
    ]
    
    await update.message.reply_text(
        f"✅ Медиа добавлено! (Всего: {len(context.user_data['post_data']['media'])})\n\n"
        "Добавить еще или перейти к предпросмотру?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    context.user_data['waiting_for'] = None

async def request_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request media from user"""
    context.user_data['waiting_for'] = 'post_media'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "📷 Отправьте фото, видео или документ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show post preview"""
    if 'post_data' not in context.user_data:
        await update.callback_query.edit_message_text("❌ Ошибка: данные поста не найдены")
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
            InlineKeyboardButton("✅ Отправить на модерацию", callback_data="pub:send"),
            InlineKeyboardButton("✏️ Редактировать", callback_data="pub:edit")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="pub:cancel")]
    ]
    
    # Send preview with media if exists
    if post_data.get('media'):
        media_group = []
        for i, media_item in enumerate(post_data['media'][:10]):  # Telegram limit
            if media_item['type'] == 'photo':
                media_group.append(InputMediaPhoto(
                    media=media_item['file_id'],
                    caption=preview_text if i == 0 else None
                ))
            elif media_item['type'] == 'video':
                media_group.append(InputMediaVideo(
                    media=media_item['file_id'],
                    caption=preview_text if i == 0 else None
                ))
        
        if media_group:
            await update.callback_query.message.reply_media_group(media_group)
            await update.callback_query.message.reply_text(
                "👆 *Предпросмотр вашего поста*\n\n"
                "Так будет выглядеть ваш пост после публикации.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    else:
        await update.callback_query.edit_message_text(
            f"👁 *Предпросмотр:*\n\n{preview_text}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def send_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send post to moderation"""
    user_id = update.effective_user.id
    
    # Check cooldown
    cooldown_service = CooldownService()
    can_post, remaining = await cooldown_service.can_post(user_id)
    
    if not can_post:
        minutes = remaining // 60
        await update.callback_query.answer(
            f"⏰ Подождите еще {minutes} минут перед следующей публикацией",
            show_alert=True
        )
        return
    
    post_data = context.user_data.get('post_data', {})
    
    # Save to database
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
        await cooldown_service.update_cooldown(user_id)
        
        # Clear user data
        context.user_data.pop('post_data', None)
        context.user_data.pop('waiting_for', None)
        
        await update.callback_query.edit_message_text(
            "✅ *Отправлено на модерацию!*\n\n"
            "Ваш пост будет проверен модераторами.\n"
            "Вы получите уведомление о результате модерации.",
            parse_mode='Markdown'
        )

async def send_to_moderation_group(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   post: Post, user: User):
    """Send post to moderation group"""
    bot = context.bot
    
    # Build moderation message
    mod_text = (
        f"📝 *Новая заявка на публикацию*\n\n"
        f"👤 Автор: @{user.username or 'no_username'} (ID: {user.id})\n"
        f"📅 Дата: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📂 Категория: {post.category}"
    )
    
    if post.subcategory:
        mod_text += f" → {post.subcategory}"
    
    if post.anonymous:
        mod_text += "\n🎭 *Анонимно*"
    
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
        # Send to moderation group
        if post.media:
            # Send with media
            media_group = []
            for i, media_item in enumerate(post.media[:10]):
                if media_item['type'] == 'photo':
                    media_group.append(InputMediaPhoto(
                        media=media_item['file_id'],
                        caption=mod_text if i == 0 else None,
                        parse_mode='Markdown'
                    ))
                elif media_item['type'] == 'video':
                    media_group.append(InputMediaVideo(
                        media=media_item['file_id'],
                        caption=mod_text if i == 0 else None,
                        parse_mode='Markdown'
                    ))
            
            if media_group:
                messages = await bot.send_media_group(
                    chat_id=Config.MODERATION_GROUP_ID,
                    media=media_group
                )
                await bot.send_message(
                    chat_id=Config.MODERATION_GROUP_ID,
                    text="Действия с постом:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await bot.send_message(
                chat_id=Config.MODERATION_GROUP_ID,
                text=mod_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error sending to moderation group: {e}")
        await update.callback_query.answer(
            "❌ Ошибка отправки на модерацию. Обратитесь к администратору.",
            show_alert=True
        )

async def handle_link_violation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle link violation"""
    await update.message.reply_text(
        "⚠️ Обнаружена запрещенная ссылка!\n"
        "Ссылки запрещены в публикациях."
    )
    context.user_data.pop('waiting_for', None)

async def edit_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit post before sending"""
    context.user_data['waiting_for'] = 'post_text'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "✏️ Отправьте новый текст для поста:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel post creation"""
    context.user_data.pop('post_data', None)
    context.user_data.pop('waiting_for', None)
    
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)
