from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle


class AuthenticationThrottle(ScopedRateThrottle):
    def allow_request(self, request, view):
        if not settings.AUTHENTICATION_THROTTLE_ENABLED:
            return True
        return super().allow_request(request, view)
