from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
import logging

logger = logging.getLogger(__name__)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command"""
    user_id = update.effective_user.id
    
    if not Config.is_admin(user_id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast")],
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

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command"""
    user_id = update.effective_user.id
    
    if not Config.is_admin(user_id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    await update.message.reply_text(
        "📢 Функция рассылки в разработке"
    )

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
        await broadcast_command(update, context)
    else:
        await query.answer("Функция в разработке", show_alert=True)
