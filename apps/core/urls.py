from django.urls import path

from . import admin_api_views, api_views, chat_views, paystack_views, stripe_views

app_name = "core"

urlpatterns = [
    # Likes
    path("like/", api_views.LikeProfileView.as_view(), name="like-profile"),
    path("like/<int:user_id>/", api_views.CheckLikeView.as_view(), name="check-like"),
    path("likes-received/", api_views.MyLikesReceivedView.as_view(), name="likes-received"),
    # Subscriptions
    path("profile-price/<int:profile_id>/", api_views.ProfilePriceView.as_view(), name="profile-price"),
    path("subscribe/", api_views.SubscribeToProfileView.as_view(), name="subscribe"),
    path("subscription/<int:user_id>/", api_views.CheckSubscriptionView.as_view(), name="check-subscription"),
    path("my-subscriptions/", api_views.MySubscriptionsView.as_view(), name="my-subscriptions"),
    # Admin
    path("admin/login/", admin_api_views.admin_login, name="admin-login"),
    path("admin/stats/", admin_api_views.admin_stats, name="admin-stats"),
    path("admin/users/", admin_api_views.admin_users, name="admin-users"),
    path("admin/users/clear-all/", admin_api_views.admin_clear_users, name="admin-clear-users"),
    path("admin/users/<int:user_id>/", admin_api_views.admin_delete_user, name="admin-delete-user"),
    path("admin/likes/", admin_api_views.admin_likes, name="admin-likes"),
    path("admin/subscriptions/", admin_api_views.admin_subscriptions, name="admin-subscriptions"),
    path("admin/profile-prices/", admin_api_views.admin_profile_prices, name="admin-profile-prices"),
    path("admin/profile-prices/<int:profile_id>/", admin_api_views.admin_profile_prices, name="admin-profile-prices-detail"),
    # Paystack payments (subscriptions — card + bank transfer)
    path("paystack/create-payment/", paystack_views.CreateSubscriptionPaymentView.as_view(), name="paystack-create-payment"),
    path("paystack/confirm-payment/", paystack_views.ConfirmSubscriptionPaymentView.as_view(), name="paystack-confirm-payment"),
    path("paystack/check-access/<int:creator_id>/", paystack_views.CheckServiceAccessView.as_view(), name="paystack-check-access"),
    # Stripe payments (service payments — kept for services, will migrate later)
    path("stripe/create-service-payment/", stripe_views.CreateServicePaymentView.as_view(), name="stripe-create-service-payment"),
    path("stripe/confirm-service-payment/", stripe_views.ConfirmServicePaymentView.as_view(), name="stripe-confirm-service-payment"),
    # User chat
    path("chat/conversations/", chat_views.UserConversationsView.as_view(), name="user-conversations"),
    path("chat/<int:profile_id>/", chat_views.UserChatView.as_view(), name="user-chat"),
    # Admin chat
    path("admin/chats/", chat_views.admin_chats, name="admin-chats"),
    path("admin/chats/<int:conversation_id>/", chat_views.admin_chat_detail, name="admin-chat-detail"),
    path("admin/chats/<int:conversation_id>/reply/", chat_views.admin_chat_reply, name="admin-chat-reply"),
    # Bookings
    path("bookings/", chat_views.CreateBookingView.as_view(), name="create-booking"),
    path("bookings/mine/", chat_views.MyBookingsView.as_view(), name="my-bookings"),
    path("admin/bookings/", chat_views.admin_bookings, name="admin-bookings"),
    path("admin/bookings/<int:booking_id>/status/", chat_views.admin_booking_status, name="admin-booking-status"),
    # Crypto payments
    path("crypto-payments/", chat_views.CreateCryptoPaymentView.as_view(), name="create-crypto-payment"),
    path("crypto-payments/mine/", chat_views.MyCryptoPaymentsView.as_view(), name="my-crypto-payments"),
    path("crypto-payments/verify/", chat_views.VerifyCryptoPaymentView.as_view(), name="verify-crypto-payment"),
    path("admin/crypto-payments/", chat_views.admin_crypto_payments, name="admin-crypto-payments"),
    path("admin/crypto-payments/<int:payment_id>/status/", chat_views.admin_crypto_payment_status, name="admin-crypto-payment-status"),
]
