from django.contrib.auth import get_user
from rest_framework.authentication import BaseAuthentication


class SessionCookieAuthentication(BaseAuthentication):
    def authenticate(self, request):
        user = get_user(request._request)
        if not user or not user.is_active:
            return None
        return (user, None)
