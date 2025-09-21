#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import random
import asyncio
import json
from datetime import datetime, timedelta
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler,
    filters
)
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ChatMember
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
    'play3xia': {
        'words': {}, 
        'current_word': None, 
        'active': False, 
        'winners': [], 
        'interval': 60,
        'description': 'Конкурс пока не активен',
        'media_url': None
    },
    'play3x': {
        'words': {}, 
        'current_word': None, 
        'active': False, 
        'winners': [], 
        'interval': 60,
        'description': 'Конкурс пока не активен',
        'media_url': None
    },
    'playxxx': {
        'words': {}, 
        'current_word': None, 
        'active': False, 
        'winners': [], 
        'interval': 60,
        'description': 'Конкурс пока не активен',
        'media_url': None
    }
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

# Участники розыгрыша (основной)
lottery_participants = {}

# Пользователи ожидающие ввода для ссылок
waiting_users = {}

# Данные пользователей для статистики
user_data = {}  # {user_id: {username, join_date, last_activity, message_count, banned, muted_until}}

# Настройки чата
chat_settings = {
    'slowmode': 0,
    'antiinvite': False,
    'lockdown': False,
    'flood_limit': 0
}

# Автопостинг
autopost_data = {
    'enabled': False,
    'message': '',
    'interval': 3600,  # в секундах
    'last_post': None
}

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

def update_user_activity(user_id, username=None):
    """Обновляет активность пользователя"""
    if user_id not in user_data:
        user_data[user_id] = {
            'username': username or f'ID_{user_id}',
            'join_date': datetime.now(),
            'last_activity': datetime.now(),
            'message_count': 0,
            'banned': False,
            'muted_until': None
        }
    else:
        user_data[user_id]['last_activity'] = datetime.now()
        if username:
            user_data[user_id]['username'] = username
    
    user_data[user_id]['message_count'] += 1

def is_user_banned(user_id):
    """Проверяет забанен ли пользователь"""
    return user_data.get(user_id, {}).get('banned', False)

def is_user_muted(user_id):
    """Проверяет замучен ли пользователь"""
    if user_id not in user_data:
        return False
    
    muted_until = user_data[user_id].get('muted_until')
    if not muted_until:
        return False
    
    if datetime.now() < muted_until:
        return True
    else:
        user_data[user_id]['muted_until'] = None
        return False

def parse_time(time_str):
    """Парсит время в формате 10m, 1h, 1d"""
    if not time_str:
        return None
    
    time_str = time_str.lower()
    multiplier = 1
    
    if time_str.endswith('m'):
        multiplier = 60
        time_str = time_str[:-1]
    elif time_str.endswith('h'):
        multiplier = 3600
        time_str = time_str[:-1]
    elif time_str.endswith('d'):
        multiplier = 86400
        time_str = time_str[:-1]
    
    try:
        return int(time_str) * multiplier
    except ValueError:
        return None

async def check_user_membership(context, user_id):
    """Проверяет членство пользователя в группе"""
    try:
        member = await context.bot.get_chat_member(chat_id=MODERATION_GROUP_ID, user_id=user_id)
        return member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except:
        return False

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

*Команды:* /admin, /trixlinks, /join, /participants, /report
*Игры:* play3xia, play3x, playxxx (см. /admin для списка)

