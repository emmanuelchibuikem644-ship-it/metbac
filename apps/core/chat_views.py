"""
Chat system — subscribers message profiles; the admin replies as the profile.

Flow:
1. A subscribed user opens a chat with a profile → GET/POST /api/core/chat/<profile_id>/
2. The user's messages are stored with is_from_subscriber=True
3. The admin sees all conversations in the admin panel, split by gay/straight
4. The admin replies as the profile → is_from_subscriber=False
5. The subscriber sees the reply as if the profile sent it
"""

import json
import re
from datetime import timedelta
from urllib.request import Request, urlopen

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny

from .models import Booking, ChatConversation, ChatMessage, CryptoPayment, ProfileSubscription

ADMIN_TOKEN = "Bearer admin-session-token"


def _conversation_data(conv):
    """Serialize a conversation for the admin panel."""
    messages = conv.messages.all().order_by("created_at")
    last_msg = messages.last()
    last_message = last_msg.content.strip() if last_msg and last_msg.content.strip() else ("Image" if last_msg and last_msg.image else "")
    return {
        "id": conv.id,
        "profile_id": conv.profile_id,
        "profile_name": conv.profile_name,
        "profile_avatar": conv.profile_avatar,
        "profile_orientation": conv.profile_orientation,
        "subscriber": {
            "id": conv.subscriber.id,
            "email": conv.subscriber.email,
            "display_name": conv.subscriber.display_name,
        },
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "last_message": last_message,
        "last_message_at": last_msg.created_at.isoformat() if last_msg else None,
        "message_count": messages.count(),
        "unread_count": messages.filter(is_from_subscriber=False, is_read=False).count(),
    }


def _message_data(msg, request=None):
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "content": msg.content,
        "image": _absolute_image_url(msg, request),
        "is_from_subscriber": msg.is_from_subscriber,
        "is_read": msg.is_read,
        "created_at": msg.created_at.isoformat(),
    }


def _absolute_image_url(msg, request=None):
    """Return a full URL for the attached image so the Next.js frontend
    (running on a different origin) can load it from the Django media server."""
    if not msg.image:
        return ""
    url = msg.image.url
    try:
        if request is not None:
            return request.build_absolute_uri(url)
        from django.conf import settings

        return f"{settings.SITE_URL}{url}"
    except Exception:
        return url


# ── User-facing chat endpoints ──────────────────────────────


class UserConversationsView(APIView):
    """GET /api/core/chat/conversations/ — list the current user's chats."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = ChatConversation.objects.filter(
            subscriber=request.user
        ).order_by("-updated_at")
        data = []
        for c in conversations:
            last_msg = c.messages.order_by("created_at").last()
            last_message = last_msg.content.strip() if last_msg and last_msg.content.strip() else ("Image" if last_msg and last_msg.image else "")
            item = {
                "id": c.id,
                "profile_id": c.profile_id,
                "profile_name": c.profile_name,
                "profile_avatar": c.profile_avatar,
                "profile_orientation": c.profile_orientation,
                "updated_at": c.updated_at.isoformat(),
                "last_message": last_message,
                "unread_count": c.messages.filter(is_from_subscriber=False, is_read=False).count(),
            }
            data.append(item)
        return Response(data)


class UserChatView(APIView):
    """
    GET  /api/core/chat/<profile_id>/  → messages + conversation info
    POST /api/core/chat/<profile_id>/  → send a message from the subscriber
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, profile_id):
        conversation = ChatConversation.objects.filter(
            subscriber=request.user,
            profile_id=profile_id,
        ).first()

        if not conversation:
            return Response({
                "conversation": None,
                "messages": [],
            })

        # Mark profile replies as read for the subscriber
        conversation.messages.filter(
            is_from_subscriber=False, is_read=False
        ).update(is_read=True)

        messages = conversation.messages.order_by("created_at")
        return Response({
            "conversation": _conversation_data(conversation),
            "messages": [_message_data(m, request) for m in messages],
        })

    def post(self, request, profile_id):
        content = (request.data.get("content") or "").strip()
        image_file = request.FILES.get("image")

        if not content and not image_file:
            return Response({"detail": "Message content or image is required."}, status=400)

        # Allow any authenticated user to open or continue a conversation.
        conversation = ChatConversation.objects.filter(
            subscriber=request.user, profile_id=profile_id
        ).first()

        if not conversation:
            # Require profile details from the static profiles list — the API
            # client sends them on the first message.
            profile_name = request.data.get("profile_name") or "Profile"
            profile_avatar = request.data.get("profile_avatar") or ""
            profile_orientation = request.data.get("profile_orientation") or "straight"
            conversation = ChatConversation.objects.create(
                subscriber=request.user,
                profile_id=profile_id,
                profile_name=profile_name,
                profile_avatar=profile_avatar,
                profile_orientation=profile_orientation,
            )

        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content,
            image=image_file or "",
            is_from_subscriber=True,
        )

        return Response(
            _message_data(message, request),
            status=status.HTTP_201_CREATED,
        )


