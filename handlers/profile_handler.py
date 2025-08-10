from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from models import User, Post, PostStatus, Gender, XPEvent
from sqlalchemy import select, func
from datetime import datetime, timedelta
import logging
import secrets
import string

logger = logging.getLogger(__name__)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile"""
    await show_profile(update, context)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display user profile"""
    user_id = update.effective_user.id
    
    async with db.get_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.effective_message.reply_text(
                "❌ Профиль не найден. Используйте /start для регистрации."
            )
            return
        
        # Count user's posts
        posts_count = await session.execute(
            select(func.count(Post.id)).where(Post.user_id == user_id)
        )
        total_posts = posts_count.scalar()
        
        approved_count = await session.execute(
            select(func.count(Post.id))
            .where(Post.user_id == user_id)
            .where(Post.status == PostStatus.APPROVED)
        )
        approved_posts = approved_count.scalar()
        
        # Get level info
        level, level_name = Config.get_level_info(user.xp)
        
        # Build profile text
        text = f"👤 *Ваш профиль*\n\n"
        text += f"🆔 ID: `{user.id}`\n"
        
        if user.username:
            text += f"📱 Username: @{user.username}\n"
        
        text += f"📝 Имя: {user.first_name or 'не указано'}\n"
        
        text += f"\n📊 *Статистика:*\n"
        text += f"⭐ XP: {user.xp}\n"
        text += f"🎖 Уровень: {level} - {level_name}\n"
        text += f"📝 Постов всего: {total_posts}\n"
        text += f"✅ Опубликовано: {approved_posts}\n"
        
        if user.referral_code:
            text += f"\n🔗 *Реферальная ссылка:*\n"
            text += f"`https://t.me/Trixlivebot?start={user.referral_code}`\n"
        
        text += f"\n📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}"
        
        # Кнопки для обычных пользователей
        keyboard = []
        
        # Добавляем статистику только для модераторов
        if Config.is_moderator(user_id):
            keyboard.append([
                InlineKeyboardButton("📊 Статистика бота", callback_data="profile:bot_stats"),
                InlineKeyboardButton("🏆 Топ", callback_data="profile:top")
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Главное меню", callback_data="menu:back")])
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.effective_message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

async def handle_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle profile callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    
    # Обработка выбора пола при регистрации
    if action == "gender":
        gender_value = data[2] if len(data) > 2 else None
        await save_gender_and_continue(update, context, gender_value)
    elif action == "skip" or action == "skip_birthdate":
        # Пропуск и переход в главное меню
        await finish_registration(update, context)
    elif action == "back":
        # Возврат в профиль
        await show_profile(update, context)
    elif action == "bot_stats" and Config.is_moderator(update.effective_user.id):
        # Статистика только для модераторов
        await show_bot_stats(update, context)
    elif action == "top" and Config.is_moderator(update.effective_user.id):
        # Топ только для модераторов
        await show_top_users(update, context)
    else:
        # По умолчанию показываем профиль
        await show_profile(update, context)

async def save_gender_and_continue(update: Update, context: ContextTypes.DEFAULT_TYPE, gender_value: str):
    """Save gender and go to main menu"""
    user_id = update.effective_user.id
    
    # Map gender value
    gender_map = {
        'M': Gender.MALE,
        'F': Gender.FEMALE,
        'other': Gender.OTHER
    }
    
    gender = gender_map.get(gender_value, Gender.UNKNOWN)
    
    # Save gender
    async with db.get_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.gender = gender
            await session.commit()
    
    # Go to main menu
    await finish_registration(update, context)

async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish registration and show main menu"""
    from handlers.start_handler import show_main_menu
    
    # Clear registration data
    context.user_data.pop('registration', None)
    context.user_data.pop('waiting_for', None)
    
    await show_main_menu(update, context)

async def show_bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics (moderators only)"""
    if not Config.is_moderator(update.effective_user.id):
        await update.callback_query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
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
        
        text = (
            f"📊 *Статистика бота*\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"✅ Активных за неделю: {active_count}\n\n"
            f"*Посты:*\n"
            f"⏳ На модерации: {pending_count}\n"
            f"✅ Опубликовано: {approved_count}\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data="profile:back")]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def show_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top users by XP (moderators only)"""
    if not Config.is_moderator(update.effective_user.id):
        await update.callback_query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    async with db.get_session() as session:
        # Get top 10 users
        result = await session.execute(
            select(User)
            .where(User.banned == False)
            .order_by(User.xp.desc())
            .limit(10)
        )
        top_users = result.scalars().all()
        
        text = "🏆 *Топ 10 пользователей*\n\n"
        
        for i, user in enumerate(top_users, 1):
            level, level_name = Config.get_level_info(user.xp)
            
            # Medal for top 3
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."
            
            username = f"@{user.username}" if user.username else f"ID:{user.id}"
            text += f"{medal} {username} - {user.xp} XP ({level_name})\n"
        
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data="profile:back")]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user statistics via command"""
    user_id = update.effective_user.id
    
    # Для обычных пользователей - только их статистика
    async with db.get_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text(
                "❌ Профиль не найден. Используйте /start для регистрации."
            )
            return
        
        posts_count = await session.execute(
            select(func.count(Post.id))
            .where(Post.user_id == user_id)
            .where(Post.status == PostStatus.APPROVED)
        )
        total_posts = posts_count.scalar()
        
        level, level_name = Config.get_level_info(user.xp)
        
        text = (
            f"📊 *Ваша статистика*\n\n"
            f"⭐ XP: {user.xp}\n"
            f"🎖 Уровень: {level} - {level_name}\n"
            f"✅ Опубликовано постов: {total_posts}"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top users via command (moderators only)"""
    user_id = update.effective_user.id
    
    if not Config.is_moderator(user_id):
        await update.message.reply_text(
            "❌ Команда доступна только модераторам"
        )
        return
    
    async with db.get_session() as session:
        result = await session.execute(
            select(User)
            .where(User.banned == False)
            .order_by(User.xp.desc())
            .limit(5)
        )
        top_users = result.scalars().all()
        
        text = "🏆 *Топ 5 пользователей*\n\n"
        
        for i, user in enumerate(top_users, 1):
            level, level_name = Config.get_level_info(user.xp)
            
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."
            
            username = f"@{user.username}" if user.username else user.first_name or "Пользователь"
            text += f"{medal} {username} - {user.xp} XP\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')

def generate_referral_code():
    """Generate unique referral code"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
