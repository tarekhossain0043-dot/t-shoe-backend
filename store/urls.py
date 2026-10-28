from django.urls import path
from . import views
from . import auth_views
from . import payment_views

urlpatterns=[
 path("health/",views.health),
 path("products/",views.products),
 path("admin/dashboard/", views.admin_dashboard),
 path("customer-actions/", views.customer_product_actions),
 path("notifications/", views.public_notifications),
 path("admin/notifications/", views.admin_notifications),
 path("admin/notifications/<int:notification_id>/", views.admin_notification_detail),
 path("admin/customer-actions/", views.admin_customer_actions),
 path("admin/products/", views.admin_products),
 path("admin/products/<int:product_id>/", views.admin_product_detail),
 path("admin/orders/", views.admin_orders),
 path("admin/orders/<str:order_number>/", views.admin_order_detail),
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
