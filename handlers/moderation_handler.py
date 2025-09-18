from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
import logging

logger = logging.getLogger(__name__)

async def handle_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle moderation callbacks with BigInt support"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if not Config.is_moderator(user_id):
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    post_id = int(data[2]) if len(data) > 2 and data[2].isdigit() else None
    
    if action == "approve" and post_id:
        await approve_post(update, context, post_id)
    elif action == "approve_chat" and post_id:  # НОВОЕ: для актуальных постов
        await approve_post_to_chat(update, context, post_id)
    elif action == "reject" and post_id:
        await reject_post(update, context, post_id)
    elif action == "edit" and post_id:
        await query.answer("Редактирование в разработке", show_alert=True)
    else:
        await query.answer("Неизвестное действие", show_alert=True)

async def safe_get_post(session, post_id):
    """Безопасное получение поста с обработкой больших ID"""
    try:
        from sqlalchemy import text
        
        result = await session.execute(
            text("""
                SELECT id, user_id, category, subcategory, text, media, hashtags, 
                       anonymous, status, created_at, is_piar
                FROM posts WHERE id = :post_id
            """),
            {"post_id": str(post_id)}
        )
        row = result.fetchone()
        
        if row:
            from models import Post
            post = Post()
            post.id = int(row[0])
            post.user_id = int(row[1]) 
            post.category = row[2]
            post.subcategory = row[3]
            post.text = row[4]
            post.media = row[5] if row[5] else []
            post.hashtags = row[6] if row[6] else []
            post.anonymous = row[7]
            post.status = row[8]
            post.created_at = row[9]
            post.is_piar = row[10] if row[10] else False
            return post
        return None
        
    except Exception as e:
        logger.error(f"Error getting post {post_id}: {e}")
        return None

async def safe_update_post_status(session, post_id, status):
    """Безопасное обновление статуса поста"""
    try:
        from sqlalchemy import text
        
        await session.execute(
            text("UPDATE posts SET status = :status WHERE id = :post_id"),
            {"status": status, "post_id": str(post_id)}
        )
        await session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error updating post {post_id}: {e}")
        return False

async def approve_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Approve post for publication with BigInt support"""
    try:
        from services.db import db
        
        async with db.get_session() as session:
            # Get post safely
            post = await safe_get_post(session, post_id)
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            # Update status safely
            success = await safe_update_post_status(session, post_id, 'approved')
            
            if not success:
                await update.callback_query.answer("❌ Ошибка обновления статуса", show_alert=True)
                return
            
            # Send to channel
            await publish_to_channel(context.bot, post)
            
            # Notify user
            try:
                success_keyboard = [
                    [InlineKeyboardButton("📺 Наш канал", url="https://t.me/snghu")],
                    [InlineKeyboardButton("📚 Каталог услуг", url="https://t.me/trixvault")]
                ]
                
                await context.bot.send_message(
                    chat_id=post.user_id,
                    text="✅ *Ваша публикация одобрена!*\n\n"
                         "Пост опубликован в канале.\n\n"
                         "🔔 *Подписывайтесь на наши каналы:*",
                    reply_markup=InlineKeyboardMarkup(success_keyboard),
                    parse_mode='Markdown'
                )
            except Exception as notify_error:
                logger.error(f"Error notifying user {post.user_id}: {notify_error}")
            
            # Update moderation message
            try:
                await update.callback_query.edit_message_text(
                    f"✅ **ОДОБРЕНО**\n\n{update.callback_query.message.text}",
                    parse_mode='Markdown'
                )
            except Exception as edit_error:
                logger.error(f"Error editing moderation message: {edit_error}")
                await update.callback_query.answer("✅ Пост одобрен и опубликован!")
            
    except Exception as e:
        logger.error(f"Error approving post {post_id}: {e}")
        await update.callback_query.answer("❌ Ошибка одобрения поста", show_alert=True)

async def approve_post_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Approve post for publication to CHAT (for Actual posts) with BigInt support"""
    try:
        from services.db import db
        
        async with db.get_session() as session:
            # Get post safely
            post = await safe_get_post(session, post_id)
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            # Update status safely
            success = await safe_update_post_status(session, post_id, 'approved')
            
            if not success:
                await update.callback_query.answer("❌ Ошибка обновления статуса", show_alert=True)
                return
            
            # Send to CHAT instead of channel
            await publish_to_chat(context.bot, post)
            
            # Notify user
            try:
                success_keyboard = [
                    [InlineKeyboardButton("💬 Чат Будапешта", url="https://t.me/tgchatxxx")],
                    [InlineKeyboardButton("📺 Наш канал", url="https://t.me/snghu")]
                ]
                
                await context.bot.send_message(
                    chat_id=post.user_id,
                    text="⚡️ *Ваше АКТУАЛЬНОЕ сообщение опубликовано!*\n\n"
                         "📌 Пост опубликован в чате и будет закреплен администратором.\n\n"
                         "🔔 *Подписывайтесь на наши каналы:*",
                    reply_markup=InlineKeyboardMarkup(success_keyboard),
                    parse_mode='Markdown'
                )
            except Exception as notify_error:
                logger.error(f"Error notifying user {post.user_id}: {notify_error}")
            
            # Update moderation message
            try:
                await update.callback_query.edit_message_text(
                    f"⚡️ **ОПУБЛИКОВАНО В ЧАТЕ**\n\n{update.callback_query.message.text}",
                    parse_mode='Markdown'
                )
            except Exception as edit_error:
                logger.error(f"Error editing moderation message: {edit_error}")
                await update.callback_query.answer("⚡️ Пост опубликован в чате!")
            
    except Exception as e:
        logger.error(f"Error approving post {post_id} to chat: {e}")
        await update.callback_query.answer("❌ Ошибка публикации поста", show_alert=True)

