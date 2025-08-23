from rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = Task
        fields = "__all__"
        read_only_field = ["uuid", "owner", "created_at"]
