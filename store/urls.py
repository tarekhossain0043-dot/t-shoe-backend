from django.urls import path
from . import views
from . import auth_views

urlpatterns=[
 path("health/",views.health),
 path("products/",views.products),
 path("orders/",views.create_order),
 path("auth/register/",auth_views.RegisterView.as_view()),
 path("auth/login/",auth_views.LoginView.as_view()),
 path("auth/refresh/",auth_views.RefreshView.as_view()),
 path("auth/logout/",auth_views.LogoutView.as_view()),
 path("auth/me/",auth_views.CurrentMemberView.as_view()),
]
