from rest_framework import serializers
from django.utils import timezone

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = Task
        fields = "__all__"
        read_only_fields = ["uuid", "owner", "created_at"]

    def validate(self, data):
        """Валидация даты выполнения"""
        end_date = data.get('end_date')
        # instance - текущий объект обрабатываемый сериализатором
        if self.instance:
            created_at = self.instance.created_at
        else:
            created_at = timezone.now()

        if end_date and end_date < created_at:
            raise serializers.ValidationError({
                'due_date': 'Дата выполнения не может быть раньше даты создания задачи'
            })

        return data
