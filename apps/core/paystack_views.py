"""
Paystack integration for profile subscriptions.

Flow:
1. User clicks "Subscribe" on a profile → chooses a recurring plan (monthly or 14 days)
2. Frontend sends profile_id + plan + country to this backend
3. Backend looks up the profile's price (set in admin) — price_cents is in the
   profile's LOCAL currency (e.g. Australia = A$, UK = £, UAE = AED, etc.)
4. Backend creates a Paystack payment PLAN for the recurring amount + interval,
   then initializes a transaction for the one-time initial unlock fee
   (initial_price_cents in local currency) with the plan attached.
5. On successful payment, Paystack auto-subscribes the customer to the plan,
   which collects the recurring amount on schedule from their saved card.
6. Frontend verifies the transaction and redirects to /services (unlocked).
"""

from datetime import timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import requests

from .models import ProfilePrice, ProfileSubscription, ServicePayment

PAYSTACK_SECRET = getattr(settings, "PAYSTACK_SECRET_KEY", "")
PAYSTACK_BASE = "https://api.paystack.co"


def _paystack_headers():
    return {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json",
    }


def _paystack_currency(country):
    """Map a profile's country to the Paystack-supported currency code.
    Paystack supports: NGN, USD, GBP, EUR, GHS, KES, ZAR.
    Anything not in the supported set falls back to USD.
    """
    currency_map = {
        # Africa
        "Nigeria": "NGN",
        "Ghana": "GHS",
        "Kenya": "KES",
        "South Africa": "ZAR",
        "Morocco": "USD",  # unsupported → USD
        # Europe
        "United Kingdom": "GBP",
        "Scotland": "GBP",
        "Wales": "GBP",
        "Manchester": "GBP",
        "Ireland": "EUR",
        "Dublin": "EUR",
        "France": "EUR",
        "Germany": "EUR",
        "Spain": "EUR",
        "Portugal": "EUR",
        "portugal": "EUR",
        "Italy": "EUR",
        "Greece": "EUR",
        "Austria": "EUR",
        "Belgium": "EUR",
        "Netherlands": "EUR",
        "Finland": "EUR",
        "Latvia": "EUR",
        "Iceland": "USD",
        "Norway": "USD",
        "Sweden": "USD",
        "sweden": "USD",
        "Denmark": "USD",
        "Switzerland": "USD",
        "SWitzerland": "USD",
        # Americas
        "USA": "USD",
        "United States": "USD",
        "Canada": "USD",
        "Mexico": "USD",
        "Argentina": "USD",
        "Brazil": "USD",
        "Colombia": "USD",
        # Asia
        "UAE": "USD",
        "Qatar": "USD",
        "Kuwait": "USD",
        "Lebanon": "USD",
        "China": "USD",
        "Singapore": "USD",
        # Oceania
        "Australia": "USD",
        "New Zealand": "USD",
    }
    return currency_map.get(country, "USD")


def _get_profile_price(profile_id):
    """Return the ProfilePrice row for a profile, or defaults if unset."""
    p = ProfilePrice.objects.filter(profile_id=profile_id).first()
    if p:
        return p
    return {
        "initial_price_cents": 20000,
        "recurring_monthly_price_cents": 3500,
        "recurring_14day_price_cents": 1400,
    }


