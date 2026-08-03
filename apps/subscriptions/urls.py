from django.urls import path

from . import api_views

app_name = "subscriptions"

urlpatterns = [
    path("plans/", api_views.PlanListView.as_view(), name="plans"),
    path("me/", api_views.MySubscriptionView.as_view(), name="my_subscription"),
    path("checkout/", api_views.StartCheckoutView.as_view(), name="start_checkout"),
    path("billing-history/", api_views.BillingHistoryView.as_view(), name="billing_history"),
    path("webhook/stripe/", api_views.StripeWebhookView.as_view(), name="stripe_webhook"),
]
