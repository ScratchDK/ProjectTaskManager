from uuid import uuid4

from django.db import models
from django.core.exceptions import ValidationError


class Task(models.Model):
    CHOICES_STATUS = [
        ('NEW', 'Новая'),
        ('WORK', 'В работе'),
        ('REVIEW', 'На проверке'),
        ('DONE', 'Выполнена'),
        ('REJECTED', 'Отклонена'),
    ]

    uuid = models.UUIDField(
        primary_key=True, editable=False, unique=True, default=uuid4
    )
    name = models.CharField(max_length=100, verbose_name="Название")
    description = models.CharField(max_length=255, verbose_name="Описание")
    status = models.CharField(
        max_length=20, choices=CHOICES_STATUS, default="NEW", verbose_name="Статус"
    )
    owner = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="created_tasks",
        verbose_name="Автор",
        editable=False,  # Запрещаем редактирование в формах
    )
    assignee = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        verbose_name="Исполнитель",
    )
#_______________________________________________________________________________________________________________________
    completion_proof = models.TextField(blank=True, null=True, verbose_name="Доказательство выполнения")
    completion_file_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="ID файла доказательства")
    completion_media_type = models.CharField(max_length=10, blank=True, null=True, verbose_name="Тип медиа")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="Время завершения")
#_______________________________________________________________________________________________________________________
    created_at = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(verbose_name="Дата выполнения")

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        db_table = "tasks"
        ordering = ["-created_at"]  # Сортировка по умолчанию

    def __str__(self):
        return f"Задача: {self.name}"

    def clean(self):
        """Валидация данных перед сохранением"""
        super().clean()

        if not self.created_at:
            return

        if self.end_date and self.end_date < self.created_at:
            raise ValidationError({
                'end_date': 'Дата выполнения не может быть раньше даты создания задачи'
            })

    def save(self, *args, **kwargs):
        self.full_clean()  # Вызов валидации перед сохранением
        super().save(*args, **kwargs)
