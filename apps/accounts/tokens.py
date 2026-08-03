from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Same HMAC scheme Django uses for password-reset tokens, but the hash
    also incorporates is_email_verified so a token is invalidated the
    moment it's been used once.
    """

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_email_verified}{user.email}"


email_verification_token = EmailVerificationTokenGenerator()
