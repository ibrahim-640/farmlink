import json
from collections import defaultdict
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import TransporterRatingForm
from django.db.models import Sum,Avg
from .mpesa import lipa_na_mpesa
from decimal import Decimal
from .models import Product, Profile, Order, TransportRequest, TransportJob,TransporterRating, Cart, CartItem
from .forms import (
    LoginForm,
    FarmerRegistrationForm,
    BuyerRegistrationForm,
    TransporterRegistrationForm,
    ProductForm,
)


# ---------------------------
# HOME PAGE
# ---------------------------
def home(request):
    return render(request, "home.html")
# views.py
def payment_status(request):
    checkout_request_id = request.session.get('checkout_request_id')
    return render(request, 'payment_status.html', {'checkout_request_id': checkout_request_id})



# ---------------------------
# LOGIN / LOGOUT
# ---------------------------
def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                if user.profile.is_farmer():
                    return redirect("dashboard_farmer")
                elif user.profile.is_buyer():
                    return redirect("dashboard_buyer")
                elif user.profile.is_transporter():
                    return redirect("dashboard_transporter")
                return redirect("home")
            messages.error(request, "Invalid username or password.")
            return redirect("login_view")
    else:
        form = LoginForm()
    return render(request, "login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("home")


# ---------------------------
# REGISTER / SIGNUP
# ---------------------------
def register(request):
    return render(request, "register.html")


def register_farmer(request):
    if request.method == "POST":
        form = FarmerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user, role="farmer")
            messages.success(request, "Farmer account created successfully.")
            return redirect("login_view")
    else:
        form = FarmerRegistrationForm()
    return render(request, "form.html", {"form": form, "title": "Farmer Registration"})


def register_buyer(request):
    if request.method == "POST":
        form = BuyerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user, role="buyer")
            messages.success(request, "Buyer account created successfully.")
            return redirect("login_view")
    else:
        form = BuyerRegistrationForm()
    return render(request, "form.html", {"form": form, "title": "Buyer Registration"})


def register_transporter(request):
    if request.method == "POST":
        form = TransporterRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user, role="transporter")
            messages.success(request, "Transporter account created successfully.")
            return redirect("login_view")
    else:
        form = TransporterRegistrationForm()
    return render(request, "form.html", {"form": form, "title": "Transporter Registration"})


# ---------------------------
# DASHBOARDS
# ---------------------------
@login_required
def dashboard_farmer(request):
    if not request.user.profile.is_farmer():
        messages.error(request, "Access denied.")
        return redirect("home")
    products = Product.objects.filter(farmer=request.user)
    return render(request, "dashboard_farmer.html", {"products": products})


@login_required
def dashboard_buyer(request):
    if not request.user.profile.is_buyer():
        messages.error(request, "Access denied.")
        return redirect("home")

    my_orders = Order.objects.filter(buyer=request.user)

    total_orders = my_orders.count()
    pending_deliveries = my_orders.filter(status__in=['pending', 'confirmed', 'in_transit']).count()
    total_spent = my_orders.aggregate(total=Sum('total_price'))['total'] or 0
    recent_orders = my_orders.order_by('-order_date')[:5]

    # Active delivery (first in-transit order)
    active_delivery = TransportJob.objects.filter(
        order__buyer=request.user,
        status='In Transit'
    ).first()

    context = {
        'total_orders': total_orders,
        'pending_deliveries': pending_deliveries,
        'total_spent': total_spent,
        'recent_orders': recent_orders,
        'active_delivery': active_delivery
    }

    return render(request, "dashboard_buyer.html", context)

@login_required
def dashboard_transporter(request):
    if not request.user.profile.is_transporter():
        messages.error(request, "Access denied.")
        return redirect("home")

    # Earnings: sum of transport fees for delivered jobs
    earnings = TransportJob.objects.filter(
        driver=request.user,
        status='Delivered'
    ).aggregate(total=Sum('transport_fee'))['total'] or 0

    # Active jobs (in transit)
    active_jobs_count = TransportJob.objects.filter(
        driver=request.user,
        status__in=['Pending', 'In Transit']
    ).count()

    # Transporter rating
    transporter_rating = request.user.profile.rating if hasattr(request.user.profile, 'rating') else 0

    # Available jobs (Pending, not assigned yet)
    available_jobs = TransportJob.objects.filter(status='Pending')

    # In-progress jobs (for marking delivery)
    in_progress_jobs = TransportJob.objects.filter(driver=request.user, status='In Transit')

    context = {
        'earnings': earnings,
        'active_jobs_count': active_jobs_count,
        'transporter_rating': transporter_rating,
        'available_jobs': available_jobs,
        'in_progress_jobs': in_progress_jobs,
    }
    return render(request, "dashboard_transporter.html", context)
@login_required
def mark_delivered(request, job_id):
    job = get_object_or_404(TransportJob, id=job_id, driver=request.user)
    if request.method == "POST":
        job.status = "Delivered"
        job.save()
        messages.success(request, f"Job #{job.id} marked as delivered.")
    return redirect("dashboard_transporter")

