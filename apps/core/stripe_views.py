"""
Stripe integration for profile subscriptions.

Flow:
1. User clicks "Subscribe" on a profile → chooses a recurring plan (monthly or 14 days)
2. Frontend sends profile_id + plan to this backend
3. Backend looks up the profile's price (set in admin) and creates a PaymentIntent
   for the one-time initial unlock fee (initial_price_cents)
4. On success, backend saves the card (PaymentMethod) and creates a real Stripe
   Subscription that auto-charges the recurring amount every month / 14 days
5. Frontend redirects to /services (unlocked)
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import stripe

from .models import ProfilePrice, ProfileSubscription, ServicePayment

stripe.api_key = settings.STRIPE_SECRET_KEY

# Recurring plan definitions (cents + Stripe interval)
PLAN_INTERVALS = {
    "month": {"interval": "month", "interval_count": 1, "label": "monthly"},
    "14days": {"interval": "day", "interval_count": 14, "label": "every 14 days"},
}


def _get_profile_price(profile_id):
    """Return the ProfilePrice row for a profile, or defaults if unset."""
    p = ProfilePrice.objects.filter(profile_id=profile_id).first()
    if p:
        return p
    # Fallback defaults
    return {
        "initial_price_cents": 20000,
        "recurring_monthly_price_cents": 3500,
        "recurring_14day_price_cents": 1400,
    }


class CreateSubscriptionPaymentView(APIView):
    """
    POST /api/core/stripe/create-payment/
    Body: { profile_id, plan }  (plan = "month" | "14days")
    Creates a Stripe PaymentIntent for the profile's initial unlock fee.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile_id = request.data.get("profile_id") or request.data.get("creator_id")
        plan = request.data.get("plan", "month")

        if not profile_id:
            return Response({"detail": "profile_id is required."}, status=400)

        if plan not in PLAN_INTERVALS:
            return Response({"detail": "plan must be 'month' or '14days'."}, status=400)

        try:
            profile_id = int(profile_id)
        except (TypeError, ValueError):
            return Response({"detail": "profile_id must be an integer."}, status=400)

        price = _get_profile_price(profile_id)
        initial_cents = price["initial_price_cents"]
        if plan == "month":
            recurring_cents = price["recurring_monthly_price_cents"]
        else:
            recurring_cents = price["recurring_14day_price_cents"]

        try:
            # Create or get existing customer
            customers = stripe.Customer.list(email=request.user.email, limit=1)
            if customers.data:
                customer = customers.data[0]
            else:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=request.user.display_name,
                    metadata={"user_id": request.user.id},
                )

            # Create PaymentIntent for the initial unlock fee
            intent = stripe.PaymentIntent.create(
                amount=initial_cents,
                currency="usd",
                customer=customer.id,
                metadata={
                    "type": "profile_subscription_initial",
                    "subscriber_id": request.user.id,
                    "profile_id": profile_id,
                    "plan": plan,
                    "recurring_amount": recurring_cents,
                },
                description=f"Initial unlock fee for profile subscription",
                automatic_payment_methods={"enabled": True},
                setup_future_usage="off_session",  # save the card for recurring billing
            )

            return Response({
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount_cents": initial_cents,
                "amount_display": f"${initial_cents / 100:.2f}",
                "recurring_cents": recurring_cents,
                "recurring_display": f"${recurring_cents / 100:.2f}/{PLAN_INTERVALS[plan]['label']}",
                "plan": plan,
            })

        except stripe.error.StripeError as e:
            return Response({"detail": f"Stripe error: {str(e)}"}, status=400)


