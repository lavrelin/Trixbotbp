# Добавьте эти функции в handlers/admin_handler.py или создайте отдельный файл

from telegram import Update
from telegram.ext import ContextTypes
from config import Config
import logging
import re

logger = logging.getLogger(__name__)

async def say_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /say command for moderators to send messages to users"""
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь модератором
    if not Config.is_moderator(user_id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    # Получаем текст команды
    command_text = update.message.text
    
    # Парсим команду: /say @username или /say ID сообщение
    # Поддерживаемые форматы:
    # /say @username Ваш пост опубликован
    # /say 123456789 Ваш пост опубликован
    # /say ID_123456789 Ваш пост опубликован
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📝 **Использование команды /say:**\n\n"
            "Формат: `/say @username сообщение` или `/say user_id сообщение`\n\n"
            "**Примеры:**\n"
            "• `/say @john Ваш пост опубликован`\n"
            "• `/say 123456789 Ваша заявка отклонена`\n"
            "• `/say ID_123456789 Пост находится на модерации`\n\n"
            "Сообщение будет отправлено от имени бота.",
            parse_mode='Markdown'
        )
        return
    
    target = context.args[0]
    message = ' '.join(context.args[1:])
    
    # Определяем целевого пользователя
    target_user_id = None
    
    if target.startswith('@'):
        # Формат @username - нужно найти пользователя в БД
        username = target[1:]  # убираем @
        target_user_id = await get_user_id_by_username(username)
        
        if not target_user_id:
            await update.message.reply_text(
                f"❌ Пользователь @{username} не найден в базе данных.\n"
                f"Используйте числовой ID вместо username."
            )
            return
            
    elif target.startswith('ID_'):
        # Формат ID_123456789
        try:
            target_user_id = int(target[3:])  # убираем ID_
        except ValueError:
            await update.message.reply_text("❌ Некорректный формат ID")
            return
            
    elif target.isdigit():
        # Формат 123456789
        target_user_id = int(target)
        
    else:
        await update.message.reply_text(
            "❌ Некорректный формат получателя.\n"
            "Используйте: @username, ID_123456789 или 123456789"
        )
        return
    
    # Отправляем сообщение
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"📢 **Сообщение от модератора:**\n\n{message}",
            parse_mode='Markdown'
        )
        
        await update.message.reply_text(
            f"✅ **Сообщение отправлено!**\n\n"
            f"📤 Получатель: {target}\n"
            f"📝 Текст: {message[:100]}{'...' if len(message) > 100 else ''}",
            parse_mode='Markdown'
        )
        
        logger.info(f"Moderator {user_id} sent message to {target_user_id}: {message[:50]}...")
        
    except Exception as e:
        error_msg = str(e)
        
        if "Forbidden: bot was blocked by the user" in error_msg:
            await update.message.reply_text(
                f"❌ Не удалось отправить сообщение пользователю {target}\n"
                f"Причина: Пользователь заблокировал бота"
            )
        elif "Bad Request: chat not found" in error_msg:
            await update.message.reply_text(
                f"❌ Пользователь {target} не найден\n"
                f"Возможно, он никогда не запускал бота"
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка отправки сообщения: {error_msg}"
            )
        
        logger.error(f"Error sending message from moderator {user_id} to {target_user_id}: {e}")

async def get_user_id_by_username(username: str) -> int | None:
    """Найти ID пользователя по username"""
    try:
        from services.db import db
        from models import User
        from sqlalchemy import select
        
        async with db.get_session() as session:
            result = await session.execute(
                select(User.id).where(User.username == username)
            )
            user_id = result.scalar_one_or_none()
            return user_id
            
    except Exception as e:
        logger.error(f"Error finding user by username {username}: {e}")
        return None

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command for sending messages to multiple users"""
    user_id = update.effective_user.id
    
    # Только админы могут использовать broadcast
    if not Config.is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 **Использование команды /broadcast:**\n\n"
            "Формат: `/broadcast сообщение`\n\n"
            "**Пример:**\n"
            "• `/broadcast Техническое обслуживание бота завтра в 10:00`\n\n"
            "⚠️ Сообщение будет отправлено ВСЕМ пользователям бота!",
            parse_mode='Markdown'
        )
        return
    
    message = ' '.join(context.args)
    
    # Подтверждение перед рассылкой
    await update.message.reply_text(
        f"⚠️ **ВНИМАНИЕ!**\n\n"
        f"Вы собираетесь отправить рассылку всем пользователям:\n\n"
        f"📝 **Текст:** {message}\n\n"
        f"Для подтверждения отправьте: `/confirm_broadcast`\n"
        f"Для отмены: любое другое сообщение",
        parse_mode='Markdown'
    )
    
    # Сохраняем сообщение для подтверждения
    context.user_data['pending_broadcast'] = message

async def confirm_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and execute broadcast"""
    user_id = update.effective_user.id
    
    if not Config.is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    message = context.user_data.get('pending_broadcast')
    
    if not message:
        await update.message.reply_text("❌ Нет ожидающей рассылки. Используйте сначала /broadcast")
        return
    
    # Очищаем pending сообщение
    context.user_data.pop('pending_broadcast', None)
    
    try:
        from services.db import db
        from models import User
        from sqlalchemy import select
        
        sent_count = 0
        failed_count = 0
        
        async with db.get_session() as session:
            result = await session.execute(select(User.id))
            user_ids = [row[0] for row in result.fetchall()]
        
        await update.message.reply_text(
            f"📤 Начинаю рассылку для {len(user_ids)} пользователей..."
        )
        
        for target_user_id in user_ids:
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"📢 **Объявление:**\n\n{message}",
                    parse_mode='Markdown'
                )
                sent_count += 1
                
                # Небольшая пауза чтобы не превысить лимиты API
                if sent_count % 20 == 0:
                    import asyncio
                    await asyncio.sleep(1)
                    
            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to send broadcast to {target_user_id}: {e}")
        
        await update.message.reply_text(
            f"✅ **Рассылка завершена!**\n\n"
            f"📤 Отправлено: {sent_count}\n"
            f"❌ Не удалось: {failed_count}\n"
            f"📊 Всего пользователей: {len(user_ids)}",
            parse_mode='Markdown'
        )
        
        logger.info(f"Broadcast completed by admin {user_id}: {sent_count}/{len(user_ids)} sent")
        
    except Exception as e:
        logger.error(f"Error in broadcast: {e}")
        await update.message.reply_text("❌ Ошибка при выполнении рассылки")
