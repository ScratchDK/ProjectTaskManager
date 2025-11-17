from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from .models import Task


async def send_telegram_notification(task_uuid, owner_id, assignee_id, message_lines_owner, message_lines_assignee):
    try:
        # Импортируем бота только когда нужно
        from .telegram_bot import bot

        # Создаем клавиатуру с кнопками
        keyboard = [
            [InlineKeyboardButton("✅ Принять", callback_data=f"accept_{task_uuid}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{task_uuid}")],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        message_owner= "\n".join(message_lines_owner)

        if assignee_id:
            message_assignee = "\n".join(message_lines_assignee)
            await bot.send_message(
                chat_id=assignee_id,
                text=message_assignee,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )

            await bot.send_message(
                chat_id=owner_id,
                text=message_owner,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await bot.send_message(
                chat_id=owner_id,
                text=message_owner,
                parse_mode=ParseMode.MARKDOWN
            )

    except Exception as e:
        print(f"[Telegram] ОШИБКА: {str(e)}")