from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from django.conf import settings
from django.utils import timezone
import asyncio
from telegram.constants import ParseMode
from telegram.ext import MessageHandler, filters
from .models import Task
from asgiref.sync import sync_to_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Инициализация бота
application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
# Получение доступа для прямых вызовов API Telegram.
bot = application.bot

# update.message               # Обычное текстовое сообщение
# update.callback_query        # Нажатие inline-кнопки
# update.inline_query          # Запрос в inline-режиме
# update.chosen_inline_result  # Выбор inline-результата
# update.edited_message        # Редактирование сообщения
# update.channel_post          # Сообщение в канале

#_______________________________________________________________________________________________________________________
async def handle_completion_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстового доказательства"""
    user_id = update.message.from_user.id
    text = update.message.text

    task_uuid = context.user_data.get('completing_task')
    if not task_uuid:
        await update.message.reply_text("❌ Сначала нажмите 'Завершить задачу'")
        return

    await process_completion_proof(update, context, user_id, task_uuid, text=text)


async def handle_completion_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото"""
    user_id = update.message.from_user.id
    photo = update.message.photo[-1]  # Берем самое качественное фото
    task_uuid = context.user_data.get('completing_task')

    if task_uuid:
        # Скачиваем фото
        photo_file = await photo.get_file()
        await process_completion_proof(update, context, user_id, task_uuid,
                                       media_type='photo', file_id=photo.file_id)


async def handle_completion_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка видео"""
    user_id = update.message.from_user.id
    video = update.message.video
    task_uuid = context.user_data.get('completing_task')

    if task_uuid:
        await process_completion_proof(update, context, user_id, task_uuid,
                                       media_type='video', file_id=video.file_id)


async def handle_completion_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка документов"""
    user_id = update.message.from_user.id
    document = update.message.document
    task_uuid = context.user_data.get('completing_task')

    if task_uuid:
        await process_completion_proof(update, context, user_id, task_uuid,
                                       media_type='document', file_id=document.file_id,
                                       file_name=document.file_name)


application.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_completion_message
))

application.add_handler(MessageHandler(
    filters.PHOTO,
    handle_completion_photo
))

application.add_handler(MessageHandler(
    filters.VIDEO,
    handle_completion_video
))

application.add_handler(MessageHandler(
    filters.Document.ALL,
    handle_completion_document
))
#_______________________________________________________________________________________________________________________


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем объект callback query из update
    query = update.callback_query
    # Отправляем подтверждение Telegram, что callback получен, иначе у пользователя будет висеть ожидание на нажатой
    # кнопке или telegram отправить повторно callback
    await query.answer()

    # Извлекаем данные которые мы положили в кнопку
    callback_data = query.data
    user_id = query.from_user.id # Получаем chat id

    # Кнопка - [Принять]
    if callback_data.startswith('accept_'):
        task_uuid = callback_data.replace('accept_', '')
        try:
            # Получаем задачу асинхронно
            task = await sync_to_async(Task.objects.get)(uuid=task_uuid)

            # Асинхронно получаем данные владельца и исполнителя
            owner_id = await sync_to_async(_get_owner_chat_id)(task)
            assignee_id = await sync_to_async(_get_assignee_chat_id)(task)

            # Проверяем права: тот ли пользователь нажал кнопку?
            if str(user_id) == str(assignee_id):
                await handle_task_accepted(user_id, owner_id, task_uuid, query)
            else:
                await query.edit_message_text("❌ У вас нет прав для этого действия")

        except Task.DoesNotExist:
            await query.edit_message_text("❌ Задача не найдена")

    # Кнопка - [Отклонить]
    elif callback_data.startswith('reject_'):
        task_uuid = callback_data.replace('reject_', '')
        await handle_task_rejection(user_id, task_uuid, query)

    # Кнопка - [Завершить задачу]
    elif callback_data.startswith('complete_'):
        task_uuid = callback_data.replace('complete_', '')
        await handle_task_completion_request(user_id, task_uuid, query, context)

    # Кнопка - [Одобрить]
    elif callback_data.startswith('approve_'):
        task_uuid = callback_data.replace('approve_', '')
        await handle_task_approve_request(user_id, task_uuid, query)

    # Кнопка - [Отклонить]
    # elif callback_data.startswith('reject_completion_'):
    #     task_uuid = callback_data.replace('reject_completion_', '')
    #     await handle_task_reject_completion_request(user_id, task_uuid, query)


