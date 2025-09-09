from datetime import datetime

from rest_framework import viewsets
import asyncio
import threading

from .models import Task
from .paginators import MyPagination
from .permissions import IsOwner
from .serializers import TaskSerializer
from .tasks import send_telegram_notification


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    pagination_class = MyPagination
    serializer_class = TaskSerializer
    permission_classes = [
        IsOwner,
    ]

    def get_queryset(self):
        """Возвращает только документы, в которых пользователь числится владельцем."""
        user = self.request.user
        queryset = super().get_queryset()

        if user.is_authenticated:
            return queryset.filter(owner=user)
        return queryset.none()

    def _run_async_in_thread(
            self, task_uuid, chat_id_owner, chat_id_assignee, message_lines_owner, message_lines_assignee):
        """Запуск асинхронной функции в отдельном потоке"""
        def run_async():
            # Создаем новый event loop для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    send_telegram_notification(
                        task_uuid, chat_id_owner, chat_id_assignee, message_lines_owner, message_lines_assignee)
                )
            finally:
                loop.close()

        thread = threading.Thread(target=run_async)
        thread.start()

    def perform_create(self, serializer):
        """Явно устанавливаем владельца перед сохранением."""
        task = serializer.save(owner=self.request.user) # Чтобы получить uuid текущей задачи

        message_lines_owner = [
            f"🎯 *Задача: {task.name}*",
            f"🆔 ID: `{task.uuid}`",
            f"",
            f"📝 *Описание:*",
            f"{task.description}",
            f"",
            f"⏰ *Срок выполнения:*",
            f"до {task.end_date.strftime('%d.%m.%Y в %H:%M')}",
            f"",
            f"📊 *Текущий статус:* {task.get_status_display()}",
            f"",
            f"🗓️ *Создана:* {task.created_at.strftime('%d.%m.%Y')}"
        ]

        message_lines_assignee = [
            f"🎯 *Задача: {task.name}*",
            f"",
            f"📝 *Описание:*",
            f"{task.description}",
            f"",
            f"⏰ *Срок выполнения:*",
            f"до {task.end_date.strftime('%d.%m.%Y в %H:%M')}"
        ]

        chat_id_owner = self.request.user.telegram_chat_id

        if task.assignee and task.assignee.telegram_chat_id:
            chat_id_assignee = task.assignee.telegram_chat_id
            # Получаем chat id исполнителя задачи
        else:
            chat_id_assignee = None

        # Celery не может сериализовать объекты, поэтому передаем только примитивные данные
        # Поэтому вместо списка, строка, а вместо объекта self.request.user, self.request.user.telegram_chat_id
        # Так как Celery асинхронный, вместе с асинхронными задачами не используем

        # Запускаем в отдельном потоке, чтобы избежать конфликта event loop
        self._run_async_in_thread(
            task.uuid, chat_id_owner, chat_id_assignee, message_lines_owner, message_lines_assignee)
