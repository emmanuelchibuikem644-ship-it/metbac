from django.conf import settings
from django.db import models


class ProfileLike(models.Model):
    """Tracks when a user likes another user's profile."""
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes_given",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["from_user", "to_user"]

    def __str__(self):
        return f"{self.from_user.email} liked {self.to_user.email}"


class ProfileSubscription(models.Model):
    """Tracks a user's subscription to another user's profile content."""
    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions_given",
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions_received",
    )
    is_active = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=200, blank=True, default="")
    stripe_payment_method_id = models.CharField(max_length=200, blank=True, default="")
    initial_payment_cents = models.PositiveIntegerField(default=20000, help_text="Initial payment in cents (e.g. 20000 = $200.00)")
    recurring_price_cents = models.PositiveIntegerField(default=1500, help_text="Recurring monthly price in cents (e.g. 1500 = $15.00)")
    last_charged_at = models.DateTimeField(null=True, blank=True)
    services_unlocked = models.BooleanField(default=False, help_text="True once initial payment is confirmed")

    class Meta:
        ordering = ["-started_at"]
        unique_together = ["subscriber", "creator"]

    def __str__(self):
        return f"{self.subscriber.email} → {self.creator.email} ({'active' if self.is_active else 'inactive'})"


class ChatConversation(models.Model):
    """
    A chat between a subscribed user and a profile (creator).
    The profile is modeled by its static data (id, name, avatar, orientation)
    from the frontend profiles.js — the admin replies on the profile's behalf.
    """

    class Orientation(models.TextChoices):
        STRAIGHT = "straight", "Straight"
        GAY = "gay", "Gay"

    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_conversations",
    )
    profile_id = models.PositiveIntegerField(help_text="ID of the profile in profiles.js")
    profile_name = models.CharField(max_length=120)
    profile_avatar = models.CharField(max_length=500, blank=True, default="")
    profile_orientation = models.CharField(
        max_length=10,
        choices=Orientation.choices,
        default=Orientation.STRAIGHT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ["subscriber", "profile_id"]

    def __str__(self):
        return f"{self.subscriber.email} ↔ {self.profile_name}"


class ChatMessage(models.Model):
    """An individual message within a chat conversation."""
    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    # The subscriber who started the chat
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    content = models.TextField(blank=True, default="")
    image = models.ImageField(
        upload_to="chat_images/%Y/%m/%d/",
        blank=True,
        default="",
        help_text="Optional image file attached to the message",
    )
    # True = sent by the subscriber, False = admin replying as the profile
    is_from_subscriber = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{'Subscriber' if self.is_from_subscriber else 'Profile'}: {self.content[:40]}"


class CryptoPayment(models.Model):
    """Tracks a crypto payment request for a subscription or service."""

    class Coin(models.TextChoices):
        BITCOIN = "bitcoin", "Bitcoin"
        ETHEREUM = "ethereum", "Ethereum"
        TETHER = "tether", "Tether"
        USDT = "usdt", "USDT"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        DECLINED = "declined", "Declined"

    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="crypto_payments",
    )
    coin = models.CharField(max_length=20, choices=Coin.choices)
    amount_cents = models.PositiveIntegerField(default=0)
    wallet_address = models.CharField(max_length=200, blank=True, default="")
    tx_hash = models.CharField(max_length=200, blank=True, default="", help_text="Transaction hash provided by the user after paying")
    purpose = models.CharField(max_length=200, blank=True, default="", help_text="e.g. subscription-14days, subscription-1month, service-Basic Massage")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subscriber.email} — {self.coin} ({self.status})"


class ServicePayment(models.Model):
    """Tracks a one-time payment for a service before booking."""
    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="service_payments",
    )
    service_name = models.CharField(max_length=200)
    service_price_cents = models.PositiveIntegerField(default=0)
    payment_intent_id = models.CharField(max_length=200, blank=True, default="")
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subscriber.email} — {self.service_name} ({'paid' if self.is_paid else 'unpaid'})"


class Booking(models.Model):
    """A booking request submitted by a subscriber for a service."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    service_name = models.CharField(max_length=200)
    service_price = models.CharField(max_length=100, blank=True, default="")
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=60, blank=True, default="")
    date = models.DateField(null=True, blank=True)
    time = models.CharField(max_length=20, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.service_name} ({self.status})"
