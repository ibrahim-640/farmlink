from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),

    # Authentication
    path('login/', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),

    # Registration (all roles)
    path('register/', views.register, name='register'),
    path('register/farmer/', views.register_farmer, name='register_farmer'),
    path('register/buyer/', views.register_buyer, name='register_buyer'),
    path('register/transporter/', views.register_transporter, name='register_transporter'),

    # Dashboards
    path('dashboard/farmer/', views.dashboard_farmer, name='dashboard_farmer'),
    path('dashboard/buyer/', views.dashboard_buyer, name='dashboard_buyer'),
    path('dashboard/transporter/', views.dashboard_transporter, name='dashboard_transporter'),

    # Transport
    path('transport/jobs/', views.transport_jobs, name='transport_jobs'),
    path('transport/myjobs/', views.transport_myjobs, name='transport_myjobs'),
    path('transport/accept-job/<int:job_id>/', views.accept_job, name='accept_job'),
    path('transport/request/<int:product_id>/<int:order_id>/',views.request_transport,name='request_transport'),
    path('rate-transporter/<int:job_id>/',views.rate_transporter,name='rate_transporter'),
    path('transport/mark-delivered/<int:job_id>/', views.mark_delivered, name='mark_delivered'),


    # Products
    path('products/<int:product_id>/buy/', views.buy_product, name='buy_product'),
    path('orders/', views.order_list, name='order_list'),
    path("confirm-order/", views.confirm_order, name="confirm_order"),
    path('products/', views.product_list, name='product_list'),
    path('products/my/', views.my_products, name='my_products'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/edit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('products/delete/<int:product_id>/', views.delete_product, name='delete_product'),

    # Cart
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:item_id>/<str:action>/', views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/save-for-later/<int:item_id>/', views.save_for_later, name='save_for_later'),
    path('cart/move-to-cart/<int:item_id>/', views.move_to_cart, name='move_to_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('payment-status/', views.payment_status, name='payment_status'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('request_transport_for_cart/', views.request_transport_for_cart, name='request_transport_for_cart'),
]
