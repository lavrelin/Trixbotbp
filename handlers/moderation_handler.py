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
    elif action == "approve_confirm":
        await approve_post_confirm(update, context, post_id)
    elif action == "edit":
        await start_edit_post(update, context, post_id)
    elif action == "reject":
        await start_reject_post(update, context, post_id)
    elif action == "confirm_edit":
        await confirm_edit_post(update, context, post_id)
    elif action == "confirm_reject":
        confirm_reject_post(update, context, post_id)
    elif action == "reject_quick":
        # Быстрое отклонение с причиной
        parts = query.data.split(":")
        if len(parts) > 3:
            reason_key = parts[3]
            await quick_reject_post(update, context, post_id, reason_key)
    elif action == "reject_custom":
        await request_custom_reject_reason(update, context, post_id)
    elif action == "back":
        # Возврат к просмотру поста
        await show_post_details(update, context, post_id)
    elif action == "list":
        # Показать список заявок
        await show_pending_posts(update, context)

async def approve_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Show confirmation before approving"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить публикацию", callback_data=f"mod:approve_confirm:{post_id}"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data=f"mod:back:{post_id}")
        ]
    ]
    
    await update.callback_query.edit_message_text(
        "❓ *Подтверждение публикации*\n\n"
        "Вы уверены, что хотите опубликовать этот пост?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def approve_post_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Actually approve and publish post"""
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
        
        try:
            # Send to channel with media if exists
            if post.media and len(post.media) > 0:
                media_group = []
                for i, media_item in enumerate(post.media[:10]):
                    if media_item.get('type') == 'photo':
                        media_group.append(InputMediaPhoto(
                            media=media_item['file_id'],
                            caption=publish_text if i == 0 else None
                        ))
                    elif media_item.get('type') == 'video':
                        media_group.append(InputMediaVideo(
                            media=media_item['file_id'],
                            caption=publish_text if i == 0 else None
                        ))
                
                if media_group:
                    messages = await context.bot.send_media_group(
                        chat_id=Config.TARGET_CHANNEL_ID,
                        media=media_group
                    )
                    post.channel_message_id = messages[0].message_id if messages else None
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
    
    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=f"mod:back:{post_id}")]]
    
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
    
    keyboard = [
        [
            InlineKeyboardButton("Спам", callback_data=f"mod:reject_quick:{post_id}:spam"),
            InlineKeyboardButton("Реклама", callback_data=f"mod:reject_quick:{post_id}:ads")
        ],
        [
            InlineKeyboardButton("Нарушение правил", callback_data=f"mod:reject_quick:{post_id}:rules"),
            InlineKeyboardButton("Оскорбления", callback_data=f"mod:reject_quick:{post_id}:insult")
        ],
        [InlineKeyboardButton("✍️ Своя причина", callback_data=f"mod:reject_custom:{post_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"mod:back:{post_id}")]
    ]
    
    await update.callback_query.edit_message_reply_markup(reply_markup=None)
    await update.callback_query.message.reply_text(
        "❌ *Отклонение поста*\n\n"
        "Выберите причину отклонения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def quick_reject_post(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                            post_id: int, reason_key: str):
    """Quick reject with predefined reason"""
    moderator_id = update.effective_user.id
    
    reasons = {
        'spam': 'Спам',
        'ads': 'Недопустимая реклама',
        'rules': 'Нарушение правил сообщества',
        'insult': 'Оскорбления или неприемлемый контент'
    }
    reason = reasons.get(reason_key, 'Нарушение правил')
    
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

async def request_custom_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Request custom rejection reason"""
    context.user_data['rejecting_post_id'] = post_id
    context.user_data['waiting_for'] = 'mod_reject_reason'
    
    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data=f"mod:back:{post_id}")]]
    
    await update.callback_query.edit_message_text(
        "✍️ *Укажите причину отклонения*\n\n"
        "Напишите свою причину:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_post_details(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Show post details again"""
    async with db.get_session() as session:
        result = await session.execute(
            select(Post).where(Post.id == post_id)
        )
        post = result.scalar_one_or_none()
        
        if not post:
            await update.callback_query.answer("❌ Пост не найден", show_alert=True)
            return
        
        # Get user
        user_result = await session.execute(
            select(User).where(User.id == post.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        # Build message
        text = (
            f"📝 *Заявка на публикацию*\n\n"
            f"👤 Автор: @{user.username or 'no_username'} (ID: {user.id})\n"
            f"📅 Дата: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📂 Категория: {post.category}"
        )
        
        if post.subcategory:
            text += f" → {post.subcategory}"
        
        if post.anonymous:
            text += "\n🎭 *Анонимно*"
        
        text += f"\n\n📝 Текст:\n{post.text}\n\n"
        text += f"🏷 Хештеги: {' '.join(post.hashtags)}"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=f"mod:approve:{post.id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"mod:edit:{post.id}")
            ],
            [
                InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}"),
                InlineKeyboardButton("📋 К списку", callback_data="mod:list")
            ]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def show_pending_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of pending posts"""
    async with db.get_session() as session:
        result = await session.execute(
            select(Post)
            .where(Post.status == PostStatus.PENDING)
            .order_by(Post.created_at.desc())
            .limit(10)
        )
        posts = result.scalars().all()
        
        if not posts:
            await update.callback_query.answer("📭 Нет заявок на модерацию", show_alert=True)
            return
        
        text = "📋 *Заявки на модерацию:*\n\n"
        
        for i, post in enumerate(posts, 1):
            text += f"{i}. {post.category} - {post.created_at.strftime('%H:%M')}\n"
        
        text += "\n_Показаны последние 10 заявок_"
        
        await update.callback_query.edit_message_text(
            text,
            parse_mode='Markdown'
        )

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
            await reject_with_custom_reason(update, context, post_id, text)

async def save_edited_text(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           post_id: int, new_text: str):
    """Save edited text and ask for confirmation"""
    context.user_data['edited_text'] = new_text
    context.user_data['editing_post_id'] = post_id
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить и опубликовать", callback_data=f"mod:confirm_edit:{post_id}")],
        [InlineKeyboardButton("◀️ Отмена", callback_data=f"mod:back:{post_id}")]
    ]
    
    await update.message.reply_text(
        f"📝 *Новый текст:*\n\n{new_text}\n\n"
        "Подтвердить изменения и опубликовать?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data.pop('waiting_for', None)

async def reject_with_custom_reason(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                    post_id: int, reason: str):
    """Reject post with custom reason"""
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
        
        # Notify moderator
        await update.message.reply_text(
            f"❌ *Пост отклонен*\n\n"
            f"Причина: {reason}",
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
    context.user_data.pop('waiting_for', None)
