from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = (
        "Creates (or updates) a superuser with the hardcoded email/password "
        "from settings.DEFAULT_ADMIN_EMAIL / DEFAULT_ADMIN_PASSWORD, so there's "
        "always a guaranteed way into /django-admin/ in dev/demo environments."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="If the admin account already exists, reset its password to the configured value too.",
        )

    def handle(self, *args, **options):
        email = settings.DEFAULT_ADMIN_EMAIL
        password = settings.DEFAULT_ADMIN_PASSWORD

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "display_name": "Admin",
                "date_of_birth": date(1990, 1, 1),
                "is_staff": True,
                "is_superuser": True,
                "is_email_verified": True,
                "is_active": True,
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created admin account: {email}"))
        else:
            # Make sure an existing account still has admin rights, and
            # optionally reset its password back to the configured value.
            changed_fields = []
            if not user.is_staff or not user.is_superuser:
                user.is_staff = True
                user.is_superuser = True
                changed_fields += ["is_staff", "is_superuser"]
            if options["reset_password"]:
                user.set_password(password)
                changed_fields.append("password")
            if changed_fields:
                user.save(update_fields=changed_fields)
            self.stdout.write(self.style.SUCCESS(f"Admin account already exists: {email}"))

        self.stdout.write(
            self.style.WARNING(
                f"Login at /django-admin/ with email='{email}' password='{password}' "
                "— change DEFAULT_ADMIN_EMAIL / DEFAULT_ADMIN_PASSWORD in .env before deploying anywhere real."
            )
        )
