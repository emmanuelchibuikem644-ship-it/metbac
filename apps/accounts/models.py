from datetime import date

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_email_verified", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Platform account. Full dating-profile fields (photos, bio, interests,
    location, etc.) are added by the profile app in the next phase — this
    model only carries what auth + premium billing need.
    """

    class Gender(models.TextChoices):
        WOMAN = "woman", "Woman"
        MAN = "man", "Man"
        NONBINARY = "nonbinary", "Non-binary"
        OTHER = "other", "Prefer to self-describe"
        UNSPECIFIED = "unspecified", "Prefer not to say"

    class Orientation(models.TextChoices):
        STRAIGHT = "straight", "Straight"
        GAY = "gay", "Gay"

    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=60)
    date_of_birth = models.DateField(
        help_text="Must indicate an age of 18 or over. Verified at signup.",
    )
    gender = models.CharField(max_length=20, choices=Gender.choices, default=Gender.UNSPECIFIED)
    orientation = models.CharField(
        max_length=10,
        choices=Orientation.choices,
        default="",
        blank=True,
        help_text="User's romantic interest preference (straight or gay).",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.email

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def is_premium(self):
        """True if the user has a currently active premium subscription."""
        # Local import avoids a circular dependency between accounts <-> subscriptions.
        from apps.subscriptions.models import Subscription

        return Subscription.objects.filter(
            user=self, status=Subscription.Status.ACTIVE
        ).exclude(plan__code="free").exists()
