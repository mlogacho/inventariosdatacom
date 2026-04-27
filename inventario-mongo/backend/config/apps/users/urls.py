from django.urls import path
from config.apps.users.views.auth_views import LoginView
from config.apps.users.views.user_views import UserListCreateView, UserDetailView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("", UserListCreateView.as_view(), name="user-list-create"),
    path("<str:pk>/", UserDetailView.as_view(), name="user-detail"),
]
