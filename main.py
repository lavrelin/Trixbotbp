import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import Config
from services.db import db
from handlers import (
    start_handler,
    menu_handler, 
    publication_handler,
    piar_handler,
    moderation_handler,
    admin_handler,
    profile_handler,
    scheduler_handler
)
from services.scheduler_service import SchedulerService
from utils.permissions import admin_only, moderator_only
import sys

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору."
        )

async def post_init(application: Application):
    """Initialize bot after start"""
    # Initialize database
    await db.init()
    
    # Initialize scheduler
    scheduler = SchedulerService(application.bot)
    await scheduler.init()
    application.bot_data['scheduler'] = scheduler
    
    logger.info("Bot initialized successfully")

async def post_shutdown(application: Application):
    """Cleanup on shutdown"""
    await db.close()
    
    if 'scheduler' in application.bot_data:
        scheduler = application.bot_data['scheduler']
        scheduler.stop()
    
    logger.info("Bot shutdown complete")

def main():
    """Start the bot"""
    if not Config.BOT_TOKEN:
        logger.error("No bot token provided!")
        sys.exit(1)
    
    # Create application
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add initialization handlers
    application.post_init = post_init
    application.post_shutdown = post_shutdown
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_handler.start_command))
    application.add_handler(CommandHandler("help", start_handler.help_command))
    application.add_handler(CommandHandler("profile", profile_handler.profile_command))
    application.add_handler(CommandHandler("stats", profile_handler.stats_command))
    application.add_handler(CommandHandler("top", profile_handler.top_command))
    
    # Admin commands
    application.add_handler(CommandHandler("panel", admin_handler.panel_command))
    application.add_handler(CommandHandler("ban", admin_handler.ban_command))
    application.add_handler(CommandHandler("unban", admin_handler.unban_command))
    application.add_handler(CommandHandler("mute", admin_handler.mute_command))
    application.add_handler(CommandHandler("unmute", admin_handler.unmute_command))
    application.add_handler(CommandHandler("cdreset", admin_handler.cdreset_command))
    application.add_handler(CommandHandler("broadcast", admin_handler.broadcast_command))
    application.add_handler(CommandHandler("admins", admin_handler.admins_command))
    application.add_handler(CommandHandler("user", admin_handler.user_info_command))
    
    # Scheduler commands
    application.add_handler(CommandHandler("scheduler", scheduler_handler.scheduler_status))
    application.add_handler(CommandHandler("scheduler_on", scheduler_handler.scheduler_on))
    application.add_handler(CommandHandler("scheduler_off", scheduler_handler.scheduler_off))
    application.add_handler(CommandHandler("scheduler_message", scheduler_handler.scheduler_message))
    application.add_handler(CommandHandler("scheduler_test", 
   
# Callback query handlers
application.add_handler(CallbackQueryHandler(start_handler.handle_registration_callback, pattern="^reg:"))                                           
application.add_handler(CallbackQueryHandler(menu_handler.handle_menu_callback, pattern="^menu:"))
application.add_handler(CallbackQueryHandler(publication_handler.handle_publication_callback, pattern="^pub:"))
application.add_handler(CallbackQueryHandler(piar_handler.handle_piar_callback, pattern="^piar:"))
application.add_handler(CallbackQueryHandler(moderation_handler.handle_moderation_callback, pattern="^mod:"))
application.add_handler(CallbackQueryHandler(profile_handler.handle_profile_callback, pattern="^profile:"))
    
    # Message handlers
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        publication_handler.handle_text_input
    ))
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL,
        publication_handler.handle_media_input
    ))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
