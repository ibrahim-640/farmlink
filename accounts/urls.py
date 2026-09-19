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
    path('farmer/orders/', views.farmer_orders, name='farmer_orders'),
    path('dashboard/buyer/', views.dashboard_buyer, name='dashboard_buyer'),
    path('dashboard/transporter/', views.dashboard_transporter, name='dashboard_transporter'),

    # Transport
    path('transport/jobs/', views.transport_jobs, name='transport_jobs'),
    path('transport/myjobs/', views.transport_myjobs, name='transport_myjobs'),
    path('transport/accept-job/<int:order_id>/', views.accept_job, name='accept_job'),
    path('transport/request/<int:order_id>/<int:product_id>/', views.request_transport, name='request_transport'),
    path('rate-transporter/<int:job_id>/',views.rate_transporter,name='rate_transporter'),
    path('transport/mark-delivered/<int:job_id>/', views.mark_delivered, name='mark_delivered'),
    path('vehicle/<int:vehicle_id>/manage/', views.manage_vehicle, name='manage_vehicle'),
    path('vehicle/add/', views.add_vehicle, name='add_vehicle'),
    path('transport/', views.transport_services, name='transport_services'),
    path('book-transport/<int:order_id>/', views.book_transport, name='book_transport'),


    # Products
    path('products/<int:product_id>/buy/', views.buy_product, name='buy_product'),
    path('orders/', views.order_list, name='order_list'),
    path('products/', views.product_list, name='product_list'),
    path('products/my/', views.my_products, name='my_products'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/edit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('products/delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('inventory/', views.inventory, name='inventory'),

    # Cart
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:item_id>/<str:action>/', views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/save-for-later/<int:item_id>/', views.save_for_later, name='save_for_later'),
    path('cart/move-to-cart/<int:item_id>/', views.move_to_cart, name='move_to_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('market-trends/', views.market_trends, name='market_trends'),
    path('payment-status/', views.payment_status, name='payment_status'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('request_transport_for_cart/', views.request_transport_for_cart, name='request_transport_for_cart'),
    path(
    'payment/success/',views.payment_success,name='payment_success'
),
# AI Services
    path('ai/price-suggestions/', views.price_suggestions, name='price_suggestions'),
    path('ai/product-recommendations/', views.product_recommendations, name='product_recommendations'),
    path('ai/demand-forecast/', views.demand_forecast, name='demand_forecast'),

    path('profile/', views.profile_view, name='profile_view'),
    # Order tracking
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('farmer/orders/', views.farmer_orders, name='farmer_orders'),
    path('orders/<int:order_id>/confirm-receipt/',views.buyer_confirm_receipt,name='buyer_confirm_receipt'),
    path('orders/<int:order_id>/refund/',views.request_refund,name='request_refund'),
    # FARMER CONFIRMS ORDER
    path('orders/<int:order_id>/confirm/', views.confirm_order_farmer, name='confirm_order_farmer'),
    #NOTIFICATIONS
    path('notifications/', views.notifications_view, name='notifications'),
]