@login_required
def rate_transporter(request, job_id):
    job = get_object_or_404(
        TransportJob,
        id=job_id,
        status='Delivered'
    )

    # Only buyer can rate
    if request.user != job.order.buyer:
        messages.error(request, "Access denied.")
        return redirect("home")

    # Prevent duplicate rating
    if TransporterRating.objects.filter(job=job).exists():
        messages.warning(request, "You already rated this transporter.")
        return redirect("buyer_dashboard")

    if request.method == "POST":
        form = TransporterRatingForm(request.POST)
        if form.is_valid():
            rating_obj = form.save(commit=False)
            rating_obj.transporter = job.driver
            rating_obj.buyer = request.user
            rating_obj.job = job
            rating_obj.save()

            # Update transporter profile rating
            profile = job.driver.profile
            avg_rating = TransporterRating.objects.filter(
                transporter=job.driver
            ).aggregate(avg=Avg('rating'))['avg']

            profile.rating = round(avg_rating, 1)
            profile.rating_count += 1
            profile.save()

            messages.success(request, "Thank you for rating!")
            return redirect("buyer_dashboard")
    else:
        form = TransporterRatingForm()

    return render(request, "rate_transporter.html", {
        "form": form,
        "job": job
    })


# ---------------------------
# PRODUCT VIEWS
# ---------------------------
@login_required
def add_product(request):
    if not request.user.profile.is_farmer():
        messages.error(request, "Only farmers can add products.")
        return redirect("home")

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.farmer = request.user
            product.save()
            messages.success(request, "Product added successfully.")
            return redirect("dashboard_farmer")
    else:
        form = ProductForm()
    return render(request, "form.html", {"form": form, "title": "Add Product"})


def product_list(request):
    products = Product.objects.all()
    return render(request, "product_list.html", {"products": products})


@login_required
def my_products(request):
    if not request.user.profile.is_farmer():
        messages.error(request, "Access denied.")
        return redirect("home")
    products = Product.objects.filter(farmer=request.user)
    return render(request, "product_list.html", {"products": products})


def buy_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":
        quantity = Decimal(request.POST.get("quantity"))

        # Calculate total price
        total_price = product.price_per_unit * quantity

        # Create order using correct field name: buyer
        order = Order.objects.create(
            product=product,
            buyer=request.user,
            quantity=quantity,
            total_price=total_price,
        )

        # Redirect to same page with order_id in GET params
        return redirect(f"/products/{product_id}/buy/?order_id={order.id}")

    # For GET request
    order_id = request.GET.get("order_id")

    return render(request, "buy_product.html", {
        "product": product,
        "order_id": order_id,
    })




# ---------------------------
# ORDER VIEWS
# ---------------------------
def order_list(request):
    orders = Order.objects.filter(buyer=request.user) if request.user.is_authenticated else []
    return render(request, 'order_list.html', {'orders': orders})


# ---------------------------
# TRANSPORT VIEWS
# ---------------------------
def transport_jobs(request):
    jobs = TransportRequest.objects.all()
    return render(request, 'transport_job.html', {'jobs': jobs})


@login_required
def transport_myjobs(request):
    completed_jobs = TransportJob.objects.filter(driver=request.user, status='Delivered')
    total_earnings = sum([job.transport_fee or 0 for job in completed_jobs])
    return render(request, 'transport_myjobs.html', {
        'jobs': completed_jobs,
        'total_earnings': total_earnings,
    })

@login_required
def accept_job(request, job_id):
    job = get_object_or_404(TransportJob, id=job_id)

    # Only allow POST requests
    if request.method == "POST":

        # Check if already accepted
        if job.status != "Pending":
            messages.warning(request, "This job has already been taken.")
            return redirect('transport_job')

        # Assign job to this transporter
        job.driver = request.user
        job.status = "In Transit"
        job.save()

        messages.success(request, "Job accepted successfully!")
        return redirect('transport_job')

    return redirect('transport_jobs')


@login_required
def request_transport(request, order_id, product_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        pickup = request.POST.get('pickup_location')
        delivery = request.POST.get('delivery_location')
        urgency = request.POST.get('urgency')  # get urgency from form

        # Check if a transport request already exists for this order
        if TransportRequest.objects.filter(order=order).exists():
            messages.warning(request, "Transport has already been requested for this order.")
            return redirect('transport_myjobs')

        # Create TransportRequest
        TransportRequest.objects.create(
            order=order,
            pickup_location=pickup,
            delivery_location=delivery,
            status='available'
        )

        # Create TransportJob from the request
        TransportJob.objects.create(
            order=order,
            pickup_location=pickup,
            delivery_location=delivery,
            urgency=urgency,
            status='Pending'
        )

        messages.success(request, "Transport requested successfully!")
        return redirect('transport_myjobs')

    return render(request, 'request_transport_cart.html', {'order': order, 'product': product})


# ---------------------------
# CART VIEWS
# ---------------------------
@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    # Group items by farmer
    grouped_items = defaultdict(list)
    for item in cart.items.all():
        grouped_items[item.product.farmer].append(item)

    return render(request, 'cart.html', {
        'cart': cart,
        'grouped_items': grouped_items
    })


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, saved_for_later=False)
    if not created:
        item.quantity += 1
        item.save()
    return redirect('cart_view')


