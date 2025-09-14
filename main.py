#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import asyncio
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler,
    filters
)

from config import Config
from handlers.start_handler import start_command, help_command
from handlers.menu_handler import handle_menu_callback
from handlers.publication_handler import (
    handle_publication_callback, 
    handle_text_input, 
    handle_media_input
)
from handlers.piar_handler import (
    handle_piar_callback, 
    handle_piar_text,
    handle_piar_photo
)
from handlers.profile_handler import handle_profile_callback
from handlers.moderation_handler import handle_moderation_callback
from handlers.admin_handler import (
    admin_command, 
    stats_command,
    broadcast_command,
    handle_admin_callback
)
from handlers.scheduler_handler import (
    SchedulerHandler,
    scheduler_command
)
from services.db import db
from services.cooldown import CooldownService

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TrixBot:
    def __init__(self):
        self.application = None
        self.scheduler = None
    
    async def setup(self):
        """Setup bot application and services"""
        # Create application
        self.application = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Initialize database
        await db.init()
        
        # Initialize cooldown service
        CooldownService()
        
        # Setup scheduler
        if Config.SCHEDULER_ENABLED:
            self.scheduler = SchedulerHandler()
            await self.scheduler.start()
        
        # Add handlers
        self._add_handlers()
        
        logger.info("Bot setup complete")
    
    def _add_handlers(self):
        """Add all command and callback handlers"""
        app = self.application
        
        # Command handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("admin", admin_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CommandHandler("scheduler", scheduler_command))
        
        # Callback query handlers
        app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern="^menu:"))
        app.add_handler(CallbackQueryHandler(handle_publication_callback, pattern="^pub:"))
        app.add_handler(CallbackQueryHandler(handle_piar_callback, pattern="^piar:"))
        app.add_handler(CallbackQueryHandler(handle_profile_callback, pattern="^profile:"))
        app.add_handler(CallbackQueryHandler(handle_moderation_callback, pattern="^mod:"))
        app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^admin:"))
        
        # Message handlers with priority order
        # Media handler (higher priority)
        app.add_handler(MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.DOCUMENT,
            self._handle_media_message
        ))
        
        # Text handler (lower priority)
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_text_message
        ))
    
    async def _handle_text_message(self, update, context):
        """Route text messages to appropriate handler"""
        waiting_for = context.user_data.get('waiting_for')
        
        if not waiting_for:
            # No active state, ignore
            return
        
        if waiting_for == 'post_text':
            await handle_text_input(update, context)
        elif waiting_for.startswith('piar_'):
            field = waiting_for.replace('piar_', '')
            await handle_piar_text(update, context, field, update.message.text)
        elif waiting_for == 'cancel_reason':
            await handle_text_input(update, context)
        else:
            logger.warning(f"Unhandled waiting_for state: {waiting_for}")
    
    async def _handle_media_message(self, update, context):
        """Route media messages to appropriate handler"""
        waiting_for = context.user_data.get('waiting_for')
        
        # Handle media for publications
        if 'post_data' in context.user_data:
            await handle_media_input(update, context)
        # Handle media for piar
        elif waiting_for == 'piar_photo':
            await handle_piar_photo(update, context)
        # Handle media with caption as text
        elif update.message.caption and waiting_for:
            await self._handle_text_message(update, context)
    
    async def run(self):
        """Run the bot"""
        try:
            await self.setup()
            
            logger.info("Starting bot polling...")
            await self.application.run_polling(
                allowed_updates=['message', 'callback_query'],
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.scheduler:
            await self.scheduler.stop()
        
        if hasattr(db, 'close'):
            await db.close()
        
        logger.info("Bot cleanup complete")

def main():
    """Main entry point"""
    bot = TrixBot()
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise

if __name__ == '__main__':
    main()