async def reject_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Reject post with BigInt support"""
    try:
        from services.db import db
        
        async with db.get_session() as session:
            # Get post safely
            post = await safe_get_post(session, post_id)
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            # Update status safely
            success = await safe_update_post_status(session, post_id, 'rejected')
            
            if not success:
                await update.callback_query.answer("❌ Ошибка обновления статуса", show_alert=True)
                return
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=post.user_id,
                    text="❌ *Ваша публикация отклонена*\n\n"
                         "Причина: не соответствует правилам сообщества.\n"
                         "Попробуйте создать новую публикацию.",
                    parse_mode='Markdown'
                )
            except Exception as notify_error:
                logger.error(f"Error notifying user {post.user_id}: {notify_error}")
            
            # Update moderation message
            try:
                await update.callback_query.edit_message_text(
                    f"❌ **ОТКЛОНЕНО**\n\n{update.callback_query.message.text}",
                    parse_mode='Markdown'
                )
            except Exception as edit_error:
                logger.error(f"Error editing moderation message: {edit_error}")
                await update.callback_query.answer("❌ Пост отклонен!")
            
    except Exception as e:
        logger.error(f"Error rejecting post {post_id}: {e}")
        await update.callback_query.answer("❌ Ошибка отклонения поста", show_alert=True)

async def publish_to_channel(bot, post):
    """Publish post to target channel"""
    try:
        # Build post text
        text = post.text
        
        if post.hashtags:
            text += f"\n\n{' '.join(post.hashtags)}"
        
        text += f"\n\n{Config.DEFAULT_SIGNATURE}"
        
        # Send media first if exists
        if post.media and len(post.media) > 0:
            for media_item in post.media:
                if media_item.get('type') == 'photo':
                    await bot.send_photo(
                        chat_id=Config.TARGET_CHANNEL_ID,
                        photo=media_item['file_id']
                    )
                elif media_item.get('type') == 'video':
                    await bot.send_video(
                        chat_id=Config.TARGET_CHANNEL_ID,
                        video=media_item['file_id']
                    )
        
        # Send text
        await bot.send_message(
            chat_id=Config.TARGET_CHANNEL_ID,
            text=text,
            parse_mode='Markdown'
        )
        
        logger.info(f"Post {post.id} published to channel")
        
    except Exception as e:
        logger.error(f"Error publishing post {post.id} to channel: {e}")

async def publish_to_chat(bot, post):
    """Publish post to target CHAT (for Actual posts)"""
    try:
        # Build post text
        text = post.text
        
        if post.hashtags:
            text += f"\n\n{' '.join(post.hashtags)}"
        
        text += f"\n\n{Config.DEFAULT_SIGNATURE}"
        
        # Send media first if exists
        if post.media and len(post.media) > 0:
            for media_item in post.media:
                if media_item.get('type') == 'photo':
                    await bot.send_photo(
                        chat_id=Config.CHAT_FOR_ACTUAL,
                        photo=media_item['file_id']
                    )
                elif media_item.get('type') == 'video':
                    await bot.send_video(
                        chat_id=Config.CHAT_FOR_ACTUAL,
                        video=media_item['file_id']
                    )
        
        # Send text
        message = await bot.send_message(
            chat_id=Config.CHAT_FOR_ACTUAL,
            text=text,
            parse_mode='Markdown'
        )
        
        # Try to pin the message (requires admin rights)
        try:
            await bot.pin_chat_message(
                chat_id=Config.CHAT_FOR_ACTUAL,
                message_id=message.message_id,
                disable_notification=False
            )
            logger.info(f"Actual post {post.id} published to chat and pinned")
        except Exception as pin_error:
            logger.warning(f"Could not pin message: {pin_error}")
            logger.info(f"Actual post {post.id} published to chat (not pinned)")
        
    except Exception as e:
        logger.error(f"Error publishing actual post {post.id} to chat: {e}")
