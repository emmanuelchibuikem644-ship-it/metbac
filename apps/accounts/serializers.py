from datetime import date

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User

MINIMUM_AGE = 18


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=10)

    class Meta:
        model = User
        fields = ["id", "display_name", "email", "date_of_birth", "gender", "orientation", "password"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_date_of_birth(self, value):
        if value is None:
            raise serializers.ValidationError("Please provide your date of birth.")
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if value > today:
            raise serializers.ValidationError("That date of birth is not valid.")
        if age < MINIMUM_AGE:
            raise serializers.ValidationError("You must be at least 18 years old to join Kindred.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class MeSerializer(serializers.ModelSerializer):
    is_premium = serializers.BooleanField(read_only=True)
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "display_name", "date_of_birth", "age", "gender",
            "orientation",
            "is_email_verified", "is_premium", "date_joined",
        ]
        read_only_fields = ["id", "email", "is_email_verified", "date_joined"]


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=10)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class ResendVerificationSerializer(serializers.Serializer):
    """Empty body — the target user comes from the authenticated request."""
    pass
