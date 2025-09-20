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
        'work': '👷 Работа',
        'rent': '🏚️ Аренда',
        'buy': '🕵🏻‍♀️ Куплю',
        'sell': '🕵🏽 Продам',
        'events': '🎉 События',
        'free': '🕵🏼 Отдам даром',
        'important': '‼️ Важно',
        'other': '❔ Другое'
    }
    
    # Сохраняем данные поста
    context.user_data['post_data'] = {
        'category': '🗯️ Будапешт',
        'subcategory': subcategory_names.get(subcategory, '❔ Другое'),
        'anonymous': False
    }

    keyboard = [[InlineKeyboardButton("⏮️ Вернуться", callback_data="menu:announcements")]]
    
    await update.callback_query.edit_message_text(
        f"🗯️ Будапешт → ‼️ Объявления → {subcategory_names.get(subcategory)}\n\n"
        "💥 Напишите текст, добавьте фото, видео контент:",
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
                    InlineKeyboardButton("📸 Еще медиа?", callback_data="pub:add_media"),
                    InlineKeyboardButton("💻 Предпросмотр", callback_data="pub:preview")
                ],
                [InlineKeyboardButton("🔙 Вернуться", callback_data="menu:back")]
            ]
            
            await update.message.reply_text(
                "✅ Отлично, текст и медиа сохранены!\n\n"
                "💚 Вы можете добавить еще медиа или перейти к предпросмотру?",
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
                InlineKeyboardButton("📹 Прикрепить медиа контент", callback_data="pub:add_media"),
                InlineKeyboardButton("💁 Предпросмотр", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("🚶‍♀️ Назад", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            "🎉 Отличный текст, сохраняю!\n\n"
            "💚 Добавить ещё фото, видео или смотрим что получилось?",
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
                InlineKeyboardButton(f"💚 Добавить еще", callback_data="pub:add_media"),
                InlineKeyboardButton("🤩 Предпросмотр", callback_data="pub:preview")
            ],
            [InlineKeyboardButton("🚶 Назад", callback_data="menu:back")]
        ]
        
        await update.message.reply_text(
            f"✅ Медиа получено! (Всего: {total_media})\n\n"
            "💚 Добавить еще или смотреть результат?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data['waiting_for'] = None

async def request_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request media from user"""
    context.user_data['waiting_for'] = 'post_media'
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="pub:preview")]]
    
    await update.callback_query.edit_message_text(
        "📹 Поделитесь фото, видео или документом:",
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
            InlineKeyboardButton("📨 Отправить на модерацию", callback_data="pub:send"),
            InlineKeyboardButton("📝 Изменить", callback_data="pub:edit")
        ],
        [InlineKeyboardButton("🚗 Отмена", callback_data="pub:cancel")]
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
                    caption = f"💿 Медиа файлы ({len(media)} шт.)"
                
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
            f"🫣 *Предпросмотр поста:*\n\n{preview_text}",
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

async def send_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send post to moderation with fixed cooldown check"""
    user_id = update.effective_user.id
    post_data = context.user_data.get('post_data')
    
    if not post_data:
        await update.callback_query.edit_message_text("💥 Данные поста не найдены")
        return
    
    try:
        async with db.get_session() as session:
            # Get user
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await update.callback_query.edit_message_text(
                    "😩 Пользователь не найден"
                )
                return
            
            # ИСПРАВЛЕНИЕ: проверяем кулдаун правильно - с await
            from services.cooldown import CooldownService
            cooldown_service = CooldownService()
            
            try:
                can_post, remaining_seconds = await cooldown_service.can_post(user_id)
            except Exception as cooldown_error:
                logger.warning(f"Cooldown check failed: {cooldown_error}, using fallback")
                # Fallback to simple check
                can_post = cooldown_service.simple_can_post(user_id)
                remaining_seconds = cooldown_service.get_remaining_time(user_id)
            
            if not can_post and not Config.is_moderator(user_id):
                remaining_minutes = remaining_seconds // 60
                await update.callback_query.edit_message_text(
                    f"💤 Нужно подождать еще {remaining_minutes} минут до следующего поста"
                )
                return
            
            # Create post
            post = Post(
                user_id=user_id,
                category=post_data.get('category'),
                subcategory=post_data.get('subcategory'),
                text=post_data.get('text'),
                hashtags=post_data.get('hashtags', []),
                anonymous=post_data.get('anonymous', False),
                media=post_data.get('media', [])
            )
            
            session.add(post)
            await session.commit()
            
            # Send to moderation
            await send_to_moderation_group(update, context, post, user)
            
            # Update cooldown
            try:
                await cooldown_service.update_cooldown(user_id)
            except Exception:
                cooldown_service.set_last_post_time(user_id)  # Fallback
            
            # Clear user data
            context.user_data.pop('post_data', None)
            context.user_data.pop('waiting_for', None)
            
            await update.callback_query.edit_message_text(
                "✅ Пост отправлен на модерацию!\n"
                "⏹️ Ожидайте ссылку на свою публикацию в ЛС"
            )
            
    except Exception as e:
        logger.error(f"Error sending to moderation: {e}")
        await update.callback_query.edit_message_text(
            "😖 Ошибка при отправке на модерацию"
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
        mod_text += "\n🫆Анонимно"
    
    # ИСПРАВЛЕНИЕ: добавляем проверку на None для медиа
    media_count = 0
    if post.media:
        try:
            media_count = len(post.media)
            if media_count > 0:
                mod_text += f"\n📀Медиа: {media_count} файл(ов)"
        except (TypeError, AttributeError):
            logger.warning(f"Invalid media data for post {post.id}: {post.media}")
    
    # Безопасно добавляем текст поста (экранируем специальные символы)
    if post.text:
        post_text = post.text[:500] + "..." if len(post.text) > 500 else post.text
        mod_text += f"\n\n📝 Текст:\n{escape_markdown(post_text)}"
    else:
        mod_text += f"\n\n📝 Текст: (без текста)"
    
    # Добавляем хештеги безопасно
    if post.hashtags:
        try:
            hashtags_text = " ".join(str(tag) for tag in post.hashtags)
            mod_text += f"\n\n#️⃣ Хештеги: {escape_markdown(hashtags_text)}"
        except (TypeError, AttributeError):
            logger.warning(f"Invalid hashtags data for post {post.id}: {post.hashtags}")
    
    # ИСПРАВЛЕНИЕ: убираем кнопку "Редактировать" которая не реализована
    if is_actual:
        keyboard = [
            [
                InlineKeyboardButton("✅ В ЧАТ + ЗАКРЕПИТЬ", callback_data=f"mod:approve_chat:{post.id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=f"mod:approve:{post.id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"mod:reject:{post.id}")
            ]
        ]
    
    try:
        # Проверяем доступность группы модерации
        try:
            await bot.get_chat(target_group)
        except Exception as chat_error:
            logger.error(f"Cannot access moderation group {target_group}: {chat_error}")
            await bot.send_message(
                chat_id=user.id,
                text="⚠️ Группа модерации недоступна. Обратитесь к администратору."
            )
            return

        # Сначала отправляем медиа, если есть
        media_messages = []
        if post.media and media_count > 0:
            for i, media_item in enumerate(post.media):
                try:
                    # ИСПРАВЛЕНИЕ: добавляем проверки на валидность медиа
                    if not media_item or not isinstance(media_item, dict):
                        logger.warning(f"Invalid media item {i}: {media_item}")
                        continue
                        
                    file_id = media_item.get('file_id')
                    media_type = media_item.get('type')
                    
                    if not file_id or not media_type:
                        logger.warning(f"Missing file_id or type in media item {i}: {media_item}")
                        continue
                    
                    caption = f"📷 Медиа {i+1}/{media_count}"
                    if is_actual:
                        caption += " ⚡️"
                    
                    if media_type == 'photo':
                        msg = await bot.send_photo(
                            chat_id=target_group,
                            photo=file_id,
                            caption=caption
                        )
                        media_messages.append(msg.message_id)
                    elif media_type == 'video':
                        msg = await bot.send_video(
                            chat_id=target_group,
                            video=file_id,
                            caption=caption
                        )
                        media_messages.append(msg.message_id)
                    elif media_type == 'document':
                        msg = await bot.send_document(
                            chat_id=target_group,
                            document=file_id,
                            caption=caption
                        )
                        media_messages.append(msg.message_id)
                        
                except Exception as e:
                    logger.error(f"Error sending media {i+1} for post {post.id}: {e}")
                    continue
        
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
                f"Текст: {(post.text or '')[:200]}..."
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
                    {"msg_id": message.message_id, "post_id": int(post.id)}  # ИСПРАВЛЕНИЕ: используем int
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

async def cancel_post_with_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for cancellation reason"""
    keyboard = [
        [InlineKeyboardButton("🤔 Передумал", callback_data="pub:cancel_confirm")],
        [InlineKeyboardButton("👎 Ошибка в тексте", callback_data="pub:cancel_confirm")],
        [InlineKeyboardButton("👈Назад", callback_data="pub:preview")]
    ]
    
    await update.callback_query.edit_message_text(
        "💭 Укажите причину отмены:",
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
        "✏️ Отправьте новый текст публикации:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel post creation"""
    context.user_data.pop('post_data', None)
    context.user_data.pop('waiting_for', None)
    context.user_data.pop('cancel_reason', None)
    
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)
