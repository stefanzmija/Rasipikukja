import jwt
from django.contrib.auth.models import User
from django.contrib.auth.backends import BaseBackend
from django.conf import settings


class SupabaseBackend(BaseBackend):
    def authenticate(self, request, token=None):
        if token is None:
            return None

        try:
            # Verify the token using Supabase's public key or by using jwt.decode with verify_signature=False for testing
            decoded = jwt.decode(token, options={"verify_signature": False})
        except jwt.InvalidTokenError:
            return None

        email = decoded.get("email")
        if not email:
            return None

        # Get or create a Django user with the email as username
        user, created = User.objects.get_or_create(username=email, defaults={"email": email})
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
