from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from tasks.serializers import TaskSerializer

from .models import Task
from .permissions import IsOwner

User = get_user_model()


class TaskModelTest(TestCase):
    """Тесты для модели Task"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.task_data = {
            "name": "Test Task",
            "description": "Test Description",
            "owner": self.user,
        }

    def test_create_task(self):
        """Тест создания задачи"""
        task = Task.objects.create(**self.task_data)
        self.assertEqual(task.name, "Test Task")
        self.assertEqual(task.description, "Test Description")
        self.assertEqual(task.owner, self.user)
        self.assertIsNotNone(task.uuid)
        self.assertIsNotNone(task.created_at)

    def test_task_string_representation(self):
        """Тест строкового представления задачи"""
        task = Task.objects.create(**self.task_data)
        self.assertEqual(str(task), f"Задаче {task.name}")

    def test_task_verbose_names(self):
        """Тест verbose names модели"""
        self.assertEqual(Task._meta.verbose_name, "Задача")
        self.assertEqual(Task._meta.verbose_name_plural, "Задачи")
        self.assertEqual(Task._meta.db_table, "tasks")


class TaskPermissionsTest(TestCase):
    """Тесты для кастомных permissions"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            email="user1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com", password="testpass123"
        )
        self.task = Task.objects.create(
            name="Test Task", description="Test Description", owner=self.user1
        )
        self.permission = IsOwner()

    def test_has_permission_authenticated(self):
        """Тест has_permission для аутентифицированного пользователя"""
        request = type("Request", (), {"user": self.user1})()
        self.assertTrue(self.permission.has_permission(request, None))

    def test_has_permission_unauthenticated(self):
        """Тест has_permission для неаутентифицированного пользователя"""
        request = type("Request", (), {"user": None})()
        self.assertFalse(self.permission.has_permission(request, None))

    def test_has_object_permission_owner(self):
        """Тест has_object_permission для владельца"""
        request = type("Request", (), {"user": self.user1})()
        self.assertTrue(self.permission.has_object_permission(request, None, self.task))

    def test_has_object_permission_not_owner(self):
        """Тест has_object_permission для не владельца"""
        request = type("Request", (), {"user": self.user2})()
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.task)
        )


