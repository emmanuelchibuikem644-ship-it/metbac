from django.conf import settings
from django.db import models


class Plan(models.Model):
    """A billing plan an admin can configure (Free, Premium Monthly, Premium Yearly, ...)."""

    class Interval(models.TextChoices):
        NONE = "none", "One-time / N/A"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    code = models.SlugField(unique=True, help_text="Stable identifier, e.g. 'free', 'premium-monthly'.")
    name = models.CharField(max_length=80)
    price_cents = models.PositiveIntegerField(default=0, help_text="Price in cents (e.g. 1999 = $19.99).")
    currency = models.CharField(max_length=3, default="USD")
    interval = models.CharField(max_length=10, choices=Interval.choices, default=Interval.NONE)

    stripe_price_id = models.CharField(max_length=120, blank=True, default="")
    paypal_plan_id = models.CharField(max_length=120, blank=True, default="")

    # Feature flags — surfaced on the pricing page and used to gate features later.
    unlimited_likes = models.BooleanField(default=False)
    unlimited_messaging = models.BooleanField(default=False)
    advanced_filters = models.BooleanField(default=False)
    verified_badge_priority = models.BooleanField(default=False)
    profile_boost = models.BooleanField(default=False)
    see_profile_viewers = models.BooleanField(default=False)
    see_who_liked_you = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "price_cents"]

    def __str__(self):
        return self.name

    @property
    def price_display(self):
        if self.price_cents == 0:
            return "Free"
        return f"${self.price_cents / 100:,.2f}"


class Subscription(models.Model):
    """A user's current relationship to a plan."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRIALING = "trialing", "Trialing"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"
        INCOMPLETE = "incomplete", "Incomplete"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    stripe_customer_id = models.CharField(max_length=120, blank=True, default="")
    stripe_subscription_id = models.CharField(max_length=120, blank=True, default="")
    paypal_subscription_id = models.CharField(max_length=120, blank=True, default="")

    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.plan.name} ({self.status})"


class Payment(models.Model):
    """A record of a single charge, used to render invoices / payment history."""

    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"

    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        PENDING = "pending", "Pending"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments"
    )
    provider = models.CharField(max_length=10, choices=Provider.choices)
    provider_reference = models.CharField(max_length=200, blank=True, default="")
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    invoice_number = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.invoice_number} — {self.user.email}"

    @property
    def amount_display(self):
        return f"${self.amount_cents / 100:,.2f}"
