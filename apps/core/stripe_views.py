"""
Stripe integration for profile subscriptions.

Flow:
1. User clicks "Subscribe" on a profile → enters card details
2. Frontend sends card + profile info to this backend
3. Backend creates a Stripe PaymentIntent for $200 (initial payment)
4. On success, backend creates/activates ProfileSubscription
5. Frontend redirects to /services (unlocked)
6. Monthly recurring $15 is charged automatically via Stripe
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import stripe

from .models import ProfileLike, ProfileSubscription, ServicePayment

stripe.api_key = settings.STRIPE_SECRET_KEY


class CreateSubscriptionPaymentView(APIView):
    """
    POST /api/core/stripe/create-payment/
    Body: { creator_id }
    Creates a Stripe PaymentIntent for $200 initial payment.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        creator_id = request.data.get("creator_id")
        if not creator_id:
            return Response({"detail": "creator_id is required."}, status=400)

        if int(creator_id) == request.user.id:
            return Response({"detail": "You cannot subscribe to yourself."}, status=400)

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

            # Create PaymentIntent for $200 (20000 cents)
            intent = stripe.PaymentIntent.create(
                amount=20000,  # $200 in cents
                currency="usd",
                customer=customer.id,
                metadata={
                    "type": "profile_subscription_initial",
                    "subscriber_id": request.user.id,
                    "creator_id": creator_id,
                    "recurring_amount": 1500,  # $15 in cents
                },
                description=f"Initial payment for profile subscription",
                automatic_payment_methods={"enabled": True},
            )

            return Response({
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount_cents": 20000,
                "amount_display": "$200.00",
                "recurring_display": "$15.00/month",
            })

        except stripe.error.StripeError as e:
            return Response({"detail": f"Stripe error: {str(e)}"}, status=400)


class ConfirmSubscriptionPaymentView(APIView):
    """
    POST /api/core/stripe/confirm-payment/
    Body: { payment_intent_id, creator_id }
    Verifies the PaymentIntent succeeded and activates the subscription.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_intent_id = request.data.get("payment_intent_id")
        creator_id = request.data.get("creator_id")

        if not payment_intent_id or not creator_id:
            return Response({"detail": "payment_intent_id and creator_id are required."}, status=400)

        try:
            # Verify the payment with Stripe
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status != "succeeded":
                return Response(
                    {"detail": f"Payment not completed. Status: {intent.status}"},
                    status=400,
                )

            # Create or update subscription
            sub, created = ProfileSubscription.objects.get_or_create(
                subscriber=request.user,
                creator_id=creator_id,
                defaults={
                    "is_active": True,
                    "stripe_customer_id": intent.customer,
                    "initial_payment_cents": 20000,
                    "recurring_price_cents": 1500,
                    "services_unlocked": True,
                    "started_at": timezone.now(),
                    "expires_at": timezone.now() + timedelta(days=30),
                    "last_charged_at": timezone.now(),
                },
            )

            if not created:
                sub.is_active = True
                sub.services_unlocked = True
                sub.expires_at = timezone.now() + timedelta(days=30)
                sub.last_charged_at = timezone.now()
                sub.save()

            return Response({
                "success": True,
                "detail": "Payment confirmed! Services are now unlocked.",
                "services_unlocked": True,
                "expires_at": sub.expires_at.isoformat(),
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