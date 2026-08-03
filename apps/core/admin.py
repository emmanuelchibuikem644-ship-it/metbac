from django.contrib import admin

from .models import Booking, ChatConversation, ChatMessage, CryptoPayment, ProfileLike, ProfileSubscription, ServicePayment


@admin.register(ProfileLike)
class ProfileLikeAdmin(admin.ModelAdmin):
    list_display = ["from_user", "to_user", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["from_user__email", "to_user__email", "from_user__display_name", "to_user__display_name"]
    ordering = ["-created_at"]


@admin.register(ProfileSubscription)
class ProfileSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["subscriber", "creator", "is_active", "started_at"]
    list_filter = ["is_active", "started_at"]
    search_fields = ["subscriber__email", "creator__email", "subscriber__display_name", "creator__display_name"]
    ordering = ["-started_at"]


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "subscriber", "profile_name", "profile_orientation", "created_at", "updated_at"]
    list_filter = ["profile_orientation"]
    search_fields = ["subscriber__email", "profile_name"]
    ordering = ["-updated_at"]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "is_from_subscriber", "is_read", "created_at"]
    list_filter = ["is_from_subscriber", "is_read"]
    search_fields = ["content"]
    ordering = ["-created_at"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "full_name", "service_name", "status", "date", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["full_name", "email", "service_name"]
    ordering = ["-created_at"]


@admin.register(ServicePayment)
class ServicePaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "subscriber", "service_name", "service_price_cents", "is_paid", "created_at"]
    list_filter = ["is_paid", "created_at"]
    search_fields = ["subscriber__email", "service_name"]
    ordering = ["-created_at"]


@admin.register(CryptoPayment)
class CryptoPaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "subscriber", "coin", "amount_cents", "status", "purpose", "created_at"]
    list_filter = ["coin", "status", "created_at"]
    search_fields = ["subscriber__email", "wallet_address", "tx_hash", "purpose"]
    ordering = ["-created_at"]
