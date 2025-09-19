# -*- coding: utf-8 -*-
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from services.cooldown import CooldownService
from services.hashtags import HashtagService
from services.filter_service import FilterService
from models import User, Post, PostStatus
from sqlalchemy import select
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def handle_publication_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle publication callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    
    if action == "cat":
        # Subcategory selected
        subcategory = data[2] if len(data) > 2 else None
        await start_post_creation(update, context, subcategory)
    elif action == "preview":
        await show_preview(update, context)
    elif action == "send":
        await send_to_moderation(update, context)
    elif action == "edit":
        await edit_post(update, context)
    elif action == "cancel":
        await cancel_post_with_reason(update, context)
    elif action == "cancel_confirm":
        await cancel_post(update, context)
    elif action == "add_media":
        await request_media(update, context)
    elif action == "back":
        # Возврат к предпросмотру
        await show_preview(update, context)

async def start_post_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, subcategory: str):
    """Start creating a post with selected subcategory"""
    subcategory_names = {
        'work': '👷‍♀️ Работа',
        'rent': '🏠 Аренда',
        'buy': '🔻 Куплю',
        'sell': '🔺 Продам',
        'events': '🎉 События',
        'free': '📦 Отдам даром',
        'important': '🌪️ Важно',
        'other': '❔ Другое'
    }
    
    # Сохраняем данные поста
    context.user_data['post_data'] = {
        'category': '🗯️ Будапешт',
        'subcategory': subcategory_names.get(subcategory, '❔ Другое'),
        'anonymous': False
    }

    keyboard = [[InlineKeyboardButton("🔙 Вернуться", callback_data="menu:announcements")]]
    
    await update.callback_query.edit_message_text(
        f"🗯️ Будапешт → 🗣️ Объявления → {subcategory_names.get(subcategory)}\n\n"
        "📝 Отправьте текст вашего объявления и/или фото/видео:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['waiting_for'] = 'post_text'

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста от пользователя"""
    
    # Проверяем, есть ли медиа вместе с текстом
    has_media = update.message.photo or update.message.video or update.message.document
    
    # Если медиа и текст одновременно (caption)
    if has_media and update.message.caption:
        text = update.message.caption
        
        # Если ждём текст поста
        if context.user_data.get('waiting_for') == 'post_text':
            # Проверяем на запрещённые ссылки
            filter_service = FilterService()
            if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
                await handle_link_violation(update, context)
                return
            
            # Сохраняем текст
            if 'post_data' not in context.user_data:
                context.user_data['post_data'] = {}
            
            context.user_data['post_data']['text'] = text
            context.user_data['post_data']['media'] = []
            
            # Сохраняем медиа
            if update.message.photo:
                context.user_data['post_data']['media'].append({
                    'type': 'photo',
                    'file_id': update.message.photo[-1].file_id
                })
            elif update.message.video:
                context.user_data['post_data']['media'].append({
                    'type': 'video',
                    'file_id': update.message.video.file_id
                })
            elif update.message.document:
                context.user_data['post_data']['media'].append({
                    'type': 'document',
                    'file_id': update.message.document.file_id
                })
            
            keyboard = [
                [
                    InlineKeyboardButton("🖼️ Добавить еще медиа", callback_data="pub:add_media"),
                    InlineKeyboardButton("👀 Предпросмотр", callback_data="pub:preview")
                ],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu:back")]
            ]
            
            await update.message.reply_text(
                "🎯 Супер! Текст и медиа сохранены!\n\n"
                "🎨 Хотите добавить еще медиа или перейти к предпросмотру?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            context.user_data['waiting_for'] = None
            return
    
    # Если только текст без медиа
    if 'waiting_for' not in context.user_data:
        return
    
    waiting_for = context.user_data['waiting_for']
    text = update.message.text if update.message.text else update.message.caption
    
    if not text:
        return
    
    logger.info(f"Text input received. waiting_for: {waiting_for}")
    
    if waiting_for == 'post_text':
        # Check for links
        filter_service = FilterService()
        if filter_service.contains_banned_link(text) and not Config.is_moderator(update.effective_user.id):
            await handle_link_violation(update, context)
            return
        
        if 'post_data' not in context.user_data:
            await update.message.reply_text(
                "🤔 Упс! Данные поста потерялись.\n"
                "Давайте начнем заново с /start"
            )
            context.user_data.pop('waiting_for', None)
            return
        
        context.user_data['post_data']['text'] = text
        context.user_data['post_data']['media'] = []
        
        keyboard = [
            [
                InlineKeyboardButton("🎬 Добавить медиа", callback_data="pub:add_media"),
                InlineKeyboardButton("👀 Предпросмотр", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            "🎉 Отлично! Текст сохранен!\n\n"
            "🎭 Хотите добавить фото/видео или сразу перейти к предпросмотру?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data['waiting_for'] = None
        
    elif waiting_for == 'cancel_reason':
        context.user_data['cancel_reason'] = text
        await cancel_post(update, context)
        
    elif waiting_for.startswith('piar_'):
        from handlers.piar_handler import handle_piar_text
        field = waiting_for.replace('piar_', '')
        await handle_piar_text(update, context, field, text)

async def handle_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media input from user"""
    # Проверяем, что пользователь в процессе добавления медиа
    if 'post_data' not in context.user_data:
        return
    
    # Принимаем медиа даже если waiting_for не установлен
    if 'media' not in context.user_data['post_data']:
        context.user_data['post_data']['media'] = []
    
    media_added = False
    
    if update.message.photo:
        # Get highest quality photo
        context.user_data['post_data']['media'].append({
            'type': 'photo',
            'file_id': update.message.photo[-1].file_id
        })
        media_added = True
        logger.info(f"Added photo: {update.message.photo[-1].file_id}")
        
    elif update.message.video:
        context.user_data['post_data']['media'].append({
            'type': 'video',
            'file_id': update.message.video.file_id
        })
        media_added = True
        logger.info(f"Added video: {update.message.video.file_id}")
        
    elif update.message.document:
        context.user_data['post_data']['media'].append({
            'type': 'document',
            'file_id': update.message.document.file_id
        })
        media_added = True
        logger.info(f"Added document: {update.message.document.file_id}")
    
    if media_added:
        total_media = len(context.user_data['post_data']['media'])
        
        keyboard = [
            [
                InlineKeyboardButton(f"➕ Добавить еще", callback_data="pub:add_media"),
                InlineKeyboardButton("🔍 Предпросмотр", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            f"🔥 Медиа добавлено! (Всего: {total_media})\n\n"
            "🎪 Добавить еще или перейти к предпросмотру?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data['waiting_for'] = None

async def request_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request media from user"""
    context.user_data['waiting_for'] = 'post_media'
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "📸 Отправьте фото, видео или документ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show post preview with media first, then buttons"""
    if 'post_data' not in context.user_data:
        await update.callback_query.edit_message_text("😵 Ошибка: данные поста не найдены")
        return
    
    post_data = context.user_data['post_data']
    
    # Generate hashtags
    hashtag_service = HashtagService()
    
    # Специальные хештеги для Актуального
    if post_data.get('is_actual'):
        hashtags = ['#Актуальное⚡️', '@Trixlivebot']
    else:
        hashtags = hashtag_service.generate_hashtags(
            post_data.get('category'),
            post_data.get('subcategory')
        )
    
    # Build preview text
    preview_text = f"{post_data.get('text', '')}\n\n"
    preview_text += f"{' '.join(hashtags)}\n\n"
    preview_text += Config.DEFAULT_SIGNATURE
    
    keyboard = [
        [
            InlineKeyboardButton("🚀 Отправить на модерацию", callback_data="pub:send"),
            InlineKeyboardButton("✏️ Редактировать", callback_data="pub:edit")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="pub:cancel")]
    ]
    
    # ИСПРАВЛЕНО: Сначала удаляем старое сообщение с кнопками
    try:
        if update.callback_query:
            await update.callback_query.delete_message()
    except:
        pass
    
    # ИСПРАВЛЕНО: Сначала показываем медиа, если есть
    media = post_data.get('media', [])
    if media:
        try:
            for i, media_item in enumerate(media[:5]):  # Показываем до 5 медиа файлов
                caption = None
                if i == 0:  # Первое медиа с подписью
                    caption = f"📷 Медиа файлы ({len(media)} шт.)"
                
                if media_item.get('type') == 'photo':
                    await update.effective_message.reply_photo(
                        photo=media_item['file_id'],
                        caption=caption
                    )
                elif media_item.get('type') == 'video':
                    await update.effective_message.reply_video(
                        video=media_item['file_id'],
                        caption=caption
                    )
                elif media_item.get('type') == 'document':
                    await update.effective_message.reply_document(
                        document=media_item['file_id'],
                        caption=caption
                    )
        except Exception as e:
            logger.error(f"Error showing media preview: {e}")
    
    # ИСПРАВЛЕНО: Потом показываем текст с кнопками (последнее сообщение)
    try:
        await update.effective_message.reply_text(
            f"🎭 *Предпросмотр поста:*\n\n{preview_text}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending preview text: {e}")
        # Fallback без форматирования
        await update.effective_message.reply_text(
            f"Предпросмотр поста:\n\n{preview_text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def send_to_moderation_group(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   post: Post, user: User):
    """Send post to moderation group with safe markdown parsing"""
    bot = context.bot
    
    # Определяем куда отправлять пост
    is_actual = context.user_data.get('post_data', {}).get('is_actual', False)
    target_group = Config.MODERATION_GROUP_ID
    
    # Функция для экранирования markdown символов
    def escape_markdown(text):
        """Экранирует специальные символы markdown"""
        if not text:
            return text
        # Заменяем проблемные символы
        text = str(text)
        text = text.replace('*', '\\*')
        text = text.replace('_', '\\_')
        text = text.replace('[', '\\[')
        text = text.replace(']', '\\]')
        text = text.replace('`', '\\`')
        return text
    
    # =========================
    # Сообщение для модерации (БЕЗ MARKDOWN для безопасности)
    # =========================
    username = user.username or 'no_username'
    category = post.category or 'Unknown'
    
    if is_actual:
        mod_text = (
            f"⚡️ АКТУАЛЬНОЕ - Заявочка залетела\n\n"
            f"💌 от: @{username} (ID: {user.id})\n"
            f"💥 Примерно в: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📚 Раздел: {category}\n"
            f"🎯 Будет опубликовано в ЧАТе и ЗАКРЕПЛЕНО"
        )
    else:
        mod_text = (
            f"🚨 Заявочка залетела\n\n"
            f"💌 от: @{username} (ID: {user.id})\n"
            f"💥 Примерно в: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📚 Из раздела: {category}"
        )
    
    if post.subcategory:
        mod_text += f" → {post.subcategory}"
    
    if post.anonymous:
        mod_text += "\n🎭 Анонимно"
    
    # Добавляем информацию о медиа
    if post.media and len(post.media) > 0:
        mod_text += f"\n📎 Медиа: {len(post.media)} файл(ов)"
    
    # Безопасно добавляем текст поста (экранируем специальные символы)
    post_text = post.text[:500] + "..." if len(post.text) > 500 else post.text
    mod_text += f"\n\n📝 Текст:\n{escape_markdown(post_text)}"
    
    # Добавляем хештеги безопасно
    if post.hashtags:
        hashtags_text = " ".join(str(tag) for tag in post.hashtags)
        mod_text += f"\n\n🏷 Хештеги: {escape_markdown(hashtags_text)}"
    
    # Кнопки для актуального отличаются
    if is_actual:
        keyboard = [
            [
                InlineKeyboardButton("✅ В ЧАТ + ЗАКРЕПИТЬ", callback_data=f"mod:approve_chat:{post.id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"mod:edit:{post.id}")
            ],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=f"mod:approve:{post.id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"mod:edit:{post.id}")
            ],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")]
        ]
    
    try:
        # Сначала отправляем медиа, если есть
        media_messages = []
        if post.media and len(post.media) > 0:
            for i, media_item in enumerate(post.media):
                try:
                    caption = f"📷 Медиа {i+1}/{len(post.media)}"
                    if is_actual:
                        caption += " ⚡️"
                    
                    if media_item.get('type') == 'photo':
                        msg = await bot.send_photo(
                            chat_id=target_group,
                            photo=media_item['file_id'],
                            caption=caption
                        )
                        media_messages.append(msg.message_id)
                    elif media_item.get('type') == 'video':
                        msg = await bot.send_video(
                            chat_id=target_group,
                            video=media_item['file_id'],
                            caption=caption
                        )
                        media_messages.append(msg.message_id)
                    elif media_item.get('type') == 'document':
                        msg = await bot.send_document(
                            chat_id=target_group,
                            document=media_item['file_id'],
                            caption=caption
                        )
                        media_messages.append(msg.message_id)
                except Exception as e:
                    logger.error(f"Error sending media {i+1}: {e}")
        
        # Затем отправляем текст с кнопками - БЕЗ parse_mode чтобы избежать ошибок
        try:
            message = await bot.send_message(
                chat_id=target_group,
                text=mod_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
                # УБРАН parse_mode='Markdown' - это причина ошибки
            )
        except Exception as text_error:
            logger.error(f"Error sending moderation text: {text_error}")
            # Fallback - отправляем упрощенное сообщение
            simple_text = (
                f"Новая заявка от @{username} (ID: {user.id})\n"
                f"Категория: {category}\n"
                f"Текст: {post_text[:200]}..."
            )
            message = await bot.send_message(
                chat_id=target_group,
                text=simple_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        # Сохраняем ID сообщения безопасно
        try:
            from sqlalchemy import text
            async with db.get_session() as session:
                await session.execute(
                    text("UPDATE posts SET moderation_message_id = :msg_id WHERE id = :post_id"),
                    {"msg_id": message.message_id, "post_id": str(post.id)}
                )
                await session.commit()
        except Exception as save_error:
            logger.error(f"Error saving moderation_message_id: {save_error}")
        
        logger.info(f"Post {post.id} sent to moderation with {len(media_messages)} media files")
            
    except Exception as e:
        logger.error(f"Error sending to moderation group: {e}")
        # Отправляем подробное сообщение об ошибке
        error_details = str(e)[:200] + "..." if len(str(e)) > 200 else str(e)
        
        try:
            await bot.send_message(
                chat_id=user.id,
                text=(
                    f"⚠️ Ошибка отправки в группу модерации\n\n"
                    f"Детали ошибки: {error_details}\n\n"
                    f"ID группы: {target_group}\n\n"
                    f"Обратитесь к администратору."
                )
            )
        except Exception as notify_error:
            logger.error(f"Could not notify user about moderation error: {notify_error}")

# ДОПОЛНИТЕЛЬНО: Исправленная функция для piar_handler.py
async def send_to_moderation_group(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   post: Post, user: User):
    """Send post to moderation group with safe markdown parsing"""
    bot = context.bot
    
    # Определяем куда отправлять пост
    is_actual = context.user_data.get('post_data', {}).get('is_actual', False)
    target_group = Config.MODERATION_GROUP_ID
    
    # Функция для экранирования markdown символов
    def escape_markdown(text):
        """Экранирует специальные символы markdown"""
        if not text:
            return text
        # Заменяем проблемные символы
        text = str(text)
        text = text.replace('*', '\\*')
        text = text.replace('_', '\\_')
        text = text.replace('[', '\\[')
        text = text.replace(']', '\\]')
        text = text.replace('`', '\\`')
        return text
    
    # =========================
    # Сообщение для модерации (БЕЗ MARKDOWN для безопасности)
    # =========================
    username = user.username or 'no_username'
    category = post.category or 'Unknown'
    
    if is_actual:
        mod_text = (
            f"⚡️ АКТУАЛЬНОЕ - Заявочка залетела\n\n"
            f"💌 от: @{username} (ID: {user.id})\n"
            f"💥 Примерно в: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📚 Раздел: {category}\n"
            f"🎯 Будет опубликовано в ЧАТе и ЗАКРЕПЛЕНО"
        )
    else:
        mod_text = (
            f"🚨 Заявочка залетела\n\n"
            f"💌 от: @{username} (ID: {user.id})\n"
            f"💥 Примерно в: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📚 Из раздела: {category}"
        )
    
    if post.subcategory:
        mod_text += f" → {post.subcategory}"
    
    if post.anonymous:
        mod_text += "\n🎭 Анонимно"
    
    # Добавляем информацию о медиа
    if post.media and len(post.media) > 0:
        mod_text += f"\n📎 Медиа: {len(post.media)} файл(ов)"
    
    # Безопасно добавляем текст поста (экранируем специальные символы)
    post_text = post.text[:500] + "..." if len(post.text) > 500 else post.text
    mod_text += f"\n\n📝 Текст:\n{escape_markdown(post_text)}"
    
    # Добавляем хештеги безопасно
    if post.hashtags:
        hashtags_text = " ".join(str(tag) for tag in post.hashtags)
        mod_text += f"\n\n🏷 Хештеги: {escape_markdown(hashtags_text)}"
    
    # Кнопки для актуального отличаются
    if is_actual:
        keyboard = [
            [
                InlineKeyboardButton("✅ В ЧАТ + ЗАКРЕПИТЬ", callback_data=f"mod:approve_chat:{post.id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"mod:edit:{post.id}")
            ],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=f"mod:approve:{post.id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"mod:edit:{post.id}")
            ],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")]
        ]
    
    try:
        # Сначала отправляем медиа, если есть
        media_messages = []
        if post.media and len(post.media) > 0:
            for i, media_item in enumerate(post.media):
                try:
                    caption = f"📷 Медиа {i+1}/{len(post.media)}"
                    if is_actual:
                        caption += " ⚡️"
                    
                    if media_item.get('type') == 'photo':
                        msg = await bot.send_photo(
                            chat_id=target_group,
                            photo=media_item['file_id'],
                            caption=caption
                        )
                        media_messages.append(msg.message_id)
                    elif media_item.get('type') == 'video':
                        msg = await bot.send_video(
                            chat_id=target_group,
                            video=media_item['file_id'],
                            caption=caption
                        )
                        media_messages.append(msg.message_id)
                    elif media_item.get('type') == 'document':
                        msg = await bot.send_document(
                            chat_id=target_group,
                            document=media_item['file_id'],
                            caption=caption
                        )
                        media_messages.append(msg.message_id)
                except Exception as e:
                    logger.error(f"Error sending media {i+1}: {e}")
        
        # Затем отправляем текст с кнопками - БЕЗ parse_mode чтобы избежать ошибок
        try:
            message = await bot.send_message(
                chat_id=target_group,
                text=mod_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
                # УБРАН parse_mode='Markdown' - это причина ошибки
            )
        except Exception as text_error:
            logger.error(f"Error sending moderation text: {text_error}")
            # Fallback - отправляем упрощенное сообщение
            simple_text = (
                f"Новая заявка от @{username} (ID: {user.id})\n"
                f"Категория: {category}\n"
                f"Текст: {post_text[:200]}..."
            )
            message = await bot.send_message(
                chat_id=target_group,
                text=simple_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        # Сохраняем ID сообщения безопасно
        try:
            from sqlalchemy import text
            async with db.get_session() as session:
                await session.execute(
                    text("UPDATE posts SET moderation_message_id = :msg_id WHERE id = :post_id"),
                    {"msg_id": message.message_id, "post_id": str(post.id)}
                )
                await session.commit()
        except Exception as save_error:
            logger.error(f"Error saving moderation_message_id: {save_error}")
        
        logger.info(f"Post {post.id} sent to moderation with {len(media_messages)} media files")
            
    except Exception as e:
        logger.error(f"Error sending to moderation group: {e}")
        # Отправляем подробное сообщение об ошибке
        error_details = str(e)[:200] + "..." if len(str(e)) > 200 else str(e)
        
        try:
            await bot.send_message(
                chat_id=user.id,
                text=(
                    f"⚠️ Ошибка отправки в группу модерации\n\n"
                    f"Детали ошибки: {error_details}\n\n"
                    f"ID группы: {target_group}\n\n"
                    f"Обратитесь к администратору."
                )
            )
        except Exception as notify_error:
            logger.error(f"Could not notify user about moderation error: {notify_error}")

# ДОПОЛНИТЕЛЬНО: Исправленная функция для piar_handler.py
async def send_piar_to_mod_group_safe(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                     post: Post, user: User, data: dict):
    """Send piar to moderation group with safe text handling"""
    bot = context.bot
    
    def escape_markdown(text):
        """Экранирует специальные символы"""
        if not text:
            return text
        text = str(text)
        text = text.replace('*', '\\*')
        text = text.replace('_', '\\_')
        text = text.replace('[', '\\[')
        text = text.replace(']', '\\]')
        text = text.replace('`', '\\`')
        return text
    
    # Безопасное сообщение без markdown
    username = user.username or 'no_username'
    
    text = (
        f"💼 Новая заявка - Услуга\n\n"
        f"👤 Автор: @{username} (ID: {user.id})\n"
        f"📅 Дата: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"Данные:\n"
        f"👤 Имя: {escape_markdown(data.get('name', ''))}\n"
        f"💼 Профессия: {escape_markdown(data.get('profession', ''))}\n"
        f"📍 Районы: {escape_markdown(', '.join(data.get('districts', [])))}\n"
    )
    
    if data.get('phone'):
        text += f"📞 Телефон: {escape_markdown(data.get('phone'))}\n"
    
    # Новая обработка контактов для модерации
    contacts = []
    if data.get('instagram'):
        contacts.append(f"📷 Instagram: @{escape_markdown(data.get('instagram'))}")
    if data.get('telegram'):
        contacts.append(f"📱 Telegram: {escape_markdown(data.get('telegram'))}")
    
    if contacts:
        text += f"📞 Контакты:\n{chr(10).join(contacts)}\n"
    
    text += f"💰 Цена: {escape_markdown(data.get('price', ''))}\n"
    
    # Добавляем информацию о медиа
    if data.get('media') and len(data['media']) > 0:
        text += f"📎 Медиа: {len(data['media'])} файл(ов)\n"
    
    # Безопасно добавляем описание
    description = data.get('description', '')[:300]
    if len(data.get('description', '')) > 300:
        description += "..."
    text += f"\n📝 Описание:\n{escape_markdown(description)}"
    
    keyboard = [
        [InlineKeyboardButton("💬 Написать автору", url=f"tg://user?id={user.id}")],
        [
            InlineKeyboardButton("✅ Опубликовать", callback_data=f"mod:approve:{post.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")
        ]
    ]
    
    try:
        # Проверяем доступность группы модерации
        try:
            await bot.get_chat(Config.MODERATION_GROUP_ID)
        except Exception as e:
            logger.error(f"Cannot access moderation group {Config.MODERATION_GROUP_ID}: {e}")
            await bot.send_message(
                chat_id=user.id,
                text="⚠️ Группа модерации недоступна. Обратитесь к администратору."
            )
            return

        # Отправляем медиа с улучшенной обработкой ошибок
        media_sent = []
        if data.get('media') and len(data['media']) > 0:
            for i, media_item in enumerate(data['media']):
                try:
                    if media_item.get('type') == 'photo':
                        msg = await bot.send_photo(
                            chat_id=Config.MODERATION_GROUP_ID,
                            photo=media_item['file_id'],
                            caption=f"📷 Медиа {i+1}/{len(data['media'])}"
                        )
                        media_sent.append(msg.message_id)
                    elif media_item.get('type') == 'video':
                        msg = await bot.send_video(
                            chat_id=Config.MODERATION_GROUP_ID,
                            video=media_item['file_id'],
                            caption=f"🎥 Медиа {i+1}/{len(data['media'])}"
                        )
                        media_sent.append(msg.message_id)
                except Exception as media_error:
                    logger.error(f"Error sending piar media {i+1}: {media_error}")
                    continue
        
        # Отправляем основное сообщение с кнопками БЕЗ parse_mode
        try:
            message = await bot.send_message(
                chat_id=Config.MODERATION_GROUP_ID,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard)
                # УБРАН parse_mode='Markdown'
            )
            
            logger.info(f"Piar sent to moderation successfully. Post ID: {post.id}")
            
        except Exception as text_error:
            logger.error(f"Error sending piar text message: {text_error}")
            raise text_error
            
    except Exception as e:
        logger.error(f"Error sending piar to moderation: {e}")
        await bot.send_message(
            chat_id=user.id,
            text="⚠️ Ошибка отправки в группу модерации. Обратитесь к администратору."
        )

async def cancel_post_with_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for cancellation reason"""
    keyboard = [
        [InlineKeyboardButton("🤷 Передумал", callback_data="pub:cancel_confirm")],
        [InlineKeyboardButton("✏️ Ошибка в тексте", callback_data="pub:cancel_confirm")],
        [InlineKeyboardButton("🔙 Назад", callback_data="pub:preview")]
    ]
    
    await update.callback_query.edit_message_text(
        "🤔 Укажите причину отмены:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_link_violation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle link violation"""
    await update.message.reply_text(
        "🚫 Обнаружена запрещенная ссылка!\n"
        "Ссылки запрещены в публикациях."
    )
    context.user_data.pop('waiting_for', None)

async def edit_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit post before sending"""
    context.user_data['waiting_for'] = 'post_text'
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "✏️ Отправьте новый текст для поста:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel post creation"""
    context.user_data.pop('post_data', None)
    context.user_data.pop('waiting_for', None)
    context.user_data.pop('cancel_reason', None)
    
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)
