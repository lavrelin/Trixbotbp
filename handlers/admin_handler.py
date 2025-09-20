from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from models import User
from sqlalchemy import select
import logging
import re
import requests
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ============ ОСНОВНЫЕ КОМАНДЫ =============

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command"""
    user_id = update.effective_user.id
    
    if not Config.is_admin(user_id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton("👥 Управление", callback_data="admin:manage")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu:back")]
    ]
    
    await update.message.reply_text(
        "🔧 *Панель администратора*\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user_id = update.effective_user.id
    
    if not Config.is_moderator(user_id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    try:
        from services.db import db
        from models import User, Post
        from sqlalchemy import select, func
        
        async with db.get_session() as session:
            # Count users
            users_count = await session.scalar(select(func.count(User.id)))
            
            # Count posts
            posts_count = await session.scalar(select(func.count(Post.id)))
            
            stats_text = (
                f"📊 *Статистика бота*\n\n"
                f"👥 Пользователей: {users_count}\n"
                f"📝 Постов: {posts_count}\n"
            )
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await update.message.reply_text("❌ Ошибка получения статистики")

# ============= КОМАНДА /SAY =============

async def say_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /say command for moderators to send messages to users"""
    user_id = update.effective_user.id
    
    if not Config.is_moderator(user_id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📝 **Использование команды /say:**\n\n"
            "Формат: `/say получатель сообщение`\n\n"
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
    
    target_user_id = None
    
    if target.startswith('@'):
        username = target[1:]
        target_user_id = await get_user_id_by_username(username)
        if not target_user_id:
            await update.message.reply_text(f"❌ Пользователь @{username} не найден в базе данных")
            return
    elif target.startswith('ID_'):
        try:
            target_user_id = int(target[3:])
        except ValueError:
            await update.message.reply_text("❌ Некорректный формат ID")
            return
    elif target.isdigit():
        target_user_id = int(target)
    else:
        await update.message.reply_text("❌ Некорректный формат получателя")
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
        
        logger.info(f"Moderator {user_id} sent message to {target_user_id}")
        
    except Exception as e:
        error_msg = str(e)
        if "bot was blocked" in error_msg:
            await update.message.reply_text(f"❌ Пользователь {target} заблокировал бота")
        elif "chat not found" in error_msg:
            await update.message.reply_text(f"❌ Пользователь {target} не найден")
        else:
            await update.message.reply_text(f"❌ Ошибка отправки: {error_msg}")

# ============= БАЗОВЫЕ КОМАНДЫ =============

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user or chat ID"""
    chat = update.effective_chat
    user = update.effective_user
    
    text = f"🆔 **Информация об ID:**\n\n"
    text += f"👤 Ваш ID: `{user.id}`\n"
    
    if chat.type != 'private':
        text += f"💬 ID чата: `{chat.id}`\n"
        text += f"📝 Тип чата: {chat.type}\n"
        
        if chat.title:
            text += f"🏷️ Название: {chat.title}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def whois_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get detailed user information"""
    if not Config.is_moderator(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 Использование: `/whois @username` или `/whois ID`",
            parse_mode='Markdown'
        )
        return
    
    target = context.args[0]
    target_user_id = None
    
    if target.startswith('@'):
        username = target[1:]
        target_user_id = await get_user_id_by_username(username)
    elif target.isdigit():
        target_user_id = int(target)
    
    if not target_user_id:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    try:
        async with db.get_session() as session:
            result = await session.execute(select(User).where(User.id == target_user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                await update.message.reply_text("❌ Пользователь не найден в базе данных")
                return
            
            text = f"👤 **Информация о пользователе:**\n\n"
            text += f"🆔 ID: `{user.id}`\n"
            text += f"👋 Имя: {user.first_name or 'Не указано'}\n"
            
            if user.username:
                text += f"📧 Username: @{user.username}\n"
            
            if hasattr(user, 'created_at') and user.created_at:
                text += f"📅 Присоединился: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            
            if hasattr(user, 'banned') and user.banned:
                text += f"🚫 Статус: Заблокирован\n"
            else:
                text += f"✅ Статус: Активен\n"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in whois command: {e}")
        await update.message.reply_text("❌ Ошибка получения информации")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Translate text using Google Translate API"""
    if not context.args:
        await update.message.reply_text(
            "📝 Использование: `/translate текст для перевода`",
            parse_mode='Markdown'
        )
        return
    
    text_to_translate = ' '.join(context.args)
    
    try:
        # Упрощенный перевод (заглушка)
        await update.message.reply_text(
            f"🔄 **Перевод:**\n\n"
            f"📝 Исходный текст: {text_to_translate}\n\n"
            f"🌐 Переведенный текст: [Функция перевода в разработке]",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in translate: {e}")
        await update.message.reply_text("❌ Ошибка перевода")

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get weather information"""
    if not context.args:
        await update.message.reply_text(
            "📝 Использование: `/weather Будапешт`",
            parse_mode='Markdown'
        )
        return
    
    city = ' '.join(context.args)
    
    try:
        # Заглушка для погоды
        await update.message.reply_text(
            f"🌤️ **Погода в {city}:**\n\n"
            f"🌡️ Температура: [Функция погоды в разработке]\n"
            f"☁️ Описание: [Данные недоступны]\n"
            f"💨 Ветер: [Данные недоступны]",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in weather: {e}")
        await update.message.reply_text("❌ Ошибка получения погоды")

# ============= РОЗЫГРЫШ =============

# В памяти храним участников розыгрыша
lottery_participants = {}

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join lottery"""
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    
    if user_id in lottery_participants:
        await update.message.reply_text(
            f"🎲 @{username}, вы уже участвуете в розыгрыше!"
        )
        return
    
    lottery_participants[user_id] = {
        'username': username,
        'joined_at': datetime.now()
    }
    
    await update.message.reply_text(
        f"🎉 @{username}, вы успешно присоединились к розыгрышу!\n"
        f"👥 Участников: {len(lottery_participants)}"
    )

async def participants_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show lottery participants"""
    if not lottery_participants:
        await update.message.reply_text("🎲 Пока нет участников розыгрыша")
        return
    
    text = f"👥 **Участники розыгрыша ({len(lottery_participants)}):**\n\n"
    
    for i, (user_id, data) in enumerate(lottery_participants.items(), 1):
        text += f"{i}. @{data['username']}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report a user to moderators"""
    if not context.args:
        await update.message.reply_text(
            "📝 Использование: `/report @username причина`",
            parse_mode='Markdown'
        )
        return
    
    target = context.args[0]
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "Не указана"
    
    reporter = update.effective_user
    
    # Отправляем жалобу модераторам
    report_text = (
        f"🚨 **Новая жалоба:**\n\n"
        f"👤 От: @{reporter.username or 'без_username'} (ID: {reporter.id})\n"
        f"🎯 На: {target}\n"
        f"📝 Причина: {reason}\n"
        f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    try:
        # Отправляем в группу модерации
        await context.bot.send_message(
            chat_id=Config.MODERATION_GROUP_ID,
            text=report_text,
            parse_mode='Markdown'
        )
        
        await update.message.reply_text(
            "✅ **Жалоба отправлена!**\n\n"
            "Модераторы рассмотрят вашу жалобу в ближайшее время."
        )
        
    except Exception as e:
        logger.error(f"Error sending report: {e}")
        await update.message.reply_text("❌ Ошибка отправки жалобы")

# ============= АДМИНСКИЕ КОМАНДЫ МОДЕРАЦИИ =============

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban user"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/ban @username причина`")
        return
    
    target = context.args[0]
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "Не указана"
    
    # Заглушка - реальная реализация требует работы с БД
    await update.message.reply_text(
        f"🚫 **Пользователь заблокирован:**\n\n"
        f"👤 Пользователь: {target}\n"
        f"📝 Причина: {reason}\n"
        f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"[Функция в разработке - требует доработку БД]"
    )

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban user"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Использование: `/unban @username`")
        return
    
    target = context.args[0]
    
    await update.message.reply_text(
        f"✅ **Пользователь разблокирован:**\n\n"
        f"👤 Пользователь: {target}\n"
        f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"[Функция в разработке]"
    )

async def admcom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin commands"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    text = """🔧 **АДМИНСКИЕ КОМАНДЫ:**

**Пользователи и модерация:**
• `/ban @user [причина]` – заблокировать
• `/unban @user` – снять бан
• `/mute @user [время]` – временный мут
• `/unmute @user` – снять мут
• `/info @user` – информация о пользователе

**Управление:**
• `/say @user текст` – отправить сообщение
• `/broadcast текст` – рассылка всем
• `/stats` – статистика бота

**Игры:**
• Команды игр в разработке

**Утилиты:**
• `/admins` – список админов
• `/whois @user` – подробная информация"""

    await update.message.reply_text(text, parse_mode='Markdown')

# ============= СЛУЖЕБНЫЕ ФУНКЦИИ =============

async def get_user_id_by_username(username: str) -> int | None:
    """Find user ID by username"""
    try:
        async with db.get_session() as session:
            result = await session.execute(
                select(User.id).where(User.username == username)
            )
            return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error finding user by username {username}: {e}")
        return None

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if not Config.is_moderator(user_id):
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    
    if action == "stats":
        await stats_command(update, context)
    elif action == "broadcast":
        await query.answer("📢 Функция рассылки в разработке", show_alert=True)
    else:
        await query.answer("Функция в разработке", show_alert=True)

# Заглушки для команд в разработке
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast command placeholder"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    await update.message.reply_text("📢 Функция рассылки в разработке")
# ДОБАВЬТЕ ЭТИ ФУНКЦИИ В КОНЕЦ ФАЙЛА handlers/admin_handler.py

# ============= СИСТЕМА УПРАВЛЕНИЯ ССЫЛКАМИ =============

# В памяти храним ссылки (в реальном проекте используйте базу данных)
trix_links = [
    {
        'id': 1,
        'name': 'Канал Будапешт',
        'url': 'https://t.me/snghu',
        'description': 'Основной канал сообщества Будапешта'
    },
    {
        'id': 2,
        'name': 'Чат Будапешт',
        'url': 'https://t.me/tgchatxxx',
        'description': 'Чат для общения участников сообщества'
    },
    {
        'id': 3,
        'name': 'Каталог услуг',
        'url': 'https://t.me/trixvault',
        'description': 'Каталог услуг и специалистов Будапешта'
    },
    {
        'id': 4,
        'name': 'Барахолка',
        'url': 'https://t.me/hungarytrade',
        'description': 'Купля, продажа, обмен товаров'
    }
]

async def trixlinks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все ссылки - доступно всем"""
    if not trix_links:
        await update.message.reply_text("📂 Список ссылок пуст")
        return
    
    text = "🔗 **ПОЛЕЗНЫЕ ССЫЛКИ TRIX:**\n\n"
    
    for i, link in enumerate(trix_links, 1):
        text += f"{i}. **{link['name']}**\n"
        text += f"🔗 {link['url']}\n"
        text += f"📝 {link['description']}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def trixlinksadd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить ссылку - только админы"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "📝 **Использование:**\n"
            "`/trixlinksadd название описание`\n\n"
            "**Пример:**\n"
            "`/trixlinksadd \"Новый канал\" \"Описание нового канала\"`\n\n"
            "После этого бот попросит ввести ссылку.",
            parse_mode='Markdown'
        )
        return
    
    # Парсим название и описание
    if len(context.args) == 2:
        name = context.args[0].strip('"')
        description = context.args[1].strip('"')
    else:
        # Если больше 2 аргументов, объединяем все кроме первого в описание
        name = context.args[0].strip('"')
        description = ' '.join(context.args[1:]).strip('"')
    
    # Сохраняем данные для следующего шага
    context.user_data['trixlinks_adding'] = {
        'name': name,
        'description': description
    }
    context.user_data['waiting_for'] = 'trixlinks_waiting_url'
    
    await update.message.reply_text(
        f"✅ **Данные сохранены:**\n\n"
        f"📝 Название: {name}\n"
        f"📋 Описание: {description}\n\n"
        f"🔗 **Теперь отправьте ссылку:**\n"
        f"(Например: https://t.me/example)",
        parse_mode='Markdown'
    )

async def trixlinksedit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактировать ссылку - только админы"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args or not context.args[0].isdigit():
        # Показываем список для выбора
        if not trix_links:
            await update.message.reply_text("📂 Список ссылок пуст")
            return
        
        text = "📝 **РЕДАКТИРОВАНИЕ ССЫЛОК**\n\n"
        text += "Используйте: `/trixlinksedit ID`\n\n"
        text += "**Доступные ссылки:**\n"
        
        for link in trix_links:
            text += f"{link['id']}. {link['name']}\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        return
    
    link_id = int(context.args[0])
    
    # Ищем ссылку
    link_to_edit = None
    for link in trix_links:
        if link['id'] == link_id:
            link_to_edit = link
            break
    
    if not link_to_edit:
        await update.message.reply_text(f"❌ Ссылка с ID {link_id} не найдена")
        return
    
    # Если есть дополнительные аргументы, обновляем сразу
    if len(context.args) >= 3:
        new_name = context.args[1].strip('"')
        new_description = ' '.join(context.args[2:]).strip('"')
        
        link_to_edit['name'] = new_name
        link_to_edit['description'] = new_description
        
        await update.message.reply_text(
            f"✅ **Ссылка обновлена:**\n\n"
            f"🆔 ID: {link_id}\n"
            f"📝 Новое название: {new_name}\n"
            f"📋 Новое описание: {new_description}\n"
            f"🔗 Ссылка: {link_to_edit['url']}",
            parse_mode='Markdown'
        )
    else:
        # Показываем текущие данные и запрашиваем новые
        context.user_data['trixlinks_editing'] = link_id
        context.user_data['waiting_for'] = 'trixlinks_waiting_edit'
        
        await update.message.reply_text(
            f"📝 **Редактирование ссылки ID {link_id}:**\n\n"
            f"📝 Текущее название: {link_to_edit['name']}\n"
            f"📋 Текущее описание: {link_to_edit['description']}\n"
            f"🔗 Ссылка: {link_to_edit['url']}\n\n"
            f"**Отправьте новые данные в формате:**\n"
            f"`название | описание | ссылка`\n\n"
            f"**Пример:**\n"
            f"`Новое название | Новое описание | https://t.me/new`",
            parse_mode='Markdown'
        )

async def trixlinksdelete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить ссылку - только админы"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args or not context.args[0].isdigit():
        # Показываем список для выбора
        if not trix_links:
            await update.message.reply_text("📂 Список ссылок пуст")
            return
        
        text = "🗑️ **УДАЛЕНИЕ ССЫЛОК**\n\n"
        text += "Используйте: `/trixlinksdelete ID`\n\n"
        text += "**Доступные ссылки:**\n"
        
        for link in trix_links:
            text += f"{link['id']}. {link['name']}\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        return
    
    link_id = int(context.args[0])
    
    # Ищем и удаляем ссылку
    link_to_delete = None
    for i, link in enumerate(trix_links):
        if link['id'] == link_id:
            link_to_delete = trix_links.pop(i)
            break
    
    if link_to_delete:
        await update.message.reply_text(
            f"✅ **Ссылка удалена:**\n\n"
            f"📝 Название: {link_to_delete['name']}\n"
            f"🔗 URL: {link_to_delete['url']}\n"
            f"📋 Описание: {link_to_delete['description']}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"❌ Ссылка с ID {link_id} не найдена")

async def handle_trixlinks_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстового ввода для команд ссылок"""
    waiting_for = context.user_data.get('waiting_for')
    text = update.message.text.strip()
    
    if waiting_for == 'trixlinks_waiting_url':
        # Добавляем URL к новой ссылке
        adding_data = context.user_data.get('trixlinks_adding')
        
        if not adding_data:
            await update.message.reply_text("❌ Ошибка: данные не найдены")
            return
        
        # Проверяем валидность URL
        if not (text.startswith('http://') or text.startswith('https://')):
            await update.message.reply_text(
                "❌ Неверный формат ссылки. Ссылка должна начинаться с http:// или https://\n\n"
                "Попробуйте еще раз:"
            )
            return
        
        # Генерируем новый ID
        new_id = max([link['id'] for link in trix_links], default=0) + 1
        
        # Добавляем ссылку
        new_link = {
            'id': new_id,
            'name': adding_data['name'],
            'url': text,
            'description': adding_data['description']
        }
        
        trix_links.append(new_link)
        
        # Очищаем временные данные
        context.user_data.pop('trixlinks_adding', None)
        context.user_data.pop('waiting_for', None)
        
        await update.message.reply_text(
            f"✅ **Ссылка добавлена:**\n\n"
            f"🆔 ID: {new_id}\n"
            f"📝 Название: {adding_data['name']}\n"
            f"🔗 URL: {text}\n"
            f"📋 Описание: {adding_data['description']}",
            parse_mode='Markdown'
        )
        
    elif waiting_for == 'trixlinks_waiting_edit':
        # Редактируем существующую ссылку
        link_id = context.user_data.get('trixlinks_editing')
        
        if not link_id:
            await update.message.reply_text("❌ Ошибка: ID ссылки не найден")
            return
        
        # Парсим данные в формате: название | описание | ссылка
        parts = [part.strip() for part in text.split('|')]
        
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ Неверный формат. Используйте:\n"
                "`название | описание | ссылка`\n\n"
                "Попробуйте еще раз:"
            )
            return
        
        new_name, new_description, new_url = parts
        
        # Проверяем валидность URL
        if not (new_url.startswith('http://') or new_url.startswith('https://')):
            await update.message.reply_text(
                "❌ Неверный формат ссылки. Ссылка должна начинаться с http:// или https://\n\n"
                "Попробуйте еще раз:"
            )
            return
        
        # Ищем и обновляем ссылку
        link_updated = False
        for link in trix_links:
            if link['id'] == link_id:
                link['name'] = new_name
                link['description'] = new_description
                link['url'] = new_url
                link_updated = True
                break
        
        if link_updated:
            # Очищаем временные данные
            context.user_data.pop('trixlinks_editing', None)
            context.user_data.pop('waiting_for', None)
            
            await update.message.reply_text(
                f"✅ **Ссылка обновлена:**\n\n"
                f"🆔 ID: {link_id}\n"
                f"📝 Название: {new_name}\n"
                f"🔗 URL: {new_url}\n"
                f"📋 Описание: {new_description}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ Ссылка с ID {link_id} не найдена")
    
    else:
        await update.message.reply_text("❌ Неизвестное состояние обработки ссылок")