⚡️ Быстро • 🎯 Удобно • 🔒 Безопасно"""
    
    user = update.effective_user
    update_user_activity(user.id, user.username)
    
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
    
    update_user_activity(user.id, user.username)
    await update.message.reply_text(text, parse_mode='Markdown')

async def whois_command(update, context):
    """Информация о пользователе (модераторы)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/whois @username` или `/whois ID`", parse_mode='Markdown')
        return
    
    target = context.args[0]
    
    if target.startswith('@'):
        target = target[1:]
        # Поиск по username
        target_id = None
        for uid, data in user_data.items():
            if data['username'].lower() == target.lower():
                target_id = uid
                break
        
        if target_id:
            data = user_data[target_id]
            text = f"""👤 **Информация о @{target}:**

🆔 ID: `{target_id}`
📅 Присоединился: {data['join_date'].strftime('%d.%m.%Y %H:%M')}
⏰ Последняя активность: {data['last_activity'].strftime('%d.%m.%Y %H:%M')}
💬 Сообщений: {data['message_count']}
🚫 Статус бана: {'Забанен' if data.get('banned') else 'Активен'}
🔇 Мут: {'Да' if is_user_muted(target_id) else 'Нет'}"""
        else:
            text = f"❌ Пользователь @{target} не найден в базе данных"
            
    elif target.isdigit():
        user_id = int(target)
        if user_id in user_data:
            data = user_data[user_id]
            text = f"""👤 **Информация о пользователе:**

🆔 ID: `{user_id}`
👤 Username: @{data['username']}
📅 Присоединился: {data['join_date'].strftime('%d.%m.%Y %H:%M')}
⏰ Последняя активность: {data['last_activity'].strftime('%d.%m.%Y %H:%M')}
💬 Сообщений: {data['message_count']}
🚫 Статус бана: {'Забанен' if data.get('banned') else 'Активен'}
🔇 Мут: {'Да' if is_user_muted(user_id) else 'Нет'}"""
        else:
            text = f"❌ Пользователь с ID {user_id} не найден в базе данных"
    else:
        text = "❌ Некорректный формат. Используйте @username или ID"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def join_command(update, context):
    """Присоединиться к розыгрышу"""
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    
    update_user_activity(user_id, update.effective_user.username)
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы заблокированы и не можете участвовать")
        return
    
    if user_id in lottery_participants:
        await update.message.reply_text(f"🎲 @{username}, вы уже участвуете в розыгрыше!")
        return
    
    lottery_participants[user_id] = {
        'username': username,
        'joined_at': datetime.now()
    }
    
    await update.message.reply_text(
        f"🎉 @{username}, вы успешно присоединились к розыгрышу!\n"
        f"👥 Участников: {len(lottery_participants)}"
    )

async def participants_command(update, context):
    """Список участников розыгрыша"""
    if not lottery_participants:
        await update.message.reply_text("🎲 Пока нет участников розыгрыша")
        return
    
    text = f"👥 **Участники розыгрыша ({len(lottery_participants)}):**\n\n"
    
    for i, (user_id, data) in enumerate(lottery_participants.items(), 1):
        text += f"{i}. @{data['username']}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def report_command(update, context):
    """Пожаловаться на пользователя"""
    if not context.args:
        await update.message.reply_text("📝 Использование: `/report @username причина`", parse_mode='Markdown')
        return
    
    target = context.args[0]
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "Не указана"
    
    reporter = update.effective_user
    update_user_activity(reporter.id, reporter.username)
    
    report_text = (
        f"🚨 **Новая жалоба:**\n\n"
        f"👤 От: @{reporter.username or 'без_username'} (ID: {reporter.id})\n"
        f"🎯 На: {target}\n"
        f"📝 Причина: {reason}\n"
        f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    try:
        await context.bot.send_message(
            chat_id=MODERATION_GROUP_ID,
            text=report_text,
            parse_mode='Markdown'
        )
        
        await update.message.reply_text(
            "✅ **Жалоба отправлена!**\n\nМодераторы рассмотрят вашу жалобу в ближайшее время.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text("❌ Ошибка отправки жалобы")

async def trixlinks_command(update, context):
    text = "🔗 **ПОЛЕЗНЫЕ ССЫЛКИ TRIX:**\n\n"
    
    for i, link in enumerate(trix_links, 1):
        text += f"{i}. **{link['name']}**\n"
        text += f"🔗 {link['url']}\n"
        text += f"📝 {link['description']}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def trixlinksadd_command(update, context):
    """Добавить ссылку (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "📝 **Использование:**\n"
            "`/trixlinksadd \"название\" \"описание\"`\n\n"
            "После этого отправьте ссылку следующим сообщением.",
            parse_mode='Markdown'
        )
        return
    
    name = context.args[0].strip('"')
    description = ' '.join(context.args[1:]).strip('"')
    
    waiting_users[update.effective_user.id] = {
        'action': 'add_link',
        'name': name,
        'description': description
    }
    
    await update.message.reply_text(
        f"✅ **Данные сохранены:**\n\n"
        f"📝 Название: {name}\n"
        f"📋 Описание: {description}\n\n"
        f"🔗 **Теперь отправьте ссылку следующим сообщением.**",
        parse_mode='Markdown'
    )