async def handle_task_accepted(user_id, owner_id, task_uuid, query):
    try:
        # Получаем задачу и данные
        task = await sync_to_async(Task.objects.get)(uuid=task_uuid)
        assignee_name = query.from_user.first_name  # Имя исполнителя
        assignee_last_name = query.from_user.last_name  # Фамилия исполнителя

        # Меняем статус задачи
        success = await sync_to_async(_sync_handle_task_accepted)(user_id, task_uuid)

        completion_keyboard = [
            [InlineKeyboardButton("✅ Завершить задачу", callback_data=f"complete_{task.uuid}")]
        ]
        completion_markup = InlineKeyboardMarkup(completion_keyboard)

        if success:
            assignee_message = "\n".join([
                f"✅ Вы приняли задачу \"{task.name}\"",
                "",
                f"📝 *Описание:*",
                f"{task.description}",
                "",
                f"⏰ *Срок выполнения:*",
                f"до {task.end_date.strftime('%d.%m.%Y в %H:%M')}",
                "",
                "После выполнения нажмите кнопку ниже 👇"
            ])


            # 1. Обновляем сообщение исполнителю
            await query.edit_message_text(
                text=assignee_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=completion_markup
            )

            # 2. Отправляем уведомление владельцу
            owner_message = (
                f"🎉 *Исполнитель принял задачу!*\n\n"
                f""
                f"📋 *Задача:* {task.name}\n"
                f""
                f"🆔 *ID:* `{task_uuid}`\n"
                f""
                f"👤 *Исполнитель:* {assignee_last_name} {assignee_name}\n"
                f""
                f"⏰ *Срок:* до {task.end_date.strftime('%d.%m.%Y в %H:%M')}"
            )

            await bot.send_message(
                chat_id=owner_id,
                text=owner_message,
                parse_mode=ParseMode.MARKDOWN
            )

        else:
            await query.edit_message_text(
                text="❌ Задача не найдена или у вас нет прав",
                reply_markup=completion_markup
            )

    except Task.DoesNotExist:
        await query.edit_message_text("❌ Задача не найдена")
    except Exception as e:
        await query.edit_message_text(
            text=f"❌ Ошибка: {str(e)}",
            reply_markup=None
        )


async def handle_task_rejection(user_id, task_uuid, query):
    try:
        success = await sync_to_async(_sync_handle_task_rejection)(user_id, task_uuid)

        if success:
            await query.edit_message_text(
                text=f"❌ Задача {task_uuid} отклонена",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=None
            )
        else:
            await query.edit_message_text(
                text="❌ Задача не найдена или у вас нет прав для её отклонения",
                reply_markup=None
            )

    except Exception as e:
        await query.edit_message_text(
            text=f"❌ Произошла ошибка при обработке запроса: {str(e)}",
            reply_markup=None
        )


async def handle_task_completion_request(user_id, task_uuid, query, context):
    """Обработка запроса на выполнение задачи"""
    try:
        # Проверяем что задача существует и пользователь с верным id
        success = await sync_to_async(_sync_handle_task_review)(user_id, task_uuid)
        if success:
            # Сохраняем task_uuid в context для последующей обработки
            context.user_data['completing_task'] = task_uuid

            await query.edit_message_text(
                text="📨 *Отправьте доказательство выполнения*\n\n"
                     "Пришлите текст, фото, видео или документ в этот чат.\n"
                     "Это будет переслано владельцу задачи.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(
                text="❌ Данная задача больше не существует!",
                reply_markup=None
            )

    except Exception as e:
        await query.edit_message_text(
            text=f"❌ Произошла ошибка при обработке запроса: {str(e)}",
            reply_markup=None
        )


async def handle_task_approve_request(user_id, task_uuid, query):
    """Обработка запроса на утверждение задачи"""
    try:
        # Проверяем что задача существует и пользователь с верным id
        task = await sync_to_async(_sync_handle_task_done)(user_id, task_uuid)

        if task:
            await query.edit_message_text(
                text="✅ Задача утверждена и завершена!",
                parse_mode=ParseMode.MARKDOWN
            )

            # Уведомляем исполнителя
            await bot.send_message(
                chat_id=task.assignee.telegram_chat_id,
                text=f"🎉 Ваша задача \"{task.name}\" утверждена владельцем!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(
                text="❌ Данная задача больше не существует!",
                reply_markup=None
            )

    except Exception as e:
        await query.edit_message_text(
            text=f"❌ Произошла ошибка при обработке запроса: {str(e)}",
            reply_markup=None
        )


async def process_completion_proof(update, context, user_id, task_uuid, **kwargs):
    """Общая функция обработки доказательств выполнения"""
    try:
        task = await sync_to_async(Task.objects.select_related('owner', 'assignee').get)(
            uuid=task_uuid,
            assignee__telegram_chat_id=str(user_id),
            status='REVIEW'
        )

        # Сохраняем доказательство в базу
        if kwargs.get('text'):
            task.completion_proof = kwargs['text']
        elif kwargs.get('file_id'):
            task.completion_file_id = kwargs['file_id']
            task.completion_media_type = kwargs['media_type']

        task.completed_at = timezone.now()
        task.status = 'REVIEW'  # Статус "На проверке"
        await sync_to_async(task.save)()

        # Очищаем контекст
        context.user_data.pop('completing_task', None)

        # Уведомляем исполнителя
        await update.message.reply_text(
            "✅ Доказательство отправлено на проверку!\n"
            "Ожидайте ответа от владельца задачи."
        )

        # Уведомляем владельца
        await notify_owner_about_completion(task, **kwargs)

    except Task.DoesNotExist:
        await update.message.reply_text("❌ Задача не найдена")
        context.user_data.pop('completing_task', None)


