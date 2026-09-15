from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

admin.site.unregister(User)

@admin.register(User)
class UsuarioAdmin(UserAdmin):
    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj and obj.pk == request.user.pk:
            return (*fields, 'is_superuser', 'is_staff', 'is_active')
        return fields

    def has_delete_permission(self, request, obj=None):
        return (obj is None or obj.pk != request.user.pk) and super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        if queryset.filter(pk=request.user.pk).exists():
            raise PermissionDenied('Não é permitido excluir seu próprio administrador.')
        super().delete_queryset(request, queryset)
