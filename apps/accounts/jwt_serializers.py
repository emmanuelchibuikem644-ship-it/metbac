from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .serializers import MeSerializer


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Identical to SimpleJWT's default (which already keys off User.USERNAME_FIELD,
    i.e. 'email' for this project) but also embeds the user's profile in the
    response so the frontend doesn't need a second round trip right after login.
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = MeSerializer(self.user).data
        return data
