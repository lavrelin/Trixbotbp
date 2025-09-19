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
        await start_approve_process(update, context, post_id)
    elif action == "approve_chat" and post_id:  # для актуальных постов
        await start_approve_process(update, context, post_id, chat=True)
    elif action == "reject" and post_id:
        await start_reject_process(update, context, post_id)
    elif action == "edit" and post_id:
        await query.answer("Редактирование в разработке", show_alert=True)
    else:
        await query.answer("Неизвестное действие", show_alert=True)

async def handle_moderation_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input from moderators"""
    user_id = update.effective_user.id
    
    if not Config.is_moderator(user_id):
        return
    
    # Проверяем, ожидает ли бот ввод от модератора
    waiting_for = context.user_data.get('mod_waiting_for')
    
    if waiting_for == 'approve_link':
        await process_approve_with_link(update, context)
    elif waiting_for == 'reject_reason':
        await process_reject_with_reason(update, context)

async def start_approve_process(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, chat: bool = False):
    """Start approval process - ask for publication link"""
    try:
        from services.db import db
        
        async with db.get_session() as session:
            # Get post safely
            post = await safe_get_post(session, post_id)
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            # Store post info for later use
            context.user_data['mod_post_id'] = post_id
            context.user_data['mod_post_user_id'] = post.user_id
            context.user_data['mod_waiting_for'] = 'approve_link'
            context.user_data['mod_is_chat'] = chat
            
            # Ask moderator for publication link
            destination = "чате" if chat else "канале"
            await update.callback_query.edit_message_text(
                f"✅ **ОДОБРЕНИЕ ЗАЯВКИ**\n\n"
                f"Заявка будет одобрена и пользователь получит уведомление.\n\n"
                f"📎 **Отправьте ссылку на пост в {destination}:**\n"
                f"(Например: https://t.me/snghu/1234)\n\n"
                f"⚠️ Отправьте только ссылку одним сообщением",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error starting approve process for post {post_id}: {e}")
        await update.callback_query.answer("❌ Ошибка обработки заявки", show_alert=True)

async def start_reject_process(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int):
    """Start rejection process - ask for reason"""
    try:
        from services.db import db
        
        async with db.get_session() as session:
            # Get post safely
            post = await safe_get_post(session, post_id)
            
            if not post:
                await update.callback_query.answer("❌ Пост не найден", show_alert=True)
                return
            
            # Store post info for later use
            context.user_data['mod_post_id'] = post_id
            context.user_data['mod_post_user_id'] = post.user_id
            context.user_data['mod_waiting_for'] = 'reject_reason'
            
            # Ask moderator for rejection reason
            await update.callback_query.edit_message_text(
                f"❌ **ОТКЛОНЕНИЕ ЗАЯВКИ**\n\n"
                f"Заявка будет отклонена и пользователь получит уведомление.\n\n"
                f"📝 **Напишите причину отклонения:**\n"
                f"(Будет отправлена пользователю)\n\n"
                f"⚠️ Отправьте причину одним сообщением",
                parse_mode='Markdown'
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
        
        if not post_id or not user_id:
            await update.message.reply_text("❌ Ошибка: данные заявки не найдены")
            return
        
        # Update post status in DB
        from services.db import db
        async with db.get_session() as session:
            success = await safe_update_post_status(session, post_id, 'approved')
            
            if not success:
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
        
        if not post_id or not user_id:
            await update.message.reply_text("❌ Ошибка: данные заявки не найдены")
            return
        
        # Update post status in DB
        from services.db import db
        async with db.get_session() as session:
            success = await safe_update_post_status(session, post_id, 'rejected')
            
            if not success:
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

# Оставляем старые функции для совместимости (могут использоваться в других местах)
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
    # Эта функция больше не используется, так как публикация происходит вручную
    logger.warning("publish_to_channel called but manual publication is now used")

async def publish_to_chat(bot, post):
    """Publish post to target CHAT - DEPRECATED"""
    # Эта функция больше не используется, так как публикация происходит вручную
    logger.warning("publish_to_chat called but manual publication is now used")
