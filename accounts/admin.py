from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import (
    Profile, Product, Order, TransportJob,
    TransportRequest, Payment, Notification,
    Wallet, PaymentSplit, EarningsRecord,
    RefundRequest, TransporterRating, Vehicle,
    Cart, CartItem
)

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'plate_number',
        'transporter',
        'vehicle_type',
        'capacity',
        'is_active',
        'created_at',
    )

    list_filter = ('vehicle_type', 'is_active')
    search_fields = ('plate_number', 'transporter__username')
    ordering = ('-created_at',)




# ---------------------------
# PROFILE ADMIN
# ---------------------------
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'role', 'phone',
        'id_number', 'location', 'rating'
    ]
    list_filter = ['role']
    search_fields = ['user__username', 'phone', 'id_number']


# ---------------------------
# PRODUCT ADMIN
# ---------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'farmer', 'category',
        'quantity', 'unit', 'price_per_unit',
        'is_available', 'created_at'
    ]
    list_filter = ['category', 'is_available']
    search_fields = ['name', 'farmer__username']


# ---------------------------
# ORDER ADMIN
# ---------------------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'product', 'buyer',
        'quantity', 'total_price',
        'status', 'order_date',
        'farmer_confirmed', 'days_since_order'
    ]
    list_filter = ['status']
    search_fields = [
        'buyer__username',
        'product__name',
        'product__farmer__username'
    ]
    readonly_fields = ['order_date']

    def farmer_confirmed(self, obj):
        """Shows if farmer has confirmed the order"""
        if obj.status == 'pending':
            return format_html(
                '<span style="color:orange;">⏳ Pending</span>'
            )
        return format_html(
            '<span style="color:green;">✅ Confirmed</span>'
        )
    farmer_confirmed.short_description = 'Farmer Confirmation'

    def days_since_order(self, obj):
        """Shows how many days since order was placed"""
        from django.utils import timezone
        delta = timezone.now() - obj.order_date
        days = delta.days
        if obj.status == 'pending' and days >= 3:
            return format_html(
                '<span style="color:red;">'
                '{} days ⚠️ Refund eligible'
                '</span>',
                days
            )
        return f'{days} days'
    days_since_order.short_description = 'Days Since Order'


# ---------------------------
# TRANSPORT JOB ADMIN
# ---------------------------
@admin.register(TransportJob)
class TransportJobAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'order', 'driver',
        'status', 'urgency',
        'pickup_location', 'delivery_location',
        'transport_fee'
    ]
    list_filter = ['status', 'urgency']
    search_fields = [
        'driver__username',
        'order__product__name',
        'pickup_location',
        'delivery_location'
    ]


# ---------------------------
# PAYMENT ADMIN
# ---------------------------
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'order', 'amount',
        'method', 'status',
        'phone_number', 'created_at'
    ]
    list_filter = ['status', 'method']
    search_fields = [
        'order__buyer__username',
        'phone_number',
        'checkout_request_id'
    ]
    readonly_fields = ['created_at']


# ---------------------------
# WALLET ADMIN
# ---------------------------
@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'user_role',
        'total_earned', 'total_paid_out',
        'total_withheld', 'pending_payout',
        'updated_at'
    ]
    search_fields = ['user__username']
    readonly_fields = ['updated_at']

    def user_role(self, obj):
        return obj.user.profile.role
    user_role.short_description = 'Role'

    def pending_payout(self, obj):
        amount = obj.pending_payout
        if amount > 0:
            return format_html(
                '<span style="color:green;font-weight:bold;">'
                'Ksh {}'
                '</span>',
                amount
            )
        return f'Ksh {amount}'
    pending_payout.short_description = 'Pending Payout'


# ---------------------------
# PAYMENT SPLIT ADMIN
# ---------------------------
@admin.register(PaymentSplit)
class PaymentSplitAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'product_subtotal',
        'transport_fee', 'commission',
        'grand_total', 'distance_km',
        'farmer_paid', 'transporter_paid',
        'transporter_withheld'
    ]
    list_filter = [
        'farmer_paid',
        'transporter_paid',
        'transporter_withheld'
    ]
    readonly_fields = ['created_at']


# ---------------------------
# EARNINGS RECORD ADMIN
# ---------------------------
@admin.register(EarningsRecord)
class EarningsRecordAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'user_role', 'order',
        'earning_type', 'amount',
        'status', 'created_at'
    ]
    list_filter = ['earning_type', 'status']
    search_fields = ['user__username']
    readonly_fields = ['created_at']

    def user_role(self, obj):
        return obj.user.profile.role
    user_role.short_description = 'Role'


# ---------------------------
# REFUND REQUEST ADMIN
# ---------------------------
@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'buyer', 'amount',
        'status', 'reason', 'created_at'
    ]
    list_filter = ['status']
    search_fields = ['buyer__username', 'order__id']
    readonly_fields = ['created_at']

    actions = ['approve_refunds']

    def approve_refunds(self, request, queryset):
        """
        Admin action to approve selected refund requests.
        Marks them as approved so admin can process manually.
        """
        updated = queryset.filter(
            status='pending'
        ).update(status='approved')
        self.message_user(
            request,
            f'{updated} refund(s) approved. '
            f'Process M-Pesa payments manually.'
        )
    approve_refunds.short_description = 'Approve selected refunds'


# ---------------------------
# NOTIFICATION ADMIN
# ---------------------------
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'notification_type',
        'is_read', 'created_at',
        'short_message'
    ]
    list_filter = ['notification_type', 'is_read']
    search_fields = ['user__username', 'message']

    def short_message(self, obj):
        return obj.message[:60] + '...' if len(
            obj.message) > 60 else obj.message
    short_message.short_description = 'Message'


# ---------------------------
# FARMLINK SUMMARY ADMIN
# ---------------------------
class FarmLinkSummaryAdmin(admin.ModelAdmin):
    """
    Custom admin view showing FarmLink overview.
    Registered as a proxy model on Order.
    """
    pass


# ---------------------------
# Register remaining models
# ---------------------------
# CHANGE: removed `admin.site.register(Product)` and
# `admin.site.register(Order)` from this block.
# WHY: both models are already registered above via the
# `@admin.register(Product)` / `@admin.register(Order)` decorators, which
# register them the moment their ProductAdmin/OrderAdmin classes are
# defined. Registering them again here -- even with no admin class
# argument -- is a second call to admin.site.register() for the same
# model, which Django's AdminSite rejects with AlreadyRegistered. This is
# what was crashing the whole server on startup (autodiscover() imports
# this file, hits the duplicate call, and raises before Django finishes
# booting).
#
# TransporterRating and TransportRequest have no decorator-based admin
# class anywhere in this file, so registering them here is NOT a
# duplicate -- they're kept as-is, just with default (unstyled) list views.
admin.site.register(TransporterRating)
admin.site.register(TransportRequest)

# ---------------------------
# CUSTOMIZE ADMIN SITE HEADER
# ---------------------------
admin.site.site_header = 'FarmLink Administration'
admin.site.site_title = 'FarmLink Admin'
admin.site.index_title = 'FarmLink Management Dashboard'