async def trixlinksedit_command(update, context):
    """Редактировать ссылку (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args or not context.args[0].isdigit():
        text = "📝 **РЕДАКТИРОВАНИЕ ССЫЛОК**\n\nИспользуйте: `/trixlinksedit ID`\n\n**Доступные ссылки:**\n"
        for link in trix_links:
            text += f"{link['id']}. {link['name']}\n"
        await update.message.reply_text(text, parse_mode='Markdown')
        return
    
    link_id = int(context.args[0])
    link_to_edit = next((link for link in trix_links if link['id'] == link_id), None)
    
    if not link_to_edit:
        await update.message.reply_text(f"❌ Ссылка с ID {link_id} не найдена")
        return
    
    waiting_users[update.effective_user.id] = {
        'action': 'edit_link',
        'link_id': link_id
    }
    
    await update.message.reply_text(
        f"📝 **Редактирование ссылки ID {link_id}:**\n\n"
        f"Текущие данные:\n"
        f"📝 Название: {link_to_edit['name']}\n"
        f"📋 Описание: {link_to_edit['description']}\n"
        f"🔗 Ссылка: {link_to_edit['url']}\n\n"
        f"**Отправьте новые данные в формате:**\n"
        f"`название | описание | ссылка`",
        parse_mode='Markdown'
    )

async def trixlinksdelete_command(update, context):
    """Удалить ссылку (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args or not context.args[0].isdigit():
        text = "🗑️ **УДАЛЕНИЕ ССЫЛОК**\n\nИспользуйте: `/trixlinksdelete ID`\n\n**Доступные ссылки:**\n"
        for link in trix_links:
            text += f"{link['id']}. {link['name']}\n"
        await update.message.reply_text(text, parse_mode='Markdown')
        return
    
    link_id = int(context.args[0])
    
    for i, link in enumerate(trix_links):
        if link['id'] == link_id:
            deleted_link = trix_links.pop(i)
            await update.message.reply_text(
                f"✅ **Ссылка удалена:**\n\n"
                f"📝 Название: {deleted_link['name']}\n"
                f"🔗 URL: {deleted_link['url']}",
                parse_mode='Markdown'
            )
            return
    
    await update.message.reply_text(f"❌ Ссылка с ID {link_id} не найдена")

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

# ============= МОДЕРАЦИОННЫЕ КОМАНДЫ =============

async def ban_command(update, context):
    """Заблокировать пользователя"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/ban @username причина`", parse_mode='Markdown')
        return
    
    target = context.args[0]
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "Не указана"
    
    # Поиск пользователя
    target_id = None
    if target.startswith('@'):
        username = target[1:]
        for uid, data in user_data.items():
            if data['username'].lower() == username.lower():
                target_id = uid
                break
    elif target.isdigit():
        target_id = int(target)
    
    if target_id and target_id in user_data:
        user_data[target_id]['banned'] = True
        
        await update.message.reply_text(
            f"🚫 **Пользователь заблокирован:**\n\n"
            f"👤 Пользователь: {target}\n"
            f"📝 Причина: {reason}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode='Markdown'
        )
        
        # Уведомляем модераторов
        try:
            await context.bot.send_message(
                chat_id=MODERATION_GROUP_ID,
                text=f"🚫 **Пользователь забанен:**\n\n"
                     f"👤 {target} (ID: {target_id})\n"
                     f"📝 Причина: {reason}\n"
                     f"👮‍♂️ Модератор: @{update.effective_user.username}",
                parse_mode='Markdown'
            )
        except:
            pass
    else:
        await update.message.reply_text("❌ Пользователь не найден")

async def unmute_command(update, context):
    """Снять мут с пользователя"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/unmute @username`", parse_mode='Markdown')
        return
    
    target = context.args[0]
    
    # Поиск пользователя
    target_id = None
    if target.startswith('@'):
        username = target[1:]
        for uid, data in user_data.items():
            if data['username'].lower() == username.lower():
                target_id = uid
                break
    elif target.isdigit():
        target_id = int(target)
    
    if target_id and target_id in user_data:
        user_data[target_id]['muted_until'] = None
        
        await update.message.reply_text(
            f"🔊 **Мут снят:**\n\n"
            f"👤 Пользователь: {target}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Пользователь не найден")

async def banlist_command(update, context):
    """Список забаненных пользователей"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    banned_users = [data for data in user_data.values() if data.get('banned')]
    
    if not banned_users:
        await update.message.reply_text("📝 **Забаненных пользователей нет**")
        return
    
    text = f"🚫 **Забаненные пользователи ({len(banned_users)}):**\n\n"
    
    for i, user in enumerate(banned_users, 1):
        text += f"{i}. @{user['username']}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def stats_command(update, context):
    """Статистика чата"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    total_users = len(user_data)
    active_users = sum(1 for data in user_data.values() if 
                      datetime.now() - data['last_activity'] <= timedelta(days=1))
    total_messages = sum(data['message_count'] for data in user_data.values())
    banned_count = sum(1 for data in user_data.values() if data.get('banned'))
    
    text = f"""📊 **Статистика чата:**

👥 Всего пользователей: {total_users}
🟢 Активных за сутки: {active_users}
💬 Всего сообщений: {total_messages}
🚫 Забанено: {banned_count}
📅 Дата сбора: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def top_command(update, context):
    """Топ активных пользователей"""
    if not user_data:
        await update.message.reply_text("📝 **Нет данных о пользователях**")
        return
    
    # Сортируем по количеству сообщений
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]['message_count'], reverse=True)[:10]
    
    text = "🏆 **Топ-10 активных пользователей:**\n\n"
    
    for i, (user_id, data) in enumerate(sorted_users, 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{emoji} @{data['username']} - {data['message_count']} сообщений\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def lastseen_command(update, context):
    """Последнее время активности пользователя"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/lastseen @username`", parse_mode='Markdown')
        return
    
    target = context.args[0]
    
    # Поиск пользователя
    target_id = None
    if target.startswith('@'):
        username = target[1:]
        for uid, data in user_data.items():
            if data['username'].lower() == username.lower():
                target_id = uid
                break
    elif target.isdigit():
        target_id = int(target)
    
    if target_id and target_id in user_data:
        data = user_data[target_id]
        last_seen = data['last_activity']
        time_diff = datetime.now() - last_seen
        
        if time_diff.seconds < 60:
            time_str = "только что"
        elif time_diff.seconds < 3600:
            time_str = f"{time_diff.seconds // 60} минут назад"
        elif time_diff.days == 0:
            time_str = f"{time_diff.seconds // 3600} часов назад"
        else:
            time_str = f"{time_diff.days} дней назад"
        
        await update.message.reply_text(
            f"👤 **Последняя активность {target}:**\n\n"
            f"⏰ {last_seen.strftime('%d.%m.%Y %H:%M')}\n"
            f"🕐 {time_str}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Пользователь не найден")

