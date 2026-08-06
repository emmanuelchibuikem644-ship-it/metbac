from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ProfileLike, ProfilePrice, ProfileSubscription
from .serializers import ProfileLikeSerializer, ProfileSubscriptionSerializer


class ProfilePriceView(APIView):
    """
    GET /api/core/profile-price/<profile_id>/
    Returns the per-profile subscription pricing (set in the admin panel).
    Falls back to sensible defaults if no admin price is configured.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, profile_id):
        p = ProfilePrice.objects.filter(profile_id=profile_id).first()
        if p:
            return Response({
                "profile_id": p.profile_id,
                "profile_name": p.profile_name,
                "initial_price_cents": p.initial_price_cents,
                "recurring_monthly_price_cents": p.recurring_monthly_price_cents,
                "recurring_14day_price_cents": p.recurring_14day_price_cents,
            })
        # No admin price set — fall back to defaults
        return Response({
            "profile_id": profile_id,
            "profile_name": "",
            "initial_price_cents": 20000,
            "recurring_monthly_price_cents": 3500,
            "recurring_14day_price_cents": 1400,
        })


class LikeProfileView(APIView):
    """POST /api/core/like/ — like or unlike a profile. Body: { to_user_id }"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        to_user_id = request.data.get("to_user_id")
        if not to_user_id:
            return Response({"detail": "to_user_id is required."}, status=400)

        if int(to_user_id) == request.user.id:
            return Response({"detail": "You cannot like yourself."}, status=400)

        like, created = ProfileLike.objects.get_or_create(
            from_user=request.user,
            to_user_id=to_user_id,
        )

        if not created:
            # Already liked — unlike
            like.delete()
            return Response({"liked": False, "detail": "Like removed."})

        return Response({"liked": True, "detail": "Profile liked."}, status=201)


class CheckLikeView(APIView):
    """GET /api/core/like/{user_id}/ — check if current user liked this profile"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        liked = ProfileLike.objects.filter(
            from_user=request.user, to_user_id=user_id
        ).exists()
        return Response({"liked": liked})


class SubscribeToProfileView(APIView):
    """POST /api/core/subscribe/ — subscribe to a profile. Body: { creator_id }"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        creator_id = request.data.get("creator_id")
        if not creator_id:
            return Response({"detail": "creator_id is required."}, status=400)

        if int(creator_id) == request.user.id:
            return Response({"detail": "You cannot subscribe to yourself."}, status=400)

        # First-time fee: $13.00, recurring: $15.00/month
        sub, created = ProfileSubscription.objects.get_or_create(
            subscriber=request.user,
            creator_id=creator_id,
            defaults={
                "is_active": True,
                "started_at": timezone.now(),
            },
        )

        if not created:
            if sub.is_active:
                return Response(
                    {"detail": "You are already subscribed to this profile."},
                    status=400,
                )
            # Reactivate
            sub.is_active = True
            sub.save()

        return Response(
            {
                "detail": "Subscription activated. You now have full access.",
                "first_payment": 13.00,
                "recurring_payment": 15.00,
                "interval": "monthly",
            },
            status=201,
        )


class CheckSubscriptionView(APIView):
    """GET /api/core/subscription/{user_id}/ — check if current user is subscribed"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        sub = ProfileSubscription.objects.filter(
            subscriber=request.user,
            creator_id=user_id,
            is_active=True,
        ).first()
        return Response({"subscribed": sub is not None})


class MySubscriptionsView(APIView):
    """GET /api/core/my-subscriptions/ — list all profiles the current user subscribes to"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subs = ProfileSubscription.objects.filter(
            subscriber=request.user,
            is_active=True,
        )
        serializer = ProfileSubscriptionSerializer(subs, many=True)
        return Response(serializer.data)


class MyLikesReceivedView(APIView):
    """GET /api/core/likes-received/ — admin/users can see who liked their profile"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        likes = ProfileLike.objects.filter(to_user=request.user)
        serializer = ProfileLikeSerializer(likes, many=True)
        return Response(serializer.data)