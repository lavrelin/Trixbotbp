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
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Простая версия для Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start_command(update, context):
    keyboard = [
        [{"text": "🙅‍♂️ Будапешт - канал", "url": "https://t.me/snghu"}],
        [{"text": "🙅‍♀️ Будапешт - чат", "url": "https://t.me/tgchatxxx"}],
        [{"text": "🙅 Будапешт - каталог", "url": "https://t.me/trixvault"}],
        [{"text": "🕵️‍♂️ Куплю / Отдам / Продам", "url": "https://t.me/hungarytrade"}]
    ]
    
    text = """🗯️ *Добро пожаловать в TrixBot!*

*Трикс* – это гид навигатор по Будапешту и Венгрии.

*Наше сообщество:*
🙅‍♂️ *Канал* - основные публикации и новости
🙅‍♀️ *Чат* - живое общение и обсуждения
🙅 *Каталог* - список мастеров услуг
🕵️‍♂️ *Барахолка* - купля/продажа/обмен

⚡️ Быстро • 🎯 Удобно • 🔒 Безопасно"""
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    kb = []
    for row in keyboard:
        kb_row = []
        for btn in row:
            kb_row.append(InlineKeyboardButton(btn["text"], url=btn["url"]))
        kb.append(kb_row)
    
    await update.message.reply_text(
        text, 
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode='Markdown'
    )

async def id_command(update, context):
    user = update.effective_user
    chat = update.effective_chat
    
    text = f"""🆔 *Информация об ID:*

👤 Ваш ID: `{user.id}`
💬 ID чата: `{chat.id}`
📝 Тип чата: {chat.type}"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def trixlinks_command(update, context):
    text = """🔗 *ПОЛЕЗНЫЕ ССЫЛКИ TRIX:*

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

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("trixlinks", trixlinks_command))
    
    logger.info("Bot started")
    application.run_polling(allowed_updates=['message'])

if __name__ == "__main__":
    main()