# ── Booking endpoints ─────────────────────────────────────────


class CreateBookingView(APIView):
    """POST /api/core/bookings/ — submit a booking request (authenticated user)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        service_name = (data.get("service_name") or "").strip()
        full_name = (data.get("full_name") or "").strip()
        email = (data.get("email") or "").strip()

        if not service_name or not full_name or not email:
            return Response({"detail": "service_name, full_name and email are required."}, status=400)

        booking = Booking.objects.create(
            subscriber=request.user,
            service_name=service_name,
            service_price=(data.get("service_price") or "").strip(),
            full_name=full_name,
            email=email,
            phone=(data.get("phone") or "").strip(),
            date=data.get("date") or None,
            time=(data.get("time") or "").strip(),
            notes=(data.get("notes") or "").strip(),
        )

        return Response({
            "id": booking.id,
            "service_name": booking.service_name,
            "full_name": booking.full_name,
            "email": booking.email,
            "date": booking.date.isoformat() if booking.date else None,
            "status": booking.status,
            "created_at": booking.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class MyBookingsView(APIView):
    """GET /api/core/bookings/ — list the current user's bookings."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookings = Booking.objects.filter(subscriber=request.user)
        return Response([_booking_data(b) for b in bookings])


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_bookings(request):
    """GET /api/core/admin/bookings/ — list all bookings (admin)."""
    if request.headers.get("Authorization") != ADMIN_TOKEN:
        return Response({"detail": "Unauthorized."}, status=401)

    bookings = Booking.objects.all().order_by("-created_at")
    return Response([_booking_data(b) for b in bookings])


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_booking_status(request, booking_id):
    """
    POST /api/core/admin/bookings/<id>/status/
    Body: { status: approved | declined }
    """
    if request.headers.get("Authorization") != ADMIN_TOKEN:
        return Response({"detail": "Unauthorized."}, status=401)

    new_status = (request.data.get("status") or "").strip().lower()
    if new_status not in ("approved", "declined"):
        return Response({"detail": "status must be 'approved' or 'declined'."}, status=400)

    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = new_status
    booking.save()
    return Response(_booking_data(booking))


def _booking_data(b):
    return {
        "id": b.id,
        "service_name": b.service_name,
        "service_price": b.service_price,
        "full_name": b.full_name,
        "email": b.email,
        "phone": b.phone,
        "date": b.date.isoformat() if b.date else None,
        "time": b.time,
        "notes": b.notes,
        "status": b.status,
        "subscriber": {
            "id": b.subscriber.id,
            "email": b.subscriber.email,
            "display_name": b.subscriber.display_name,
        },
        "created_at": b.created_at.isoformat(),
    }


# ── Crypto payment endpoints ─────────────────────────────────


