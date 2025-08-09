from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes, ConversationHandler
from config import Config
from services.db import db
from models import Post, PostStatus, ModerationLog, ModerationAction, User
from sqlalchemy import select
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# States for moderation
EDIT_TEXT, REJECT_REASON = range(2)

async def handle_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle moderation callbacks"""
    query = update.callback_query
    
    # Check if user is moderator
    if not Config.is_moderator(update.effective_user.id):
        await query.answer("❌ У вас нет прав модератора", show_alert=True)
        return
    
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    post_id = int(data[2]) if len(data) > 2 else None
    
    if action == "approve":
        await approve_post(update, context, post_id)
    elif action == "edit":
        await start_edit_post(update, context, post_id)
    elif action == "reject":
        await start_reject_post(update, context, post_id)
    elif action == "confirm_edit":
        await confirm_edit_post(update, context, post_id)
    elif action == "confirm_reject":
        await confirm_reject_post(update, context, post_id)

async def approve_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Approve and publish post"""
    moderator_id = update.effective_user.id
    
    async with db.get_session() as session:
        # Get post
        result = await session.execute(
            select(Post).where(Post.id == post_id)
        )
        post = result.scalar_one_or_none()
        
        if not post:
            await update.callback_query.answer("❌ Пост не найден", show_alert=True)
            return
        
        if post.status != PostStatus.PENDING:
            await update.callback_query.answer("❌ Пост уже обработан", show_alert=True)
            return
        
        # Get user
        user_result = await session.execute(
            select(User).where(User.id == post.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        # Update post status
        post.status = PostStatus.APPROVED
        post.moderated_by = moderator_id
        post.moderated_at = datetime.utcnow()
        
        # Create moderation log
        log = ModerationLog(
            post_id=post_id,
            moderator_id=moderator_id,
            action=ModerationAction.APPROVE
        )
        session.add(log)
        
        # Publish to channel
        publish_text = f"{post.text}\n\n"
        publish_text += f"{' '.join(post.hashtags)}\n\n"
        publish_text += Config.DEFAULT_SIGNATURE
        
        # If anonymous, don't show author info
        if post.anonymous:
            author_info = "🎭 Анонимно"
        else:
            author_info = f"👤 @{user.username}" if user.username else f"👤 ID: {user.id}"
        
        try:
            # Send to channel
            if post.media:
                media_group = []
                for i, media_item in enumerate(post.media[:10]):
                    if media_item['type'] == 'photo':
                        media_group.append(InputMediaPhoto(
                            media=media_item['file_id'],
                            caption=publish_text if i == 0 else None
                        ))
                    elif media_item['type'] == 'video':
                        media_group.append(InputMediaVideo(
                            media=media_item['file_id'],
                            caption=publish_text if i == 0 else None
                        ))
                
                if media_group:
                    messages = await context.bot.send_media_group(
                        chat_id=Config.TARGET_CHANNEL_ID,
                        media=media_group
                    )
                    post.channel_message_id = messages[0].message_id
            else:
                message = await context.bot.send_message(
                    chat_id=Config.TARGET_CHANNEL_ID,
                    text=publish_text
                )
                post.channel_message_id = message.message_id
            
            await session.commit()
            
            # Update moderation message
            await update.callback_query.edit_message_text(
                f"✅ *Пост опубликован!*\n\n"
                f"Модератор: @{update.effective_user.username}\n"
                f"Время: {datetime.utcnow().strftime('%H:%M:%S')}\n"
                f"ID поста в канале: {post.channel_message_id}",
                parse_mode='Markdown'
            )
            
            # Notify user
            channel_link = f"https://t.me/snghu/{post.channel_message_id}"
            await context.bot.send_message(
                chat_id=post.user_id,
                text=f"✅ Ваш пост опубликован в канале @snghu!\n\n"
                     f"Ссылка: {channel_link}\n"
                     f"Спасибо! 🗯️"
            )
            
        except Exception as e:
            logger.error(f"Error publishing post {post_id}: {e}")
            await update.callback_query.answer("❌ Ошибка при публикации", show_alert=True)
            post.status = PostStatus.PENDING
            await session.commit()

async def start_edit_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Start editing post text"""
    context.user_data['editing_post_id'] = post_id
    context.user_data['waiting_for'] = 'mod_edit_text'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"mod:approve:{post_id}")]]
    
    await update.callback_query.edit_message_reply_markup(reply_markup=None)
    await update.callback_query.message.reply_text(
        "✏️ *Редактирование поста*\n\n"
        "Отправьте новый текст для поста:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    return EDIT_TEXT

async def start_reject_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Start rejecting post"""
    context.user_data['rejecting_post_id'] = post_id
    context.user_data['waiting_for'] = 'mod_reject_reason'
    
    keyboard = [
        [
            InlineKeyboardButton("Спам", callback_data=f"mod:reject_quick:{post_id}:spam"),
            InlineKeyboardButton("Реклама", callback_data=f"mod:reject_quick:{post_id}:ads")
        ],
        [
            InlineKeyboardButton("Нарушение правил", callback_data=f"mod:reject_quick:{post_id}:rules"),
            InlineKeyboardButton("Оскорбления", callback_data=f"mod:reject_quick:{post_id}:insult")
        ],
        [InlineKeyboardButton("✍️ Своя причина", callback_data=f"mod:reject_custom:{post_id}")]
    ]
    
    await update.callback_query.edit_message_reply_markup(reply_markup=None)
    await update.callback_query.message.reply_text(
        "❌ *Отклонение поста*\n\n"
        "Выберите причину отклонения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def confirm_reject_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Confirm post rejection with reason"""
    moderator_id = update.effective_user.id
    
    # Get reason from callback data or user data
    if ":" in update.callback_query.data:
        parts = update.callback_query.data.split(":")
        if len(parts) > 3:
            reason_key = parts[3]
            reasons = {
                'spam': 'Спам',
                'ads': 'Недопустимая реклама',
                'rules': 'Нарушение правил сообщества',
                'insult': 'Оскорбления или неприемлемый контент'
            }
            reason = reasons.get(reason_key, 'Нарушение правил')
        else:
            reason = context.user_data.get('reject_reason', 'Нарушение правил')
    else:
        reason = context.user_data.get('reject_reason', 'Нарушение правил')
    
    async with db.get_session() as session:
        # Get post
        result = await session.execute(
            select(Post).where(Post.id == post_id)
        )
        post = result.scalar_one_or_none()
        
        if not post:
            await update.callback_query.answer("❌ Пост не найден", show_alert=True)
            return
        
        if post.status != PostStatus.PENDING:
            await update.callback_query.answer("❌ Пост уже обработан", show_alert=True)
            return
        
        # Update post status
        post.status = PostStatus.REJECTED
        post.moderated_by = moderator_id
        post.moderated_at = datetime.utcnow()
        
        # Create moderation log
        log = ModerationLog(
            post_id=post_id,
            moderator_id=moderator_id,
            action=ModerationAction.REJECT,
            reason=reason
        )
        session.add(log)
        await session.commit()
        
        # Update moderation message
        await update.callback_query.message.edit_text(
            f"❌ *Пост отклонен*\n\n"
            f"Модератор: @{update.effective_user.username}\n"
            f"Причина: {reason}\n"
            f"Время: {datetime.utcnow().strftime('%H:%M:%S')}",
            parse_mode='Markdown'
        )
        
        # Notify user
        await context.bot.send_message(
            chat_id=post.user_id,
            text=f"❌ Ваш пост отклонён\n\n"
                 f"Причина: *{reason}*\n\n"
                 f"Если хотите — отредактируйте и отправьте снова.",
            parse_mode='Markdown'
        )
    
    # Clear user data
    context.user_data.pop('rejecting_post_id', None)
    context.user_data.pop('reject_reason', None)

async def handle_mod_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input during moderation"""
    if 'waiting_for' not in context.user_data:
        return
    
    waiting_for = context.user_data['waiting_for']
    text = update.message.text
    
    if waiting_for == 'mod_edit_text':
        post_id = context.user_data.get('editing_post_id')
        if post_id:
            await save_edited_text(update, context, post_id, text)
    
    elif waiting_for == 'mod_reject_reason':
        post_id = context.user_data.get('rejecting_post_id')
        if post_id:
            context.user_data['reject_reason'] = text
            await confirm_reject_post(update, context, post_id)

async def save_edited_text(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           post_id: int, new_text: str):
    """Save edited text and publish"""
    moderator_id = update.effective_user.id
    
    async with db.get_session() as session:
        # Get post
        result = await session.execute(
            select(Post).where(Post.id == post_id)
        )
        post = result.scalar_one_or_none()
        
        if not post:
            await update.message.reply_text("❌ Пост не найден")
            return
        
        # Create moderation log
        log = ModerationLog(
            post_id=post_id,
            moderator_id=moderator_id,
            action=ModerationAction.EDIT,
            new_text=new_text
        )
        session.add(log)
        
        # Update post
        post.text = new_text
        post.status = PostStatus.EDITED
        
        await session.commit()
        
        # Now approve and publish
        await approve_post_after_edit(update, context, post)
    
    # Clear user data
    context.user_data.pop('editing_post_id', None)
    context.user_data.pop('waiting_for', None)

async def approve_post_after_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, post: Post):
    """Approve post after editing"""
    # Publish to channel
    publish_text = f"{post.text}\n\n"
    publish_text += f"{' '.join(post.hashtags)}\n\n"
    publish_text += Config.DEFAULT_SIGNATURE
    
    try:
        # Send to channel
        if post.media:
            media_group = []
            for i, media_item in enumerate(post.media[:10]):
                if media_item['type'] == 'photo':
                    media_group.append(InputMediaPhoto(
                        media=media_item['file_id'],
                        caption=publish_text if i == 0 else None
                    ))
                elif media_item['type'] == 'video':
                    media_group.append(InputMediaVideo(
                        media=media_item['file_id'],
                        caption=publish_text if i == 0 else None
                    ))
            
            if media_group:
                messages = await context.bot.send_media_group(
                    chat_id=Config.TARGET_CHANNEL_ID,
                    media=media_group
                )
                post.channel_message_id = messages[0].message_id
        else:
            message = await context.bot.send_message(
                chat_id=Config.TARGET_CHANNEL_ID,
                text=publish_text
            )
            post.channel_message_id = message.message_id
        
        # Update post status
        async with db.get_session() as session:
            result = await session.execute(
                select(Post).where(Post.id == post.id)
            )
            db_post = result.scalar_one_or_none()
            db_post.status = PostStatus.APPROVED
            db_post.channel_message_id = post.channel_message_id
            db_post.moderated_at = datetime.utcnow()
            await session.commit()
        
        await update.message.reply_text(
            f"✅ *Пост отредактирован и опубликован!*\n\n"
            f"ID поста в канале: {post.channel_message_id}",
            parse_mode='Markdown'
        )
        
        # Notify user
        channel_link = f"https://t.me/snghu/{post.channel_message_id}"
        await context.bot.send_message(
            chat_id=post.user_id,
            text=f"✅ Ваш пост опубликован в канале @snghu!\n"
                 f"(с редактированием модератора)\n\n"
                 f"Ссылка: {channel_link}\n"
                 f"Спасибо! 🗯️"
        )
        
    except Exception as e:
        logger.error(f"Error publishing edited post {post.id}: {e}")
        await update.message.reply_text("❌ Ошибка при публикации")
