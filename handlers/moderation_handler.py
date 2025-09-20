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
    
    logger.info(f"Moderation callback from user {user_id}")
    logger.info(f"Is moderator check: {Config.is_moderator(user_id)}")
    
    if not Config.is_moderator(user_id):
        await query.answer("❌ Доступ запрещен", show_alert=True)
        logger.warning(f"Access denied for user {user_id}")
        return
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    post_id = int(data[2]) if len(data) > 2 and data[2].isdigit() else None
    
    logger.info(f"Moderation callback: action={action}, post_id={post_id}, user_id={user_id}")
    
    if action == "approve" and post_id:
        await start_approve_process(update, context, post_id)
    elif action == "approve_chat" and post_id:  # для актуальных постов
        await start_approve_process(update, context, post_id, chat=True)
    elif action == "reject" and post_id:
        await start_reject_process(update, context, post_id)
    elif action == "edit" and post_id:
        await query.answer("Редактирование в разработке", show_alert=True)
    else:
        logger.error(f"Unknown action or missing post_id: action={action}, post_id={post_id}")
        await query.answer("Неизвестное действие", show_alert=True)

async def handle_moderation_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input from moderators"""
    user_id = update.effective_user.id
    
    logger.info(f"Moderation text from user {user_id}: {update.message.text[:50]}...")
    
    if not Config.is_moderator(user_id):
        logger.warning(f"Non-moderator {user_id} tried to send moderation text")
        return
    
    # Проверяем, ожидает ли бот ввод от модератора
    waiting_for = context.user_data.get('mod_waiting_for')
    logger.info(f"Moderator {user_id} sent text, waiting_for: {waiting_for}")
    
    if waiting_for == 'approve_link':
        await process_approve_with_link(update, context)
    elif waiting_for == 'reject_reason':
        await process_reject_with_reason(update, context)
    else:
        logger.info(f"Moderator {user_id} sent text but not in moderation process")

async def start_approve_process(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, chat: bool = False):
    """Start approval process - ask for publication link"""
    try:
        logger.info(f"Starting approve process for post {post_id}")
        
        try:
            from services.db import db
            from models import Post
            from sqlalchemy import select
            
            async with db.get_session() as session:
                result = await session.execute(
                    select(Post).where(Post.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if not post:
                    logger.error(f"Post {post_id} not found")
                    await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                    return
                    
                logger.info(f"Found post {post_id}, user {post.user_id}")
                
        except Exception as db_error:
            logger.error(f"Database error when getting post {post_id}: {db_error}")
            await update.callback_query.answer("❌ Ошибка базы данных", show_alert=True)
            return
        
        # Store post info for later use
        context.user_data['mod_post_id'] = post_id
        context.user_data['mod_post_user_id'] = post.user_id
        context.user_data['mod_waiting_for'] = 'approve_link'
        context.user_data['mod_is_chat'] = chat
        
        logger.info(f"Stored context data for approval: {context.user_data}")
        
        # Ask moderator for publication link
        destination = "чате" if chat else "канале"
        await update.callback_query.edit_message_text(
            f"✅ **ОДОБРЕНИЕ ЗАЯВКИ**\n\n"
            f"Заявка будет одобрена и пользователь получит уведомление.\n\n"
            f"📎 **Отправьте ссылку на пост в {destination}:**\n"
            f"(Например: https://t.me/snghu/1234)\n\n"
            f"⚠️ Отправьте только ссылку одним сообщением\n\n"
            f"📊 Post ID: {post_id}\n"
            f"👤 User ID: {post.user_id}"
        )
        
    except Exception as e:
        logger.error(f"Error starting approve process for post {post_id}: {e}")
        await update.callback_query.answer("❌ Ошибка обработки заявки", show_alert=True)

async def start_reject_process(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Start rejection process - ask for reason"""
    try:
        logger.info(f"Starting reject process for post {post_id}")
        
        try:
            from services.db import db
            from models import Post
            from sqlalchemy import select
            
            async with db.get_session() as session:
                result = await session.execute(
                    select(Post).where(Post.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if not post:
                    logger.error(f"Post {post_id} not found")
                    await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                    return
                    
                logger.info(f"Found post {post_id}, user {post.user_id}")
                
        except Exception as db_error:
            logger.error(f"Database error when getting post {post_id}: {db_error}")
            await update.callback_query.answer("❌ Ошибка базы данных", show_alert=True)
            return
        
        # Store post info for later use
        context.user_data['mod_post_id'] = post_id
        context.user_data['mod_post_user_id'] = post.user_id
        context.user_data['mod_waiting_for'] = 'reject_reason'
        
        logger.info(f"Stored context data for rejection: {context.user_data}")
        
        # Ask moderator for rejection reason
        await update.callback_query.edit_message_text(
            f"❌ **ОТКЛОНЕНИЕ ЗАЯВКИ**\n\n"
            f"Заявка будет отклонена и пользователь получит уведомление.\n\n"
            f"📝 **Напишите причину отклонения:**\n"
            f"(Будет отправлена пользователю)\n\n"
            f"⚠️ Отправьте причину одним сообщением\n\n"
            f"📊 Post ID: {post_id}\n"
            f"👤 User ID: {post.user_id}"
        )
        
    except Exception as e:
        logger.error(f"Error starting reject process for post {post_id}: {e}")
        await update.callback_query.answer("❌ Ошибка обработки заявки", show_alert=True)

async def process_approve_with_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process approval with publication link"""
    try:
        link = update.message.text.strip()
        post_id = context.user_data.get('mod_post_id')
        user_id = context.user_data.get('mod_post_user_id')
        is_chat = context.user_data.get('mod_is_chat', False)
        
        logger.info(f"Processing approval: post_id={post_id}, user_id={user_id}, link={link}")
        
        if not post_id or not user_id:
            await update.message.reply_text("❌ Ошибка: данные заявки не найдены")
            return
        
        # Update post status in DB - ИСПРАВЛЕНО: используем правильные значения enum
        try:
            from services.db import db
            from models import Post, PostStatus
            from sqlalchemy import select
            
            async with db.get_session() as session:
                result = await session.execute(
                    select(Post).where(Post.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if post:
                    # ИСПРАВЛЕНО: используем enum PostStatus вместо строки
                    post.status = PostStatus.APPROVED  # Вместо 'approved'
                    await session.commit()
                    logger.info(f"Updated post {post_id} status to approved")
                else:
                    logger.error(f"Post {post_id} not found for status update")
                    await update.message.reply_text("❌ Заявка не найдена")
                    return
                    
        except Exception as db_error:
            logger.error(f"Database error updating post {post_id}: {db_error}")
            await update.message.reply_text("❌ Ошибка обновления статуса заявки")
            return
        
        # Send notification to user
        try:
            destination_text = "чате" if is_chat else "канале"
            success_keyboard = [
                [InlineKeyboardButton("📺 Перейти к посту", url=link)],
                [InlineKeyboardButton("📺 Наш канал", url="https://t.me/snghu")],
                [InlineKeyboardButton("📚 Каталог услуг", url="https://t.me/trixvault")]
            ]
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ **Ваша заявка одобрена!**\n\n"
                     f"📝 Ваш пост опубликован в {destination_text}.\n\n"
                     f"🔗 **Ссылка на публикацию:**\n{link}\n\n"
                     f"🔔 *Подписывайтесь на наши каналы:*",
                reply_markup=InlineKeyboardMarkup(success_keyboard),
                parse_mode='Markdown'
            )
            
            await update.message.reply_text(
                f"✅ **ЗАЯВКА ОДОБРЕНА**\n\n"
                f"👤 Пользователю отправлено уведомление\n"
                f"🔗 Ссылка: {link}\n"
                f"📊 Post ID: {post_id}",
                parse_mode='Markdown'
            )
            
            logger.info(f"Successfully approved post {post_id} for user {user_id}")
            
        except Exception as notify_error:
            logger.error(f"Error notifying user {user_id}: {notify_error}")
            await update.message.reply_text(
                f"⚠️ Заявка одобрена, но не удалось уведомить пользователя\n"
                f"User ID: {user_id}\nPost ID: {post_id}"
            )
        
        # Clear context
        context.user_data.pop('mod_post_id', None)
        context.user_data.pop('mod_post_user_id', None)
        context.user_data.pop('mod_waiting_for', None)
        context.user_data.pop('mod_is_chat', None)
        
    except Exception as e:
        logger.error(f"Error processing approval: {e}")
        await update.message.reply_text("❌ Ошибка обработки одобрения")

async def process_reject_with_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process rejection with reason"""
    try:
        reason = update.message.text.strip()
        post_id = context.user_data.get('mod_post_id')
        user_id = context.user_data.get('mod_post_user_id')
        
        logger.info(f"Processing rejection: post_id={post_id}, user_id={user_id}, reason={reason[:50]}...")
        
        if not post_id or not user_id:
            await update.message.reply_text("❌ Ошибка: данные заявки не найдены")
            return
        
        # Update post status in DB - ИСПРАВЛЕНО: используем правильные значения enum
        try:
            from services.db import db
            from models import Post, PostStatus
            from sqlalchemy import select
            
            async with db.get_session() as session:
                result = await session.execute(
                    select(Post).where(Post.id == post_id)
                )
                post = result.scalar_one_or_none()
                
                if post:
                    # ИСПРАВЛЕНО: используем enum PostStatus вместо строки
                    post.status = PostStatus.REJECTED  # Вместо 'rejected'
                    await session.commit()
                    logger.info(f"Updated post {post_id} status to rejected")
                else:
                    logger.error(f"Post {post_id} not found for status update")
                    await update.message.reply_text("❌ Заявка не найдена")
                    return
                    
        except Exception as db_error:
            logger.error(f"Database error updating post {post_id}: {db_error}")
            await update.message.reply_text("❌ Ошибка обновления статуса заявки")
            return
        
        # Send notification to user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ **Ваша заявка отклонена**\n\n"
                     f"📝 **Причина:**\n{reason}\n\n"
                     f"💡 Вы можете создать новую заявку, учтя указанные замечания.",
                parse_mode='Markdown'
            )
            
            await update.message.reply_text(
                f"❌ **ЗАЯВКА ОТКЛОНЕНА**\n\n"
                f"👤 Пользователю отправлено уведомление\n"
                f"📝 Причина: {reason}\n"
                f"📊 Post ID: {post_id}",
                parse_mode='Markdown'
            )
            
            logger.info(f"Successfully rejected post {post_id} for user {user_id}")
            
        except Exception as notify_error:
            logger.error(f"Error notifying user {user_id}: {notify_error}")
            await update.message.reply_text(
                f"⚠️ Заявка отклонена, но не удалось уведомить пользователя\n"
                f"User ID: {user_id}\nPost ID: {post_id}"
            )
        
        # Clear context
        context.user_data.pop('mod_post_id', None)
        context.user_data.pop('mod_post_user_id', None)
        context.user_data.pop('mod_waiting_for', None)
        
    except Exception as e:
        logger.error(f"Error processing rejection: {e}")
        await update.message.reply_text("❌ Ошибка обработки отклонения")

# Оставляем старые функции для совместимости
async def approve_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Legacy function - redirects to new process"""
    await start_approve_process(update, context, post_id)

async def approve_post_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Legacy function - redirects to new process"""
    await start_approve_process(update, context, post_id, chat=True)

async def reject_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Legacy function - redirects to new process"""
    await start_reject_process(update, context, post_id)

async def publish_to_channel(bot, post):
    """Publish post to target channel - DEPRECATED"""
    logger.warning("publish_to_channel called but manual publication is now used")

async def publish_to_chat(bot, post):
    """Publish post to target CHAT - DEPRECATED"""
    logger.warning("publish_to_chat called but manual publication is now used")
