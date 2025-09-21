# -*- coding: utf-8 -*-
from telegram import Update
from telegram.ext import ContextTypes
from config import Config
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Импорты из data модулей
from data.games_data import (
    word_games, roll_games, user_attempts,
    get_game_version, can_attempt, record_attempt,
    normalize_word, start_word_game, stop_word_game,
    add_winner, get_unique_roll_number
)
from data.user_data import update_user_activity, is_user_banned, is_user_muted

logger = logging.getLogger(__name__)

# ============= ИГРА "УГАДАЙ СЛОВО" =============

class WordGame:
    def __init__(self):
        # Словари для каждой версии игры
        self.games_data = {
            'play3xia': {
                'words': {},  # {word: {'description': str, 'hints': [], 'media': []}}
                'current_word': None,
                'active': False,
                'winners': [],
                'attempts_interval': 60  # минуты
            },
            'play3x': {
                'words': {},
                'current_word': None,
                'active': False,
                'winners': [],
                'attempts_interval': 60
            },
            'playxxx': {
                'words': {},
                'current_word': None,
                'active': False,
                'winners': [],
                'attempts_interval': 60
            }
        }
        self.user_attempts = {}  # {user_id: {game_version: last_attempt_time}}

    def get_game_version(self, command: str) -> str:
        """Определяет версию игры по команде"""
        if command.startswith('/play3xia'):
            return 'play3xia'
        elif command.startswith('/play3x'):
            return 'play3x'
        elif command.startswith('/playxxx'):
            return 'playxxx'
        return 'play3xia'  # По умолчанию

    def can_attempt(self, user_id: int, game_version: str) -> bool:
        """Проверяет, может ли пользователь делать попытку"""
        if user_id not in self.user_attempts:
            return True
        
        if game_version not in self.user_attempts[user_id]:
            return True
        
        last_attempt = self.user_attempts[user_id][game_version]
        interval_minutes = self.games_data[game_version]['attempts_interval']
        
        return datetime.now() - last_attempt >= timedelta(minutes=interval_minutes)

    def record_attempt(self, user_id: int, game_version: str):
        """Записывает попытку пользователя"""
        if user_id not in self.user_attempts:
            self.user_attempts[user_id] = {}
        
        self.user_attempts[user_id][game_version] = datetime.now()

    def normalize_word(self, word: str) -> str:
        """Нормализует слово для сравнения"""
        return word.lower().strip().replace('ё', 'е')

# Глобальный экземпляр игры
word_game = WordGame()

# ============= КОМАНДЫ УПРАВЛЕНИЯ СЛОВАМИ (АДМИН) =============

async def wordadd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить новое слово"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 Использование: `/play3xiawordadd слово`\n"
            "Пример: `/play3xiawordadd Мост`",
            parse_mode='Markdown'
        )
        return
    
    command_text = update.message.text
    game_version = word_game.get_game_version(command_text)
    
    text = f"""🔧 **АДМИНСКИЕ ИГРОВЫЕ КОМАНДЫ {game_version.upper()}:**

**🎯 Управление словами:**
• `/{game_version}wordadd слово` – добавить слово
• `/{game_version}wordedit слово описание` – изменить
• `/{game_version}wordclear слово` – удалить слово
• `/{game_version}wordon` – запустить конкурс
• `/{game_version}wordoff` – завершить конкурс
• `/{game_version}wordinfoedit текст` – изменить описание
• `/{game_version}anstimeset минуты` – интервал попыток

**🎲 Управление розыгрышем:**
• `/{game_version}roll [1-5]` – провести розыгрыш
• `/{game_version}rollreset` – сбросить участников
• `/{game_version}rollstatus` – список участников

**👥 Пользовательские команды:**
• `/{game_version}say слово` – попытка угадать
• `/{game_version}wordinfo` – информация о конкурсе
• `/{game_version}roll 9999` – получить номер
• `/{game_version}mynumber` – проверить номер"""

    await update.message.reply_text(text, parse_mode='Markdown') word_game.get_game_version(command_text)
    word = context.args[0].lower()
    
    word_game.games_data[game_version]['words'][word] = {
        'description': f'Угадайте слово: {word}',
        'hints': [],
        'media': []
    }
    
    await update.message.reply_text(
        f"✅ **Слово добавлено в игру {game_version}:**\n\n"
        f"🎯 Слово: {word}\n"
        f"📝 Описание: {word_game.games_data[game_version]['words'][word]['description']}",
        parse_mode='Markdown'
    )

