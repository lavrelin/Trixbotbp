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
        
        # Calculate next level XP
        next_level_xp = 0
        for lvl, (min_xp, _) in Config.XP_LEVELS.items():
            if lvl == level + 1:
                next_level_xp = min_xp
                break
        
        # Build profile text
        text = f"👤 *Ваш профиль*\n\n"
        text += f"🆔 ID: `{user.id}`\n"
        
        if user.username:
            text += f"📱 Username: @{user.username}\n"
        
        text += f"📝 Имя: {user.first_name or 'не указано'}\n"
        
        if user.gender and user.gender != Gender.UNKNOWN:
            gender_icons = {'M': '👨', 'F': '👩', 'other': '🤷'}
            text += f"👤 Пол: {gender_icons.get(user.gender.value, '')} {user.gender.value}\n"
        
        if user.birthdate:
            text += f"🎂 Дата рождения: {user.birthdate.strftime('%d.%m.%Y')}\n"
        
        text += f"\n📊 *Статистика:*\n"
        text += f"⭐ XP: {user.xp}"
        
        if next_level_xp:
            text += f" / {next_level_xp}"
        
        text += f"\n🎖 Уровень: {level} - {level_name}\n"
        text += f"📝 Постов всего: {total_posts}\n"
        text += f"✅ Опубликовано: {approved_posts}\n"
        
        if user.referral_code:
            text += f"\n🔗 *Реферальная ссылка:*\n"
            text += f"`https://t.me/Trixlivebot?start={user.referral_code}`\n"
            text += f"Приглашайте друзей и получайте +{Config.XP_REFERRAL} XP!\n"
        
        text += f"\n📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}"
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Моя статистика", callback_data="profile:stats"),
                InlineKeyboardButton("🏆 Топ", callback_data="profile:top")
            ],
            [
                InlineKeyboardButton("✏️ Изменить данные", callback_data="profile:edit"),
                InlineKeyboardButton("🔗 Реф. ссылка", callback_data="profile:referral")
            ],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="menu:back")]
        ]
        
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
    
    if action == "stats":
        await show_user_stats(update, context)
    elif action == "top":
        await show_top_users(update, context)
    elif action == "edit":
        await start_edit_profile(update, context)
    elif action == "referral":
        await show_referral_info(update, context)
    elif action == "gender":
        # Обработка выбора пола при регистрации
        gender_value = data[2] if len(data) > 2 else None
        await save_gender(update, context, gender_value)
    elif action == "birthdate":
        await request_birthdate(update, context)
    elif action == "skip_birthdate" or action == "skip":
        # Пропуск даты рождения
        await finish_registration(update, context)
    elif action == "back":
        # Возврат в профиль
        await show_profile(update, context)

