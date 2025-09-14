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

# Configure logging first
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Попытка импорта admin handlers с обработкой ошибки
try:
    from handlers.admin_handler import (
        admin_command, 
        stats_command,
        broadcast_command,
        handle_admin_callback
    )
    ADMIN_HANDLERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Admin handlers not available: {e}")
    ADMIN_HANDLERS_AVAILABLE = False

# Попытка импорта других handlers
try:
    from handlers.profile_handler import handle_profile_callback
    PROFILE_HANDLER_AVAILABLE = True
except ImportError:
    PROFILE_HANDLER_AVAILABLE = False

try:
    from handlers.moderation_handler import handle_moderation_callback
    MODERATION_HANDLER_AVAILABLE = True
except ImportError:
    MODERATION_HANDLER_AVAILABLE = False

try:
    from handlers.scheduler_handler import (
        SchedulerHandler,
        scheduler_command
    )
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

from services.db import db
from services.cooldown import CooldownService

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
        if Config.SCHEDULER_ENABLED and SCHEDULER_AVAILABLE:
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
        
        # Admin handlers (если доступны)
        if ADMIN_HANDLERS_AVAILABLE:
            app.add_handler(CommandHandler("admin", admin_command))
            app.add_handler(CommandHandler("stats", stats_command))
            app.add_handler(CommandHandler("broadcast", broadcast_command))
        
        if SCHEDULER_AVAILABLE:
            app.add_handler(CommandHandler("scheduler", scheduler_command))
        
        # Callback query handlers
        app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern="^menu:"))
        app.add_handler(CallbackQueryHandler(handle_publication_callback, pattern="^pub:"))
        app.add_handler(CallbackQueryHandler(handle_piar_callback, pattern="^piar:"))
        
        if PROFILE_HANDLER_AVAILABLE:
            app.add_handler(CallbackQueryHandler(handle_profile_callback, pattern="^profile:"))
        
        if MODERATION_HANDLER_AVAILABLE:
            app.add_handler(CallbackQueryHandler(handle_moderation_callback, pattern="^mod:"))
        
        if ADMIN_HANDLERS_AVAILABLE:
            app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^admin:"))
        
        # Message handlers with priority order
        # Media handler (higher priority) - исправленные фильтры
        try:
            # Пробуем новый синтаксис для документов
            media_filter = filters.PHOTO | filters.VIDEO | filters.Document.ALL
        except AttributeError:
            # Fallback для старых версий
            try:
                media_filter = filters.PHOTO | filters.VIDEO | filters.DOCUMENT
            except AttributeError:
                # Если и это не работает, только фото и видео
                media_filter = filters.PHOTO | filters.VIDEO
                logger.warning("Document filter not available, using only PHOTO and VIDEO")
        
        app.add_handler(MessageHandler(media_filter, self._handle_media_message))
        
        # Text handler (lower priority) - активация любым сообщением
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_text_message
        ))
    
    async def _handle_text_message(self, update, context):
        """Route text messages to appropriate handler"""
        user_id = update.effective_user.id
        waiting_for = context.user_data.get('waiting_for')
        
        # Если пользователь новый или нет активного состояния - показать главное меню
        if not waiting_for:
            # Проверяем, зарегистрирован ли пользователь
            try:
                from services.db import db
                from models import User
                from sqlalchemy import select
                
                async with db.get_session() as session:
                    result = await session.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = result.scalar_one_or_none()
                    
                    if not user:
                        # Новый пользователь - запускаем команду start
                        await start_command(update, context)
                        return
                    else:
                        # Существующий пользователь - показываем главное меню
                        from handlers.start_handler import show_main_menu
                        await show_main_menu(update, context)
                        return
            except Exception as e:
                logger.error(f"Error checking user: {e}")
                # В случае ошибки БД показываем меню
                from handlers.start_handler import show_main_menu
                await show_main_menu(update, context)
                return
        
        # Обработка активных состояний
        if waiting_for == 'post_text':
            await handle_text_input(update, context)
        elif waiting_for.startswith('piar_'):
            field = waiting_for.replace('piar_', '')
            await handle_piar_text(update, context, field, update.message.text)
        elif waiting_for == 'cancel_reason':
            await handle_text_input(update, context)
        else:
            logger.warning(f"Unhandled waiting_for state: {waiting_for}")
            # Показать главное меню при неизвестном состоянии
            from handlers.start_handler import show_main_menu
            await show_main_menu(update, context)
    
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
        else:
            # Если нет активного состояния, показать меню
            from handlers.start_handler import show_main_menu
            await show_main_menu(update, context)
    
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