async def wordedit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактировать слово"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "📝 Использование: `/play3xiawordedit слово новое_описание`\n"
            "Пример: `/play3xiawordedit мост Знаменитый мост в Будапеште`",
            parse_mode='Markdown'
        )
        return
    
    command_text = update.message.text
    game_version = word_game.get_game_version(command_text)
    word = context.args[0].lower()
    new_description = ' '.join(context.args[1:])
    
    if word not in word_game.games_data[game_version]['words']:
        await update.message.reply_text(f"❌ Слово '{word}' не найдено в игре {game_version}")
        return
    
    word_game.games_data[game_version]['words'][word]['description'] = new_description
    
    await update.message.reply_text(
        f"✅ **Слово обновлено в игре {game_version}:**\n\n"
        f"🎯 Слово: {word}\n"
        f"📝 Новое описание: {new_description}",
        parse_mode='Markdown'
    )

async def wordclear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить слово"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/play3xiawordclear слово`", parse_mode='Markdown')
        return
    
    command_text = update.message.text
    game_version = word_game.get_game_version(command_text)
    word = context.args[0].lower()
    
    if word in word_game.games_data[game_version]['words']:
        del word_game.games_data[game_version]['words'][word]
        await update.message.reply_text(f"✅ Слово '{word}' удалено из игры {game_version}")
    else:
        await update.message.reply_text(f"❌ Слово '{word}' не найдено в игре {game_version}")

async def wordon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включить режим конкурса"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    command_text = update.message.text
    game_version = word_game.get_game_version(command_text)
    
    if not word_game.games_data[game_version]['words']:
        await update.message.reply_text(f"❌ Нет слов для игры {game_version}. Добавьте слова командой wordadd")
        return
    
    # Выбираем случайное слово
    available_words = list(word_game.games_data[game_version]['words'].keys())
    current_word = random.choice(available_words)
    
    word_game.games_data[game_version]['current_word'] = current_word
    word_game.games_data[game_version]['active'] = True
    word_game.games_data[game_version]['winners'] = []
    
    description = word_game.games_data[game_version]['words'][current_word]['description']
    
    await update.message.reply_text(
        f"🎮 **Конкурс {game_version} НАЧАЛСЯ!**\n\n"
        f"📝 {description}\n\n"
        f"🎯 Используйте команду `/{game_version}say слово` для участия\n"
        f"⏰ Интервал между попытками: {word_game.games_data[game_version]['attempts_interval']} минут",
        parse_mode='Markdown'
    )

async def wordoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выключить режим конкурса"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    command_text = update.message.text
    game_version = word_game.get_game_version(command_text)
    
    word_game.games_data[game_version]['active'] = False
    current_word = word_game.games_data[game_version]['current_word']
    winners = word_game.games_data[game_version]['winners']
    
    winner_text = ""
    if winners:
        winner_text = f"🏆 Победители: {', '.join([f'@{w}' for w in winners])}"
    else:
        winner_text = "🏆 Победителей не было"
    
    await update.message.reply_text(
        f"🛑 **Конкурс {game_version} ЗАВЕРШЕН!**\n\n"
        f"🎯 Слово было: {current_word or 'не выбрано'}\n"
        f"{winner_text}\n\n"
        f"📋 Конкурс пока что не активен. Ожидайте новый конкурс.",
        parse_mode='Markdown'
    )

