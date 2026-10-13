from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["display_name", "organization", "user", "status", "input_bytes", "output_bytes",
                    "target_bytes", "met_target", "text_quality", "created_at"]
    list_filter = ["status", "met_target", "output_format", "color_mode", "via_api"]
    search_fields = ["label", "organization__name", "user__email"]
    exclude = ["password"]
    readonly_fields = [f.name for f in Job._meta.fields if f.name != "password"]

    def has_add_permission(self, request):
        return False
