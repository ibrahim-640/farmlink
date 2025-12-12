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

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # optional extra details
    phone = models.CharField(max_length=15, blank=True)
    location = models.CharField(max_length=200, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    def is_farmer(self):
        return self.role == self.ROLE_FARMER

    def is_buyer(self):
        return self.role == self.ROLE_BUYER

    def is_transporter(self):
        return self.role == self.ROLE_TRANSPORTER


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
    description = models.TextField()
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.name


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
        ('In Transit', 'In Transit'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]

    URGENCY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    driver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='transport_jobs')
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    pickup_location = models.CharField(max_length=255)
    delivery_location = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    urgency = models.CharField(max_length=10, choices=URGENCY_CHOICES, default='medium')
    transport_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job #{self.id} - {self.order.product.name}"


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
    PAYMENT_METHODS = [('mpesa','M-Pesa'),('card','Card'),('cod','Cash on Delivery')]
    PAYMENT_STATUS = [('pending','Pending'),('completed','Completed'),('failed','Failed')]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='mpesa')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    checkout_request_id = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=12, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)