class ConfirmSubscriptionPaymentView(APIView):
    """
    POST /api/core/stripe/confirm-payment/
    Body: { payment_intent_id, profile_id, plan }
    Verifies the PaymentIntent succeeded, saves the card, and creates a
    real recurring Stripe Subscription.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_intent_id = request.data.get("payment_intent_id")
        profile_id = request.data.get("profile_id") or request.data.get("creator_id")
        plan = request.data.get("plan", "month")

        if not payment_intent_id or not profile_id:
            return Response({"detail": "payment_intent_id and profile_id are required."}, status=400)

        if plan not in PLAN_INTERVALS:
            return Response({"detail": "plan must be 'month' or '14days'."}, status=400)

        try:
            profile_id = int(profile_id)
        except (TypeError, ValueError):
            return Response({"detail": "profile_id must be an integer."}, status=400)

        price = _get_profile_price(profile_id)
        if plan == "month":
            recurring_cents = price["recurring_monthly_price_cents"]
        else:
            recurring_cents = price["recurring_14day_price_cents"]

        try:
            # Verify the payment with Stripe
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status != "succeeded":
                return Response(
                    {"detail": f"Payment not completed. Status: {intent.status}"},
                    status=400,
                )

            customer_id = intent.customer
            payment_method_id = intent.payment_method

            # Create a Stripe Price for the recurring amount
            price_obj = stripe.Price.create(
                currency="usd",
                unit_amount=recurring_cents,
                recurring={
                    "interval": PLAN_INTERVALS[plan]["interval"],
                    "interval_count": PLAN_INTERVALS[plan]["interval_count"],
                },
                product_data={
                    "name": f"Metlink Profile {profile_id} — {PLAN_INTERVALS[plan]['label']}",
                    "metadata": {"profile_id": str(profile_id), "plan": plan},
                },
            )

            # Create the recurring subscription (starts after the initial period)
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_obj.id}],
                default_payment_method=payment_method_id,
                metadata={
                    "type": "profile_subscription_recurring",
                    "subscriber_id": request.user.id,
                    "profile_id": profile_id,
                    "plan": plan,
                },
                off_session=True,
            )

            # Create or update subscription record
            sub, created = ProfileSubscription.objects.get_or_create(
                subscriber=request.user,
                creator_id=profile_id,
                defaults={
                    "is_active": True,
                    "stripe_customer_id": customer_id,
                    "stripe_payment_method_id": payment_method_id or "",
                    "stripe_subscription_id": subscription.id,
                    "initial_payment_cents": intent.amount,
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
                sub.stripe_customer_id = customer_id
                sub.stripe_payment_method_id = payment_method_id or sub.stripe_payment_method_id
                sub.stripe_subscription_id = subscription.id
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
                "recurring_display": f"${recurring_cents / 100:.2f}/{PLAN_INTERVALS[plan]['label']}",
            })

        except stripe.error.StripeError as e:
            return Response({"detail": f"Stripe error: {str(e)}"}, status=400)


class CreateServicePaymentView(APIView):
    """
    POST /api/core/stripe/create-service-payment/
    Body: { service_name, amount_cents }
    Creates a Stripe PaymentIntent for a one-time service payment.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        service_name = (request.data.get("service_name") or "").strip()
        amount_cents = request.data.get("amount_cents")

        if not service_name or not amount_cents:
            return Response({"detail": "service_name and amount_cents are required."}, status=400)

        try:
            amount_cents = int(amount_cents)
        except (TypeError, ValueError):
            return Response({"detail": "amount_cents must be an integer."}, status=400)

        if amount_cents <= 0:
            return Response({"detail": "amount_cents must be greater than zero."}, status=400)

        try:
            # Create or get existing customer
            customers = stripe.Customer.list(email=request.user.email, limit=1)
            if customers.data:
                customer = customers.data[0]
            else:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=request.user.display_name,
                    metadata={"user_id": request.user.id},
                )

            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="usd",
                customer=customer.id,
                metadata={
                    "type": "service_payment",
                    "subscriber_id": request.user.id,
                    "service_name": service_name,
                },
                description=f"Payment for {service_name}",
                automatic_payment_methods={"enabled": True},
            )

            # Record the payment intent
            ServicePayment.objects.create(
                subscriber=request.user,
                service_name=service_name,
                service_price_cents=amount_cents,
                payment_intent_id=intent.id,
                is_paid=False,
            )

            return Response({
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount_cents": amount_cents,
                "amount_display": f"${amount_cents / 100:.2f}",
            })

        except stripe.error.StripeError as e:
            return Response({"detail": f"Stripe error: {str(e)}"}, status=400)


class ConfirmServicePaymentView(APIView):
    """
    POST /api/core/stripe/confirm-service-payment/
    Body: { payment_intent_id }
    Verifies the PaymentIntent succeeded and marks the service as paid.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_intent_id = request.data.get("payment_intent_id")
        if not payment_intent_id:
            return Response({"detail": "payment_intent_id is required."}, status=400)

        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status != "succeeded":
                return Response(
                    {"detail": f"Payment not completed. Status: {intent.status}"},
                    status=400,
                )

            # Mark the service payment as paid
            payment = ServicePayment.objects.filter(
                subscriber=request.user,
                payment_intent_id=payment_intent_id,
            ).first()

            if payment:
                payment.is_paid = True
                payment.save()

            return Response({
                "success": True,
                "detail": "Payment confirmed! You can now book this service.",
                "service_name": payment.service_name if payment else "",
            })

        except stripe.error.StripeError as e:
            return Response({"detail": f"Stripe error: {str(e)}"}, status=400)


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