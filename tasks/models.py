from uuid import uuid4

from django.db import models


class Task(models.Model):
    CHOICES_STATUS = (
        ("CREATED", "Создано"),
        ("WORK", "В работе"),
        ("COMPLETED", "Завершено"),
    )

    uuid = models.UUIDField(
        primary_key=True, editable=False, unique=True, default=uuid4
    )
    name = models.CharField(max_length=100, verbose_name="Название")
    description = models.CharField(max_length=255, verbose_name="Описание")
    status = models.CharField(
        max_length=20, choices=CHOICES_STATUS, default="CREATED", verbose_name="Статус"
    )
    owner = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Автор",
        editable=False,  # Запрещаем редактирование в формах
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        db_table = "tasks"

    def __str__(self):
        return f"Задаче {self.name}"
