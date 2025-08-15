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
        # ÐÐ¾Ð·Ð²ÑÐ°Ñ Ðº Ð¿ÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÑ
        await show_preview(update, context)

async def start_post_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, subcategory: str):
    """Start creating a post with selected subcategory"""
    subcategory_names = {
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
        'category': 'ð¯ï¸ ÐÑÐ´Ð°Ð¿ÐµÑÑ',
        'subcategory': subcategory_names.get(subcategory, 'â ÐÑÑÐ³Ð¾Ðµ'),
        'anonymous': False
    }
    
    keyboard = [[InlineKeyboardButton("âï¸ ÐÐ°Ð·Ð°Ð´", callback_data="menu:announcements")]]
    
    await update.callback_query.edit_message_text(
        f"ð¯ï¸ ÐÑÐ´Ð°Ð¿ÐµÑÑ â ð£ï¸ ÐÐ±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ â {subcategory_names.get(subcategory)}\n\n"
        "ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ ÑÐµÐºÑÑ Ð²Ð°ÑÐµÐ³Ð¾ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ Ð¸/Ð¸Ð»Ð¸ ÑÐ¾ÑÐ¾/Ð²Ð¸Ð´ÐµÐ¾:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['waiting_for'] = 'post_text'

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input from user"""
    
    # ÐÑÐ¾Ð²ÐµÑÑÐµÐ¼, ÐµÑÑÑ Ð»Ð¸ Ð¼ÐµÐ´Ð¸Ð° Ð² ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ð¸ Ð²Ð¼ÐµÑÑÐµ Ñ ÑÐµÐºÑÑÐ¾Ð¼
    has_media = update.message.photo or update.message.video or update.message.document
    
    # ÐÑÐ»Ð¸ ÐµÑÑÑ Ð¼ÐµÐ´Ð¸Ð° Ð¸ ÑÐµÐºÑÑ Ð²Ð¼ÐµÑÑÐµ (caption)
    if has_media and update.message.caption:
        text = update.message.caption
        
        # ÐÑÐ»Ð¸ Ð¶Ð´ÐµÐ¼ ÑÐµÐºÑÑ Ð¿Ð¾ÑÑÐ°
        if context.user_data.get('waiting_for') == 'post_text':
            # ÐÑÐ¾Ð²ÐµÑÑÐµÐ¼ Ð½Ð° Ð·Ð°Ð¿ÑÐµÑÐµÐ½Ð½ÑÐµ ÑÑÑÐ»ÐºÐ¸
            filter_service = FilterService()
            if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
                await handle_link_violation(update, context)
                return
            
            # Ð¡Ð¾ÑÑÐ°Ð½ÑÐµÐ¼ ÑÐµÐºÑÑ
            if 'post_data' not in context.user_data:
                context.user_data['post_data'] = {}
            
            context.user_data['post_data']['text'] = text
            context.user_data['post_data']['media'] = []
            
            # Ð¡Ð¾ÑÑÐ°Ð½ÑÐµÐ¼ Ð¼ÐµÐ´Ð¸Ð°
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
                    InlineKeyboardButton("ð· ÐÐ¾Ð±Ð°Ð²Ð¸ÑÑ ÐµÑÐµ Ð¼ÐµÐ´Ð¸Ð°", callback_data="pub:add_media"),
                    InlineKeyboardButton("ð ÐÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑ", callback_data="pub:preview")
                ],
                [InlineKeyboardButton("âï¸ ÐÐ°Ð·Ð°Ð´", callback_data="menu:back")]
            ]
            
            await update.message.reply_text(
                "â Ð¢ÐµÐºÑÑ Ð¸ Ð¼ÐµÐ´Ð¸Ð° ÑÐ¾ÑÑÐ°Ð½ÐµÐ½Ñ!\n\n"
                "Ð¥Ð¾ÑÐ¸ÑÐµ Ð´Ð¾Ð±Ð°Ð²Ð¸ÑÑ ÐµÑÐµ Ð¼ÐµÐ´Ð¸Ð° Ð¸Ð»Ð¸ Ð¿ÐµÑÐµÐ¹ÑÐ¸ Ðº Ð¿ÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÑ?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            context.user_data['waiting_for'] = None
            return
    
    # ÐÑÐ»Ð¸ ÑÐ¾Ð»ÑÐºÐ¾ ÑÐµÐºÑÑ Ð±ÐµÐ· Ð¼ÐµÐ´Ð¸Ð°
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
                "â ÐÑÐ¸Ð±ÐºÐ°: Ð´Ð°Ð½Ð½ÑÐµ Ð¿Ð¾ÑÑÐ° Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ñ.\n"
                "ÐÐ¾Ð¶Ð°Ð»ÑÐ¹ÑÑÐ°, Ð½Ð°ÑÐ½Ð¸ÑÐµ Ð·Ð°Ð½Ð¾Ð²Ð¾ Ñ /start"
            )
            context.user_data.pop('waiting_for', None)
            return
        
        context.user_data['post_data']['text'] = text
        context.user_data['post_data']['media'] = []
        
        keyboard = [
            [
                InlineKeyboardButton("ð· ÐÐ¾Ð±Ð°Ð²Ð¸ÑÑ Ð¼ÐµÐ´Ð¸Ð°", callback_data="pub:add_media"),
                InlineKeyboardButton("ð ÐÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑ", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("âï¸ ÐÐ°Ð·Ð°Ð´", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            "â Ð¢ÐµÐºÑÑ ÑÐ¾ÑÑÐ°Ð½ÐµÐ½!\n\n"
            "Ð¥Ð¾ÑÐ¸ÑÐµ Ð´Ð¾Ð±Ð°Ð²Ð¸ÑÑ ÑÐ¾ÑÐ¾/Ð²Ð¸Ð´ÐµÐ¾ Ð¸Ð»Ð¸ ÑÑÐ°Ð·Ñ Ð¿ÐµÑÐµÐ¹ÑÐ¸ Ðº Ð¿ÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÑ?",
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
    # ÐÑÐ¾Ð²ÐµÑÑÐµÐ¼, ÑÑÐ¾ Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ Ð² Ð¿ÑÐ¾ÑÐµÑÑÐµ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¸Ñ Ð¼ÐµÐ´Ð¸Ð°
    if 'post_data' not in context.user_data:
        return
    
    # ÐÑÐ¸Ð½Ð¸Ð¼Ð°ÐµÐ¼ Ð¼ÐµÐ´Ð¸Ð° Ð´Ð°Ð¶Ðµ ÐµÑÐ»Ð¸ waiting_for Ð½Ðµ ÑÑÑÐ°Ð½Ð¾Ð²Ð»ÐµÐ½
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
                InlineKeyboardButton(f"ð· ÐÐ¾Ð±Ð°Ð²Ð¸ÑÑ ÐµÑÐµ", callback_data="pub:add_media"),
                InlineKeyboardButton("ð ÐÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑ", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("âï¸ ÐÐ°Ð·Ð°Ð´", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            f"â ÐÐµÐ´Ð¸Ð° Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¾! (ÐÑÐµÐ³Ð¾: {total_media})\n\n"
            "ÐÐ¾Ð±Ð°Ð²Ð¸ÑÑ ÐµÑÐµ Ð¸Ð»Ð¸ Ð¿ÐµÑÐµÐ¹ÑÐ¸ Ðº Ð¿ÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÑ?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data['waiting_for'] = None

async def request_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request media from user"""
    context.user_data['waiting_for'] = 'post_media'
    
    keyboard = [[InlineKeyboardButton("âï¸ ÐÐ°Ð·Ð°Ð´", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "ð· ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ ÑÐ¾ÑÐ¾, Ð²Ð¸Ð´ÐµÐ¾ Ð¸Ð»Ð¸ Ð´Ð¾ÐºÑÐ¼ÐµÐ½Ñ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show post preview"""
    if 'post_data' not in context.user_data:
        await update.callback_query.edit_message_text("â ÐÑÐ¸Ð±ÐºÐ°: Ð´Ð°Ð½Ð½ÑÐµ Ð¿Ð¾ÑÑÐ° Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ñ")
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
            InlineKeyboardButton("â ÐÑÐ¿ÑÐ°Ð²Ð¸ÑÑ Ð½Ð° Ð¼Ð¾Ð´ÐµÑÐ°ÑÐ¸Ñ", callback_data="pub:send"),
            InlineKeyboardButton("âï¸ Ð ÐµÐ´Ð°ÐºÑÐ¸ÑÐ¾Ð²Ð°ÑÑ", callback_data="pub:edit")
        ],
        [InlineKeyboardButton("â ÐÑÐ¼ÐµÐ½Ð°", callback_data="pub:cancel")]
    ]
    
    # Send preview
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"ð *ÐÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑ:*\n\n{preview_text}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.effective_message.reply_text(
                f"ð *ÐÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑ:*\n\n{preview_text}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    except:
        await update.effective_message.reply_text(
            f"ð *ÐÑÐµÐ´Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑ:*\n\n{preview_text}",
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
        hours = minutes // 60
        mins = minutes % 60
        
        if hours > 0:
            time_str = f"{hours} Ñ. {mins} Ð¼Ð¸Ð½."
        else:
            time_str = f"{minutes} Ð¼Ð¸Ð½."
            
        await update.callback_query.answer(
            f"â° ÐÐ¾Ð´Ð¾Ð¶Ð´Ð¸ÑÐµ ÐµÑÐµ {time_str} Ð¿ÐµÑÐµÐ´ ÑÐ»ÐµÐ´ÑÑÑÐµÐ¹ Ð¿ÑÐ±Ð»Ð¸ÐºÐ°ÑÐ¸ÐµÐ¹",
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
            await update.callback_query.answer("â ÐÑÐ¸Ð±ÐºÐ°: Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½", show_alert=True)
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
        
        # Calculate next post time
        cooldown_minutes = Config.COOLDOWN_SECONDS // 60
        hours = cooldown_minutes // 60
        mins = cooldown_minutes % 60
        
        if hours > 0:
            next_post_time = f"{hours} ÑÐ°ÑÐ° {mins} Ð¼Ð¸Ð½ÑÑ"
        else:
            next_post_time = f"{cooldown_minutes} Ð¼Ð¸Ð½ÑÑ"
        
        await update.callback_query.edit_message_text(
            f"â *ÐÑÐ¿ÑÐ°Ð²Ð»ÐµÐ½Ð¾ Ð½Ð° Ð¼Ð¾Ð´ÐµÑÐ°ÑÐ¸Ñ!*\n\n"
            f"ÐÐ°Ñ Ð¿Ð¾ÑÑ Ð±ÑÐ´ÐµÑ Ð¿ÑÐ¾Ð²ÐµÑÐµÐ½ Ð¼Ð¾Ð´ÐµÑÐ°ÑÐ¾ÑÐ°Ð¼Ð¸.\n"
            f"ÐÑ Ð¿Ð¾Ð»ÑÑÐ¸ÑÐµ ÑÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ðµ Ð¾ ÑÐµÐ·ÑÐ»ÑÑÐ°ÑÐµ.\n\n"
            f"â° Ð¡Ð»ÐµÐ´ÑÑÑÐ¸Ð¹ Ð¿Ð¾ÑÑ Ð¼Ð¾Ð¶Ð½Ð¾ Ð¾ÑÐ¿ÑÐ°Ð²Ð¸ÑÑ ÑÐµÑÐµÐ· {next_post_time}",
            parse_mode='Markdown'
        )

async def send_to_moderation_group(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   post: Post, user: User):
    """Send post to moderation group with media"""
    bot = context.bot
    
    # Build moderation message
    mod_text = (
        f"ð *ÐÐ¾Ð²Ð°Ñ Ð·Ð°ÑÐ²ÐºÐ° Ð½Ð° Ð¿ÑÐ±Ð»Ð¸ÐºÐ°ÑÐ¸Ñ*\n\n"
        f"ð¤ ÐÐ²ÑÐ¾Ñ: @{user.username or 'no_username'} (ID: {user.id})\n"
        f"ð ÐÐ°ÑÐ°: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"ð ÐÐ°ÑÐµÐ³Ð¾ÑÐ¸Ñ: {post.category}"
    )
    
    if post.subcategory:
        mod_text += f" â {post.subcategory}"
    
    if post.anonymous:
        mod_text += "\nð­ *ÐÐ½Ð¾Ð½Ð¸Ð¼Ð½Ð¾*"
    
    # ÐÐ¾Ð±Ð°Ð²Ð»ÑÐµÐ¼ Ð¸Ð½ÑÐ¾ÑÐ¼Ð°ÑÐ¸Ñ Ð¾ Ð¼ÐµÐ´Ð¸Ð°
    if post.media and len(post.media) > 0:
        mod_text += f"\nð ÐÐµÐ´Ð¸Ð°: {len(post.media)} ÑÐ°Ð¹Ð»(Ð¾Ð²)"
    
    mod_text += f"\n\nð Ð¢ÐµÐºÑÑ:\n{post.text}\n\n"
    mod_text += f"ð· Ð¥ÐµÑÑÐµÐ³Ð¸: {' '.join(post.hashtags)}"
    
    keyboard = [
        [
            InlineKeyboardButton("â ÐÐ¿ÑÐ±Ð»Ð¸ÐºÐ¾Ð²Ð°ÑÑ", callback_data=f"mod:approve:{post.id}"),
            InlineKeyboardButton("âï¸ Ð ÐµÐ´Ð°ÐºÑÐ¸ÑÐ¾Ð²Ð°ÑÑ", callback_data=f"mod:edit:{post.id}")
        ],
        [InlineKeyboardButton("â ÐÑÐºÐ»Ð¾Ð½Ð¸ÑÑ", callback_data=f"mod:reject:{post.id}")]
    ]
    
    try:
        # Ð¡Ð½Ð°ÑÐ°Ð»Ð° Ð¾ÑÐ¿ÑÐ°Ð²Ð»ÑÐµÐ¼ Ð¼ÐµÐ´Ð¸Ð°, ÐµÑÐ»Ð¸ ÐµÑÑÑ
        if post.media and len(post.media) > 0:
            # ÐÑÐ¿ÑÐ°Ð²Ð»ÑÐµÐ¼ ÐºÐ°Ð¶Ð´Ð¾Ðµ Ð¼ÐµÐ´Ð¸Ð° Ð¾ÑÐ´ÐµÐ»ÑÐ½Ð¾ Ð´Ð»Ñ Ð»ÑÑÑÐµÐ³Ð¾ Ð¾ÑÐ¾Ð±ÑÐ°Ð¶ÐµÐ½Ð¸Ñ
            for media_item in post.media:
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
                    elif media_item.get('type') == 'document':
                        await bot.send_document(
                            chat_id=Config.MODERATION_GROUP_ID,
                            document=media_item['file_id']
                        )
                except Exception as e:
                    logger.error(f"Error sending media: {e}")
        
        # ÐÐ°ÑÐµÐ¼ Ð¾ÑÐ¿ÑÐ°Ð²Ð»ÑÐµÐ¼ ÑÐµÐºÑÑ Ñ ÐºÐ½Ð¾Ð¿ÐºÐ°Ð¼Ð¸
        message = await bot.send_message(
            chat_id=Config.MODERATION_GROUP_ID,
            text=mod_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Ð¡Ð¾ÑÑÐ°Ð½ÑÐµÐ¼ ID ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ñ
        post.moderation_message_id = message.message_id
            
    except Exception as e:
        logger.error(f"Error sending to moderation group: {e}")
        # Fallback - ÑÐ²ÐµÐ´Ð¾Ð¼Ð»ÑÐµÐ¼ Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ Ð¾Ð± Ð¾ÑÐ¸Ð±ÐºÐµ
        await bot.send_message(
            chat_id=user.id,
            text=(
                "â ï¸ ÐÑÐ¸Ð±ÐºÐ° Ð¾ÑÐ¿ÑÐ°Ð²ÐºÐ¸ Ð² Ð³ÑÑÐ¿Ð¿Ñ Ð¼Ð¾Ð´ÐµÑÐ°ÑÐ¸Ð¸.\n\n"
                "ÐÐ¾Ð·Ð¼Ð¾Ð¶Ð½ÑÐµ Ð¿ÑÐ¸ÑÐ¸Ð½Ñ:\n"
                "â¢ ÐÐ¾Ñ Ð½Ðµ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½ Ð² Ð³ÑÑÐ¿Ð¿Ñ Ð¼Ð¾Ð´ÐµÑÐ°ÑÐ¸Ð¸\n"
                "â¢ ÐÐ¾Ñ Ð½Ðµ ÑÐ²Ð»ÑÐµÑÑÑ Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑÑÐ°ÑÐ¾ÑÐ¾Ð¼ Ð³ÑÑÐ¿Ð¿Ñ\n"
                "â¢ ÐÐµÐ²ÐµÑÐ½ÑÐ¹ ID Ð³ÑÑÐ¿Ð¿Ñ\n\n"
                "ÐÐ±ÑÐ°ÑÐ¸ÑÐµÑÑ Ðº Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑÑÐ°ÑÐ¾ÑÑ."
            )
        )

async def cancel_post_with_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for cancellation reason"""
    keyboard = [
        [InlineKeyboardButton("ÐÐµÑÐµÐ´ÑÐ¼Ð°Ð»", callback_data="pub:cancel_confirm")],
        [InlineKeyboardButton("ÐÑÐ¸Ð±ÐºÐ° Ð² ÑÐµÐºÑÑÐµ", callback_data="pub:cancel_confirm")],
        [InlineKeyboardButton("âï¸ ÐÐ°Ð·Ð°Ð´", callback_data="pub:preview")]
    ]
    
    await update.callback_query.edit_message_text(
        "â Ð£ÐºÐ°Ð¶Ð¸ÑÐµ Ð¿ÑÐ¸ÑÐ¸Ð½Ñ Ð¾ÑÐ¼ÐµÐ½Ñ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_link_violation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle link violation"""
    await update.message.reply_text(
        "â ï¸ ÐÐ±Ð½Ð°ÑÑÐ¶ÐµÐ½Ð° Ð·Ð°Ð¿ÑÐµÑÐµÐ½Ð½Ð°Ñ ÑÑÑÐ»ÐºÐ°!\n"
        "Ð¡ÑÑÐ»ÐºÐ¸ Ð·Ð°Ð¿ÑÐµÑÐµÐ½Ñ Ð² Ð¿ÑÐ±Ð»Ð¸ÐºÐ°ÑÐ¸ÑÑ."
    )
    context.user_data.pop('waiting_for', None)

async def edit_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit post before sending"""
    context.user_data['waiting_for'] = 'post_text'
    
    keyboard = [[InlineKeyboardButton("âï¸ ÐÐ°Ð·Ð°Ð´", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "âï¸ ÐÑÐ¿ÑÐ°Ð²ÑÑÐµ Ð½Ð¾Ð²ÑÐ¹ ÑÐµÐºÑÑ Ð´Ð»Ñ Ð¿Ð¾ÑÑÐ°:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel post creation"""
    context.user_data.pop('post_data', None)
    context.user_data.pop('waiting_for', None)
    context.user_data.pop('cancel_reason', None)
    
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)