async def anstimeset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Задать интервал между попытками"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("📝 Использование: `/play3xiaanstimeset 60` (в минутах)", parse_mode='Markdown')
        return
    
    command_text = update.message.text
    game_version = word_game.get_game_version(command_text)
    minutes = int(context.args[0])
    
    word_game.games_data[game_version]['attempts_interval'] = minutes
    
    await update.message.reply_text(
        f"✅ **Интервал обновлен для {game_version}:**\n\n"
        f"⏰ Новый интервал: {minutes} минут",
        parse_mode='Markdown'
    )

async def wordinfoedit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить описание конкурса (админ)"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/play3xiawordinfoedit новое описание`", parse_mode='Markdown')
        return
    
    command_text = update.message.text
    game_version = word_game.get_game_version(command_text)
    new_description = ' '.join(context.args)
    
    # Обновляем общее описание игры
    if 'description' not in word_game.games_data[game_version]:
        word_game.games_data[game_version]['description'] = new_description
    else:
        word_game.games_data[game_version]['description'] = new_description
    
    await update.message.reply_text(
        f"✅ **Описание {game_version} изменено:**\n\n{new_description}",
        parse_mode='Markdown'
    )

# ============= КОМАНДЫ ДЛЯ УЧАСТНИКОВ =============

async def game_say_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Попытка угадать слово"""
    if not context.args:
        await update.message.reply_text("📝 Использование: `/play3xiasay слово`", parse_mode='Markdown')
        return
    
    command_text = update.message.text
    game_version = word_game.get_game_version(command_text)
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    guess = context.args[0]
    
    # Обновляем активность пользователя
    update_user_activity(user_id, update.effective_user.username)
    
    # Проверяем бан и мут
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы заблокированы и не можете участвовать")
        return
    
    if is_user_muted(user_id):
        await update.message.reply_text("❌ Вы находитесь в муте")
        return
    
    # Проверяем, активна ли игра
    if not word_game.games_data[game_version]['active']:
        await update.message.reply_text(f"❌ Конкурс {game_version} неактивен")
        return
    
    # Проверяем интервал между попытками
    if not word_game.can_attempt(user_id, game_version):
        interval = word_game.games_data[game_version]['attempts_interval']
        await update.message.reply_text(
            f"⏰ Вы можете делать попытку раз в {interval} минут"
        )
        return
    
    # Записываем попытку
    word_game.record_attempt(user_id, game_version)
    
    current_word = word_game.games_data[game_version]['current_word']
    
    # Отправляем уведомление в группу модерации
    try:
        await context.bot.send_message(
            chat_id=Config.MODERATION_GROUP_ID,
            text=f"🎮 **Игровая попытка {game_version}:**\n\n"
                 f"👤 @{username} (ID: {user_id})\n"
                 f"🎯 Попытка: {guess}\n"
                 f"✅ Правильный ответ: {current_word}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending game notification: {e}")
    
    # Проверяем правильность ответа
    if word_game.normalize_word(guess) == word_game.normalize_word(current_word):
        # ПОБЕДА!
        word_game.games_data[game_version]['winners'].append(username)
        word_game.games_data[game_version]['active'] = False
        
        await update.message.reply_text(
            f"🎉 **ПОЗДРАВЛЯЕМ!**\n\n"
            f"@{username}, вы угадали слово '{current_word}' и стали победителем!\n\n"
            f"👑 Администратор свяжется с вами в ближайшее время."
        )
        
        # Уведомляем модераторов о победе
        try:
            await context.bot.send_message(
                chat_id=Config.MODERATION_GROUP_ID,
                text=f"🏆 **ПОБЕДИТЕЛЬ В ИГРЕ {game_version}!**\n\n"
                     f"👤 @{username} (ID: {user_id})\n"
                     f"🎯 Угадал слово: {current_word}\n\n"
                     f"Свяжитесь с победителем!",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending winner notification: {e}")
    
    else:
        # Неправильный ответ
        await update.message.reply_text(f"❌ Неправильно. Попробуйте еще раз через {word_game.games_data[game_version]['attempts_interval']} минут")

async def wordinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о текущем слове"""
    command_text = update.message.text
    game_version = word_game.get_game_version(command_text)
    
    if not word_game.games_data[game_version]['active']:
        # Показываем общую информацию о игре
        description = word_game.games_data[game_version].get('description', f"Конкурс {game_version} пока не активен")
        await update.message.reply_text(
            f"ℹ️ **Информация о {game_version}:**\n\n"
            f"📝 {description}",
            parse_mode='Markdown'
        )
        return
    
    current_word = word_game.games_data[game_version]['current_word']
    if current_word and current_word in word_game.games_data[game_version]['words']:
        description = word_game.games_data[game_version]['words'][current_word]['description']
        
        await update.message.reply_text(
            f"🎯 **Информация о текущем конкурсе {game_version}:**\n\n"
            f"📝 {description}\n\n"
            f"💡 Используйте `/{game_version}say слово` для участия",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Нет активного слова")

# ============= СИСТЕМА РОЗЫГРЫШЕЙ (RollGame) =============

class RollGame:
    def __init__(self):
        self.games_data = {
            'play3xia': {'participants': {}, 'active': True},
            'play3x': {'participants': {}, 'active': True},
            'playxxx': {'participants': {}, 'active': True}
        }
    
    def get_game_version(self, command: str) -> str:
        if command.startswith('/play3xia'):
            return 'play3xia'
        elif command.startswith('/play3x'):
            return 'play3x'
        elif command.startswith('/playxxx'):
            return 'playxxx'
        return 'play3xia'

roll_game = RollGame()

async def roll_participant_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить номер для участия в розыгрыше"""
    if not context.args or context.args[0] != '9999':
        await update.message.reply_text("📝 Использование: `/play3xiaroll 9999`", parse_mode='Markdown')
        return
    
    command_text = update.message.text
    game_version = roll_game.get_game_version(command_text)
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    
    # Обновляем активность пользователя
    update_user_activity(user_id, update.effective_user.username)
    
    # Проверяем бан и мут
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы заблокированы и не можете участвовать")
        return
    
    if is_user_muted(user_id):
        await update.message.reply_text("❌ Вы находитесь в муте")
        return
    
    # Проверяем, участвует ли уже пользователь
    if user_id in roll_game.games_data[game_version]['participants']:
        existing_number = roll_game.games_data[game_version]['participants'][user_id]['number']
        await update.message.reply_text(
            f"@{username}, у вас уже есть номер для розыгрыша: **{existing_number}**",
            parse_mode='Markdown'
        )
        return
    
    # Генерируем уникальный номер
    existing_numbers = [p['number'] for p in roll_game.games_data[game_version]['participants'].values()]
    
    while True:
        number = random.randint(1, 9999)
        if number not in existing_numbers:
            break
    
    # Сохраняем участника
    roll_game.games_data[game_version]['participants'][user_id] = {
        'username': username,
        'number': number,
        'joined_at': datetime.now()
    }
    
    await update.message.reply_text(
        f"@{username}, ваш номер для розыгрыша: **{number}**\n\n"
        f"🎲 Участников: {len(roll_game.games_data[game_version]['participants'])}",
        parse_mode='Markdown'
    )
    
    # Уведомляем модераторов
    try:
        await context.bot.send_message(
            chat_id=Config.MODERATION_GROUP_ID,
            text=f"🎲 **Новый участник розыгрыша {game_version}:**\n\n"
                 f"👤 @{username} (ID: {user_id})\n"
                 f"🔢 Номер: {number}\n"
                 f"📊 Всего участников: {len(roll_game.games_data[game_version]['participants'])}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending roll notification: {e}")

async def mynumber_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать свой номер в розыгрыше"""
    command_text = update.message.text
    game_version = roll_game.get_game_version(command_text)
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    
    if user_id not in roll_game.games_data[game_version]['participants']:
        await update.message.reply_text(
            f"@{username}, вы не участвуете в розыгрыше {game_version}\n"
            f"Используйте `/{game_version}roll 9999` для участия",
            parse_mode='Markdown'
        )
        return
    
    number = roll_game.games_data[game_version]['participants'][user_id]['number']
    await update.message.reply_text(f"@{username}, ваш номер: **{number}**", parse_mode='Markdown')

async def roll_draw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Провести розыгрыш (админ)"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("📝 Использование: `/play3xiaroll 3` (количество победителей 1-5)", parse_mode='Markdown')
        return
    
    command_text = update.message.text
    game_version = roll_game.get_game_version(command_text)
    winners_count = min(5, max(1, int(context.args[0])))
    
    participants = roll_game.games_data[game_version]['participants']
    
    if len(participants) < winners_count:
        await update.message.reply_text(
            f"❌ Недостаточно участников для {winners_count} победителей\n"
            f"Участников: {len(participants)}"
        )
        return
    
    # Генерируем случайное число
    winning_number = random.randint(1, 9999)
    
    # Находим ближайшие номера
    participants_list = [
        (user_id, data['username'], data['number'])
        for user_id, data in participants.items()
    ]
    
    # Сортируем по близости к выигрышному числу
    participants_list.sort(key=lambda x: abs(x[2] - winning_number))
    
    # Берем нужное количество победителей
    winners = participants_list[:winners_count]
    
    winners_text = []
    for user_id, username, number in winners:
        winners_text.append(f"@{username} ({number})")
    
    result_text = (
        f"🎉 **РЕЗУЛЬТАТЫ РОЗЫГРЫША {game_version.upper()}!**\n\n"
        f"🎲 Выигрышное число: **{winning_number}**\n\n"
        f"🏆 Победители:\n" + "\n".join([f"{i+1}. {w}" for i, w in enumerate(winners_text)]) +
        f"\n\n🎊 Поздравляем победителей!"
    )
    
    await update.message.reply_text(result_text, parse_mode='Markdown')

async def rollreset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить розыгрыш (админ)"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    command_text = update.message.text
    game_version = roll_game.get_game_version(command_text)
    
    participants_count = len(roll_game.games_data[game_version]['participants'])
    roll_game.games_data[game_version]['participants'] = {}
    
    await update.message.reply_text(
        f"✅ **Розыгрыш {game_version} сброшен!**\n\n"
        f"📊 Удалено участников: {participants_count}\n"
        f"🆕 Новый розыгрыш готов к запуску",
        parse_mode='Markdown'
    )

async def rollstatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статус розыгрыша (админ)"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    command_text = update.message.text
    game_version = roll_game.get_game_version(command_text)
    
    participants = roll_game.games_data[game_version]['participants']
    
    if not participants:
        await update.message.reply_text(f"📊 Розыгрыш {game_version}: нет участников")
        return
    
    text = f"📊 **Статус розыгрыша {game_version}:**\n\n"
    text += f"👥 Участников: {len(participants)}\n\n"
    text += "📋 **Список участников:**\n"
    
    for i, (user_id, data) in enumerate(participants.items(), 1):
        text += f"{i}. @{data['username']} – {data['number']}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ============= ИНФОРМАЦИОННЫЕ КОМАНДЫ =============

async def gamesinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация об игровых командах для пользователей"""
    command_text = update.message.text
    game_version = word_game.get_game_version(command_text)
    
    text = f"""🎮 **ИГРОВЫЕ КОМАНДЫ {game_version.upper()}:**

**🎯 Угадай слово:**
• `/{game_version}say слово` – попытка угадать
• `/{game_version}wordinfo` – подсказка о слове

**🎲 Розыгрыш номеров:**
• `/{game_version}roll 9999` – получить номер
• `/{game_version}mynumber` – мой номер

**ℹ️ Правила:**
• В игре "угадай слово" есть интервал между попытками
• В розыгрыше каждый получает уникальный номер 1-9999
• Победители определяются администраторами"""

    await update.message.reply_text(text, parse_mode='Markdown')

async def admgamesinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация об игровых командах для админов"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    command_text = update.message.text
    game_version =