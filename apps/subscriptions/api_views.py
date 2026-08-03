import stripe
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Payment, Plan, Subscription
from .serializers import PaymentSerializer, PlanSerializer, StartCheckoutSerializer, SubscriptionSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY


class PlanListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        plans = Plan.objects.filter(is_active=True)
        return Response(PlanSerializer(plans, many=True).data)


class MySubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = (
            Subscription.objects.filter(user=request.user, status=Subscription.Status.ACTIVE)
            .select_related("plan")
            .first()
        )
        if not sub:
            return Response(None)
        return Response(SubscriptionSerializer(sub).data)


class StartCheckoutView(APIView):
    """
    POST {plan_code} -> for the free plan, activates it immediately and
    returns {checkout_url: null}. For paid plans, creates a Stripe Checkout
    Session and returns {checkout_url: "https://checkout.stripe.com/..."}
    for the frontend to redirect the browser to.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StartCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = get_object_or_404(Plan, code=serializer.validated_data["plan_code"], is_active=True)

        if plan.price_cents == 0:
            Subscription.objects.update_or_create(
                user=request.user, plan=plan, defaults={"status": Subscription.Status.ACTIVE}
            )
            return Response({"checkout_url": None, "detail": f"You're on the {plan.name} plan."})

        if not plan.stripe_price_id:
            return Response({"detail": "This plan isn't connected to a Stripe price yet."}, status=400)

        try:
            checkout_session = stripe.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
                customer_email=request.user.email,
                client_reference_id=str(request.user.pk),
                success_url=f"{settings.FRONTEND_URL}/premium/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/premium/cancel",
            )
        except stripe.error.StripeError as exc:
            return Response(
                {"detail": f"Stripe checkout could not be started: {exc.user_message or 'check API keys.'}"},
                status=400,
            )

        return Response({"checkout_url": checkout_session.url})


class BillingHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = Payment.objects.filter(user=request.user)
        return Response(PaymentSerializer(payments, many=True).data)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """
    Receives Stripe events and reconciles local Subscription/Payment rows.
    Wire up real handling of each event.type once STRIPE_WEBHOOK_SECRET is a
    real value from the Stripe dashboard.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError):
            return HttpResponse(status=400)

        if event["type"] == "checkout.session.completed":
            # TODO: look up the user via session["client_reference_id"], create/
            # update the Subscription row, and log a Payment with a fresh invoice number.
            pass
        elif event["type"] in ("invoice.paid", "customer.subscription.deleted"):
            # TODO: keep Subscription.status / current_period_end in sync.
            pass

        return HttpResponse(status=200)