# ============= АВТОПОСТИНГ =============

async def autopost_command(update, context):
    """Управление автопостингом"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        status = "включен" if autopost_data['enabled'] else "выключен"
        text = f"""⚙️ **Автопостинг {status}**

📝 Сообщение: {autopost_data['message'] or 'не установлено'}
⏰ Интервал: {autopost_data['interval']} секунд
📅 Последний пост: {autopost_data['last_post'].strftime('%d.%m.%Y %H:%M') if autopost_data['last_post'] else 'никогда'}

**Команды:**
• `/autopost "текст" интервал` - установить
• `/autopost on/off` - вкл/выкл
• `/autopost edit "новый_текст"` - изменить текст
• `/autopost interval секунды` - изменить интервал"""
        
        await update.message.reply_text(text, parse_mode='Markdown')
        return
    
    action = context.args[0].lower()
    
    if action == 'on':
        autopost_data['enabled'] = True
        await update.message.reply_text("✅ **Автопостинг включен**", parse_mode='Markdown')
    
    elif action == 'off':
        autopost_data['enabled'] = False
        await update.message.reply_text("❌ **Автопостинг выключен**", parse_mode='Markdown')
    
    elif action == 'edit' and len(context.args) > 1:
        new_text = ' '.join(context.args[1:]).strip('"')
        autopost_data['message'] = new_text
        await update.message.reply_text(f"✅ **Текст изменен:**\n{new_text}", parse_mode='Markdown')
    
    elif action == 'interval' and len(context.args) > 1 and context.args[1].isdigit():
        new_interval = int(context.args[1])
        autopost_data['interval'] = new_interval
        await update.message.reply_text(f"✅ **Интервал изменен на {new_interval} секунд**", parse_mode='Markdown')
    
    elif len(context.args) >= 2:
        # Установить текст и интервал
        if context.args[-1].isdigit():
            interval = int(context.args[-1])
            message = ' '.join(context.args[:-1]).strip('"')
        else:
            interval = 3600
            message = ' '.join(context.args).strip('"')
        
        autopost_data['message'] = message
        autopost_data['interval'] = interval
        autopost_data['enabled'] = True
        
        await update.message.reply_text(
            f"✅ **Автопостинг настроен:**\n\n"
            f"📝 Сообщение: {message}\n"
            f"⏰ Интервал: {interval} секунд",
            parse_mode='Markdown'
        )

async def admin_command(update, context):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    text = """🔧 **АДМИНСКИЕ КОМАНДЫ:**

**Основные:**
• `/say ID сообщение` - отправить сообщение пользователю
• `/id` - показать ID пользователя/чата
• `/whois @user` - информация о пользователе

**Модерация:**
• `/ban @user причина` - заблокировать
• `/unban @user` - разблокировать
• `/mute @user время` - временный мут (10m, 1h, 1d)
• `/unmute @user` - снять мут
• `/banlist` - список забаненных
• `/stats` - статистика чата
• `/top` - топ активных пользователей
• `/lastseen @user` - последняя активность

**Ссылки:**
• `/trixlinks` - просмотр ссылок
• `/trixlinksadd "название" "описание"` - добавить
• `/trixlinksedit ID` - редактировать
• `/trixlinksdelete ID` - удалить

**Автопостинг:**
• `/autopost "текст" интервал` - настроить
• `/autopost on/off` - включить/выключить

**Игра "Угадай слово":**
• `/play3xiawordadd слово` - добавить слово
• `/play3xiawordon` - запустить конкурс
• `/play3xiawordoff` - завершить конкурс
• `/play3xiawordinfo` - информация о конкурсе
• `/play3xiawordinfoedit текст` - изменить описание
• `/play3xiaanstimeset минуты` - интервал попыток
• `/play3xiagamesinfo` - инфо для пользователей
• `/play3xiaadmgamesinfo` - инфо для админов

**Розыгрыш номеров:**
• `/play3xiaroll 3` - провести розыгрыш (1-5 победителей)
• `/play3xiarollreset` - сбросить участников
• `/play3xiarollstatus` - список участников
• `/play3xiamynumber` - показать номер участника

**Обычный розыгрыш:**
• `/join` - войти в розыгрыш
• `/participants` - участники розыгрыша

**Для всех пользователей:**
• `/report @user причина` - пожаловаться
• `/play3xiasay слово` - угадать слово
• `/play3xiaroll 9999` - получить номер"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ============= ИГРОВЫЕ КОМАНДЫ =============

