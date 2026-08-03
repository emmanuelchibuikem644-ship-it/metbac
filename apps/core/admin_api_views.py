from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.serializers import MeSerializer
from .models import ProfileLike, ProfileSubscription

User = get_user_model()

# ── Hardcoded admin credentials ──────────────────────────────
ADMIN_EMAIL = "admin@metlink.com"
ADMIN_PASSWORD = "MetlinkAdmin@2026"
ADMIN_DISPLAY = "Oga Admin"


@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login(request):
    """POST /api/core/admin/login/ — verify admin credentials."""
    email = request.data.get("email", "")
    password = request.data.get("password", "")

    if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
        return Response({
            "token": "admin-session-token",
            "user": {
                "id": 0,
                "email": ADMIN_EMAIL,
                "display_name": ADMIN_DISPLAY,
                "is_admin": True,
            }
        })
    return Response({"detail": "Invalid admin credentials."}, status=401)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_stats(request):
    """GET /api/core/admin/stats/ — platform-wide statistics."""
    token = request.headers.get("Authorization", "")
    if token != "Bearer admin-session-token":
        return Response({"detail": "Unauthorized."}, status=401)

    users = User.objects.all()
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = users.count()
    active_today = users.filter(last_login__gte=today_start).count()
    straight_count = users.filter(orientation="straight").count()
    gay_count = users.filter(orientation="gay").count()

    # Gender breakdown
    gender_counts = {}
    for row in users.values("gender").annotate(count=Count("gender")):
        gender_counts[row["gender"] or "unspecified"] = row["count"]

    # Likes & subscriptions stats
    total_likes = ProfileLike.objects.count()
    total_subscriptions = ProfileSubscription.objects.filter(is_active=True).count()

    return Response({
        "total_users": total_users,
        "active_today": active_today,
        "straight_count": straight_count,
        "gay_count": gay_count,
        "gender_counts": gender_counts,
        "total_likes": total_likes,
        "total_subscriptions": total_subscriptions,
    })


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_users(request):
    """GET /api/core/admin/users/ — list all registered users."""
    token = request.headers.get("Authorization", "")
    if token != "Bearer admin-session-token":
        return Response({"detail": "Unauthorized."}, status=401)

    users = User.objects.all().order_by("-date_joined")
    data = []
    for u in users:
        data.append({
            "id": u.id,
            "display_name": u.display_name,
            "email": u.email,
            "gender": u.gender,
            "orientation": u.orientation,
            "is_email_verified": u.is_email_verified,
            "is_active": u.is_active,
            "date_joined": u.date_joined.isoformat() if u.date_joined else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
        })
    return Response(data)


@api_view(["DELETE"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_delete_user(request, user_id):
    """DELETE /api/core/admin/users/<id>/ — delete a specific user."""
    token = request.headers.get("Authorization", "")
    if token != "Bearer admin-session-token":
        return Response({"detail": "Unauthorized."}, status=401)

    try:
        user = User.objects.get(id=user_id)
        user.delete()
        return Response({"detail": "User deleted."})
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=404)


@api_view(["DELETE"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_clear_users(request):
    """DELETE /api/core/admin/users/clear-all/ — delete ALL non-superuser users."""
    token = request.headers.get("Authorization", "")
    if token != "Bearer admin-session-token":
        return Response({"detail": "Unauthorized."}, status=401)

    count, _ = User.objects.filter(is_superuser=False).delete()
    return Response({"detail": f"Deleted {count} users."})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_likes(request):
    """GET /api/core/admin/likes/ — list all profile likes."""
    token = request.headers.get("Authorization", "")
    if token != "Bearer admin-session-token":
        return Response({"detail": "Unauthorized."}, status=401)

    likes = ProfileLike.objects.all().order_by("-created_at")[:100]
    data = []
    for l in likes:
        data.append({
            "id": l.id,
            "from_user": {"id": l.from_user.id, "email": l.from_user.email, "display_name": l.from_user.display_name},
            "to_user": {"id": l.to_user.id, "email": l.to_user.email, "display_name": l.to_user.display_name},
            "created_at": l.created_at.isoformat(),
        })
    return Response(data)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_subscriptions(request):
    """GET /api/core/admin/subscriptions/ — list all active profile subscriptions."""
    token = request.headers.get("Authorization", "")
    if token != "Bearer admin-session-token":
        return Response({"detail": "Unauthorized."}, status=401)

    subs = ProfileSubscription.objects.filter(is_active=True).order_by("-started_at")[:100]
    data = []
    for s in subs:
        data.append({
            "id": s.id,
            "subscriber": {"id": s.subscriber.id, "email": s.subscriber.email, "display_name": s.subscriber.display_name},
            "creator": {"id": s.creator.id, "email": s.creator.email, "display_name": s.creator.display_name},
            "started_at": s.started_at.isoformat() if s.started_at else None,
        })
    return Response(data)