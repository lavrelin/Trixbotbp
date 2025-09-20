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

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Основные импорты
try:
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
    CORE_HANDLERS_AVAILABLE = True
    logger.info("Core handlers loaded successfully")
except ImportError as e:
    logger.error(f"Failed to load core handlers: {e}")
    CORE_HANDLERS_AVAILABLE = False

# Дополнительные импорты с обработкой ошибок
try:
    from handlers.admin_handler import (
        admin_command, 
        stats_command,
        broadcast_command,
        handle_admin_callback
    )
    ADMIN_HANDLERS_AVAILABLE = True
    logger.info("Admin handlers loaded")
except ImportError as e:
    logger.warning(f"Admin handlers not available: {e}")
    ADMIN_HANDLERS_AVAILABLE = False

try:
    from handlers.profile_handler import handle_profile_callback
    PROFILE_HANDLER_AVAILABLE = True
    logger.info("Profile handler loaded")
except ImportError:
    PROFILE_HANDLER_AVAILABLE = False

try:
    from handlers.moderation_handler import handle_moderation_callback, handle_moderation_text
    MODERATION_HANDLER_AVAILABLE = True
    logger.info("Moderation handler loaded")
except ImportError:
    MODERATION_HANDLER_AVAILABLE = False

try:
    from services.db import db
    from services.cooldown import CooldownService
    DB_AVAILABLE = True
    logger.info("Database services loaded")
except ImportError as e:
    logger.error(f"Database services not available: {e}")
    DB_AVAILABLE = False