async def wordadd_command(update, context):
    """Добавить слово (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/play3xiawordadd слово`", parse_mode='Markdown')
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

async def wordedit_command(update, context):
    """Редактировать слово (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    
    if not context.args:
        words_list = list(word_games[game_version]['words'].keys())
        if not words_list:
            await update.message.reply_text(f"❌ Нет слов для игры {game_version}")
            return
        
        text = f"📝 **Слова в игре {game_version}:**\n\n"
        for i, word in enumerate(words_list, 1):
            text += f"{i}. {word}\n"
        text += f"\n**Использование:** `/{game_version}wordedit слово`"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        return
    
    word = context.args[0].lower()
    
    if word in word_games[game_version]['words']:
        waiting_users[update.effective_user.id] = {
            'action': 'edit_word',
            'game_version': game_version,
            'word': word
        }
        
        await update.message.reply_text(
            f"📝 **Редактирование слова '{word}' для {game_version}:**\n\n"
            f"Отправьте новое описание следующим сообщением."
        )
    else:
        await update.message.reply_text(f"❌ Слово '{word}' не найдено в игре {game_version}")

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
    word_games[game_version]['description'] = f"🎮 Конкурс активен! Угадайте слово используя /{game_version}say"
    
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
    winners = word_games[game_version]['winners']
    
    if winners:
        winner_list = ", ".join([f"@{winner}" for winner in winners])
        word_games[game_version]['description'] = f"🏆 Последний конкурс завершен! Победители: {winner_list}. Слово было: {current_word}"
    else:
        word_games[game_version]['description'] = f"Конкурс завершен. Слово было: {current_word or 'не выбрано'}"
    
    await update.message.reply_text(
        f"🛑 **Конкурс {game_version} ЗАВЕРШЕН!**\n\n"
        f"🎯 Слово было: {current_word or 'не выбрано'}",
        parse_mode='Markdown'
    )

async def wordinfo_command(update, context):
    """Информация о текущем конкурсе"""
    command_text = update.message.text
    game_version = get_game_version(command_text)
    
    game_data = word_games[game_version]
    
    text = f"ℹ️ **Информация о конкурсе {game_version}:**\n\n"
    text += f"📝 {game_data['description']}\n\n"
    
    if game_data['active']:
        text += f"🎮 Статус: Активен\n"
        text += f"⏰ Интервал попыток: {game_data['interval']} минут\n"
        text += f"🎯 Команда для участия: `/{game_version}say слово`"
    else:
        text += f"🎮 Статус: Неактивен"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def wordinfoedit_command(update, context):
    """Изменить описание конкурса (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/play3xiawordinfoedit новое описание`", parse_mode='Markdown')
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    new_description = ' '.join(context.args)
    
    word_games[game_version]['description'] = new_description
    
    await update.message.reply_text(
        f"✅ **Описание {game_version} изменено:**\n\n{new_description}",
        parse_mode='Markdown'
    )

async def anstimeset_command(update, context):
    """Установить интервал попыток (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("📝 Использование: `/play3xiaanstimeset 60`", parse_mode='Markdown')
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    minutes = int(context.args[0])
    
    word_games[game_version]['interval'] = minutes
    
    await update.message.reply_text(
        f"✅ **Интервал обновлен для {game_version}: {minutes} минут**",
        parse_mode='Markdown'
    )

async def gamesinfo_command(update, context):
    """Информация об игровых командах для пользователей"""
    command_text = update.message.text
    game_version = get_game_version(command_text)
    
    text = f"""🎮 **Игровые команды {game_version}:**

**Угадай слово:**
• `/{game_version}say слово` - попытка угадать
• `/{game_version}wordinfo` - информация о конкурсе

**Розыгрыш номеров:**
• `/{game_version}roll 9999` - получить номер
• `/{game_version}mynumber` - проверить свой номер

**Общие команды:**
• `/join` - войти в обычный розыгрыш
• `/participants` - участники обычного розыгрыша
• `/report @user причина` - пожаловаться

ℹ️ Все команды работают одинаково для всех версий: play3xia, play3x, playxxx"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def admgamesinfo_command(update, context):
    """Информация об игровых командах для админов"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    
    text = f"""🔧 **Админские игровые команды {game_version}:**

**Управление словами:**
• `/{game_version}wordadd слово` - добавить слово
• `/{game_version}wordedit слово` - редактировать слово
• `/{game_version}wordon` - включить конкурс
• `/{game_version}wordoff` - завершить конкурс
• `/{game_version}wordinfoedit текст` - изменить описание
• `/{game_version}anstimeset минуты` - интервал попыток

**Розыгрыш номеров:**
• `/{game_version}roll [1-5]` - провести розыгрыш
• `/{game_version}rollreset` - сбросить участников
• `/{game_version}rollstatus` - список участников

**Пользовательские команды:**
• `/{game_version}say слово` - попытка угадать
• `/{game_version}wordinfo` - информация о конкурсе
• `/{game_version}roll 9999` - получить номер
• `/{game_version}mynumber` - проверить номер"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def game_say_command(update, context):
    """Попытка угадать слово (пользователи)"""
    user_id = update.effective_user.id
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы заблокированы и не можете участвовать")
        return
    
    if is_user_muted(user_id):
        await update.message.reply_text("❌ Вы находитесь в муте")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/play3xiasay слово`", parse_mode='Markdown')
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    username = update.effective_user.username or f"ID_{user_id}"
    guess = context.args[0]
    
    update_user_activity(user_id, update.effective_user.username)
    
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
        word_games[game_version]['description'] = f"🏆 @{username} угадал слово '{current_word}' и стал победителем! Ожидайте новый конкурс."
        
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
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы заблокированы и не можете участвовать")
        return
    
    update_user_activity(user_id, update.effective_user.username)
    
    # Если админ с числом 1-5 = проведение розыгрыша
    if (user_id in ADMIN_IDS and context.args and 
        len(context.args) == 1 and context.args[0].isdigit() and 
        1 <= int(context.args[0]) <= 5):
        
        winners_count = int(context.args[0])
        participants = roll_games[game_version]['participants']
        
        if len(participants) < winners_count:
            await update.message.reply_text(
                f"❌ Недостаточно участников для розыгрыша {winners_count} победителей\n"
                f"Участников: {len(participants)}"
            )
            return
        
        # Генерируем случайное число от 1 до 9999
        target_number = random.randint(1, 9999)
        
        # Находим ближайшие номера
        numbers_with_distance = []
        for uid, data in participants.items():
            distance = abs(data['number'] - target_number)
            numbers_with_distance.append((distance, uid, data['number'], data['username']))
        
        # Сортируем по расстоянию и берем нужное количество победителей
        numbers_with_distance.sort(key=lambda x: x[0])
        winners = numbers_with_distance[:winners_count]
        
        # Формируем сообщение о победителях
        winners_text = []
        for i, (distance, uid, number, username) in enumerate(winners, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            winners_text.append(f"{emoji} @{username} (номер {number})")
        
        result_text = (
            f"🎉 **РОЗЫГРЫШ {game_version} ЗАВЕРШЕН!**\n\n"
            f"🎲 Выпавшее число: {target_number}\n\n"
            f"🏆 **Победители:**\n"
            f"{chr(10).join(winners_text)}\n\n"
            f"🎊 Поздравляем победителей!"
        )
        
        await update.message.reply_text(result_text, parse_mode='Markdown')
        
        # Уведомляем модераторов
        try:
            await context.bot.send_message(
                chat_id=MODERATION_GROUP_ID,
                text=f"🎲 **Розыгрыш {game_version} проведен:**\n\n"
                     f"🎯 Число: {target_number}\n"
                     f"🏆 Победителей: {winners_count}\n"
                     f"👥 Участников было: {len(participants)}",
                parse_mode='Markdown'
            )
        except:
            pass
        
        return
    
    # Если пользователь с аргументом 9999 = получение номера
    if context.args and context.args[0] == '9999':
        username = update.effective_user.username or f"ID_{user_id}"
        
        # Проверяем членство в группе
        if not await check_user_membership(context, user_id):
            await update.message.reply_text(
                "❌ Для участия в розыгрыше необходимо быть участником группы"
            )
            return
        
        # Проверяем, есть ли уже номер у пользователя
        if user_id in roll_games[game_version]['participants']:
            existing_number = roll_games[game_version]['participants'][user_id]['number']
            await update.message.reply_text(
                f"🎲 @{username}, у вас уже есть номер: **{existing_number}**",
                parse_mode='Markdown'
            )
            return
        
        # Генерируем уникальный номер
        existing_numbers = set(data['number'] for data in roll_games[game_version]['participants'].values())
        
        # Пытаемся найти свободный номер
        for _ in range(100):  # Ограничиваем попытки
            new_number = random.randint(1, 9999)
            if new_number not in existing_numbers:
                break
        else:
            await update.message.reply_text("❌ Не удалось найти свободный номер")
            return
        
        # Сохраняем участника
        roll_games[game_version]['participants'][user_id] = {
            'username': username,
            'number': new_number,
            'joined_at': datetime.now()
        }
        
        await update.message.reply_text(
            f"🎲 @{username}, ваш номер для розыгрыша: **{new_number}**",
            parse_mode='Markdown'
        )
        
        # Уведомляем модераторов
        try:
            await context.bot.send_message(
                chat_id=MODERATION_GROUP_ID,
                text=f"🎲 **Новый участник {game_version}:**\n\n"
                     f"👤 @{username} (ID: {user_id})\n"
                     f"🎯 Номер: {new_number}",
                parse_mode='Markdown'
            )
        except:
            pass
        
        return
    
    # Если команда без аргументов или неправильные аргументы
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            f"📝 **Использование команды /{game_version}roll:**\n\n"
            f"**Для админов:**\n"
            f"• `/{game_version}roll [1-5]` - провести розыгрыш\n\n"
            f"**Для участников:**\n"
            f"• `/{game_version}roll 9999` - получить номер",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"📝 **Для получения номера используйте:**\n"
            f"`/{game_version}roll 9999`",
            parse_mode='Markdown'
        )

async def rollreset_command(update, context):
    """Сбросить участников розыгрыша (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    
    participants_count = len(roll_games[game_version]['participants'])
    roll_games[game_version]['participants'] = {}
    
    await update.message.reply_text(
        f"✅ **Участники розыгрыша {game_version} сброшены**\n\n"
        f"Было участников: {participants_count}",
        parse_mode='Markdown'
    )

async def rollstatus_command(update, context):
    """Показать участников розыгрыша (админ)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    command_text = update.message.text
    game_version = get_game_version(command_text)
    participants = roll_games[game_version]['participants']
    
    if not participants:
        await update.message.reply_text(f"🎲 Нет участников в розыгрыше {game_version}")
        return
    
    text = f"🎲 **Участники розыгрыша {game_version} ({len(participants)}):**\n\n"
    
    # Сортируем по номерам
    sorted_participants = sorted(participants.items(), key=lambda x: x[1]['number'])
    
    for user_id, data in sorted_participants:
        text += f"@{data['username']} - номер {data['number']}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def mynumber_command(update, context):
    """Показать свой номер участника"""
    user_id = update.effective_user.id
    command_text = update.message.text
    game_version = get_game_version(command_text)
    
    if user_id in roll_games[game_version]['participants']:
        number = roll_games[game_version]['participants'][user_id]['number']
        username = update.effective_user.username or f"ID_{user_id}"
        
        await update.message.reply_text(
            f"🎲 @{username}, ваш номер: **{number}**",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ У вас нет номера в розыгрыше {game_version}\n"
            f"Используйте `/{game_version}roll 9999` для получения номера",
            parse_mode='Markdown'
        )

# ============= ОБРАБОТКА СООБЩЕНИЙ =============

async def handle_text_messages(update, context):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text
    
    update_user_activity(user_id, update.effective_user.username)
    
    # Проверяем бан и мут
    if is_user_banned(user_id):
        try:
            await update.message.delete()
        except:
            pass
        return
    
    if is_user_muted(user_id):
        try:
            await update.message.delete()
            await update.message.reply_text("🔇 Вы находитесь в муте", disable_notification=True)
        except:
            pass
        return
    
    # Проверяем, ожидает ли пользователь ввод данных
    if user_id in waiting_users:
        action_data = waiting_users[user_id]
        
        if action_data['action'] == 'add_link':
            # Добавляем новую ссылку
            new_id = max([link['id'] for link in trix_links]) + 1 if trix_links else 1
            new_link = {
                'id': new_id,
                'name': action_data['name'],
                'url': text.strip(),
                'description': action_data['description']
            }
            trix_links.append(new_link)
            
            await update.message.reply_text(
                f"✅ **Ссылка добавлена!**\n\n"
                f"🆔 ID: {new_id}\n"
                f"📝 Название: {new_link['name']}\n"
                f"🔗 URL: {new_link['url']}\n"
                f"📋 Описание: {new_link['description']}",
                parse_mode='Markdown'
            )
            
            del waiting_users[user_id]
            return
        
        elif action_data['action'] == 'edit_link':
            # Редактируем ссылку
            parts = text.split(' | ')
            if len(parts) != 3:
                await update.message.reply_text("❌ Неправильный формат. Используйте: название | описание | ссылка")
                return
            
            link_id = action_data['link_id']
            for link in trix_links:
                if link['id'] == link_id:
                    link['name'] = parts[0].strip()
                    link['description'] = parts[1].strip()
                    link['url'] = parts[2].strip()
                    
                    await update.message.reply_text(
                        f"✅ **Ссылка обновлена!**\n\n"
                        f"🆔 ID: {link_id}\n"
                        f"📝 Название: {link['name']}\n"
                        f"🔗 URL: {link['url']}\n"
                        f"📋 Описание: {link['description']}",
                        parse_mode='Markdown'
                    )
                    break
            
            del waiting_users[user_id]
            return
        
        elif action_data['action'] == 'edit_word':
            # Редактируем описание слова
            game_version = action_data['game_version']
            word = action_data['word']
            
            word_games[game_version]['words'][word]['description'] = text.strip()
            
            await update.message.reply_text(
                f"✅ **Описание слова '{word}' обновлено для {game_version}:**\n\n{text.strip()}",
                parse_mode='Markdown'
            )
            
            del waiting_users[user_id]
            return
    
    # Проверка на ссылки-приглашения (если включена защита)
    if chat_settings.get('antiinvite') and ('t.me/' in text or 'telegram.me/' in text):
        if user_id not in ADMIN_IDS:
            try:
                await update.message.delete()
                await update.message.reply_text("❌ Ссылки на другие чаты запрещены", disable_notification=True)
            except:
                pass
            return

async def autopost_task():
    """Задача автопостинга"""
    while True:
        try:
            if (autopost_data['enabled'] and autopost_data['message'] and 
                (not autopost_data['last_post'] or 
                 datetime.now() - autopost_data['last_post'] >= timedelta(seconds=autopost_data['interval']))):
                
                # Отправляем автопост (здесь нужно указать ID чата для автопостинга)
                # await bot.send_message(chat_id=CHAT_ID, text=autopost_data['message'])
                autopost_data['last_post'] = datetime.now()
            
            await asyncio.sleep(60)  # Проверяем каждую минуту
        except Exception as e:
            logger.error(f"Ошибка в autopost_task: {e}")
            await asyncio.sleep(60)

# ============= ОСНОВНАЯ ФУНКЦИЯ =============

def main():
    """Основная функция запуска бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Базовые команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("whois", whois_command))
    application.add_handler(CommandHandler("join", join_command))
    application.add_handler(CommandHandler("participants", participants_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("admin", admin_command))
    
    # Команды для ссылок
    application.add_handler(CommandHandler("trixlinks", trixlinks_command))
    application.add_handler(CommandHandler("trixlinksadd", trixlinksadd_command))
    application.add_handler(CommandHandler("trixlinksedit", trixlinksedit_command))
    application.add_handler(CommandHandler("trixlinksdelete", trixlinksdelete_command))
    
    # Модерационные команды
    application.add_handler(CommandHandler("say", say_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    application.add_handler(CommandHandler("banlist", banlist_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("lastseen", lastseen_command))
    
    # Автопостинг
    application.add_handler(CommandHandler("autopost", autopost_command))
    
    # Игровые команды для всех версий (play3xia, play3x, playxxx)
    game_versions = ['play3xia', 'play3x', 'playxxx']
    
    for version in game_versions:
        # Команды управления словами
        application.add_handler(CommandHandler(f"{version}wordadd", wordadd_command))
        application.add_handler(CommandHandler(f"{version}wordedit", wordedit_command))
        application.add_handler(CommandHandler(f"{version}wordon", wordon_command))
        application.add_handler(CommandHandler(f"{version}wordoff", wordoff_command))
        application.add_handler(CommandHandler(f"{version}wordinfo", wordinfo_command))
        application.add_handler(CommandHandler(f"{version}wordinfoedit", wordinfoedit_command))
        application.add_handler(CommandHandler(f"{version}anstimeset", anstimeset_command))
        
        # Информационные команды
        application.add_handler(CommandHandler(f"{version}gamesinfo", gamesinfo_command))
        application.add_handler(CommandHandler(f"{version}admgamesinfo", admgamesinfo_command))
        
        # Игровые команды
        application.add_handler(CommandHandler(f"{version}say", game_say_command))
        application.add_handler(CommandHandler(f"{version}roll", roll_command))
        application.add_handler(CommandHandler(f"{version}rollreset", rollreset_command))
        application.add_handler(CommandHandler(f"{version}rollstatus", rollstatus_command))
        application.add_handler(CommandHandler(f"{version}mynumber", mynumber_command))
    
    # Обработка текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    
    # Запуск задачи автопостинга
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(autopost_task())
    
    # Запуск бота
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=['message', 'callback_query'])

if __name__ == '__main__':
    main()ден")

async def unban_command(update, context):
    """Разблокировать пользователя"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/unban @username`", parse_mode='Markdown')
        return
    
    target = context.args[0]
    
    # Поиск пользователя
    target_id = None
    if target.startswith('@'):
        username = target[1:]
        for uid, data in user_data.items():
            if data['username'].lower() == username.lower():
                target_id = uid
                break
    elif target.isdigit():
        target_id = int(target)
    
    if target_id and target_id in user_data:
        user_data[target_id]['banned'] = False
        
        await update.message.reply_text(
            f"✅ **Пользователь разблокирован:**\n\n"
            f"👤 Пользователь: {target}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Пользователь не найден")

async def mute_command(update, context):
    """Временно замутить пользователя"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("📝 Использование: `/mute @username время` (например: 10m, 1h, 1d)", parse_mode='Markdown')
        return
    
    target = context.args[0]
    time_str = context.args[1]
    
    seconds = parse_time(time_str)
    if not seconds:
        await update.message.reply_text("❌ Некорректный формат времени. Используйте: 10m, 1h, 1d")
        return
    
    # Поиск пользователя
    target_id = None
    if target.startswith('@'):
        username = target[1:]
        for uid, data in user_data.items():
            if data['username'].lower() == username.lower():
                target_id = uid
                break
    elif target.isdigit():
        target_id = int(target)
    
    if target_id and target_id in user_data:
        mute_until = datetime.now() + timedelta(seconds=seconds)
        user_data[target_id]['muted_until'] = mute_until
        
        await update.message.reply_text(
            f"🔇 **Пользователь замучен:**\n\n"
            f"👤 Пользователь: {target}\n"
            f"⏰ До: {mute_until.strftime('%d.%m.%Y %H:%M')}\n"
            f"🕐 Длительность: {time_str}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Пользователь не най
