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
        admin_command, stats_command, say_command,
        id_command, whois_command, translate_command, weather_command,
        join_command, participants_command, report_command,
        ban_command, unban_command, admcom_command, handle_admin_callback
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
    from handlers.games_handler import (
        # Игра "Угадай слово"
        wordadd_command, wordedit_command, wordclear_command, 
        wordon_command, wordoff_command, anstimeset_command,
        game_say_command, wordinfo_command,
        # Розыгрыш
        roll_participant_command, mynumber_command, roll_draw_command,
        rollreset_command, rollstatus_command,
        # Информационные
        gamesinfo_command, admgamesinfo_command
    )
    GAMES_HANDLERS_AVAILABLE = True
    logger.info("Games handlers loaded")
except ImportError as e:
    logger.warning(f"Games handlers not available: {e}")
    GAMES_HANDLERS_AVAILABLE = False

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
            # Базовые команды
            app.add_handler(CommandHandler("start", start_command))
            app.add_handler(CommandHandler("help", help_command))
            logger.info("Basic command handlers added")
            
            # Админские и модераторские команды
            if ADMIN_HANDLERS_AVAILABLE:
                app.add_handler(CommandHandler("admin", admin_command))
                app.add_handler(CommandHandler("stats", stats_command))
                app.add_handler(CommandHandler("say", say_command))
                app.add_handler(CommandHandler("id", id_command))
                app.add_handler(CommandHandler("whois", whois_command))
                app.add_handler(CommandHandler("translate", translate_command))
                app.add_handler(CommandHandler("weather", weather_command))
                app.add_handler(CommandHandler("join", join_command))
                app.add_handler(CommandHandler("participants", participants_command))
                app.add_handler(CommandHandler("report", report_command))
                app.add_handler(CommandHandler("ban", ban_command))
                app.add_handler(CommandHandler("unban", unban_command))
                app.add_handler(CommandHandler("admcom", admcom_command))
                logger.info("Admin command handlers added")
            
            # Игровые команды
            if GAMES_HANDLERS_AVAILABLE:
                # Игра "Угадай слово" - версия play3xia
                app.add_handler(CommandHandler("play3xiawordadd", wordadd_command))
                app.add_handler(CommandHandler("play3xiawordedit", wordedit_command))
                app.add_handler(CommandHandler("play3xiawordclear", wordclear_command))
                app.add_handler(CommandHandler("play3xiawordon", wordon_command))
                app.add_handler(CommandHandler("play3xiawordoff", wordoff_command))
                app.add_handler(CommandHandler("play3xiaanstimeset", anstimeset_command))
                app.add_handler(CommandHandler("play3xiasay", game_say_command))
                app.add_handler(CommandHandler("play3xiawordinfo", wordinfo_command))
                app.add_handler(CommandHandler("play3xiagamesinfo", gamesinfo_command))
                app.add_handler(CommandHandler("play3xiaadmgamesinfo", admgamesinfo_command))
                
                # Игра "Угадай слово" - версия play3x  
                app.add_handler(CommandHandler("play3xwordadd", wordadd_command))
                app.add_handler(CommandHandler("play3xwordedit", wordedit_command))
                app.add_handler(CommandHandler("play3xwordclear", wordclear_command))
                app.add_handler(CommandHandler("play3xwordon", wordon_command))
                app.add_handler(CommandHandler("play3xwordoff", wordoff_command))
                app.add_handler(CommandHandler("play3xanstimeset", anstimeset_command))
                app.add_handler(CommandHandler("play3xsay", game_say_command))
                app.add_handler(CommandHandler("play3xwordinfo", wordinfo_command))
                app.add_handler(CommandHandler("play3xgamesinfo", gamesinfo_command))
                app.add_handler(CommandHandler("play3xadmgamesinfo", admgamesinfo_command))
                
                # Игра "Угадай слово" - версия playxxx
                app.add_handler(CommandHandler("playxxxwordadd", wordadd_command))
                app.add_handler(CommandHandler("playxxxwordedit", wordedit_command))
                app.add_handler(CommandHandler("playxxxwordclear", wordclear_command))
                app.add_handler(CommandHandler("playxxxwordon", wordon_command))
                app.add_handler(CommandHandler("playxxxwordoff", wordoff_command))
                app.add_handler(CommandHandler("playxxxanstimeset", anstimeset_command))
                app.add_handler(CommandHandler("playxxxsay", game_say_command))
                app.add_handler(CommandHandler("playxxxwordinfo", wordinfo_command))
                app.add_handler(CommandHandler("playxxxgamesinfo", gamesinfo_command))
                app.add_handler(CommandHandler("playxxxadmgamesinfo", admgamesinfo_command))
                
                # Розыгрыш - версия play3xia
                app.add_handler(CommandHandler("play3xiaroll", roll_participant_command))
                app.add_handler(CommandHandler("play3xiamynumber", mynumber_command))
                app.add_handler(CommandHandler("play3xiarollreset", rollreset_command))
                app.add_handler(CommandHandler("play3xiarollstatus", rollstatus_command))
                
                # Розыгрыш - версия play3x
                app.add_handler(CommandHandler("play3xroll", roll_participant_command))
                app.add_handler(CommandHandler("play3xmynumber", mynumber_command))
                app.add_handler(CommandHandler("play3xrollreset", rollreset_command))
                app.add_handler(CommandHandler("play3xrollstatus", rollstatus_command))
                
                # Розыгрыш - версия playxxx
                app.add_handler(CommandHandler("playxxxroll", roll_participant_command))
                app.add_handler(CommandHandler("playxxxmynumber", mynumber_command))
                app.add_handler(CommandHandler("playxxxrollreset", rollreset_command))
                app.add_handler(CommandHandler("playxxxrollstatus", rollstatus_command))
                
                # Специальная обработка для админского /roll с количеством победителей
                # Эти команды обрабатываются той же функцией, но логика внутри определяет режим
                app.add_handler(CommandHandler("play3xiaroll", self._handle_admin_roll))
                app.add_handler(CommandHandler("play3xroll", self._handle_admin_roll))
                app.add_handler(CommandHandler("playxxxroll", self._handle_admin_roll))
                
                logger.info("Games command handlers added")
            
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
    
    async def _handle_admin_roll(self, update, context):
        """Handle admin roll command vs user roll command"""
        user_id = update.effective_user.id
        
        # Если есть аргументы и это админ, и аргумент - число от 1 до 5
        if (Config.is_admin(user_id) and context.args and 
            len(context.args) == 1 and context.args[0].isdigit() and 
            1 <= int(context.args[0]) <= 5):
            # Это админская команда для проведения розыгрыша
            await roll_draw_command(update, context)
        else:
            # Это обычная команда участника для получения номера
            await roll_participant_command(update, context)
    
    async def _handle_text_message(self, update, context):
        """Route text messages to appropriate handler"""
        try:
            user_id = update.effective_user.id
            waiting_for = context.user_data.get('waiting_for')
            
            logger.debug(f"Text message from user {user_id}, waiting_for: {waiting_for}")
            
            # Проверяем, если это модератор и он отправляет ответ на заявку
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
