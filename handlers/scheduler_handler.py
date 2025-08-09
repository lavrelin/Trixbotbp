from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from models import Scheduler
from sqlalchemy import select
from utils.permissions import admin_only
import logging

logger = logging.getLogger(__name__)

@admin_only
async def scheduler_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show scheduler status"""
    async with db.get_session() as session:
        result = await session.execute(
            select(Scheduler).where(Scheduler.id == 1)
        )
        scheduler = result.scalar_one_or_none()
        
        if not scheduler:
            # Create default scheduler config
            scheduler = Scheduler(
                id=1,
                enabled=Config.SCHEDULER_ENABLED,
                min_interval=Config.SCHEDULER_MIN_INTERVAL,
                max_interval=Config.SCHEDULER_MAX_INTERVAL,
                message_text=Config.DEFAULT_PROMO_MESSAGE
            )
            session.add(scheduler)
            await session.commit()
        
        status = "✅ Включен" if scheduler.enabled else "❌ Выключен"
        last_run = scheduler.last_run.strftime('%d.%m %H:%M') if scheduler.last_run else "Никогда"
        
        text = (
            f"⏰ *Планировщик рассылки*\n\n"
            f"Статус: {status}\n"
            f"Интервал: {scheduler.min_interval}-{scheduler.max_interval} минут\n"
            f"Последний запуск: {last_run}\n\n"
            f"*Текст сообщения:*\n{scheduler.message_text}\n\n"
            f"*Команды:*\n"
            f"/scheduler_on - включить\n"
            f"/scheduler_off - выключить\n"
            f"/scheduler_message - изменить текст\n"
            f"/scheduler_test - тестовая отправка"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')

@admin_only
async def scheduler_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable scheduler"""
    async with db.get_session() as session:
        result = await session.execute(
            select(Scheduler).where(Scheduler.id == 1)
        )
        scheduler = result.scalar_one_or_none()
        
        if not scheduler:
            scheduler = Scheduler(
                id=1,
                enabled=True,
                min_interval=Config.SCHEDULER_MIN_INTERVAL,
                max_interval=Config.SCHEDULER_MAX_INTERVAL,
                message_text=Config.DEFAULT_PROMO_MESSAGE
            )
            session.add(scheduler)
        else:
            scheduler.enabled = True
        
        await session.commit()
    
    # Restart scheduler service
    if 'scheduler' in context.bot_data:
        scheduler_service = context.bot_data['scheduler']
        await scheduler_service.start()
    
    await update.message.reply_text("✅ Планировщик включен")

@admin_only
async def scheduler_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable scheduler"""
    async with db.get_session() as session:
        result = await session.execute(
            select(Scheduler).where(Scheduler.id == 1)
        )
        scheduler = result.scalar_one_or_none()
        
        if scheduler:
            scheduler.enabled = False
            await session.commit()
    
    # Stop scheduler service
    if 'scheduler' in context.bot_data:
        scheduler_service = context.bot_data['scheduler']
        scheduler_service.stop()
    
    await update.message.reply_text("❌ Планировщик выключен")

@admin_only
async def scheduler_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change scheduler message"""
    if not context.args:
        await update.message.reply_text(
            "Использование: /scheduler_message <новый текст>"
        )
        return
    
    new_text = ' '.join(context.args)
    
    async with db.get_session() as session:
        result = await session.execute(
            select(Scheduler).where(Scheduler.id == 1)
        )
        scheduler = result.scalar_one_or_none()
        
        if not scheduler:
            scheduler = Scheduler(
                id=1,
                enabled=Config.SCHEDULER_ENABLED,
                min_interval=Config.SCHEDULER_MIN_INTERVAL,
                max_interval=Config.SCHEDULER_MAX_INTERVAL,
                message_text=new_text
            )
            session.add(scheduler)
        else:
            scheduler.message_text = new_text
        
        await session.commit()
    
    await update.message.reply_text(
        f"✅ Текст обновлен:\n\n{new_text}"
    )

@admin_only
async def scheduler_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test scheduler message"""
    async with db.get_session() as session:
        result = await session.execute(
            select(Scheduler).where(Scheduler.id == 1)
        )
        scheduler = result.scalar_one_or_none()
        
        if not scheduler:
            message_text = Config.DEFAULT_PROMO_MESSAGE
        else:
            message_text = scheduler.message_text
    
    # Send test message to admin
    await update.message.reply_text(
        f"📢 *Тестовое сообщение планировщика:*\n\n{message_text}",
        parse_mode='Markdown'
    )
    
    await update.message.reply_text(
        "✅ Тестовое сообщение отправлено вам.\n"
        "В рабочем режиме оно будет отправлено в чат."
    )
