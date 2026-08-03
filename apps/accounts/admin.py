from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["email", "display_name", "gender", "orientation", "is_email_verified", "is_premium", "is_active", "date_joined"]
    list_filter = ["is_email_verified", "is_active", "is_staff", "gender", "orientation"]
    search_fields = ["email", "display_name"]
    readonly_fields = ["date_joined", "last_login"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "date_of_birth", "gender", "orientation")}),
        ("Status", {"fields": ("is_active", "is_staff", "is_superuser", "is_email_verified")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "display_name", "date_of_birth", "gender", "orientation", "password1", "password2"),
        }),
    )