async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish registration and show main menu"""
    from handlers.start_handler import show_main_menu
    
    # Clear registration data
    context.user_data.pop('registration', None)
    context.user_data.pop('waiting_for', None)
    
    await show_main_menu(update, context)

async def show_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed user statistics"""
    user_id = update.effective_user.id
    
    async with db.get_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.callback_query.answer("❌ Профиль не найден", show_alert=True)
            return
        
        # Statistics for last 30 days
        month_ago = datetime.utcnow() - timedelta(days=30)
        
        # Posts statistics
        month_posts = await session.execute(
            select(func.count(Post.id))
            .where(Post.user_id == user_id)
            .where(Post.created_at > month_ago)
        )
        month_posts_count = month_posts.scalar()
        
        # XP events
        month_xp = await session.execute(
            select(func.sum(XPEvent.xp_amount))
            .where(XPEvent.user_id == user_id)
            .where(XPEvent.timestamp > month_ago)
        )
        month_xp_earned = month_xp.scalar() or 0
        
        # Referrals count
        referrals = await session.execute(
            select(func.count(User.id))
            .where(User.referred_by == user_id)
        )
        referrals_count = referrals.scalar()
        
        text = (
            f"📊 *Ваша статистика*\n\n"
            f"*За последние 30 дней:*\n"
            f"📝 Постов: {month_posts_count}\n"
            f"⭐ XP заработано: {month_xp_earned}\n\n"
            f"*За все время:*\n"
            f"👥 Приглашено друзей: {referrals_count}\n"
            f"⭐ Всего XP: {user.xp}\n"
        )
        
        # Add cooldown info if exists
        if user.cooldown_expires_at and user.cooldown_expires_at > datetime.utcnow():
            remaining = int((user.cooldown_expires_at - datetime.utcnow()).total_seconds())
            minutes = remaining // 60
            text += f"\n⏰ До следующего поста: {minutes} мин."
        
        keyboard = [
            [InlineKeyboardButton("◀️ Назад в профиль", callback_data="profile:back")]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user statistics via command"""
    user_id = update.effective_user.id
    
    async with db.get_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text(
                "❌ Профиль не найден. Используйте /start для регистрации."
            )
            return
        
        # Quick stats
        posts_count = await session.execute(
            select(func.count(Post.id))
            .where(Post.user_id == user_id)
            .where(Post.status == PostStatus.APPROVED)
        )
        total_posts = posts_count.scalar()
        
        level, level_name = Config.get_level_info(user.xp)
        
        text = (
            f"📊 *Краткая статистика*\n\n"
            f"⭐ XP: {user.xp}\n"
            f"🎖 Уровень: {level} - {level_name}\n"
            f"✅ Опубликовано постов: {total_posts}"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')

async def show_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top users by XP"""
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

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top users via command"""
    async with db.get_session() as session:
        # Get top 5 users for command
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

async def show_referral_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show referral information"""
    user_id = update.effective_user.id
    
    async with db.get_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.callback_query.answer("❌ Профиль не найден", show_alert=True)
            return
        
        # Generate referral code if doesn't exist
        if not user.referral_code:
            user.referral_code = generate_referral_code()
            await session.commit()
        
        # Count referrals
        referrals = await session.execute(
            select(func.count(User.id))
            .where(User.referred_by == user_id)
        )
        referrals_count = referrals.scalar()
        
        text = (
            f"🔗 *Реферальная программа*\n\n"
            f"Приглашайте друзей и получайте *+{Config.XP_REFERRAL} XP* "
            f"за каждого нового пользователя!\n\n"
            f"*Ваша реферальная ссылка:*\n"
            f"`https://t.me/Trixlivebot?start={user.referral_code}`\n\n"
            f"Нажмите на ссылку чтобы скопировать\n\n"
            f"👥 Приглашено друзей: {referrals_count}\n"
            f"⭐ XP заработано: {referrals_count * Config.XP_REFERRAL}"
        )
        
        keyboard = [
            [InlineKeyboardButton("📤 Поделиться ссылкой", 
                                 url=f"https://t.me/share/url?url=https://t.me/Trixlivebot?start={user.referral_code}&text=Присоединяйся к боту TRIX!")],
            [InlineKeyboardButton("◀️ Назад", callback_data="profile:back")]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def start_edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start profile editing"""
    keyboard = [
        [InlineKeyboardButton("👤 Изменить пол", callback_data="profile:edit_gender")],
        [InlineKeyboardButton("🎂 Изменить дату рождения", callback_data="profile:edit_birthdate")],
        [InlineKeyboardButton("◀️ Назад", callback_data="profile:back")]
    ]
    
    await update.callback_query.edit_message_text(
        "✏️ *Редактирование профиля*\n\n"
        "Что вы хотите изменить?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def save_gender(update: Update, context: ContextTypes.DEFAULT_TYPE, gender_value: str):
    """Save user gender during registration"""
    user_id = update.effective_user.id
    
    # Map gender value
    gender_map = {
        'M': Gender.MALE,
        'F': Gender.FEMALE,
        'other': Gender.OTHER
    }
    
    gender = gender_map.get(gender_value, Gender.UNKNOWN)
    
    # Check if this is registration or profile edit
    if 'registration' in context.user_data:
        # Registration flow
        context.user_data['registration']['gender'] = gender
        context.user_data['waiting_for'] = 'birthdate'
        
        keyboard = [[InlineKeyboardButton("⏭ Пропустить", callback_data="profile:skip_birthdate")]]
        
        await update.callback_query.edit_message_text(
            "🎂 Укажите дату рождения в формате ДД.ММ.ГГГГ\n"
            "(например: 15.03.1990)\n\n"
            "Или нажмите 'Пропустить'",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Profile edit
        async with db.get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                user.gender = gender
                await session.commit()
                
                await update.callback_query.answer("✅ Пол обновлен", show_alert=True)
                await show_profile(update, context)

async def request_birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request birthdate from user"""
    context.user_data['waiting_for'] = 'birthdate_edit'
    
    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="profile:back")]]
    
    await update.callback_query.edit_message_text(
        "🎂 Введите дату рождения в формате ДД.ММ.ГГГГ\n"
        "(например: 15.03.1990)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def generate_referral_code():
    """Generate unique referral code"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