@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.delete()
    return redirect('cart_view')


@login_required
def update_cart_quantity(request, item_id, action):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    if action == 'increase' and item.quantity < item.product.quantity:
        item.quantity += 1
        item.save()
    elif action == 'decrease' and item.quantity > 1:
        item.quantity -= 1
        item.save()
    return redirect('cart_view')
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('my_products')  # redirect to your product list
    else:
        form = ProductForm(instance=product)

    return render(request, 'edit_product.html', {'form': form})


def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':  # confirm deletion
        product.delete()
        return redirect('my_products')

    # Show a confirmation page
    return render(request, 'delete_product.html', {'product': product})


@login_required
def save_for_later(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.saved_for_later = True
    item.save()
    return redirect('cart_view')


@login_required
def move_to_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.saved_for_later = False
    item.save()
    return redirect('cart_view')


@login_required
def confirm_order(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        messages.error(request, "Your cart is empty!")
        return redirect('product_list')

    amount = cart.total()  # compute total including tax/delivery

    if request.method == "POST":
        phone = request.POST.get("phoneNumber")

        if not phone:
            messages.error(request, "Please enter your M-Pesa phone number!")
            return redirect("confirm_order")

        # Call your M-Pesa payment function
        response = lipa_na_mpesa(phone, amount)

        # Optionally, handle response, save order, etc.
        messages.success(request, "Payment initiated successfully! Check your phone for the prompt.")
        return redirect("success_page")  # replace with your success page

    return render(request, "confirm_order.html", {"amount": amount})


@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    if not cart.items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('product_list')

    total_amount = sum(item.subtotal for item in cart.items.all())

    if request.method == "POST":
        phone = request.POST.get("phoneNumber")  # match your form input name
        if not phone:
            messages.error(request, "Please enter a phone number.")
            return redirect('checkout')

        # Convert phone to international format for M-Pesa
        phone = phone.strip()
        if phone.startswith("0"):
            phone = "254" + phone[1:]
        elif phone.startswith("+"):
            phone = phone[1:]  # remove + sign
        # else assume already in 254XXXXXXXXX format

        # Convert total_amount to int (M-Pesa does not accept decimals)
        amount = int(total_amount)

        account_ref = f"Cart{cart.id}"

        response = lipa_na_mpesa(
            phone_number=phone,
            amount=amount,
            account_reference=account_ref,
            transaction_desc="Order Payment"
        )

        # Capture exact error if any
        if not response or "errorMessage" in response:
            error_msg = response.get("errorMessage", "Unknown error occurred")
            messages.error(request, f"M-Pesa error: {error_msg}")
            print("M-Pesa response:", response)
            return redirect('checkout')

        checkout_request_id = response.get('CheckoutRequestID')
        if not checkout_request_id:
            messages.error(request, "Failed to initiate M-Pesa payment. Try again later.")
            print("M-Pesa response:", response)
            return redirect('checkout')

        # Store session for callback
        request.session['checkout_request_id'] = checkout_request_id
        request.session['cart_id'] = cart.id

        messages.info(request, "A payment prompt has been sent to your phone. Complete payment to confirm order.")
        return redirect('payment_status')

    return render(request, 'checkout.html', {'cart': cart, 'total_amount': total_amount})

@login_required
def request_transport_for_cart(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    if not cart.items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('product_list')

    if request.method == 'POST':
        pickup = request.POST.get('pickup_location')
        delivery = request.POST.get('delivery_location')
        for item in cart.items.filter(saved_for_later=False):
            TransportRequest.objects.create(
                order=Order.objects.filter(product=item.product, buyer=request.user).last(),
                pickup_location=pickup,
                delivery_location=delivery
            )
        messages.success(request, "Transport request submitted for your cart.")
        return redirect('transport_myjobs')

    return render(request, 'request_transport_cart.html', {'cart': cart})


# ---------------------------
# UNIVERSAL FORM VIEW
# ---------------------------
def simple_form_view(request, form_class, title, success_url):
    if request.method == "POST":
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved successfully.")
            return redirect(success_url)
    else:
        form = form_class()
    return render(request, "form.html", {"form": form, "title": title})
def mpesa_callback(request):
    try:
        data = json.loads(request.body)
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        checkout_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')

        if result_code == 0 and checkout_id:
            cart_id = request.session.get('cart_id')
            cart = Cart.objects.get(id=cart_id)

            for item in cart.items.all():
                Order.objects.create(
                    product=item.product,
                    buyer=cart.user,
                    quantity=item.quantity,
                    total_price=item.subtotal,
                    status='pending'
                )
                # Reduce stock
                item.product.quantity -= item.quantity
                item.product.save()

            # Clear cart
            cart.items.all().delete()
    except Exception as e:
        print("MPESA callback error:", str(e))

    return HttpResponse("Received")

