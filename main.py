#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import random
from datetime import datetime, timedelta
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
ADMIN_IDS = [7811593067]  # ID админов
MODERATION_GROUP_ID = -1002734837434  # ID группы модерации

# ============= ИГРОВЫЕ ДАННЫЕ =============

# Система игры "Угадай слово"
word_games = {
    'play3xia': {'words': {}, 'current_word': None, 'active': False, 'winners': [], 'interval': 60},
    'play3x': {'words': {}, 'current_word': None, 'active': False, 'winners': [], 'interval': 60},
    'playxxx': {'words': {}, 'current_word': None, 'active': False, 'winners': [], 'interval': 60}
}

user_attempts = {}  # {user_id: {game_version: last_attempt_time}}

# Система розыгрыша номеров
roll_games = {
    'play3xia': {'participants': {}, 'active': True},
    'play3x': {'participants': {}, 'active': True},
    'playxxx': {'participants': {}, 'active': True}
}

# Ссылки
trix_links = [
    {'id': 1, 'name': 'Канал Будапешт', 'url': 'https://t.me/snghu', 'description': 'Основной канал сообщества'},
    {'id': 2, 'name': 'Чат Будапешт', 'url': 'https://t.me/tgchatxxx', 'description': 'Чат для общения'},
    {'id': 3, 'name': 'Каталог услуг', 'url': 'https://t.me/trixvault', 'description': 'Каталог специалистов'},
    {'id': 4, 'name': 'Барахолка', 'url': 'https://t.me/hungarytrade', 'description': 'Купля, продажа, обмен'}
]

# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

def get_game_version(command):
    """Определяет версию игры по команде"""
    if 'play3xia' in command:
        return 'play3xia'
    elif 'play3x' in command:
        return 'play3x'
    elif 'playxxx' in command:
        return 'playxxx'
    return 'play3xia'

def can_attempt(user_id, game_version):
    """Проверяет интервал между попытками"""
    if user_id not in user_attempts:
        return True
    if game_version not in user_attempts[user_id]:
        return True
    
    last_attempt = user_attempts[user_id][game_version]
    interval_minutes = word_games[game_version]['interval']
    return datetime.now() - last_attempt >= timedelta(minutes=interval_minutes)

def record_attempt(user_id, game_version):
    """Записывает попытку пользователя"""
    if user_id not in user_attempts:
        user_attempts[user_id] = {}
    user_attempts[user_id][game_version] = datetime.now()

def normalize_word(word):
    """Нормализует слово для сравнения"""
    return word.lower().strip().replace('ё', 'е')

# ============= БАЗОВЫЕ КОМАНДЫ =============

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

*Игры:* используйте команды с префиксами play3xia, play3x, playxxx
*Команды:* /admin для админов, /trixlinks для ссылок

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
    text = "🔗 **ПОЛЕЗНЫЕ ССЫЛКИ TRIX:**\n\n"
    
    for i, link in enumerate(trix_links, 1):
        text += f"{i}. **{link['name']}**\n"
        text += f"🔗 {link['url']}\n"
        text += f"📝 {link['description']}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def say_command(update, context):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📝 **Использование команды /say:**\n\n"
            "Формат: `/say получатель сообщение`\n\n"
            "**Примеры:**\n"
            "• `/say 123456789 Ваш пост опубликован`\n"
            "• `/say ID_123456789 Заявка отклонена`",
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
        
    except Exception as e:
        error_msg = str(e)
        if "bot was blocked" in error_msg:
            await update.message.reply_text(f"❌ Пользователь {target} заблокировал бота")
        else:
            await update.message.reply_text(f"❌ Ошибка отправки: {error_msg}")

