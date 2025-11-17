from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["uuid", "name", "description"]
    list_filter = ["owner"]
    search_fields = ["name", "owner__username"]
    readonly_fields = ["created_at", "owner", "uuid"]

    # ИСКЛЮЧАЕМ поле owner из формы добавления и изменения
    exclude = ["owner"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("owner")
