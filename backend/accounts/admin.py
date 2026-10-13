from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ApiKey, Invite, Organization, User


class MemberInline(admin.TabularInline):
    model = User
    fields = ["email", "full_name", "role", "is_active", "last_login"]
    readonly_fields = ["email", "last_login"]
    extra = 0
    show_change_link = True


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "plan", "plan_expires_at", "phone", "docs_this_month", "created_at"]
    list_filter = ["plan"]
    search_fields = ["name", "phone", "members__email"]
    inlines = [MemberInline]

    @admin.display(description="Docs this month")
    def docs_this_month(self, obj):
        return obj.docs_used()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "full_name", "organization", "role", "is_active", "last_login"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "full_name", "organization__name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "organization", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ["organization", "role", "created_at", "expires_at", "used_by"]


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "prefix", "created_at", "last_used_at", "revoked"]
    readonly_fields = ["key_hash", "prefix"]
