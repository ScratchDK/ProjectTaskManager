from rest_framework import viewsets

from .models import Task
from .paginators import MyPagination
from .permissions import IsOwner
from .serializers import TaskSerializer


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

    def perform_create(self, serializer):
        """Явно устанавливаем владельца перед сохранением."""
        serializer.save(owner=self.request.user)
