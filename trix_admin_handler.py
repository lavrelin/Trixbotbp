from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from services.cooldown import CooldownService
from models import User, Post, PostStatus, BanMute, ActionType
from sqlalchemy import select, func
from datetime import datetime, timedelta
from utils.permissions import admin_only, moderator_only
import logging
import re

logger = logging.getLogger(__name__)

@moderator_only
async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel"""
    text = (
        "🛠 *Панель модератора*\n\n"
        "*Доступные команды:*\n\n"
        "📊 /stats - статистика бота\n"
        "👤 /user [id/@username] - информация о пользователе\n"
        "🚫 /ban @username - забанить пользователя\n"
        "✅ /unban @username - разбанить пользователя\n"
        "🔇 /mute @username [время] - замутить пользователя\n"
        "🔊 /unmute @username - размутить пользователя\n"
        "⏰ /cdreset @username - сбросить кулдаун\n"
        "📢 /broadcast <текст> - массовая рассылка (только админы)\n"
        "👥 /admins - список админов и модераторов\n"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

@moderator_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    async with db.get_session() as session:
        # Count users
        users_count = await session.execute(
            select(func.count(User.id))
        )
        total_users = users_count.scalar()
        
        # Count active users (posted in last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_users = await session.execute(
            select(func.count(func.distinct(Post.user_id)))
            .where(Post.created_at > week_ago)
        )
        active_count = active_users.scalar()
        
        # Count posts by status
        pending = await session.execute(
            select(func.count(Post.id))
            .where(Post.status == PostStatus.PENDING)
        )
        pending_count = pending.scalar()
        
        approved = await session.execute(
            select(func.count(Post.id))
            .where(Post.status == PostStatus.APPROVED)
        )
        approved_count = approved.scalar()
        
        rejected = await session.execute(
            select(func.count(Post.id))
            .where(Post.status == PostStatus.REJECTED)
        )
        rejected_count = rejected.scalar()
        
        # Count banned users
        banned = await session.execute(
            select(func.count(User.id))
            .where(User.banned == True)
        )
        banned_count = banned.scalar()
    
    text = (
        "📊 *Статистика бота*\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Активных за неделю: {active_count}\n"
        f"🚫 Забаненных: {banned_count}\n\n"
        f"*Посты:*\n"
        f"⏳ На модерации: {pending_count}\n"
        f"✅ Опубликовано: {approved_count}\n"
        f"❌ Отклонено: {rejected_count}\n"
        f"📝 Всего: {pending_count + approved_count + rejected_count}"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

@moderator_only
async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user information"""
    if not context.args:
        await update.message.reply_text("Использование: /user [id/@username]")
        return
    
    user_identifier = context.args[0]
    
    # Parse user ID or username
    if user_identifier.startswith('@'):
        username = user_identifier[1:]
        query = select(User).where(User.username == username)
    else:
        try:
            user_id = int(user_identifier)
            query = select(User).where(User.id == user_id)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат ID")
            return
    
    async with db.get_session() as session:
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        # Count user's posts
        posts_count = await session.execute(
            select(func.count(Post.id))
            .where(Post.user_id == user.id)
        )
        total_posts = posts_count.scalar()
        
        # Get level info
        level, level_name = Config.get_level_info(user.xp)
        
        text = (
            f"👤 *Информация о пользователе*\n\n"
            f"ID: `{user.id}`\n"
            f"Username: @{user.username or 'нет'}\n"
            f"Имя: {user.first_name or 'нет'}\n"
            f"Фамилия: {user.last_name or 'нет'}\n"
            f"Пол: {user.gender.value if user.gender else 'не указан'}\n"
            f"Дата рождения: {user.birthdate.strftime('%d.%m.%Y') if user.birthdate else 'не указана'}\n\n"
            f"📊 *Статистика:*\n"
            f"XP: {user.xp}\n"
            f"Уровень: {level} - {level_name}\n"
            f"Постов: {total_posts}\n"
            f"Нарушений ссылок: {user.link_violations}\n\n"
            f"🚫 Забанен: {'Да' if user.banned else 'Нет'}\n"
            f"🔇 Мут до: {user.mute_until.strftime('%d.%m %H:%M') if user.mute_until and user.mute_until > datetime.utcnow() else 'Нет'}\n"
            f"⏰ Кулдаун до: {user.cooldown_expires_at.strftime('%d.%m %H:%M') if user.cooldown_expires_at and user.cooldown_expires_at > datetime.utcnow() else 'Нет'}\n"
            f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')

@moderator_only
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban user"""
    if not context.args:
        await update.message.reply_text("Использование: /ban @username")
        return
    
    username = context.args[0].replace('@', '')
    
    async with db.get_session() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        if Config.is_moderator(user.id):
            await update.message.reply_text("❌ Нельзя забанить модератора")
            return
        
        user.banned = True
        
        # Log ban
        ban_log = BanMute(
            user_id=user.id,
            type=ActionType.BAN,
            imposed_by=update.effective_user.id,
            reason="Manual ban by moderator"
        )
        session.add(ban_log)
        
        await session.commit()
        
        await update.message.reply_text(
            f"✅ Пользователь @{username} забанен"
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text="❌ Вы были заблокированы модератором"
            )
        except:
            pass

@moderator_only
async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban user"""
    if not context.args:
        await update.message.reply_text("Использование: /unban @username")
        return
    
    username = context.args[0].replace('@', '')
    
    async with db.get_session() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        user.banned = False
        user.link_violations = 0  # Reset violations
        await session.commit()
        
        await update.message.reply_text(
            f"✅ Пользователь @{username} разбанен"
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text="✅ Вы были разблокированы. Соблюдайте правила сообщества!"
            )
        except:
            pass

@moderator_only
async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute user"""
    if len(context.args) < 1:
        await update.message.reply_text(
            "Использование: /mute @username [время]\n"
            "Время: 5m, 1h, 1d (по умолчанию 1h)"
        )
        return
    
    username = context.args[0].replace('@', '')
    duration_str = context.args[1] if len(context.args) > 1 else "1h"
    
    # Parse duration
    duration = parse_duration(duration_str)
    if not duration:
        await update.message.reply_text("❌ Неверный формат времени. Используйте: 5m, 1h, 1d")
        return
    
    async with db.get_session() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        if Config.is_moderator(user.id):
            await update.message.reply_text("❌ Нельзя замутить модератора")
            return
        
        user.mute_until = datetime.utcnow() + duration
        
        # Log mute
        mute_log = BanMute(
            user_id=user.id,
            type=ActionType.MUTE,
            until=user.mute_until,
            imposed_by=update.effective_user.id,
            reason=f"Mute for {duration_str}"
        )
        session.add(mute_log)
        
        await session.commit()
        
        await update.message.reply_text(
            f"✅ Пользователь @{username} замучен на {duration_str}"
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=f"🔇 Вы замучены на {duration_str}"
            )
        except:
            pass

@moderator_only
async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmute user"""
    if not context.args:
        await update.message.reply_text("Использование: /unmute @username")
        return
    
    username = context.args[0].replace('@', '')
    
    async with db.get_session() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        user.mute_until = None
        await session.commit()
        
        await update.message.reply_text(
            f"✅ Пользователь @{username} размучен"
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text="🔊 Вы были размучены"
            )
        except:
            pass

@moderator_only
async def cdreset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset user cooldown"""
    if not context.args:
        await update.message.reply_text("Использование: /cdreset @username")
        return
    
    username = context.args[0].replace('@', '')
    
    async with db.get_session() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        cooldown_service = CooldownService()
        if await cooldown_service.reset_cooldown(user.id):
            await update.message.reply_text(
                f"✅ Кулдаун пользователя @{username} сброшен"
            )
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text="⏰ Ваш кулдаун был сброшен модератором"
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ Ошибка при сбросе кулдауна")

@admin_only
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users"""
    if not context.args:
        await update.message.reply_text("Использование: /broadcast <текст сообщения>")
        return
    
    message = ' '.join(context.args)
    
    async with db.get_session() as session:
        result = await session.execute(
            select(User).where(User.banned == False)
        )
        users = result.scalars().all()
        
        sent = 0
        failed = 0
        
        await update.message.reply_text(
            f"📢 Начинаю рассылку {len(users)} пользователям..."
        )
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"📢 *Объявление от администрации:*\n\n{message}",
                    parse_mode='Markdown'
                )
                sent += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to send broadcast to {user.id}: {e}")
        
        await update.message.reply_text(
            f"✅ Рассылка завершена!\n"
            f"Отправлено: {sent}\n"
            f"Ошибок: {failed}"
        )

