from django.urls import path
from . import views
from . import auth_views
from . import payment_views

urlpatterns=[
 path("health/",views.health),
 path("products/",views.products),
 path("orders/",views.create_order),
 path("orders/history/",views.order_history),
 path("payments/<str:provider>/start/",payment_views.start_payment),
 path("payments/bkash/complete/",payment_views.complete_bkash_payment),
 path("payments/bkash/callback/",payment_views.bkash_callback,name="bkash-callback"),
 path("payments/nagad/callback/",payment_views.nagad_callback,name="nagad-callback"),
 path("auth/register/",auth_views.RegisterView.as_view()),
 path("auth/login/",auth_views.LoginView.as_view()),
 path("auth/refresh/",auth_views.RefreshView.as_view()),
 path("auth/logout/",auth_views.LogoutView.as_view()),
 path("auth/me/",auth_views.CurrentMemberView.as_view()),
]
