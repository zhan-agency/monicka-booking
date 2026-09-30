from django.contrib import admin

from .models import BookingWidgetConfig


@admin.register(BookingWidgetConfig)
class BookingWidgetConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        ("API", {"fields": ("api_base_url", "primary_clinic_id"),
                 "description": "Set MONICKA_API_KEY in the website environment. The secret is never stored or shown here."}),
        ("Appearance", {"fields": ("title", "introduction", "theme", "font_scale", "currency_label")}),
        ("Contact", {"fields": ("show_phone_support", "support_phone")}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not BookingWidgetConfig.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return request.user.is_staff
