from rest_framework import serializers

from .models import ProfileLike, ProfileSubscription


class ProfileLikeSerializer(serializers.ModelSerializer):
    from_user_email = serializers.EmailField(source="from_user.email", read_only=True)
    from_user_display = serializers.CharField(source="from_user.display_name", read_only=True)

    class Meta:
        model = ProfileLike
        fields = ["id", "from_user", "from_user_email", "from_user_display", "created_at"]


class ProfileSubscriptionSerializer(serializers.ModelSerializer):
    creator_email = serializers.EmailField(source="creator.email", read_only=True)
    creator_display = serializers.CharField(source="creator.display_name", read_only=True)

    class Meta:
        model = ProfileSubscription
        fields = [
            "id", "creator", "creator_email", "creator_display",
            "is_active", "started_at", "expires_at",
        ]