async def notify_owner_about_completion(task, **kwargs):
    """Уведомление владельца (менеджера) о выполнении задачи"""
    owner_message = [
        f"🎉 *Задача выполнена!*\n\n",
        f"📋 *Задача:* {task.name}",
        f"🆔 *ID:* `{task.uuid}`",
        f"👤 *Исполнитель:* {task.assignee.email}",
        f"⏰ *Срок:* до {task.end_date.strftime('%d.%m.%Y в %H:%M')}",
        f"",
        f"📨 *Доказательство выполнения:*"
    ]

    if kwargs.get('text'):
        owner_message.append(f"\n{kwargs['text']}")

    # Отправляем основное сообщение
    await bot.send_message(
        chat_id=task.owner.telegram_chat_id,
        text="\n".join(owner_message),
        parse_mode=ParseMode.MARKDOWN
    )

    # Отправляем медиафайл если есть
    if kwargs.get('file_id'):
        media_type = kwargs['media_type']
        file_id = kwargs['file_id']

        if media_type == 'photo':
            await bot.send_photo(
                chat_id=task.owner.telegram_chat_id,
                photo=file_id,
                caption="📷 Фото доказательство"
            )
        elif media_type == 'video':
            await bot.send_video(
                chat_id=task.owner.telegram_chat_id,
                video=file_id,
                caption="🎥 Видео доказательство"
            )
        elif media_type == 'document':
            await bot.send_document(
                chat_id=task.owner.telegram_chat_id,
                document=file_id,
                caption=f"📄 Документ: {kwargs.get('file_name', '')}"
            )

    # Добавляем кнопки для владельца
    review_keyboard = [
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{task.uuid}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_completion_{task.uuid}")]
    ]
    review_markup = InlineKeyboardMarkup(review_keyboard)

    await bot.send_message(
        chat_id=task.owner.telegram_chat_id,
        text="Проверьте доказательство и выберите действие:",
        reply_markup=review_markup,
        parse_mode=ParseMode.MARKDOWN
    )


# Синхронные функции для работы с ORM
#_______________________________________________________________________________________________________________________
def _sync_handle_task_accepted(user_id, task_uuid):
    """Синхронная обработка принятия задачи"""
    try:
        task = Task.objects.get(uuid=task_uuid, assignee__telegram_chat_id=user_id)
        task.status = 'WORK'  # Меняем статус на "В работе"
        task.save()
        return True
    except Task.DoesNotExist:
        return False


def _sync_handle_task_rejection(user_id, task_uuid):
    """Синхронная обработка отклонения задачи"""
    try:
        task = Task.objects.get(uuid=task_uuid, owner__telegram_chat_id=user_id)
        task.status = 'REJECTED'
        task.save()
        return True
    except Task.DoesNotExist:
        return False


def _sync_handle_task_review(user_id, task_uuid):
    """Синхронная обработка задачи на проверке"""
    try:
        task = Task.objects.get(uuid=task_uuid, assignee__telegram_chat_id=user_id, status='WORK')
        task.status = 'REVIEW'  # Меняем статус на "На проверке"
        task.save()
        return True
    except Task.DoesNotExist:
        return False


def _sync_handle_task_done(user_id, task_uuid):
    """Синхронная обработка утверждения задачи"""
    try:
        # Используем select_related, чтобы избежать дополнительных запросов
        task = Task.objects.select_related('assignee').get(
            uuid=task_uuid,
            owner__telegram_chat_id=user_id,
            status='REVIEW'
        )
        task.status = 'DONE'  # Меняем статус на "Выполнена"
        task.save()
        return task
    except Task.DoesNotExist:
        return False


# Вспомогательные синхронные функции для получения telegram_chat_id
def _get_owner_chat_id(task):
    """Синхронная функция для получения chat_id владельца"""
    return task.owner.telegram_chat_id if task.owner else None


def _get_assignee_chat_id(task):
    """Синхронная функция для получения chat_id исполнителя"""
    return task.assignee.telegram_chat_id if task.assignee else None
#_______________________________________________________________________________________________________________________


# Добавляем обработчик
application.add_handler(CallbackQueryHandler(handle_callback_query))


# Функция для запуска бота
async def start_bot():
    await application.initialize()
    await application.start()
    await application.updater.start_polling()


# Функция для остановки бота
async def stop_bot():
    await application.updater.stop()
    await application.stop()
    await application.shutdown()