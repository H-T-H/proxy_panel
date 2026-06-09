from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClientDownloadViewSet,
    NodeViewSet,
    SettingViewSet,
    SourceViewSet,
    SubscriptionUserViewSet,
    dashboard_view,
    health,
    login_view,
    logout_view,
    me_view,
    subscribe,
    subscription_user_login_view,
    subscription_user_logout_view,
    subscription_user_me_view,
    subscription_user_subscription_view,
)


router = DefaultRouter()
router.register("sources", SourceViewSet, basename="source")
router.register("client-downloads", ClientDownloadViewSet, basename="client-download")
router.register("nodes", NodeViewSet, basename="node")
router.register("users", SubscriptionUserViewSet, basename="subscription-user")
router.register("settings", SettingViewSet, basename="setting")


urlpatterns = [
    path("api/health/", health),
    path("api/auth/login/", login_view),
    path("api/auth/logout/", logout_view),
    path("api/auth/me/", me_view),
    path("api/user-auth/login/", subscription_user_login_view),
    path("api/user-auth/logout/", subscription_user_logout_view),
    path("api/user-auth/me/", subscription_user_me_view),
    path("api/user/subscription/", subscription_user_subscription_view),
    path("api/dashboard/", dashboard_view),
    path("api/", include(router.urls)),
    path("sub/<str:token>", subscribe),
]
