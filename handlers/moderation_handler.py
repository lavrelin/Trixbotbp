from telegram import Update
from telegram.ext import ContextTypes
from config import Config
import logging

logger = logging.getLogger(__name__)

async def handle_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle moderation callbacks"""
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

async def approve_post_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Approve post for publication to CHAT (for Actual posts)"""
    try:
        from services.db import db
        from models import Post, PostStatus
        from sqlalchemy import select
        
        async with db.get_session() as session:
            # Get post
            result = await session.execute(
                select(Post).where(Post.id == post_id)
            )
            post = result.scalar_one_or_none()
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            # Update status
            post.status = PostStatus.APPROVED
            await session.commit()
            
            # Send to CHAT instead of channel
            await publish_to_chat(context.bot, post)
            
            # Notify user
            success_keyboard = [
                [InlineKeyboardButton("💬 Чат Будапешта", url="https://t.me/tgchatxxx")],
                [InlineKeyboardButton("📺 Наш канал", url="https://t.me/snghu")]
            ]
            
            await context.bot.send_message(
                chat_id=post.user_id,
                text=f"⚡️ *Ваше АКТУАЛЬНОЕ сообщение опубликовано!*\n\n"
                     f"📌 Пост опубликован в чате и будет закреплен администратором.\n\n"
                     f"🔔 *Подписывайтесь на наши каналы:*",
                reply_markup=InlineKeyboardMarkup(success_keyboard),
                parse_mode='Markdown'
            )
            
            # Update moderation message
            await update.callback_query.edit_message_text(
                f"⚡️ **ОПУБЛИКОВАНО В ЧАТЕ**\n\n{update.callback_query.message.text}",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error approving post {post_id} to chat: {e}")
        await update.callback_query.answer("❌ Ошибка публикации поста", show_alert=True)

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

async def approve_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Approve post for publication"""
    try:
        from services.db import db
        from models import Post, PostStatus
        from sqlalchemy import select
        
        async with db.get_session() as session:
            # Get post
            result = await session.execute(
                select(Post).where(Post.id == post_id)
            )
            post = result.scalar_one_or_none()
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            # Update status
            post.status = PostStatus.APPROVED
            await session.commit()
            
            # Send to channel
            await publish_to_channel(context.bot, post)
            
            # Notify user
            success_keyboard = [
                [InlineKeyboardButton("📺 Наш канал", url="https://t.me/snghu")],
                [InlineKeyboardButton("📚 Каталог услуг", url="https://t.me/trixvault")]
            ]
            
            await context.bot.send_message(
                chat_id=post.user_id,
                text=f"✅ *Ваша публикация одобрена!*\n\n"
                     f"Пост опубликован в канале.\n\n"
                     f"🔔 *Подписывайтесь на наши каналы:*",
                reply_markup=InlineKeyboardMarkup(success_keyboard),
                parse_mode='Markdown'
            )
            
            # Update moderation message
            await update.callback_query.edit_message_text(
                f"✅ **ОДОБРЕНО**\n\n{update.callback_query.message.text}",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error approving post {post_id}: {e}")
        await update.callback_query.answer("❌ Ошибка одобрения поста", show_alert=True)

async def reject_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Reject post"""
    try:
        from services.db import db
        from models import Post, PostStatus
        from sqlalchemy import select
        
        async with db.get_session() as session:
            # Get post
            result = await session.execute(
                select(Post).where(Post.id == post_id)
            )
            post = result.scalar_one_or_none()
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            # Update status
            post.status = PostStatus.REJECTED
            await session.commit()
            
            # Notify user
            await context.bot.send_message(
                chat_id=post.user_id,
                text="❌ *Ваша публикация отклонена*\n\n"
                     "Причина: не соответствует правилам сообщества.\n"
                     "Попробуйте создать новую публикацию.",
                parse_mode='Markdown'
            )
            
            # Update moderation message
            await update.callback_query.edit_message_text(
                f"❌ **ОТКЛОНЕНО**\n\n{update.callback_query.message.text}",
                parse_mode='Markdown'
            )
            
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