async def admin_command(update, context):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    text = """🔧 **АДМИНСКИЕ КОМАНДЫ:**

**Основные:**
• `/say ID сообщение` - отправить сообщение пользователю
• `/id` - показать ID пользователя/чата
• `/trixlinks` - список полезных ссылок

**Игра "Угадай слово" (для всех версий play3xia, play3x, playxxx):**
• `/play3xiawordadd слово` - добавить слово
• `/play3xiawordon` - запустить конкурс
• `/play3xiawordoff` - завершить конкурс
• `/play3xiaanstimeset минуты` - интервал попыток

**Розыгрыш номеров:**
• `/play3xiaroll 3` - провести розыгрыш (1-5 победителей)
• `/play3xiarollreset` - сбросить участников
• `/play3xiarollstatus` - список участников

**Для пользователей доступны:**
• `/play3xiasay слово` - угадать слово
• `/play3xiaroll 9999` - получить номер розыгрыша"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ============= ИГРА "УГАДАЙ СЛОВО" =============

async def wordadd_command(update, context):
    """Добавить слово (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/play3xiawordadd слово`")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    word = context.args[0].lower()
    
    word_games[game_version]['words'][word] = {
        'description': f'Угадайте слово: {word}',
        'hints': []
    }
    
    await update.message.reply_text(
        f"✅ **Слово добавлено в игру {game_version}:**\n\n"
        f"🎯 Слово: {word}",
        parse_mode='Markdown'
    )

async def wordon_command(update, context):
    """Включить конкурс (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    
    if not word_games[game_version]['words']:
        await update.message.reply_text(f"❌ Нет слов для игры {game_version}")
        return
    
    # Выбираем случайное слово
    current_word = random.choice(list(word_games[game_version]['words'].keys()))
    word_games[game_version]['current_word'] = current_word
    word_games[game_version]['active'] = True
    word_games[game_version]['winners'] = []
    
    await update.message.reply_text(
        f"🎮 **Конкурс {game_version} НАЧАЛСЯ!**\n\n"
        f"🎯 Используйте команду `/{game_version}say слово` для участия\n"
        f"⏰ Интервал между попытками: {word_games[game_version]['interval']} минут",
        parse_mode='Markdown'
    )

async def wordoff_command(update, context):
    """Завершить конкурс (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    
    word_games[game_version]['active'] = False
    current_word = word_games[game_version]['current_word']
    
    await update.message.reply_text(
        f"🛑 **Конкурс {game_version} ЗАВЕРШЕН!**\n\n"
        f"🎯 Слово было: {current_word or 'не выбрано'}",
        parse_mode='Markdown'
    )

async def anstimeset_command(update, context):
    """Установить интервал попыток (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("📝 Использование: `/play3xiaanstimeset 60`")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    minutes = int(context.args[0])
    
    word_games[game_version]['interval'] = minutes
    
    await update.message.reply_text(
        f"✅ **Интервал обновлен для {game_version}: {minutes} минут**",
        parse_mode='Markdown'
    )

async def game_say_command(update, context):
    """Попытка угадать слово (пользователи)"""
    if not context.args:
        await update.message.reply_text("📝 Использование: `/play3xiasay слово`")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    guess = context.args[0]
    
    # Проверяем активность игры
    if not word_games[game_version]['active']:
        await update.message.reply_text(f"❌ Конкурс {game_version} неактивен")
        return
    
    # Проверяем интервал
    if not can_attempt(user_id, game_version):
        interval = word_games[game_version]['interval']
        await update.message.reply_text(f"⏰ Попытка раз в {interval} минут")
        return
    
    record_attempt(user_id, game_version)
    current_word = word_games[game_version]['current_word']
    
    # Уведомляем модераторов
    try:
        await context.bot.send_message(
            chat_id=MODERATION_GROUP_ID,
            text=f"🎮 **Игровая попытка {game_version}:**\n\n"
                 f"👤 @{username} (ID: {user_id})\n"
                 f"🎯 Попытка: {guess}\n"
                 f"✅ Правильный ответ: {current_word}",
            parse_mode='Markdown'
        )
    except:
        pass
    
    # Проверяем ответ
    if normalize_word(guess) == normalize_word(current_word):
        word_games[game_version]['winners'].append(username)
        word_games[game_version]['active'] = False
        
        await update.message.reply_text(
            f"🎉 **ПОЗДРАВЛЯЕМ!**\n\n"
            f"@{username}, вы угадали слово '{current_word}' и стали победителем!\n\n"
            f"👑 Администратор свяжется с вами в ближайшее время."
        )
        
        # Уведомляем модераторов о победе
        try:
            await context.bot.send_message(
                chat_id=MODERATION_GROUP_ID,
                text=f"🏆 **ПОБЕДИТЕЛЬ В ИГРЕ {game_version}!**\n\n"
                     f"👤 @{username} (ID: {user_id})\n"
                     f"🎯 Угадал слово: {current_word}",
                parse_mode='Markdown'
            )
        except:
            pass
    else:
        await update.message.reply_text(f"❌ Неправильно. Следующая попытка через {word_games[game_version]['interval']} минут")

# ============= РОЗЫГРЫШ НОМЕРОВ =============

async def roll_command(update, context):
    """Команда /roll - для участника или админа"""
    user_id = update.effective_user.id
    command_text = update.message.text
    game_version = get_game_version(command_text)
    
    # Если админ с числом 1-5 = проведение розыгрыша
    if (user_id in ADMIN_IDS and context.args and 
        len(context.args) == 1 and context.args[0].isdigit() and 
        1 <= int(context.args[0]) <= 5):
        
        winners_count = int(context.args[0])
        participants = roll_games[game_version]['participants']
        
        if len(participants) < winners_count:
            await update.message.reply_text(
                f"❌ Недостаточно участников для {winners_count} победителей\n"
                f"Участников: {len(participants)}"
            )
            return
        
        # Генерируем выигрышное число
        winning_number = random.randint(1, 9999)
        
        # Находим ближайшие номера
        participants_list = [(data['username'], data['number']) for data in participants.values()]
        participants_list.sort(key=lambda x: abs(x[1] - winning_number))
        
        winners = participants_list[:winners_count]
        winners_text = [f"@{username} ({number})" for username, number in winners]
        
        result_text = (
            f"🎉 **РЕЗУЛЬТАТЫ РОЗЫГРЫША {game_version.upper()}!**\n\n"
            f"🎲 Выигрышное число: **{winning_number}**\n\n"
            f"🏆 Победители:\n" + "\n".join([f"{i+1}. {w}" for i, w in enumerate(winners_text)]) +
            f"\n\n🎊 Поздравляем победителей!"
        )
        
        await update.message.reply_text(result_text)
        return
    
    # Если пользователь с "9999" = получение номера
    if not context.args or context.args[0] != '9999':
        await update.message.reply_text("📝 Использование: `/play3xiaroll 9999`")
        return
    
    username = update.effective_user.username or f"ID_{user_id}"
    
    # Проверяем участие
    if user_id in roll_games[game_version]['participants']:
        existing_number = roll_games[game_version]['participants'][user_id]['number']
        await update.message.reply_text(
            f"@{username}, у вас уже есть номер: **{existing_number}**"
        )
        return
    
    # Генерируем уникальный номер
    existing_numbers = [p['number'] for p in roll_games[game_version]['participants'].values()]
    
    while True:
        number = random.randint(1, 9999)
        if number not in existing_numbers:
            break
    
    roll_games[game_version]['participants'][user_id] = {
        'username': username,
        'number': number,
        'joined_at': datetime.now()
    }
    
    await update.message.reply_text(
        f"@{username}, ваш номер для розыгрыша: **{number}**\n\n"
        f"🎲 Участников: {len(roll_games[game_version]['participants'])}"
    )
    
    # Уведомляем модераторов
    try:
        await context.bot.send_message(
            chat_id=MODERATION_GROUP_ID,
            text=f"🎲 **Новый участник розыгрыша {game_version}:**\n\n"
                 f"👤 @{username} (ID: {user_id})\n"
                 f"🔢 Номер: {number}",
            parse_mode='Markdown'
        )
    except:
        pass

async def mynumber_command(update, context):
    """Показать свой номер"""
    command_text = update.message.text
    game_version = get_game_version(command_text)
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    
    if user_id not in roll_games[game_version]['participants']:
        await update.message.reply_text(
            f"@{username}, вы не участвуете в розыгрыше {game_version}\n"
            f"Используйте `/{game_version}roll 9999` для участия"
        )
        return
    
    number = roll_games[game_version]['participants'][user_id]['number']
    await update.message.reply_text(f"@{username}, ваш номер: **{number}**")

async def rollreset_command(update, context):
    """Сбросить розыгрыш (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    
    participants_count = len(roll_games[game_version]['participants'])
    roll_games[game_version]['participants'] = {}
    
    await update.message.reply_text(
        f"✅ **Розыгрыш {game_version} сброшен!**\n\n"
        f"📊 Удалено участников: {participants_count}"
    )

async def rollstatus_command(update, context):
    """Статус розыгрыша (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    participants = roll_games[game_version]['participants']
    
    if not participants:
        await update.message.reply_text(f"📊 Розыгрыш {game_version}: нет участников")
        return
    
    text = f"📊 **Статус розыгрыша {game_version}:**\n\nУчастников: {len(participants)}\n\n"
    
    for i, (user_id, data) in enumerate(participants.items(), 1):
        text += f"{i}. @{data['username']} – {data['number']}\n"
    
    await update.message.reply_text(text)

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Базовые команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("trixlinks", trixlinks_command))
    application.add_handler(CommandHandler("say", say_command))
    application.add_handler(CommandHandler("admin", admin_command))
    
    # Игровые команды - play3xia
    application.add_handler(CommandHandler("play3xiawordadd", wordadd_command))
    application.add_handler(CommandHandler("play3xiawordon", wordon_command))
    application.add_handler(CommandHandler("play3xiawordoff", wordoff_command))
    application.add_handler(CommandHandler("play3xiaanstimeset", anstimeset_command))
    application.add_handler(CommandHandler("play3xiasay", game_say_command))
    application.add_handler(CommandHandler("play3xiaroll", roll_command))
    application.add_handler(CommandHandler("play3xiamynumber", mynumber_command))
    application.add_handler(CommandHandler("play3xiarollreset", rollreset_command))
    application.add_handler(CommandHandler("play3xiarollstatus", rollstatus_command))
    
    # Игровые команды - play3x
    application.add_handler(CommandHandler("play3xwordadd", wordadd_command))
    application.add_handler(CommandHandler("play3xwordon", wordon_command))
    application.add_handler(CommandHandler("play3xwordoff", wordoff_command))
    application.add_handler(CommandHandler("play3xanstimeset", anstimeset_command))
    application.add_handler(CommandHandler("play3xsay", game_say_command))
    application.add_handler(CommandHandler("play3xroll", roll_command))
    application.add_handler(CommandHandler("play3xmynumber", mynumber_command))
    application.add_handler(CommandHandler("play3xrollreset", rollreset_command))
    application.add_handler(CommandHandler("play3xrollstatus", rollstatus_command))
    
    # Игровые команды - playxxx
    application.add_handler(CommandHandler("playxxxwordadd", wordadd_command))
    application.add_handler(CommandHandler("playxxxwordon", wordon_command))
    application.add_handler(CommandHandler("playxxxwordoff", wordoff_command))
    application.add_handler(CommandHandler("playxxxanstimeset", anstimeset_command))
    application.add_handler(CommandHandler("playxxxsay", game_say_command))
    application.add_handler(CommandHandler("playxxxroll", roll_command))
    application.add_handler(CommandHandler("playxxxmynumber", mynumber_command))
    application.add_handler(CommandHandler("playxxxrollreset", rollreset_command))
    application.add_handler(CommandHandler("playxxxrollstatus", rollstatus_command))
    
    logger.info("Bot with games started successfully")
    application.run_polling(allowed_updates=['message'])

if __name__ == "__main__":
    main()
