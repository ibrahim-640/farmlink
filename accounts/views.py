import json
from collections import defaultdict
from django.http import HttpResponse
from django.db.models import Exists, OuterRef
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import TransporterRatingForm
from .models import Vehicle, Payment
from django.db.models import Q
from django.db.models import Sum,Avg
from .mpesa import lipa_na_mpesa
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from .models import Notification
from .ai.price_recommender import get_price_recommendation
from .ai.product_recommender import get_product_recommendations
from .ai.demand_forecaster import get_demand_forecast
from .models import Product, Profile, Order, TransportRequest, TransportJob,TransporterRating, Cart, CartItem,PaymentSplit
from .forms import (
    LoginForm,
    FarmerRegistrationForm,
    BuyerRegistrationForm,
    TransporterRegistrationForm,
    ProductForm
)


# ---------------------------
# HOME PAGE
# ---------------------------
def home(request):
    return render(request, "home.html")
# views.py
# NEW
@login_required
def payment_status(request):
    checkout_request_id = request.session.get(
        'checkout_request_id'
    )
    cart_id = request.session.get('cart_id')

    # If no session data — redirect to dashboard
    if not checkout_request_id or not cart_id:
        messages.warning(
            request,
            "No pending payment found."
        )
        return redirect('dashboard_buyer')

    return render(request, 'Payment/payment_status.html', {
        'checkout_request_id': checkout_request_id,
        'cart_id': cart_id,
    })



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
    return render(request, "Authentication/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("home")


# ---------------------------
# REGISTER / SIGNUP
# ---------------------------
def register(request):
    return render(request, "Authentication/register.html")


def register_farmer(request):
    if request.method == "POST":
        form = FarmerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.profile.role = Profile.ROLE_FARMER
            user.profile.save()
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
            user.profile.role = Profile.ROLE_BUYER
            user.profile.save()
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
            user.profile.role = Profile.ROLE_TRANSPORTER
            user.profile.save()
            messages.success(request, "Transporter account created successfully.")
            return redirect("login_view")
    else:
        form = TransporterRegistrationForm()
    return render(request, "form.html", {"form": form, "title": "Transporter Registration"})


# ---------------------------
# DASHBOARDS
# ---------------------------
@login_required
def dashboard_buyer(request):
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_buyer():
        messages.error(request, "Access denied.")
        return redirect("home")
    from django.utils import timezone
    from .models import RefundRequest

    my_orders = Order.objects.filter(buyer=request.user)
    total_orders = my_orders.count()
    # Add days waiting to pending orders for refund eligibility
    now = timezone.now()
    pending_orders_raw = (
        my_orders.filter(status='pending')
        .select_related('product', 'product__farmer')
        .order_by('-order_date')
    )

    # Pending — waiting for farmer to confirm
    pending_orders = []
    for order in pending_orders_raw:
        days = (now - order.order_date).days
        has_refund_request = RefundRequest.objects.filter(
            order=order
        ).exists()
        pending_orders.append({
            'order': order,
            'days_waiting': days,
            'can_request_refund': days >= 3 and not has_refund_request,
            'refund_requested': has_refund_request,
        })

    # Confirmed — farmer confirmed, buyer can now request transport
    confirmed_orders = (
        my_orders.filter(status='confirmed')
        .select_related('product', 'product__farmer')
        .order_by('-order_date')
    )

    # In transit — transporter accepted and is delivering
    in_transit_orders = (
        my_orders.filter(status='in_transit')
        .select_related('product', 'product__farmer')
        .order_by('-order_date')
    )

    # Delivered — completed orders, buyer can rate transporter
    delivered_orders = (
        my_orders.filter(status='delivered')
        .select_related('product', 'product__farmer')
        .order_by('-order_date')
    )

    # Total spent — only count money actually delivered
    total_spent = (
        my_orders.filter(status='delivered')
        .aggregate(total=Sum('total_price'))
        .get('total') or 0
    )

    # Cart — only fetch, never auto-create on dashboard load
    try:
        cart = Cart.objects.get(user=request.user)
        cart_count = cart.items.filter(saved_for_later=False).count()
        saved_for_later = cart.items.filter(saved_for_later=True).count()
    except Cart.DoesNotExist:
        cart = None
        cart_count = 0
        saved_for_later = 0

    # Recommended — products buyer hasn't ordered yet
    ordered_product_ids = my_orders.values_list('product_id', flat=True)
    recommended_products = (
        Product.objects.filter(is_available=True)
        .exclude(id__in=ordered_product_ids)
        .order_by('-created_at')[:6]
    )

    context = {
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'in_transit_orders': in_transit_orders,
        'delivered_orders': delivered_orders,
        'total_spent': total_spent,
        'cart': cart,
        'cart_count': cart_count,
        'saved_for_later': saved_for_later,
        'recommended_products': recommended_products,
    }
    return render(request, "Dashboards/dashboard_buyer.html", context)
@login_required
def buyer_confirm_receipt(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        buyer=request.user,
        status='delivered'
    )

    if request.method == "POST":
        from decimal import Decimal
        from django.db.models import Sum
        from .models import Wallet, EarningsRecord

        try:
            job = order.transport_job
        except Exception:
            messages.error(
                request,
                "No transport job found for this order."
            )
            return redirect('dashboard_buyer')

        if not job.driver:
            messages.error(
                request,
                "No transporter assigned to this order."
            )
            return redirect('dashboard_buyer')

        # Get transport fee
        # If None calculate from urgency as fallback
        URGENCY_RATES = {
            'high': Decimal('500'),
            'medium': Decimal('300'),
            'low': Decimal('150'),
        }
        transport_fee = job.transport_fee
        if not transport_fee:
            transport_fee = URGENCY_RATES.get(
                job.urgency, Decimal('300')
            )
            # Save correct fee back to job
            job.transport_fee = transport_fee
            job.save()
            print(f"Job #{job.id} fee set to Ksh {transport_fee}")

        # update_or_create — handles both cases:
        # 1. Record exists with amount=0 → updates to correct amount
        # 2. Record does not exist → creates with correct amount
        # Unlike get_or_create which only sets defaults on create
        record, created = EarningsRecord.objects.update_or_create(
            user=job.driver,
            order=order,
            earning_type='transport_fee',
            defaults={
                'amount': transport_fee,
                'status': 'pending',
                'description': (
                    f"Transport fee for delivering "
                    f"'{order.product.name}' "
                    f"from {job.pickup_location} "
                    f"to {job.delivery_location}. "
                    f"Order #{order.id}"
                )
            }
        )
        print(f"Earnings record {'created' if created else 'updated'}: "
              f"Ksh {transport_fee}")

        # Recalculate wallet by summing ALL earnings records
        # This is safer than incremental addition because:
        # - Immune to stale wallet values
        # - Prevents double counting
        # - Always reflects true total
        total = EarningsRecord.objects.filter(
            user=job.driver,
            earning_type='transport_fee'
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        transporter_wallet, _ = Wallet.objects.get_or_create(
            user=job.driver
        )
        transporter_wallet.total_earned = total
        transporter_wallet.save()
        print(f"Transporter wallet updated: Ksh {total}")

        # Update PaymentSplit to mark transporter as paid
        try:
            split = order.payment_split
            split.transporter_paid = True
            split.save()
        except Exception:
            pass

        # Notify transporter
        Notification.objects.create(
            user=job.driver,
            notification_type='payment',
            message=(
                f"Buyer confirmed receipt of "
                f"'{order.product.name}'. "
                f"Ksh {transport_fee} added to "
                f"your pending earnings."
            )
        )

        messages.success(
            request,
            "Receipt confirmed! "
            "Please rate your transporter."
        )
        return redirect('rate_transporter', job_id=job.id)

    return render(request, 'buyer_confirm_receipt.html', {
        'order': order
    })
@login_required
def request_refund(request, order_id):
    """
    Buyer can request refund if farmer hasn't
    confirmed order within 3 days.
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import RefundRequest

    order = get_object_or_404(
        Order,
        id=order_id,
        buyer=request.user,
        status='pending'
    )

    # Check if 3 days have passed
    days_waiting = (timezone.now() - order.order_date).days
    if days_waiting < 3:
        days_left = 3 - days_waiting
        messages.warning(
            request,
            f"You can request a refund in {days_left} more day(s) "
            f"if the farmer does not confirm."
        )
        return redirect('dashboard_buyer')

    # Check if refund already requested
    if RefundRequest.objects.filter(order=order).exists():
        messages.info(
            request,
            "Refund already requested. "
            "FarmLink admin will process it shortly."
        )
        return redirect('dashboard_buyer')

    if request.method == "POST":
        # Create refund request
        RefundRequest.objects.create(
            order=order,
            buyer=request.user,
            amount=order.total_price,
            reason='Farmer did not confirm order within 3 days',
            status='pending'
        )

        # Cancel the order
        order.status = 'cancelled'
        order.save()

        # Notify farmer
        Notification.objects.create(
            user=order.product.farmer,
            notification_type='order',
            message=(
                f"Order #{order.id} for '{order.product.name}' "
                f"has been cancelled by the buyer "
                f"due to no confirmation within 3 days."
            )
        )

        messages.success(
            request,
            "Refund requested successfully. "
            "FarmLink admin will process your refund "
            "within 24 hours."
        )
        return redirect('dashboard_buyer')

    return render(request, 'request_refund.html', {
        'order': order,
        'days_waiting': days_waiting
    })

@login_required
def farmer_orders(request):
    """
    Shows all orders for the farmer's products.

    Farmers can:
    - See all incoming orders
    - Filter by status
    - See buyer details
    - Track payment status
    """
    if not request.user.profile.is_farmer():
        messages.error(request, "Access denied.")
        return redirect('home')

    orders = Order.objects.filter(
        product__farmer=request.user
    ).select_related(
        'product',
        'buyer'
    ).order_by('-order_date')

    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    # Summary counts
    pending_count = orders.filter(status='pending').count()
    confirmed_count = orders.filter(status='confirmed').count()
    in_transit_count = orders.filter(status='in_transit').count()
    delivered_count = orders.filter(status='delivered').count()

    # Total revenue from non-cancelled orders
    total_revenue = orders.exclude(
        status='cancelled'
    ).aggregate(
        total=Sum('total_price')
    )['total'] or 0

    context = {
        'orders': orders,
        'status_filter': status_filter,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count,
        'in_transit_count': in_transit_count,
        'delivered_count': delivered_count,
        'total_revenue': total_revenue,
    }

    return render(request, 'Orders/farmer_orders.html', context)
@login_required
def dashboard_farmer(request):
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_farmer():
        messages.error(request, "Access denied.")
        return redirect("home")
    from .models import Wallet, EarningsRecord
    from django.utils import timezone

    products = Product.objects.filter(farmer=request.user)

    # Revenue from delivered orders ONLY
    total_revenue = (
        Order.objects.filter(
            product__farmer=request.user,
            status='delivered'
        )
        .aggregate(total=Sum('total_price'))['total'] or 0
    )

    total_orders = Order.objects.filter(
        product__farmer=request.user
    ).count()

    total_products = products.count()

    # Stock alerts
    out_of_stock = products.filter(quantity=0)
    low_stock = products.filter(quantity__gt=0, quantity__lte=5)

    # Pending orders — farmer needs to confirm these
    pending_orders = (
        Order.objects.filter(
            product__farmer=request.user,
            status='pending'
        )
        .select_related('product', 'buyer')
        .order_by('-order_date')
    )
    # Add days waiting to each pending order
    # and flag refund-eligible ones (3+ days)
    now = timezone.now()
    pending_orders_with_days = []
    for order in pending_orders:
        days = (now - order.order_date).days
        pending_orders_with_days.append({
            'order': order,
            'days_waiting': days,
            'refund_eligible': days >= 3
        })

    # Confirmed orders — farmer confirmed, buyer requesting transport
    confirmed_orders = (
        Order.objects.filter(
            product__farmer=request.user,
            status='confirmed'
        )
        .select_related('product', 'buyer')
        .order_by('-order_date')
    )
    delivered_orders = (
        Order.objects
        .filter(product__farmer=request.user, status='delivered')
        .select_related('product', 'buyer')
        .order_by('-order_date')
    )

    # In transit orders — transporter accepted
    in_transit_orders = (
        Order.objects.filter(
            product__farmer=request.user,
            status='in_transit'
        )
        .select_related('product', 'buyer')
        .order_by('-order_date')
    )
    # Wallet and earnings
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    recent_earnings = (
        EarningsRecord.objects
        .filter(user=request.user)
        .order_by('-created_at')[:5]
    )

    context = {
        'products': products,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_products': total_products,
        'out_of_stock': out_of_stock,
        'low_stock': low_stock,
        'pending_orders': pending_orders,
        'pending_orders_with_days': pending_orders_with_days,
        'confirmed_orders': confirmed_orders,
        'in_transit_orders': in_transit_orders,
        'delivered_orders': delivered_orders,
        'wallet': wallet,
        'recent_earnings': recent_earnings,
    }


    return render(request, "Dashboards/dashboard_farmer.html", context)

@login_required
def dashboard_transporter(request):
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_transporter():
        messages.error(request, "Access denied.")
        return redirect("home")
    from .models import Wallet, EarningsRecord
    from .forms import TransporterProfileForm

    if request.method == "POST":
        form = TransporterProfileForm(
            request.POST,
            request.FILES,
            instance=profile
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("dashboard_transporter")
    else:
        form = TransporterProfileForm(instance=profile)


    earnings = (
        TransportJob.objects
        .filter(driver=request.user, status='Delivered')
        .aggregate(total=Sum('transport_fee'))['total'] or 0
    )

    active_jobs_count = TransportJob.objects.filter(
        driver=request.user,
        status__in=['Accepted', 'In Transit']
    ).count()

    completed_jobs_count = TransportJob.objects.filter(
        driver=request.user,
        status='Delivered'
    ).count()

    transporter_rating = profile.rating or 0

    # Available jobs — TransportJobs that are Pending with no driver yet
    # Sorted by urgency: high first, then medium, then low
    urgency_order = {'high': 0, 'medium': 1, 'low': 2}
    available_jobs = sorted(
        TransportJob.objects.filter(
            status='Pending',
            driver__isnull=True
        ).select_related(
            'order',
            'order__product',
            'order__buyer'
        ),
        key=lambda j: urgency_order.get(j.urgency, 99)
    )

    # In-progress jobs for this transporter
    in_progress_jobs = (
        TransportJob.objects.filter(
            driver=request.user,
            status__in=['Accepted', 'In Transit']
        )
        .select_related('order', 'order__product', 'order__buyer', 'vehicle')
    )

    # Most recent in-progress job for the active delivery card
    active_delivery = in_progress_jobs.first()

    vehicles = Vehicle.objects.filter(transporter=request.user)
    # Wallet and earnings
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    recent_earnings = (
        EarningsRecord.objects
        .filter(user=request.user)
        .order_by('-created_at')[:5]
    )
    # Weekly earnings chart — last 7 days
    from django.utils import timezone
    from datetime import timedelta

    today = timezone.now().date()
    week_days = []
    weekly_earnings = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        week_days.append(day.strftime('%a'))
        day_total = (
            TransportJob.objects
            .filter(
                driver=request.user,
                status='Delivered',
                updated_at__date=day
            )
            .aggregate(total=Sum('transport_fee'))['total'] or 0
        )
        weekly_earnings.append(float(day_total))

    max_earning = max(weekly_earnings) if any(weekly_earnings) else 1
    weekly_earnings_pct = [
        round((e / max_earning) * 100) for e in weekly_earnings
    ]

    context = {
        'form': form,
        'profile': profile,
        'earnings': earnings,
        'active_jobs_count': active_jobs_count,
        'completed_jobs_count': completed_jobs_count,
        'transporter_rating': transporter_rating,
        'available_jobs': available_jobs,
        'in_progress_jobs': in_progress_jobs,
        'active_delivery': active_delivery,
        'vehicles': vehicles,
        'weekly_earnings': weekly_earnings_pct,
        'week_days': week_days,
        'wallet': wallet,
        'recent_earnings': recent_earnings,
    }
    return render(request, "Dashboards/dashboard_transporter.html", context)
#book transport view
@login_required
def book_transport(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)

    # Only active vehicles
    vehicles = Vehicle.objects.filter(is_active=True)

    if request.method == "POST":
        vehicle_id = request.POST.get("vehicle_id")
        pickup = request.POST.get("pickup_location")
        delivery = request.POST.get("delivery_location")
        urgency = request.POST.get("urgency")

        # ✅ Get the vehicle instance
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)

        # 🚫 Prevent double booking
        if TransportJob.objects.filter(order=order).exists():
            messages.warning(request, "Transport has already been booked for this order.")
            return redirect("dashboard_buyer")

        TransportJob.objects.create(
            order=order,
            pickup_location=pickup,
            delivery_location=delivery,
            urgency=urgency,
            vehicle=vehicle
        )

        messages.success(request, "Transport booked successfully.")
        return redirect("dashboard_buyer")

    return render(request, "Transport/book_transport.html", {
        "order": order,
        "vehicles": vehicles
    })


@login_required
def mark_delivered(request, job_id):
    job = get_object_or_404(
        TransportJob,
        id=job_id,
        driver=request.user
    )

    if request.method == "POST":
        job.status = "Delivered"
        job.save()

        # Update order status
        job.order.status = 'delivered'
        job.order.save()

        # Notify buyer order was delivered
        Notification.objects.create(
            user=job.order.buyer,
            notification_type='delivery',
            message=(
                f"Your order for '{job.order.product.name}' "
                f"has been delivered!"
                f"Please confirm receipt on your dashboard "
                f"so the transporter gets paid."
            )
        )

        messages.success(
            request,
            f"Order #{job.order.id} marked as delivered. "
            f"Waiting for buyer to confirm receipt."
        )
    return redirect("dashboard_transporter")

@login_required
def rate_transporter(request, job_id):
    job = get_object_or_404(
        TransportJob.objects.select_related('order', 'driver', 'driver__profile'),
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
        return redirect("dashboard_buyer")

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
            profile.rating_count = TransporterRating.objects.filter(transporter=job.driver).count()

            profile.save()

            messages.success(request, "Thank you for rating!")
            return redirect("dashboard_buyer")
    else:
        form = TransporterRatingForm()

    return render(request, "Transport/rate_transporter.html", {
        "form": form,
        "job": job
    })
#Market trends view
@login_required
def market_trends(request):
    # ✅ SAFE profile access (prevents crash)
    profile = getattr(request.user, "profile", None)

    if not profile or not profile.is_buyer():
        messages.error(request, "Access denied.")
        return redirect("home")

    # ✅ Top-selling products (based on delivered orders only)
    top_products = (
        Order.objects
        .filter(status='delivered')
        .values(
            'product__id',
            'product__name',
            'product__category',
        )
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:5]
    )

    # ✅ Category trends (total quantity sold per category)
    category_stats = (
        Order.objects
        .filter(status='delivered')
        .values('product__category')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')
    )

    context = {
        'top_products': top_products,
        'category_stats': category_stats,
    }

    return render(request, 'Ai_Services/market_trends.html', context)
#Inventory view
@login_required
def inventory(request):
    profile = getattr(request.user, "profile", None)

    if not profile:
        messages.error(request, "Access denied.")
        return redirect("home")

    if profile.is_farmer():
        products = Product.objects.filter(
            farmer=request.user
        ).order_by('-created_at')
        return render(request, 'Inventory/inventory.html', {
            'products': products,
            'view_type': 'farmer'
        })

    if profile.is_buyer():
        products = (
            Product.objects
            .filter(order__buyer=request.user)
            .distinct()
            .order_by('-created_at')
        )
        orders = (
            Order.objects
            .filter(buyer=request.user)
            .exclude(status='cancelled')
            .select_related('product')
            .order_by('-order_date')
        )
        return render(request, 'Inventory/inventory.html', {
            'products': products,
            'orders': orders,
            'view_type': 'buyer'
        })

    messages.error(
        request,
        "Transporters do not have an inventory."
    )
    return redirect("dashboard_transporter")
# Transport services view
@login_required
def transport_services(request):
    if not request.user.profile.is_buyer():
        messages.error(request, "Access denied.")
        return redirect("home")

    # Get all transport jobs for the buyer's orders
    transport_jobs = TransportJob.objects.filter(order__buyer=request.user).order_by('-created_at')

    context = {
        'transport_jobs': transport_jobs
    }

    return render(request, 'Transport/transport_services.html', context)
#manage vehicle view
@login_required
def manage_vehicle(request, vehicle_id):
    if not request.user.profile.is_transporter():
        messages.error(request, "Access denied.")
        return redirect("home")

    vehicle = get_object_or_404(
        Vehicle,
        id=vehicle_id,
        transporter=request.user
    )

    return render(request, "Transport/manage_vehicle.html", {
        "vehicle": vehicle
    })
#add vehicle view
@login_required
def add_vehicle(request):
    # Only transporters can add vehicles
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_transporter():
        messages.error(request, "Access denied.")
        return redirect("home")

    if request.method == "POST":
        plate_number = request.POST.get("plate_number")
        vehicle_type = request.POST.get("vehicle_type")
        capacity = request.POST.get("capacity")

        # Check duplicate plate
        if Vehicle.objects.filter(plate_number=plate_number).exists():
            messages.error(request, f"Vehicle with plate '{plate_number}' already exists.")
            return render(request, "add_vehicle.html", {
                "plate_number": plate_number,
                "vehicle_type": vehicle_type,
                "capacity": capacity,
            })

        Vehicle.objects.create(
            transporter=request.user,
            plate_number=plate_number,
            vehicle_type=vehicle_type.lower(),  # match your model choices
            capacity=capacity,
            is_active=True
        )

        messages.success(request, "Vehicle added successfully.")
        return redirect("dashboard_transporter")

    # GET request
    return render(request, "Transport/add_vehicle.html")

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
    query = request.GET.get("q")   # get search text from search box

    products = Product.objects.filter(is_available=True)

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__icontains=query)
        )

    return render(request, "products/product_list.html", {
        "products": products,
        "query": query
    })



@login_required
def my_products(request):
    if not request.user.profile.is_farmer():
        messages.error(request, "Access denied.")
        return redirect("home")
    products = Product.objects.filter(farmer=request.user)
    return render(request, "products/product_list.html", {"products": products})

@login_required
def buy_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":
        quantity = Decimal(request.POST.get("quantity"))
        total_price = product.price_per_unit * quantity

        # Create order with pending status
        order = Order.objects.create(
            product=product,
            buyer=request.user,
            quantity=quantity,
            total_price=total_price,
            status="pending"
        )

        # DO NOT create TransportJob here
        # TransportJob is only created when:
        # 1. Farmer confirms the order
        # 2. Buyer explicitly requests transport
        # Creating it here means transporters see jobs
        # for unconfirmed, unpaid orders

        return redirect(
            f"/products/{product_id}/buy/?order_id={order.id}"
        )

    order_id = request.GET.get("order_id")
    return render(request, "products/buy_product.html", {
        "product": product,
        "order_id": order_id,
    })


# ---------------------------
# ORDER VIEWS
# ---------------------------
@login_required
def order_list(request):
    """
    Shows all orders for the logged in user.

    For buyers: shows their purchase history
    For farmers: redirects to farmer_orders

    Each order shows:
    - Product name and image
    - Quantity and total price
    - Current status
    - Date ordered
    - Link to order detail
    """
    profile = getattr(request.user, 'profile', None)

    if profile and profile.is_farmer():
        return redirect('farmer_orders')

    # Buyer orders — newest first
    orders = Order.objects.filter(
        buyer=request.user
    ).select_related(
        'product',
        'product__farmer'
    ).order_by('-order_date')

    # Group orders by status for easy filtering
    pending = orders.filter(status='pending')
    confirmed = orders.filter(status='confirmed')
    in_transit = orders.filter(status='in_transit')
    delivered = orders.filter(status='delivered')
    cancelled = orders.filter(status='cancelled')

    context = {
        'orders': orders,
        'pending': pending,
        'confirmed': confirmed,
        'in_transit': in_transit,
        'delivered': delivered,
        'cancelled': cancelled,
        'total_orders': orders.count(),
        'total_spent': orders.exclude(
            status='cancelled'
        ).aggregate(
            total=Sum('total_price')
        )['total'] or 0,
    }

    return render(request, 'Orders/order_list.html', context)

@login_required
def order_detail(request, order_id):
    """
    Shows full details of a single order.

    Accessible by:
    - The buyer who placed the order
    - The farmer whose product is in the order

    Shows:
    - Product details
    - Payment status
    - Delivery/transport status
    - Timeline of order events
    """
    order = get_object_or_404(Order, id=order_id)

    # Security check
    # Only the buyer or the farmer can view this order
    profile = getattr(request.user, 'profile', None)
    is_buyer = profile and profile.is_buyer() and order.buyer == request.user
    is_farmer = profile and profile.is_farmer() and order.product.farmer == request.user

    if not is_buyer and not is_farmer:
        messages.error(request, "Access denied.")
        return redirect('home')

    # Get related transport job if exists
    transport_job = getattr(order, 'transport_job', None)

    # Get payment if exists
    payment = order.payments.first()

    context = {
        'order': order,
        'transport_job': transport_job,
        'payment': payment,
        'is_buyer': is_buyer,
        'is_farmer': is_farmer,
    }

    return render(request, 'Orders/order_detail.html', context)

# ---------------------------
# TRANSPORT VIEWS
# ---------------------------
# NEW
@login_required
def transport_jobs(request):
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_transporter():
        messages.error(request, "Access denied.")
        return redirect("home")

    urgency_order = {'high': 0, 'medium': 1, 'low': 2}
    jobs = sorted(
        TransportJob.objects.filter(
            status='Pending',
            driver__isnull=True
        ).select_related(
            'order',
            'order__product',
            'order__buyer',
            'order__buyer__profile'
        ),
        key=lambda j: urgency_order.get(j.urgency, 99)
    )

    return render(request, 'Transport/transport_job.html', {
        'jobs': jobs
    })
@login_required
def transport_myjobs(request):
    completed_jobs = TransportJob.objects.filter(driver=request.user, status='Delivered')
    total_earnings = sum([job.transport_fee or 0 for job in completed_jobs])
    return render(request, 'Transport/transport_myjobs.html', {
        'jobs': completed_jobs,
        'total_earnings': total_earnings,
    })
#def accept job view
@login_required
def accept_job(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_transporter():
        messages.error(request, "Access denied.")
        return redirect("home")

    if request.method == "POST":
        # Fetch the job directly from database — not from Python memory
        # This prevents two transporters accepting the same job simultaneously
        try:
            job = TransportJob.objects.select_for_update().get(
                order=order,
                status='Pending',
                driver__isnull=True
            )
        except TransportJob.DoesNotExist:
            messages.warning(
                request,
                "This job has already been accepted or no longer exists."
            )
            return redirect("dashboard_transporter")

        # Only assign active vehicles
        vehicle = Vehicle.objects.filter(
            transporter=request.user,
            is_active=True
        ).first()

        # Update the existing job — do NOT create a new one
        # Pickup and delivery locations already set by buyer's transport request
        job.driver = request.user
        job.vehicle = vehicle
        job.status = 'Accepted'
        job.save()

        # Update order status to in_transit
        order.transporter = request.user
        order.status = 'in_transit'
        order.save()

        # Notify buyer their order is now in transit
        Notification.objects.create(
            user=order.buyer,
            notification_type='delivery',
            message=(
                f"Your order for '{order.product.name}' has been accepted "
                f"by transporter {request.user.username} and is now in transit."
            )
        )

        messages.success(request, "Job accepted! Order is now in transit.")

    return redirect("dashboard_transporter")
@login_required
def request_transport(request, order_id, product_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        buyer=request.user,
        status='confirmed'
    )
    product = order.product

    from .utils import (
        calculate_transport_fee,
        get_recommended_urgency,
        get_urgency_warning,
        URGENCY_RATES,
        MINIMUM_FEES,
        URGENCY_LABELS,
    )

    # Get recommended urgency based on product category
    recommended_urgency = get_recommended_urgency(
        product.category
    )

    if request.method == 'POST':
        pickup = request.POST.get(
            'pickup_location', ''
        ).strip()
        delivery = request.POST.get(
            'delivery_location', ''
        ).strip()
        urgency = request.POST.get(
            'urgency', recommended_urgency
        )

        if not pickup:
            messages.error(
                request,
                "Pickup location is required."
            )
            return render(request, 'request_transport.html', {
                'order': order,
                'product': product,
                'recommended_urgency': recommended_urgency,
                'urgency_rates': {
                    k: str(v)
                    for k, v in URGENCY_RATES.items()
                },
                'urgency_labels': URGENCY_LABELS,
            })

        if not delivery:
            messages.error(
                request,
                "Delivery location is required."
            )
            return render(request, 'request_transport.html', {
                'order': order,
                'product': product,
                'recommended_urgency': recommended_urgency,
                'urgency_rates': {
                    k: str(v)
                    for k, v in URGENCY_RATES.items()
                },
                'urgency_labels': URGENCY_LABELS,
            })

        # Check if buyer selected lower urgency
        # than recommended — show warning but allow
        warning = get_urgency_warning(
            product.category, urgency
        )
        if warning:
            messages.warning(request, warning)

        # Calculate transport fee using Google Maps
        transport_result = calculate_transport_fee(
            pickup, delivery, urgency
        )
        transport_fee = transport_result['transport_fee']
        distance_km = transport_result['distance_km']

        # Warn if Google Maps failed
        if transport_result['error']:
            messages.warning(
                request,
                f"Note: {transport_result['error']}. "
                f"Estimated fee: Ksh {transport_fee}"
            )

        # Prevent duplicate transport request
        if TransportRequest.objects.filter(
            order=order
        ).exists():
            messages.warning(
                request,
                "Transport already requested for this order."
            )
            return redirect('dashboard_buyer')

        # Prevent duplicate transport job
        if TransportJob.objects.filter(order=order).exists():
            messages.warning(
                request,
                "A transport job already exists for this order."
            )
            return redirect('dashboard_buyer')

        TransportRequest.objects.create(
            order=order,
            pickup_location=pickup,
            delivery_location=delivery,
            transport_fee=transport_fee,
            status='available'
        )

        TransportJob.objects.create(
            order=order,
            pickup_location=pickup,
            delivery_location=delivery,
            urgency=urgency,
            transport_fee=transport_fee,
            status='Pending'
        )

        # Update payment split with real distance
        # NEW — creates split if missing, updates if exists
        try:
            from decimal import Decimal
            split, created = PaymentSplit.objects.get_or_create(
                order=order,
                defaults={
                    'product_subtotal': order.total_price,
                    'transport_fee': transport_fee,
                    'commission': (
                                          order.total_price + transport_fee
                                  ) * Decimal('0.10'),
                    'grand_total': (
                            order.total_price +
                            transport_fee +
                            (order.total_price + transport_fee)
                            * Decimal('0.10')
                    ),
                    'distance_km': distance_km,
                }
            )
            if not created:
                split.transport_fee = transport_fee
                split.distance_km = distance_km
                total = split.product_subtotal + transport_fee
                split.commission = total * Decimal('0.10')
                split.grand_total = total + split.commission
                split.save()
            print(f"PaymentSplit saved: transport_fee={transport_fee}")
        except Exception as e:
            print(f"PaymentSplit error: {e}")

        # Notify all transporters with full job details
        transporter_profiles = Profile.objects.filter(
            role=Profile.ROLE_TRANSPORTER
        )

        # Build urgency notification label
        urgency_emoji = {
            'high': '🔴 URGENT',
            'medium': '🟡 Medium',
            'low': '🟢 Low'
        }.get(urgency, urgency.title())

        for tp in transporter_profiles:
            Notification.objects.create(
                user=tp.user,
                notification_type='delivery',
                message=(
                    f"{urgency_emoji} transport job available: "
                    f"'{order.product.name}' "
                    f"({order.product.category.title()}) "
                    f"from {pickup} to {delivery}. "
                    f"Distance: {distance_km} km. "
                    f"Fee: Ksh {transport_fee}."
                )
            )

        # Notify farmer urgency level
        urgency_farmer_msg = {
            'high': (
                f"⚠️ URGENT: Your order #{order.id} "
                f"for '{product.name}' has transport requested "
                f"with HIGH urgency. "
                f"Transporter will pick up immediately."
            ),
            'medium': (
                f"Order #{order.id} for '{product.name}' "
                f"has transport requested. "
                f"Pickup within 24 hours."
            ),
            'low': (
                f"Order #{order.id} for '{product.name}' "
                f"has transport requested. "
                f"Flexible pickup timing."
            ),
        }.get(urgency, '')

        if urgency_farmer_msg:
            Notification.objects.create(
                user=order.product.farmer,
                notification_type='delivery',
                message=urgency_farmer_msg
            )

        # Build success message
        dist_msg = (
            f" ({distance_km} km)"
            if distance_km else ""
        )
        messages.success(
            request,
            f"Transport requested successfully! "
            f"Fee: Ksh {transport_fee}{dist_msg}. "
            f"Transporters have been notified."
        )
        return redirect('dashboard_buyer')

    # GET — show form with recommended urgency
    return render(request, 'request_transport.html', {
        'order': order,
        'product': product,
        'recommended_urgency': recommended_urgency,
        'urgency_rates': {
            k: str(v) for k, v in URGENCY_RATES.items()
        },
        'minimum_fees': {
            k: str(v) for k, v in MINIMUM_FEES.items()
        },
        'urgency_labels': URGENCY_LABELS,
    })
# ---------------------------
# CART VIEWS
# ---------------------------
@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    items = cart.items.filter(saved_for_later=False)

    grouped_items = {}
    subtotal = 0

    for item in items:
        farmer = item.product.farmer
        grouped_items.setdefault(farmer, []).append(item)
        subtotal += item.subtotal

    delivery_fee = 2
    total = subtotal + delivery_fee

    return render(request, 'Orders/cart.html', {
        'grouped_items': grouped_items,
        'subtotal': subtotal,
        'delivery_fee': delivery_fee,
        'total': total,
        'cart': cart
    })



@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    # Prevent farmer from buying their own product
    if product.farmer == request.user:
        messages.error(
            request,
            "You cannot add your own product to cart."
        )
        return redirect('product_list')
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
@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # ✅ Only farmers allowed
    if request.user.profile.role != "farmer":
        messages.error(request, "You are not allowed to edit products.")
        return redirect("home")

    # ✅ Only the owner farmer can edit
    if product.farmer != request.user:
        messages.error(request, "You can only edit your own products.")
        return redirect("dashboard_farmer")

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")
            return redirect('dashboard_farmer')
    else:
        form = ProductForm(instance=product)

    return render(request, 'products/edit_product.html', {'form': form})


@login_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # ✅ Only farmers allowed
    if request.user.profile.role != "farmer":
        messages.error(request, "You are not allowed to delete products.")
        return redirect("home")

    # ✅ Only the owner farmer can delete
    if product.farmer != request.user:
        messages.error(request, "You can only delete your own products.")
        return redirect("dashboard_farmer")

    if request.method == 'POST':  # confirm deletion
        product.delete()
        messages.success(request, "Product deleted successfully.")
        return redirect('dashboard_farmer')

    return render(request, 'products/delete_product.html', {'product': product})


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
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    if not cart.items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('product_list')

    total_amount = cart.total()

    if request.method == "POST":
        phone = request.POST.get("phoneNumber")

        if not phone:
            messages.error(request, "Please enter a phone number.")
            return redirect('checkout')

        # Normalize phone to 254 format
        phone = phone.strip()
        if phone.startswith("0"):
            phone = "254" + phone[1:]
        elif phone.startswith("+"):
            phone = phone[1:]

        amount = int(total_amount)

        response = lipa_na_mpesa(
            phone_number=phone,
            amount=amount,
            account_reference=f"Cart-{cart.id}",
            transaction_desc="FarmLink Order Payment"
        )

        if not response or response.get("ResponseCode") != "0":
            messages.error(request, "Payment initiation failed. Try again.")
            return redirect('checkout')

        checkout_request_id = response.get("CheckoutRequestID")

        # Save ONE pending payment record linked to the cart
        # This is how mpesa_callback knows which cart to process
        # We use a temporary order-less Payment by linking to cart via
        # checkout_request_id — callback will look this up
        # Store cart_id in session as backup
        request.session['checkout_request_id'] = checkout_request_id
        request.session['cart_id'] = cart.id

        # Save phone on session so callback can use it
        request.session['phone'] = phone

        # DO NOT create orders here
        # DO NOT reduce stock here
        # DO NOT clear cart here
        # All of that happens in mpesa_callback ONLY after payment confirmed

        messages.success(
            request,
            "Payment prompt sent to your phone. "
            "Please complete the M-Pesa payment."
        )
        return redirect('payment_status')

    return render(request, 'Orders/checkout.html', {
        'cart': cart,
        'total_amount': total_amount
    })

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

            # 1️⃣ Get the related order
            order = Order.objects.filter(
                product=item.product,
                buyer=request.user
            ).last()

            if not order:
                continue

            # 2️⃣ UPDATE ORDER STATUS
            order.status = "confirmed"
            order.save()

            # WHY:
            # Pending orders are hidden from transporter dashboards.
            # Confirmed means "ready for transport".

            # 3️⃣ CREATE TRANSPORT REQUEST
            tr = TransportRequest.objects.create(
                order=order,
                pickup_location=pickup,
                delivery_location=delivery,
                status="pending"
            )

            # WHY:
            # This records that buyer requested transport.

            # 4️⃣ CREATE TRANSPORT JOB (CRITICAL)
            TransportJob.objects.get_or_create(
                order=order,
                defaults={
                    "status": "Pending",
                }
            )

            # WHY:
            # Transporter dashboards read from TransportJob.
            # If job not created → no available jobs shown.

        messages.success(request, "Transport request submitted for your cart.")
        return redirect('transport_myjobs')

    return render(request, 'Transport/request_transport.html', {'cart': cart})

# ---------------------------
# FARMER CONFIRMS ORDER — NEW
# ---------------------------
@login_required
def confirm_order_farmer(request, order_id):
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_farmer():
        messages.error(request, "Access denied.")
        return redirect("home")

    order = get_object_or_404(
        Order,
        id=order_id,
        product__farmer=request.user,
        status='pending'
    )

    if request.method == "POST":
        from decimal import Decimal
        from .models import Wallet, EarningsRecord, PaymentSplit

        COMMISSION_RATE = Decimal('0.10')
        product_amount = Decimal(str(order.total_price))
        commission = product_amount * COMMISSION_RATE
        farmer_amount = product_amount - commission

        # Confirm the order
        order.status = 'confirmed'
        order.save()

        # Create PaymentSplit if not exists
        PaymentSplit.objects.get_or_create(
            order=order,
            defaults={
                'product_subtotal': product_amount,
                'transport_fee': Decimal('0'),
                'commission': commission,
                'grand_total': product_amount + commission,
                'farmer_paid': True,
                'transporter_paid': False,
            }
        )

        # Create earnings record if not exists
        record, created = EarningsRecord.objects.get_or_create(
            user=request.user,
            order=order,
            earning_type='product_sale',
            defaults={
                'amount': farmer_amount,
                'status': 'pending',
                'description': (
                    f"Sale of {order.product.name} "
                    f"to {order.buyer.username}. "
                    f"Order #{order.id}"
                )
            }
        )

        # Update farmer wallet
        wallet, _ = Wallet.objects.get_or_create(
            user=request.user
        )
        if created:
            wallet.total_earned += farmer_amount
            wallet.save()

        # Notify buyer
        Notification.objects.create(
            user=order.buyer,
            notification_type='order',
            message=(
                f"Your order for '{order.product.name}' "
                f"has been confirmed by the farmer. "
                f"You can now request transport."
            )
        )

        messages.success(
            request,
            f"Order #{order.id} confirmed. "
            f"Ksh {farmer_amount} added to your "
            f"pending earnings."
        )

    return redirect("dashboard_farmer")
# ---------------------------
# REQUEST TRANSPORT — fixed
# ---------------------------
@login_required
def request_transport(request, order_id, product_id):
    # Only confirmed orders can request transport
    order = get_object_or_404(
        Order,
        id=order_id,
        buyer=request.user,
        status='confirmed'   # ← only confirmed orders
    )
    product = order.product  # get from order directly — ignore product_id

    if request.method == 'POST':
        pickup = request.POST.get('pickup_location')
        delivery = request.POST.get('delivery_location')
        urgency = request.POST.get('urgency')

        # Prevent duplicate transport request
        if TransportRequest.objects.filter(order=order).exists():
            messages.warning(
                request,
                "Transport already requested for this order."
            )
            return redirect('dashboard_buyer')

        # Prevent duplicate transport job
        if TransportJob.objects.filter(order=order).exists():
            messages.warning(
                request,
                "A transport job already exists for this order."
            )
            return redirect('dashboard_buyer')

        TransportRequest.objects.create(
            order=order,
            pickup_location=pickup,
            delivery_location=delivery,
            status='available'
        )

        TransportJob.objects.create(
            order=order,
            pickup_location=pickup,
            delivery_location=delivery,
            urgency=urgency,
            status='Pending'
        )

        # Notify ALL active transporters about new job
        transporter_profiles = Profile.objects.filter(
            role=Profile.ROLE_TRANSPORTER
        )
        for tp in transporter_profiles:
            Notification.objects.create(
                user=tp.user,
                notification_type='delivery',
                message=(
                    f"New transport job available: '{order.product.name}' "
                    f"from {pickup} to {delivery}. "
                    f"Urgency: {urgency.title()}."
                )
            )

        messages.success(request, "Transport requested successfully!")
        return redirect('dashboard_buyer')

    return render(request, 'Transport/request_transport.html', {
        'order': order,
        'product': product
    })


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


@csrf_exempt
def mpesa_callback(request):
    print("\n" + "=" * 50)
    print("MPESA CALLBACK HIT")
    print("=" * 50)

    try:
        # Step 1 — Parse request body
        body = request.body
        print(f"Raw body: {body[:500]}")

        data = json.loads(body)
        print(f"Parsed data keys: {list(data.keys())}")

        stk_callback = data.get('Body', {}).get('stkCallback', {})
        checkout_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')

        print(f"CheckoutID: {checkout_id}")
        print(f"ResultCode: {result_code}")
        print(f"ResultCode type: {type(result_code)}")

        # Step 2 — Check result code
        # CRITICAL: result_code must be integer 0 not string "0"
        if result_code != 0:
            print(f"PAYMENT FAILED or wrong type. "
                  f"ResultCode={result_code} "
                  f"type={type(result_code)}")
            return HttpResponse("Received", status=200)

        print("Payment SUCCESS — proceeding to create orders")

        # Step 3 — Extract metadata
        metadata = (
            stk_callback
            .get('CallbackMetadata', {})
            .get('Item', [])
        )
        print(f"Metadata: {metadata}")

        mpesa_receipt = None
        phone = None
        amount_paid = None
        account_reference = None

        for item in metadata:
            name = item.get('Name')
            value = item.get('Value')
            print(f"  Metadata item: {name} = {value}")
            if name == 'MpesaReceiptNumber':
                mpesa_receipt = value
            if name == 'PhoneNumber':
                phone = str(value)
            if name == 'Amount':
                amount_paid = value
            if name == 'AccountReference':
                account_reference = value

        print(f"Receipt: {mpesa_receipt}")
        print(f"Phone: {phone}")
        print(f"Amount: {amount_paid}")
        print(f"AccountReference: {account_reference}")

        # Step 4 — Parse cart ID
        cart_id = None
        if account_reference and str(account_reference).startswith('Cart-'):
            try:
                cart_id = int(
                    str(account_reference).replace('Cart-', '')
                )
                print(f"Parsed cart_id: {cart_id}")
            except ValueError as e:
                print(f"ERROR parsing cart_id: {e}")
        else:
            print(f"ERROR: account_reference is '{account_reference}' "
                  f"— does not start with 'Cart-'")

        if not cart_id:
            print("STOPPING: No cart_id")
            return HttpResponse("Received", status=200)

        # Step 5 — Duplicate check
        already_processed = Payment.objects.filter(
            checkout_request_id=checkout_id,
            status='completed'
        ).exists()
        print(f"Already processed: {already_processed}")

        if already_processed:
            print("STOPPING: Already processed")
            return HttpResponse("Received", status=200)

        # Step 6 — Find cart
        try:
            cart = Cart.objects.get(id=cart_id)
            print(f"Cart found: user={cart.user.username}")
        except Cart.DoesNotExist:
            print(f"ERROR: Cart {cart_id} does not exist")
            print(f"All carts: {list(Cart.objects.values('id', 'user__username'))}")
            return HttpResponse("Received", status=200)

        # Step 7 — Check cart items
        items = cart.items.filter(saved_for_later=False)
        print(f"Cart items count: {items.count()}")

        for item in items:
            print(f"  Item: {item.product.name} "
                  f"x {item.quantity} "
                  f"farmer={item.product.farmer.username}")

        if not items.exists():
            print("ERROR: Cart is EMPTY — no items to process")
            return HttpResponse("Received", status=200)

        # Step 8 — Create orders
        from decimal import Decimal
        from .models import Wallet, EarningsRecord

        created_orders = []

        for item in items:
            print(f"Creating order for: {item.product.name}")

            product_amount = (
                    item.product.price_per_unit * item.quantity
            )
            print(f"  Product amount: {product_amount}")

            try:
                order = Order.objects.create(
                    product=item.product,
                    buyer=cart.user,
                    quantity=item.quantity,
                    total_price=product_amount,
                    status='pending'
                )
                print(f"  Order #{order.id} created ✅")
                created_orders.append(order)
            except Exception as e:
                print(f"  ERROR creating order: {e}")
                import traceback
                traceback.print_exc()
                continue

            try:
                Payment.objects.create(
                    order=order,
                    amount=product_amount,
                    method='mpesa',
                    status='completed',
                    phone_number=phone,
                    checkout_request_id=checkout_id
                )
                print(f"  Payment created ✅")
            except Exception as e:
                print(f"  ERROR creating payment: {e}")

            try:
                item.product.quantity -= item.quantity
                item.product.save()
                print(f"  Stock reduced ✅")
            except Exception as e:
                print(f"  ERROR reducing stock: {e}")

            try:
                Notification.objects.create(
                    user=item.product.farmer,
                    notification_type='order',
                    message=(
                        f"New order for '{item.product.name}' "
                        f"from {cart.user.username}. "
                        f"Qty: {item.quantity} {item.product.unit}. "
                        f"Please confirm."
                    )
                )
                print(f"  Farmer notified ✅")
            except Exception as e:
                print(f"  ERROR notifying farmer: {e}")

        # Step 9 — Notify buyer
        if created_orders:
            try:
                Notification.objects.create(
                    user=cart.user,
                    notification_type='payment',
                    message=(
                        f"Payment of Ksh {amount_paid} confirmed. "
                        f"Receipt: {mpesa_receipt}. "
                        f"{len(created_orders)} order(s) created."
                    )
                )
                print(f"Buyer notified ✅")
            except Exception as e:
                print(f"ERROR notifying buyer: {e}")

        # Step 10 — Clear cart
        try:
            deleted = cart.items.all().delete()
            print(f"Cart cleared ✅ — deleted: {deleted}")
        except Exception as e:
            print(f"ERROR clearing cart: {e}")

        print(f"DONE — {len(created_orders)} orders created")
        print("=" * 50 + "\n")

    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in request body: {e}")
    except Exception as e:
        print(f"UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    return HttpResponse("Received", status=200)
# ---------------------------
# AI SERVICES VIEWS
# ---------------------------
@login_required
def price_suggestions(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_farmer():
        messages.error(request, 'Access denied.')
        return redirect('home')

    products = Product.objects.filter(farmer=request.user)
    suggestions = []

    for product in products:
        # CHANGED: filter to only orders that actually completed, so
        # cancelled orders (which still carry a total_price) don't
        # skew the price recommendation.
        orders = Order.objects.filter(
            product=product,
            status__in=['confirmed', 'in_transit', 'delivered']
        )
        suggestions.append(get_price_recommendation(product, orders))
    return render(request, 'Ai_Services/price_suggestions.html', {
        'suggestions': suggestions
    })


@login_required
def product_recommendations(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_buyer():
        messages.error(request, 'Access denied.')
        return redirect('home')

    all_products = Product.objects.filter(is_available=True)
    user_orders = Order.objects.filter(buyer=request.user)

    recommendations = get_product_recommendations(
        request.user,
        all_products,
        user_orders
    )

    return render(request, 'Ai_Services/product_recommendations.html', {
        'recommendations': recommendations
    })


@login_required
def demand_forecast(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_farmer():
        messages.error(request, 'Access denied.')
        return redirect('home')

    products = Product.objects.filter(farmer=request.user)
    forecasts = []

    for product in products:
        orders = Order.objects.filter(
            product=product,
            status__in=['confirmed', 'in_transit', 'delivered']
        )
        forecasts.append(get_demand_forecast(product, orders))
    return render(request, 'Ai_Services/demand_forecast.html', {
        'forecasts': forecasts
    })

@login_required
def profile_view(request):
    profile = getattr(request.user, 'profile', None)
    return render(request, 'profile.html', {
        'profile': profile,
        'user': request.user
    })

@login_required
def notifications_view(request):
    """
    Shows all Notification records for the logged-in user.
    Also passes role-specific extra context:
    - Farmers get low_stock_products
    - Buyers get recent_orders
    - Transporters get available_jobs_count
    Marks all unread as read when page opens.
    """
    # Get all notifications for this user newest first
    user_notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')

    # Mark all unread as read in one query
    user_notifications.filter(is_read=False).update(is_read=True)

    context = {
        'notifications': user_notifications
    }

    profile = getattr(request.user, 'profile', None)

    # Add role-specific context to match template sections
    if profile and profile.is_farmer():
        context['low_stock_products'] = Product.objects.filter(
            farmer=request.user,
            quantity__lte=5
        )

    if profile and profile.is_buyer():
        context['recent_orders'] = Order.objects.filter(
            buyer=request.user
        ).select_related('product').order_by('-order_date')[:10]

    if profile and profile.is_transporter():
        context['available_jobs_count'] = TransportJob.objects.filter(
            status='Pending',
            driver__isnull=True
        ).count()

    return render(request, 'notifications.html', context)
@login_required
def payment_success(request):
    checkout_request_id = request.session.get(
        'checkout_request_id'
    )
    cart_id = request.session.get('cart_id')
    phone = request.session.get('phone')

    print(f"payment_success: checkout_id={checkout_request_id}")
    print(f"payment_success: cart_id={cart_id}")

    if not checkout_request_id or not cart_id:
        messages.warning(
            request,
            "Session expired. Check your dashboard."
        )
        return redirect('dashboard_buyer')

    # Prevent double processing
    already_processed = Order.objects.filter(
        payments__checkout_request_id=checkout_request_id
    ).exists()

    if already_processed:
        messages.info(
            request,
            "Payment already processed. "
            "Check your pending orders."
        )
        request.session.pop('checkout_request_id', None)
        request.session.pop('cart_id', None)
        request.session.pop('phone', None)
        return redirect('dashboard_buyer')

    try:
        cart = Cart.objects.get(id=cart_id)
    except Cart.DoesNotExist:
        messages.error(request, "Cart not found.")
        return redirect('dashboard_buyer')

    items = cart.items.filter(saved_for_later=False)

    if not items.exists():
        messages.warning(
            request,
            "Cart is empty. Check your dashboard."
        )
        request.session.pop('checkout_request_id', None)
        request.session.pop('cart_id', None)
        request.session.pop('phone', None)
        return redirect('dashboard_buyer')

    from decimal import Decimal
    COMMISSION_RATE = Decimal('0.10')
    created_orders = []
    total_buyer_spent = Decimal('0')

    for item in items:
        product_amount = (
            item.product.price_per_unit * item.quantity
        )

        # Create order
        order = Order.objects.create(
            product=item.product,
            buyer=request.user,
            quantity=item.quantity,
            total_price=product_amount,
            status='pending'
        )
        created_orders.append(order)
        print(f"Order #{order.id} created")

        # Create payment record
        Payment.objects.create(
            order=order,
            amount=product_amount,
            method='mpesa',
            status='completed',
            phone_number=phone,
            checkout_request_id=checkout_request_id
        )

        # Track total buyer spent
        total_buyer_spent += product_amount

        # Reduce stock
        item.product.quantity -= item.quantity
        item.product.save()

        # Notify farmer
        Notification.objects.create(
            user=item.product.farmer,
            notification_type='order',
            message=(
                f"New order received for "
                f"'{item.product.name}' "
                f"from {request.user.username}. "
                f"Quantity: {item.quantity} "
                f"{item.product.unit}. "
                f"Please confirm on your dashboard."
            )
        )

    # Notify buyer with total spent
    if created_orders:
        Notification.objects.create(
            user=request.user,
            notification_type='payment',
            message=(
                f"Payment of Ksh {total_buyer_spent} confirmed. "
                f"{len(created_orders)} order(s) placed. "
                f"Waiting for farmer confirmation."
            )
        )

    # Clear cart after all orders created
    cart.items.all().delete()
    print(f"Cart cleared. {len(created_orders)} orders created.")

    # Clear session
    request.session.pop('checkout_request_id', None)
    request.session.pop('cart_id', None)
    request.session.pop('phone', None)

    messages.success(
        request,
        f"Payment confirmed! "
        f"{len(created_orders)} order(s) placed. "
        f"Total: Ksh {total_buyer_spent}."
    )
    return redirect('dashboard_buyer')