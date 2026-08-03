from django.contrib import admin

from .models import Payment, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "price_display", "interval", "is_active", "sort_order"]
    list_editable = ["sort_order", "is_active"]
    prepopulated_fields = {"code": ("name",)}


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "status", "current_period_end", "cancel_at_period_end"]
    list_filter = ["status", "plan"]
    search_fields = ["user__email"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "user", "provider", "amount_display", "status", "created_at"]
    list_filter = ["provider", "status"]
    search_fields = ["invoice_number", "user__email"]