class CreateSubscriptionPaymentView(APIView):
    """
    POST /api/core/paystack/create-payment/
    Body: { profile_id, plan, country, currency_symbol }
    Creates a Paystack plan (recurring) + initializes a transaction
    for the initial unlock fee in the profile's local currency.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile_id = request.data.get("profile_id") or request.data.get("creator_id")
        plan = request.data.get("plan", "month")
        country = request.data.get("country", "")

        if not profile_id:
            return Response({"detail": "profile_id is required."}, status=400)

        if plan not in ("month", "14days"):
            return Response({"detail": "plan must be 'month' or '14days'."}, status=400)

        try:
            profile_id = int(profile_id)
        except (TypeError, ValueError):
            return Response({"detail": "profile_id must be an integer."}, status=400)

        if not PAYSTACK_SECRET:
            return Response({"detail": "Paystack is not configured. Set PAYSTACK_SECRET_KEY."}, status=500)

        currency = _paystack_currency(country)
        price = _get_profile_price(profile_id)
        initial_cents = price["initial_price_cents"]
        if plan == "month":
            recurring_cents = price["recurring_monthly_price_cents"]
            interval = "monthly"
        else:
            recurring_cents = price["recurring_14day_price_cents"]
            # Paystack supports daily/weekly/monthly/quarterly/bi-annually/annually.
            # 14 days ≈ twice a month → use "weekly" as closest supported cadence.
            interval = "weekly"

        try:
            # 1) Create/refresh a Paystack plan for the recurring amount
            # Paystack charges in the smallest unit (kobo for NGN, cents for others).
            plan_name = (
                f"Metlink {profile_id} {plan}"
            )
            plan_resp = requests.post(
                f"{PAYSTACK_BASE}/plan",
                headers=_paystack_headers(),
                json={
                    "name": plan_name,
                    "amount": recurring_cents,
                    "interval": interval,
                    "currency": currency,
                    "send_invoices": True,
                    "send_sms": False,
                    "metadata": {"profile_id": profile_id, "plan": plan, "type": "profile_subscription"},
                },
                timeout=30,
            )
            if plan_resp.status_code not in (200, 201):
                data = plan_resp.json()
                return Response(
                    {"detail": f"Paystack plan error: {data.get('message', plan_resp.text)}"},
                    status=400,
                )
            plan_code = plan_resp.json()["data"]["plan_code"]

            # 2) Initialize a transaction for the INITIAL unlock fee in local currency
            reference = f"metlink-{request.user.id}-{profile_id}-{int(timezone.now().timestamp())}"
            callback_url = getattr(settings, "FRONTEND_URL", "https://metlinks.vercel.app") + "/payment"
            init_resp = requests.post(
                f"{PAYSTACK_BASE}/transaction/initialize",
                headers=_paystack_headers(),
                json={
                    "email": request.user.email,
                    "amount": initial_cents,
                    "currency": currency,
                    "reference": reference,
                    "callback_url": callback_url,
                    "plan": plan_code,
                    "metadata": {
                        "type": "profile_subscription_initial",
                        "subscriber_id": request.user.id,
                        "profile_id": profile_id,
                        "plan": plan,
                        "country": country,
                    },
                },
                timeout=30,
            )
            if init_resp.status_code not in (200, 201):
                data = init_resp.json()
                return Response(
                    {"detail": f"Paystack init error: {data.get('message', init_resp.text)}"},
                    status=400,
                )

            init_data = init_resp.json()["data"]

            return Response({
                "authorization_url": init_data["authorization_url"],
                "reference": init_data["reference"],
                "access_code": init_data.get("access_code", ""),
                "amount_cents": initial_cents,
                "amount_display": f"{request.data.get('currency_symbol', '')}{(initial_cents / 100):.2f}",
                "currency": currency,
                "recurring_cents": recurring_cents,
                "recurring_display": f"{request.data.get('currency_symbol', '')}{(recurring_cents / 100):.2f}/{interval}",
                "plan": plan,
                "country": country,
            })

        except requests.RequestException as e:
            return Response({"detail": f"Paystack network error: {str(e)}"}, status=400)


class ConfirmSubscriptionPaymentView(APIView):
    """
    POST /api/core/paystack/confirm-payment/
    Body: { reference, profile_id, plan, country }
    Verifies the Paystack transaction and activates the subscription.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        reference = request.data.get("reference")
        profile_id = request.data.get("profile_id") or request.data.get("creator_id")
        plan = request.data.get("plan", "month")
        country = request.data.get("country", "")

        if not reference or not profile_id:
            return Response({"detail": "reference and profile_id are required."}, status=400)

        try:
            profile_id = int(profile_id)
        except (TypeError, ValueError):
            return Response({"detail": "profile_id must be an integer."}, status=400)

        if not PAYSTACK_SECRET:
            return Response({"detail": "Paystack is not configured. Set PAYSTACK_SECRET_KEY."}, status=500)

        try:
            # Verify the transaction with Paystack
            verify_resp = requests.get(
                f"{PAYSTACK_BASE}/transaction/verify/{reference}",
                headers=_paystack_headers(),
                timeout=30,
            )
            if verify_resp.status_code != 200:
                return Response({"detail": "Could not verify payment with Paystack."}, status=400)

            verify_data = verify_resp.json()["data"]
            if verify_data["status"] != "success":
                return Response(
                    {"detail": f"Payment not completed. Status: {verify_data.get('status')}"},
                    status=400,
                )

            price = _get_profile_price(profile_id)
            if plan == "month":
                recurring_cents = price["recurring_monthly_price_cents"]
                interval = "monthly"
            else:
                recurring_cents = price["recurring_14day_price_cents"]
                interval = "weekly"

            # Create or update subscription record
            sub, created = ProfileSubscription.objects.get_or_create(
                subscriber=request.user,
                creator_id=profile_id,
                defaults={
                    "is_active": True,
                    "stripe_customer_id": verify_data.get("customer", {}).get("customer_code", ""),
                    "stripe_subscription_id": reference,
                    "initial_payment_cents": verify_data.get("amount", 0),
                    "recurring_price_cents": recurring_cents,
                    "recurring_interval": plan,
                    "services_unlocked": True,
                    "started_at": timezone.now(),
                    "expires_at": timezone.now() + timedelta(days=30 if plan == "month" else 14),
                    "last_charged_at": timezone.now(),
                },
            )

            if not created:
                sub.is_active = True
                sub.services_unlocked = True
                sub.stripe_customer_id = verify_data.get("customer", {}).get("customer_code", sub.stripe_customer_id)
                sub.stripe_subscription_id = reference
                sub.recurring_price_cents = recurring_cents
                sub.recurring_interval = plan
                sub.expires_at = timezone.now() + timedelta(days=30 if plan == "month" else 14)
                sub.last_charged_at = timezone.now()
                sub.save()

            return Response({
                "success": True,
                "detail": "Payment confirmed! Services are now unlocked.",
                "services_unlocked": True,
                "expires_at": sub.expires_at.isoformat(),
                "recurring_display": f"{request.data.get('currency_symbol', '')}{(recurring_cents / 100):.2f}/{interval}",
            })

        except requests.RequestException as e:
            return Response({"detail": f"Paystack verification error: {str(e)}"}, status=400)


class CheckServiceAccessView(APIView):
    """
    GET /api/core/stripe/check-access/<creator_id>/
    Returns whether the current user has paid and can access services.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, creator_id):
        sub = ProfileSubscription.objects.filter(
            subscriber=request.user,
            creator_id=creator_id,
            is_active=True,
            services_unlocked=True,
        ).first()

        return Response({
            "has_access": sub is not None,
            "expires_at": sub.expires_at.isoformat() if sub and sub.expires_at else None,
        })