class CreateCryptoPaymentView(APIView):
    """POST /api/core/crypto-payments/ — create a crypto payment request."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        coin = (request.data.get("coin") or "").strip().lower()
        amount_cents = request.data.get("amount_cents")
        purpose = (request.data.get("purpose") or "").strip()
        wallet_address = (request.data.get("wallet_address") or "").strip()

        if coin not in ("bitcoin", "ethereum", "tether", "usdt"):
            return Response({"detail": "coin must be bitcoin, ethereum, tether or usdt."}, status=400)

        try:
            amount_cents = int(amount_cents or 0)
        except (TypeError, ValueError):
            return Response({"detail": "amount_cents must be an integer."}, status=400)

        if amount_cents <= 0:
            return Response({"detail": "amount_cents must be greater than zero."}, status=400)

        payment = CryptoPayment.objects.create(
            subscriber=request.user,
            coin=coin,
            amount_cents=amount_cents,
            wallet_address=wallet_address,
            purpose=purpose,
        )

        return Response(_crypto_payment_data(payment), status=status.HTTP_201_CREATED)


class MyCryptoPaymentsView(APIView):
    """GET /api/core/crypto-payments/mine/ — list the current user's crypto payments."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = CryptoPayment.objects.filter(subscriber=request.user)
        return Response([_crypto_payment_data(p) for p in payments])


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_crypto_payments(request):
    """GET /api/core/admin/crypto-payments/ — list all crypto payments (admin)."""
    if request.headers.get("Authorization") != ADMIN_TOKEN:
        return Response({"detail": "Unauthorized."}, status=401)

    payments = CryptoPayment.objects.all().order_by("-created_at")
    return Response([_crypto_payment_data(p) for p in payments])


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_crypto_payment_status(request, payment_id):
    """
    POST /api/core/admin/crypto-payments/<id>/status/
    Body: { status: confirmed | declined }
    """
    if request.headers.get("Authorization") != ADMIN_TOKEN:
        return Response({"detail": "Unauthorized."}, status=401)

    new_status = (request.data.get("status") or "").strip().lower()
    if new_status not in ("confirmed", "declined"):
        return Response({"detail": "status must be 'confirmed' or 'declined'."}, status=400)

    payment = get_object_or_404(CryptoPayment, id=payment_id)
    payment.status = new_status
    payment.save()
    return Response(_crypto_payment_data(payment))


def _crypto_payment_data(p):
    return {
        "id": p.id,
        "coin": p.coin,
        "amount_cents": p.amount_cents,
        "amount_display": f"${p.amount_cents / 100:.2f}",
        "wallet_address": p.wallet_address,
        "tx_hash": p.tx_hash,
        "purpose": p.purpose,
        "status": p.status,
        "subscriber": {
            "id": p.subscriber.id,
            "email": p.subscriber.email,
            "display_name": p.subscriber.display_name,
        },
        "created_at": p.created_at.isoformat(),
    }


# ── Crypto payment verification ─────────────────────────────