class TaskViewSetTest(APITestCase):
    """Тесты для TaskViewSet"""

    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(
            email="user1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com", password="testpass123"
        )

        # Создаем задачи для пользователей
        self.task1 = Task.objects.create(
            name="Task 1 User1", description="Description 1", owner=self.user1
        )
        self.task2 = Task.objects.create(
            name="Task 2 User1", description="Description 2", owner=self.user1
        )
        self.task3 = Task.objects.create(
            name="Task User2", description="Description 3", owner=self.user2
        )

        self.list_url = reverse("task:task-list")
        self.detail_url = lambda uuid: reverse("task:task-detail", kwargs={"pk": uuid})

    def test_list_tasks_unauthenticated(self):
        """Тест получения списка задач без аутентификации"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_tasks_authenticated(self):
        """Тест получения списка задач с аутентификацией"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)  # Только задачи user1

    def test_retrieve_own_task(self):
        """Тест получения своей задачи"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.detail_url(self.task1.uuid))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Task 1 User1")

    def test_retrieve_other_user_task(self):
        """Тест получения чужой задачи (должен вернуть 404)"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.detail_url(self.task3.uuid))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_task(self):
        """Тест создания задачи"""
        self.client.force_authenticate(user=self.user1)
        data = {"name": "New Task", "description": "New Description"}
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Task")
        self.assertEqual(response.data["owner_email"], self.user1.email)

        # Проверяем, что задача действительно создалась
        task = Task.objects.get(name="New Task")
        self.assertEqual(task.owner, self.user1)

    def test_update_own_task(self):
        """Тест обновления своей задачи"""
        self.client.force_authenticate(user=self.user1)
        data = {"name": "Updated Task", "description": "Updated Description"}
        response = self.client.put(self.detail_url(self.task1.uuid), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Task")

        # Обновляем данные в БД
        self.task1.refresh_from_db()
        self.assertEqual(self.task1.name, "Updated Task")

    def test_update_other_user_task(self):
        """Тест обновления чужой задачи (должен вернуть 404)"""
        self.client.force_authenticate(user=self.user1)
        data = {"name": "Hacked Task", "description": "Hacked Description"}
        response = self.client.put(self.detail_url(self.task3.uuid), data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_own_task(self):
        """Тест удаления своей задачи"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(self.detail_url(self.task1.uuid))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Проверяем, что задача удалилась
        with self.assertRaises(Task.DoesNotExist):
            Task.objects.get(uuid=self.task1.uuid)

    def test_delete_other_user_task(self):
        """Тест удаления чужой задачи (должен вернуть 404)"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(self.detail_url(self.task3.uuid))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_pagination(self):
        """Тест пагинации"""
        self.client.force_authenticate(user=self.user1)

        # Создаем больше задач для тестирования пагинации
        for i in range(15):
            Task.objects.create(
                name=f"Task {i}", description=f"Description {i}", owner=self.user1
            )

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

        # Проверяем размер страницы по умолчанию
        self.assertEqual(len(response.data["results"]), 10)

        # Тестируем параметр page_size
        response = self.client.get(f"{self.list_url}?page_size=5")
        self.assertEqual(len(response.data["results"]), 5)


class TaskSerializerTest(TestCase):
    """Тесты для сериализатора TaskSerializer"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.task_data = {
            "name": "Test Task",
            "description": "Test Description",
            "owner": self.user.pk,
        }

    def test_serializer_valid_data(self):
        """Тест валидных данных сериализатора"""
        serializer = TaskSerializer(data=self.task_data)
        self.assertTrue(serializer.is_valid())

    def test_serializer_missing_required_field(self):
        """Тест отсутствия обязательного поля"""
        invalid_data = self.task_data.copy()
        del invalid_data["name"]
        serializer = TaskSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_serializer_read_only_fields(self):
        """Тест read_only полей"""
        task = Task.objects.create(
            name="Test Task", description="Test Description", owner=self.user
        )

        serializer = TaskSerializer(instance=task)
        data = serializer.data

        # Проверяем, что read_only поля присутствуют в выводе
        self.assertIn("uuid", data)
        self.assertIn("owner", data)
        self.assertIn("created_at", data)

        # Пытаемся обновить read_only поле (должно игнорироваться)
        update_data = {
            "name": "Updated Task",
            "uuid": str(uuid4()),  # Пытаемся изменить read_only поле
            "owner": self.user.pk + 1,  # Пытаемся изменить read_only поле
        }
        serializer = TaskSerializer(instance=task, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid())

        # Сохраняем и проверяем, что read_only поля не изменились
        serializer.save()
        task.refresh_from_db()
        self.assertEqual(task.name, "Updated Task")
        self.assertNotEqual(str(task.uuid), update_data["uuid"])  # UUID не изменился
        self.assertEqual(task.owner, self.user)  # Владелец не изменился


class TaskAdminTest(TestCase):
    """Тесты для админки Task"""

    def setUp(self):
        from django.contrib.admin.sites import site

        from tasks.admin import TaskAdmin

        self.user = User.objects.create_user(
            email="admin@example.com",
            password="adminpass",
            is_staff=True,
            is_superuser=True,
        )
        self.task = Task.objects.create(
            name="Admin Test Task",
            description="Admin Test Description",
            owner=self.user,
        )

        self.model_admin = TaskAdmin(Task, site)

    def test_admin_list_display(self):
        """Тест list_display в админке"""
        self.assertEqual(self.model_admin.list_display, ["uuid", "name", "description"])

    def test_admin_list_filter(self):
        """Тест list_filter в админке"""
        self.assertEqual(self.model_admin.list_filter, ["owner"])

    def test_admin_search_fields(self):
        """Тест search_fields в админке"""
        self.assertEqual(self.model_admin.search_fields, ["name", "owner__username"])

    def test_admin_readonly_fields(self):
        """Тест readonly_fields в админке"""
        self.assertEqual(
            self.model_admin.readonly_fields, ["created_at", "owner", "uuid"]
        )

    def test_admin_get_queryset(self):
        """Тест get_queryset в админке"""
        queryset = self.model_admin.get_queryset(None)
        # Проверяем, что используется select_related
        self.assertTrue(hasattr(queryset.query, "select_related"))
        self.assertTrue("owner" in queryset.query.select_related)


class TaskURLsTest(APITestCase):
    """Тесты URL маршрутов"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_task_list_url(self):
        """Тест URL списка задач"""
        url = reverse("task:task-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_task_detail_url(self):
        """Тест URL детальной информации о задаче"""
        task = Task.objects.create(
            name="Test Task", description="Test Description", owner=self.user
        )
        url = reverse("task:task-detail", kwargs={"pk": task.uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
