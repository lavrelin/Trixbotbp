#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler,
    filters
)
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start_command(update, context):
    keyboard = [
        [InlineKeyboardButton("🙅‍♂️ Будапешт - канал", url="https://t.me/snghu")],
        [InlineKeyboardButton("🙅‍♀️ Будапешт - чат", url="https://t.me/tgchatxxx")],
        [InlineKeyboardButton("🙅 Будапешт - каталог", url="https://t.me/trixvault")],
        [InlineKeyboardButton("🕵️‍♂️ Куплю / Отдам / Продам", url="https://t.me/hungarytrade")]
    ]
    
    text = """🗯️ *Добро пожаловать в TrixBot!*

*Трикс* – это гид навигатор по Будапешту и Венгрии.

*Наше сообщество:*
🙅‍♂️ *Канал* - основные публикации и новости
🙅‍♀️ *Чат* - живое общение и обсуждения
🙅 *Каталог* - список мастеров услуг
🕵️‍♂️ *Барахолка* - купля/продажа/обмен

⚡️ Быстро • 🎯 Удобно • 🔒 Безопасно"""
    
    await update.message.reply_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def id_command(update, context):
    user = update.effective_user
    chat = update.effective_chat
    
    text = f"""🆔 **Информация об ID:**

👤 Ваш ID: `{user.id}`"""
    
    if chat.type != 'private':
        text += f"""
💬 ID чата: `{chat.id}`
📝 Тип чата: {chat.type}"""
        
        if chat.title:
            text += f"""
🏷️ Название: {chat.title}"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def trixlinks_command(update, context):
    text = """🔗 **ПОЛЕЗНЫЕ ССЫЛКИ TRIX:**

1. **Канал Будапешт**
🔗 https://t.me/snghu
📝 Основной канал сообщества Будапешта

2. **Чат Будапешт**  
🔗 https://t.me/tgchatxxx
📝 Чат для общения участников сообщества

3. **Каталог услуг**
🔗 https://t.me/trixvault  
📝 Каталог услуг и специалистов Будапешта

4. **Барахолка**
🔗 https://t.me/hungarytrade
📝 Купля, продажа, обмен товаров"""

    await update.message.reply_text(text, parse_mode='Markdown')

async def say_command(update, context):
    user_id = update.effective_user.id
    
    # Проверяем админа (замените на ваш ID)
    ADMIN_IDS = [7811593067]  # Добавьте ваши ID админов
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📝 **Использование команды /say:**\n\n"
            "Формат: `/say получатель сообщение`\n\n"
            "**Примеры:**\n"
            "• `/say @john Ваш пост опубликован`\n"
            "• `/say 123456789 Ваша заявка отклонена`\n"
            "• `/say ID_123456789 Пост находится на модерации`",
            parse_mode='Markdown'
        )
        return
    
    target = context.args[0]
    message = ' '.join(context.args[1:])
    
    target_user_id = None
    
    if target.startswith('ID_'):
        try:
            target_user_id = int(target[3:])
        except ValueError:
            await update.message.reply_text("❌ Некорректный формат ID")
            return
    elif target.isdigit():
        target_user_id = int(target)
    else:
        await update.message.reply_text("❌ Используйте числовой ID или формат ID_123456789")
        return
    
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
        
        logger.info(f"Admin {user_id} sent message to {target_user_id}")
        
    except Exception as e:
        error_msg = str(e)
        if "bot was blocked" in error_msg:
            await update.message.reply_text(f"❌ Пользователь {target} заблокировал бота")
        elif "chat not found" in error_msg:
            await update.message.reply_text(f"❌ Пользователь {target} не найден")
        else:
            await update.message.reply_text(f"❌ Ошибка отправки: {error_msg}")

async def admin_command(update, context):
    user_id = update.effective_user.id
    ADMIN_IDS = [7811593067]  # Добавьте ваши ID админов
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    text = """🔧 **АДМИНСКИЕ КОМАНДЫ:**

• `/say ID сообщение` - отправить сообщение пользователю
• `/id` - показать ID пользователя/чата  
• `/trixlinks` - список полезных ссылок
• `/admin` - эта панель

**Примеры:**
• `/say 123456789 Ваш пост опубликован`
• `/say ID_123456789 Заявка отклонена`"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("trixlinks", trixlinks_command))
    application.add_handler(CommandHandler("say", say_command))
    application.add_handler(CommandHandler("admin", admin_command))
    
    logger.info("Bot started successfully")
    application.run_polling(allowed_updates=['message'])

if __name__ == "__main__":
    main()
