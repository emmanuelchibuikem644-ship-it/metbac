from django.conf import settings
from django.core.management.base import BaseCommand

from apps.subscriptions.models import Plan


class Command(BaseCommand):
    help = "Seeds the default Free / Premium Monthly / Premium Yearly plans."

    def handle(self, *args, **options):
        plans = [
            dict(
                code="free",
                name="Free",
                price_cents=0,
                interval=Plan.Interval.NONE,
                sort_order=0,
            ),
            dict(
                code="premium-monthly",
                name="Premium Monthly",
                price_cents=1999,
                interval=Plan.Interval.MONTHLY,
                stripe_price_id=settings.STRIPE_PRICE_PREMIUM_MONTHLY,
                unlimited_likes=True,
                unlimited_messaging=True,
                advanced_filters=True,
                verified_badge_priority=True,
                profile_boost=True,
                see_profile_viewers=True,
                see_who_liked_you=True,
                sort_order=1,
            ),
            dict(
                code="premium-yearly",
                name="Premium Yearly",
                price_cents=14999,
                interval=Plan.Interval.YEARLY,
                stripe_price_id=settings.STRIPE_PRICE_PREMIUM_YEARLY,
                unlimited_likes=True,
                unlimited_messaging=True,
                advanced_filters=True,
                verified_badge_priority=True,
                profile_boost=True,
                see_profile_viewers=True,
                see_who_liked_you=True,
                sort_order=2,
            ),
        ]

        for data in plans:
            plan, created = Plan.objects.update_or_create(code=data["code"], defaults=data)
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{action} plan: {plan.name}"))