class TrixBot:
    def __init__(self):
        self.application = None
    
    async def setup(self):
        """Setup bot application and services"""
        try:
            # Create application
            self.application = Application.builder().token(Config.BOT_TOKEN).build()
            logger.info("Telegram application created")
            
            # Initialize database if available
            if DB_AVAILABLE:
                try:
                    await db.init()
                    logger.info("Database initialized successfully")
                    
                    # Initialize cooldown service
                    CooldownService()
                    logger.info("Cooldown service initialized")
                except Exception as e:
                    logger.error(f"Database initialization failed: {e}")
            
            # Add handlers
            self._add_handlers()
            
            logger.info("Bot setup complete")
            
        except Exception as e:
            logger.error(f"Error during bot setup: {e}")
            raise
    
    def _add_handlers(self):
        """Add all command and callback handlers"""
        if not CORE_HANDLERS_AVAILABLE:
            logger.error("Core handlers not available - bot cannot function properly")
            return
            
        app = self.application
        
        try:
            # Command handlers
            app.add_handler(CommandHandler("start", start_command))
            app.add_handler(CommandHandler("help", help_command))
            logger.info("Basic command handlers added")
            
            # Admin handlers (если доступны)
            if ADMIN_HANDLERS_AVAILABLE:
                app.add_handler(CommandHandler("admin", admin_command))
                app.add_handler(CommandHandler("stats", stats_command))
                app.add_handler(CommandHandler("broadcast", broadcast_command))
                logger.info("Admin command handlers added")
            
            # Callback query handlers
            app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern="^menu:"))
            app.add_handler(CallbackQueryHandler(handle_publication_callback, pattern="^pub:"))
            app.add_handler(CallbackQueryHandler(handle_piar_callback, pattern="^piar:"))
            logger.info("Core callback handlers added")
            
            if PROFILE_HANDLER_AVAILABLE:
                app.add_handler(CallbackQueryHandler(handle_profile_callback, pattern="^profile:"))
                logger.info("Profile callback handler added")
            
            if MODERATION_HANDLER_AVAILABLE:
                app.add_handler(CallbackQueryHandler(handle_moderation_callback, pattern="^mod:"))
                logger.info("Moderation callback handler added")
            
            if ADMIN_HANDLERS_AVAILABLE:
                app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^admin:"))
                logger.info("Admin callback handler added")
            
            # Message handlers - только фото и видео
            app.add_handler(MessageHandler(
                filters.PHOTO | filters.VIDEO,
                self._handle_media_message
            ))
            logger.info("Media handler added")
            
            # Text handler - активация любым сообщением
            app.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_text_message
            ))
            logger.info("Text handler added")
            
            logger.info("All handlers added successfully")
            
        except Exception as e:
            logger.error(f"Error adding handlers: {e}")
            raise
    
    async def _handle_text_message(self, update, context):
        """Route text messages to appropriate handler"""
        try:
            user_id = update.effective_user.id
            waiting_for = context.user_data.get('waiting_for')
            
            logger.debug(f"Text message from user {user_id}, waiting_for: {waiting_for}")
            
            # НОВОЕ: Проверяем, если это модератор и он отправляет ответ на заявку
            if MODERATION_HANDLER_AVAILABLE and Config.is_moderator(user_id):
                mod_waiting_for = context.user_data.get('mod_waiting_for')
                if mod_waiting_for in ['approve_link', 'reject_reason']:
                    await handle_moderation_text(update, context)
                    return
            
            # Проверяем, если бот ожидает медиа, а пользователь отправил текст
            if waiting_for == 'piar_photo':
                await update.message.reply_text("📷 Пожалуйста, отправьте фото или видео, либо нажмите кнопку 'Дальше' для продолжения")
                return
            elif waiting_for == 'post_photo':
                await update.message.reply_text("📷 Пожалуйста, отправьте фото или видео для вашей публикации")
                return
            
            if not waiting_for:
                if DB_AVAILABLE:
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
                                await start_command(update, context)
                                return
                            else:
                                from handlers.start_handler import show_main_menu
                                await show_main_menu(update, context)
                                return
                    except Exception as e:
                        logger.error(f"Error checking user in DB: {e}")
                        from handlers.start_handler import show_main_menu
                        await show_main_menu(update, context)
                        return
                else:
                    from handlers.start_handler import show_main_menu
                    await show_main_menu(update, context)
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
                from handlers.start_handler import show_main_menu
                await show_main_menu(update, context)
                
        except Exception as e:
            logger.error(f"Error handling text message: {e}")
            try:
                from handlers.start_handler import show_main_menu
                await show_main_menu(update, context)
            except:
                await update.message.reply_text("Произошла ошибка. Попробуйте /start")
    
    async def _handle_media_message(self, update, context):
        """Route media messages to appropriate handler"""
        try:
            waiting_for = context.user_data.get('waiting_for')
            
            logger.debug(f"Media message, waiting_for: {waiting_for}")
            
            # Проверяем, если бот ожидает текст, а пользователь отправил медиа
            if waiting_for and waiting_for.startswith('piar_') and waiting_for != 'piar_photo':
                await update.message.reply_text("💭 Пожалуйста, добавьте текст как указано в инструкции")
                return
            elif waiting_for == 'post_text':
                await update.message.reply_text("📝 Пожалуйста, сначала добавьте текст для вашей публикации")
                return
            
            if 'post_data' in context.user_data:
                await handle_media_input(update, context)
            elif waiting_for == 'piar_photo':
                await handle_piar_photo(update, context)
            elif update.message.caption and waiting_for:
                await self._handle_text_message(update, context)
            else:
                await update.message.reply_text("📷 Для загрузки медиа используйте соответствующий раздел в меню")
                
        except Exception as e:
            logger.error(f"Error handling media message: {e}")
            await update.message.reply_text("Произошла ошибка при обработке медиа")
    
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
        try:
            if DB_AVAILABLE and hasattr(db, 'close'):
                await db.close()
            logger.info("Bot cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# конец класса TrixBot
# --------------------

def main():
    """Main entry point"""
    logger.info("Starting TrixBot...")

    bot = TrixBot()

    try:
        import asyncio
        # Асинхронная инициализация
        asyncio.get_event_loop().run_until_complete(bot.setup())

        # Запуск polling напрямую
        bot.application.run_polling(
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