def _blockstream_tx(tx_hash):
    """Verify a Bitcoin transaction via Blockstream's public API."""
    url = f"https://blockstream.info/api/tx/{tx_hash}"
    req = Request(url, headers={"User-Agent": "Metlink/1.0"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _etherscan_tx(tx_hash):
    """Verify an Ethereum transaction via Etherscan's public API."""
    url = f"https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}"
    req = Request(url, headers={"User-Agent": "Metlink/1.0"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _trongrid_tx(tx_hash):
    """Verify a USDT (TRC20) transaction via TronGrid's public API."""
    url = f"https://api.trongrid.io/v1/transactions/{tx_hash}"
    req = Request(url, headers={"User-Agent": "Metlink/1.0"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


class VerifyCryptoPaymentView(APIView):
    """
    POST /api/core/crypto-payments/verify/
    Body: { payment_id, tx_hash }
    Verifies the transaction on the blockchain and updates the payment status.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get("payment_id")
        tx_hash = (request.data.get("tx_hash") or "").strip()

        if not payment_id or not tx_hash:
            return Response({"detail": "payment_id and tx_hash are required."}, status=400)

        if not re.fullmatch(r"[A-Fa-f0-9]{64}", tx_hash):
            return Response({"detail": "Invalid transaction hash format."}, status=400)

        payment = get_object_or_404(CryptoPayment, id=payment_id, subscriber=request.user)
        if payment.status == "confirmed":
            return Response({"detail": "This payment is already confirmed."}, status=400)

        payment.tx_hash = tx_hash
        payment.save()

        try:
            verified = False

            if payment.coin == "bitcoin":
                tx = _blockstream_tx(tx_hash)
                # Check the output includes our wallet address
                for out in tx.get("vout", []):
                    addr = out.get("scriptpubkey_address", "")
                    if addr == payment.wallet_address:
                        verified = True
                        break

            elif payment.coin == "ethereum":
                data = _etherscan_tx(tx_hash)
                result = data.get("result") or {}
                to = (result.get("to") or "").lower()
                if to and payment.wallet_address and to == payment.wallet_address.lower():
                    verified = True

            elif payment.coin in ("tether", "usdt"):
                data = _trongrid_tx(tx_hash)
                raw = data.get("data") or []
                if raw:
                    raw_tx = raw[0]
                    raw_contract = raw_tx.get("raw_data", {}).get("contract", [])
                    for contract in raw_contract:
                        value = contract.get("parameter", {}).get("value", {})
                        to_addr = value.get("to_address", "")
                        # Tron addresses are base58; wallet_address stored is already T...
                        if to_addr and payment.wallet_address and to_addr == payment.wallet_address:
                            verified = True
                            break

            if verified:
                payment.status = "confirmed"
                payment.save()

                return Response({
                    "success": True,
                    "detail": "Payment verified on the blockchain! Subscription will be activated shortly.",
                    "status": payment.status,
                })

            return Response({
                "success": False,
                "detail": "Transaction found but could not confirm it was sent to our wallet address. Please double-check and try again.",
                "status": payment.status,
            }, status=400)

        except Exception as e:
            return Response({
                "success": False,
                "detail": f"Could not verify transaction. It may not be confirmed on the blockchain yet. Error: {str(e)}",
                "status": payment.status,
            }, status=400)


# ── Admin-facing chat endpoints ─────────────────────────────


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_chats(request):
    """
    GET /api/core/admin/chats/?orientation=gay|straight|all
    List all conversations for the admin panel with full message history.
    """
    if request.headers.get("Authorization") != ADMIN_TOKEN:
        return Response({"detail": "Unauthorized."}, status=401)

    orientation = request.query_params.get("orientation", "all")
    conversations = ChatConversation.objects.all()
    if orientation in ("gay", "straight"):
        conversations = conversations.filter(profile_orientation=orientation)

    conversations = conversations.order_by("-updated_at")
    return Response([_conversation_data(c) for c in conversations])


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_chat_detail(request, conversation_id):
    """GET /api/core/admin/chats/<id>/ — full messages for one conversation."""
    if request.headers.get("Authorization") != ADMIN_TOKEN:
        return Response({"detail": "Unauthorized."}, status=401)

    conversation = get_object_or_404(ChatConversation, id=conversation_id)
    messages = conversation.messages.order_by("created_at")
    return Response({
        "conversation": _conversation_data(conversation),
        "messages": [_message_data(m, request) for m in messages],
    })


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_chat_reply(request, conversation_id):
    """
    POST /api/core/admin/chats/<id>/reply/
    Body: { content }
    The admin replies as the profile (is_from_subscriber=False).
    """
    if request.headers.get("Authorization") != ADMIN_TOKEN:
        return Response({"detail": "Unauthorized."}, status=401)

    content = (request.data.get("content") or "").strip()
    image_file = request.FILES.get("image")

    if not content and not image_file:
        return Response({"detail": "Message content or image is required."}, status=400)

    conversation = get_object_or_404(ChatConversation, id=conversation_id)
    message = ChatMessage.objects.create(
        conversation=conversation,
        sender=conversation.subscriber,
        content=content,
        image=image_file or "",
        is_from_subscriber=False,
        is_read=False,
    )
    return Response(_message_data(message, request), status=status.HTTP_201_CREATED)
