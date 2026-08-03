from rest_framework import serializers

from .models import Payment, Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    price_display = serializers.CharField(read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id", "code", "name", "price_cents", "price_display", "currency", "interval",
            "unlimited_likes", "unlimited_messaging", "advanced_filters",
            "verified_badge_priority", "profile_boost", "see_profile_viewers",
            "see_who_liked_you", "sort_order",
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id", "plan", "status", "current_period_start", "current_period_end",
            "cancel_at_period_end", "created_at",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    amount_display = serializers.CharField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "provider", "amount_cents", "amount_display", "currency",
            "status", "invoice_number", "created_at",
        ]


class StartCheckoutSerializer(serializers.Serializer):
    plan_code = serializers.SlugField()
