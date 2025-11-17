from rest_framework.routers import DefaultRouter

import tasks.views as views
from tasks.apps import TasksConfig

app_name = TasksConfig.name

router = DefaultRouter()

router.register("task", views.TaskViewSet, basename="task")

urlpatterns = [] + router.urls