@moderator_only
async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of admins and moderators"""
    admins = []
    moderators = []
    
    async with db.get_session() as session:
        for admin_id in Config.ADMIN_IDS:
            result = await session.execute(
                select(User).where(User.id == admin_id)
            )
            user = result.scalar_one_or_none()
            if user:
                admins.append(f"@{user.username}" if user.username else f"ID: {user.id}")
        
        for mod_id in Config.MODERATOR_IDS:
            if mod_id not in Config.ADMIN_IDS:
                result = await session.execute(
                    select(User).where(User.id == mod_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    moderators.append(f"@{user.username}" if user.username else f"ID: {user.id}")
    
    text = "👥 *Администрация бота*\n\n"
    
    if admins:
        text += "*Админы:*\n"
        text += "\n".join(f"• {admin}" for admin in admins)
        text += "\n\n"
    
    if moderators:
        text += "*Модераторы:*\n"
        text += "\n".join(f"• {mod}" for mod in moderators)
    
    if not admins and not moderators:
        text += "Список пуст"
    
    await update.message.reply_text(text, parse_mode='Markdown')

def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string to timedelta"""
    match = re.match(r'^(\d+)([mhd]), duration_str.lower())
    if not match:
        return None
    
    value = int(match.group(1))
    unit = match.group(2)
    
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    
    return None