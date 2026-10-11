from django.urls import path

from .views import (
    EmailTokenObtainPairView,
    ForgotPasswordView,
    RateLimitedTokenRefreshView,
    RegisterView,
    ResetPasswordView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", EmailTokenObtainPairView.as_view(), name="login"),
    path("refresh/", RateLimitedTokenRefreshView.as_view(), name="token_refresh"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset_password"),
]
