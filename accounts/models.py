from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
# ---------------------------
# USER PROFILE
# ---------------------------
class Profile(models.Model):
    ROLE_FARMER = "farmer"
    ROLE_BUYER = "buyer"
    ROLE_TRANSPORTER = "transporter"

    ROLE_CHOICES = [
        (ROLE_FARMER, "Farmer"),
        (ROLE_BUYER, "Buyer"),
        (ROLE_TRANSPORTER, "Transporter"),
    ]
    id_number = models.CharField(max_length=20, blank=True, null=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # optional extra details
    phone = models.CharField(max_length=15, blank=True)
    location = models.CharField(max_length=200, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    # ⭐ Transporter rating fields (NEW)
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        default=0
    )
    rating_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    def is_farmer(self):
        return self.role == self.ROLE_FARMER

    def is_buyer(self):
        return self.role == self.ROLE_BUYER

    def is_transporter(self):
        return self.role == self.ROLE_TRANSPORTER

class TransporterRating(models.Model):
    transporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_ratings"
    )
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="given_ratings"
    )
    job = models.OneToOneField('TransportJob', on_delete=models.CASCADE,related_name='rating')
    rating = models.PositiveSmallIntegerField()  # 1–5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transporter.username} - {self.rating}⭐"

# ---------------------------
# PRODUCT
# ---------------------------
class Product(models.Model):
    CATEGORIES = [
        ('vegetables', 'Vegetables'),
        ('fruits', 'Fruits'),
        ('grains', 'Grains'),
        ('dairy', 'Dairy'),
        ('poultry', 'Poultry'),
        ('other', 'Other'),
    ]

    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20, default='kg')
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)

    description = models.TextField(blank=True)   # optional improvement
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.farmer.username}"


class Vehicle(models.Model):
    transporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="vehicles"
    )
    plate_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(
        max_length=50,
        choices=[
            ('truck', 'Truck'),
            ('van', 'Van'),
            ('pickup', 'Pickup'),
            ('motorbike', 'Motorbike'),
        ]
    )
    is_available = models.BooleanField(default=True)
    capacity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Capacity in kg")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.plate_number} ({self.vehicle_type})"

# ---------------------------
# ORDER
# ---------------------------
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    transporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transporter_orders"
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    order_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.product.name}"


# ---------------------------
# TRANSPORT REQUEST / JOB
# ---------------------------
class TransportRequest(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    transporter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    pickup_location = models.CharField(max_length=200)
    delivery_location = models.CharField(max_length=200)
    transport_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, default='available')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transport for Order #{self.order.id}"

class TransportJob(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Accepted', 'Accepted'),
        ('In Transit', 'In Transit'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]

    URGENCY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    # Transporter / Driver who accepts the job
    driver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transport_jobs'
    )

    # One transport job per order (VERY IMPORTANT)
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='transport_job'
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transport_jobs'
    )

    pickup_location = models.CharField(max_length=255, blank=True, default='')
    delivery_location = models.CharField(max_length=255, blank=True, default='')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    urgency = models.CharField(
        max_length=10,
        choices=URGENCY_CHOICES,
        default='medium'
    )

    transport_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transport Job #{self.id} - Order #{self.order.id}"

# ---------------------------
# CART
# ---------------------------
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def subtotal(self):
        return sum(item.subtotal for item in self.items.all())

    def total(self, tax_rate=Decimal('0.16'), delivery_fee=Decimal('10')):
        subtotal = self.subtotal()  # this should already be Decimal
        tax = subtotal * tax_rate
        return subtotal + tax + delivery_fee

    @property
    def total_amount(self):
        return self.total()

    def __str__(self):
        return f"Cart for {self.user.username}"



class CartItem(models.Model):
    cart = models.ForeignKey('Cart', on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    saved_for_later = models.BooleanField(default=False)

    @property
    def subtotal(self):
        return self.product.price_per_unit * self.quantity

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
class Payment(models.Model):
    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('card', 'Card'),
        ('cod', 'Cash on Delivery')
    ]
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default='mpesa'
    )
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default='pending'
    )
    checkout_request_id = models.CharField(
        max_length=100,  # ← increased from 50
        blank=True,
        null=True
    )
    phone_number = models.CharField(
        max_length=15,   # ← increased from 12 — 254XXXXXXXXX is 12 but safer at 15
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

# ---------------------------
# NOTIFICATION
# ---------------------------
class Notification(models.Model):
    TYPE_CHOICES = [
        ('low_stock', 'Low Stock Alert'),
        ('order', 'Order Update'),
        ('delivery', 'Delivery Update'),
        ('payment', 'Payment Update'),
        ('general', 'General'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='general'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username} — {self.notification_type}"


# ---------------------------
# WALLET
# ---------------------------
class Wallet(models.Model):
    """
    Virtual wallet for each user.
    Tracks pending earnings before B2C payout.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    # Total earnings recorded
    total_earned = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    # Amount already paid out
    total_paid_out = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    # Amount withheld (failed deliveries)
    total_withheld = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def pending_payout(self):
        """Amount earned but not yet paid out"""
        return self.total_earned - self.total_paid_out - self.total_withheld

    def __str__(self):
        return (
            f"Wallet: {self.user.username} "
            f"(Pending: Ksh {self.pending_payout})"
        )


# ---------------------------
# PAYMENT SPLIT
# ---------------------------
class PaymentSplit(models.Model):
    """
    Records how each order payment was divided
    between farmer, transporter and FarmLink.
    """
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment_split'
    )

    # Amounts for each party
    product_subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    transport_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    commission = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    grand_total = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # Distance info
    distance_km = models.DecimalField(
        max_digits=8,
        decimal_places=1,
        null=True,
        blank=True
    )

    # Payout status
    farmer_paid = models.BooleanField(default=False)
    transporter_paid = models.BooleanField(default=False)
    transporter_withheld = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Split for Order #{self.order.id}"


# ---------------------------
# EARNINGS RECORD
# ---------------------------
class EarningsRecord(models.Model):
    """
    Individual earning entry for each user.
    Like a bank statement — one row per transaction.
    """
    TYPE_CHOICES = [
        ('product_sale', 'Product Sale'),
        ('transport_fee', 'Transport Fee'),
        ('commission', 'FarmLink Commission'),
        ('withheld', 'Withheld Payment'),
        ('refund', 'Refund'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Payout'),
        ('paid', 'Paid Out'),
        ('withheld', 'Withheld'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='earnings'
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='earnings_records'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    earning_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.user.username} | "
            f"{self.earning_type} | "
            f"Ksh {self.amount} | "
            f"{self.status}"
        )


# ---------------------------
# REFUND REQUEST
# ---------------------------
class RefundRequest(models.Model):
    """
    Created when buyer requests refund after
    farmer doesn't confirm within 3 days.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('processed', 'Processed'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='refund_request'
    )
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='refund_requests'
    )
    reason = models.TextField(
        default='Farmer did not confirm order within 3 days'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"Refund for Order #{self.order.id} "
            f"by {self.buyer.username} — {self.status}"
        )