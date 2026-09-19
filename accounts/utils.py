import requests
from django.conf import settings
from decimal import Decimal

# ---------------------------
# URGENCY BASE RATES (Ksh)
# ---------------------------
URGENCY_RATES = {
    'high':   Decimal('500'),
    'medium': Decimal('300'),
    'low':    Decimal('150'),
}

# ---------------------------
# MINIMUM FEES PER URGENCY
# ---------------------------
MINIMUM_FEES = {
    'high':   Decimal('300'),
    'medium': Decimal('200'),
    'low':    Decimal('100'),
}

# ---------------------------
# DISTANCE MULTIPLIERS
# ---------------------------
DISTANCE_MULTIPLIERS = [
    (0,    20,   Decimal('1.0')),
    (21,   50,   Decimal('1.5')),
    (51,   100,  Decimal('2.0')),
    (101,  9999, Decimal('3.0')),
]

# ---------------------------
# FARMLINK COMMISSION RATE
# ---------------------------
COMMISSION_RATE = Decimal('0.10')

# ---------------------------
# CATEGORY → DEFAULT URGENCY
# ---------------------------
CATEGORY_URGENCY = {
    'dairy':      'high',
    'poultry':    'high',
    'vegetables': 'medium',
    'fruits':     'medium',
    'grains':     'low',
    'other':      'medium',
}

# ---------------------------
# URGENCY WARNING MESSAGES
# ---------------------------
URGENCY_WARNINGS = {
    'dairy': (
        "⚠️ Dairy products spoil quickly. "
        "High urgency is strongly recommended."
    ),
    'poultry': (
        "⚠️ Poultry products are highly perishable. "
        "High urgency is strongly recommended."
    ),
    'vegetables': (
        "⚠️ Vegetables have a short shelf life. "
        "Medium or High urgency is recommended."
    ),
    'fruits': (
        "⚠️ Fruits can spoil quickly. "
        "Medium or High urgency is recommended."
    ),
    'grains': None,  # grains are not perishable — no warning
    'other': None,
}

# ---------------------------
# URGENCY DISPLAY LABELS
# ---------------------------
URGENCY_LABELS = {
    'high':   '🔴 High — Immediate pickup',
    'medium': '🟡 Medium — Within 24 hours',
    'low':    '🟢 Low — Flexible timing',
}


def get_recommended_urgency(category):
    """
    Returns the recommended urgency level
    based on product category.
    """
    return CATEGORY_URGENCY.get(category, 'medium')


def get_urgency_warning(category, selected_urgency):
    """
    Returns a warning message if the selected urgency
    is lower than recommended for this product category.
    Returns None if no warning needed.
    """
    recommended = get_recommended_urgency(category)

    # Define urgency priority
    priority = {'high': 3, 'medium': 2, 'low': 1}

    recommended_priority = priority.get(recommended, 2)
    selected_priority = priority.get(selected_urgency, 2)

    # Only warn if selected is LOWER than recommended
    if selected_priority < recommended_priority:
        return URGENCY_WARNINGS.get(category)

    return None


def get_distance_km(pickup_location, delivery_location):
    """
    Uses Google Maps Distance Matrix API to get
    real driving distance between two locations.
    Returns distance in km as float, or None if fails.
    """
    api_key = settings.GOOGLE_MAPS_API_KEY

    if not api_key:
        print("ERROR: GOOGLE_MAPS_API_KEY not set in settings")
        return None

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"

    params = {
        'origins': pickup_location,
        'destinations': delivery_location,
        'key': api_key,
        'units': 'metric',
        'region': 'ke',  # Kenya region bias
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data['status'] != 'OK':
            print(f"API error: {data['status']}")
            return None

        element = data['rows'][0]['elements'][0]

        if element['status'] != 'OK':
            print(f"Route error: {element['status']}")
            return None

        distance_meters = element['distance']['value']
        distance_km = distance_meters / 1000

        return distance_km

    except requests.exceptions.Timeout:
        print("Google Maps API request timed out")
        return None
    except Exception as e:
        print(f"Google Maps API error: {e}")
        return None


def get_distance_multiplier(distance_km):
    """
    Returns fee multiplier based on distance.
    """
    for min_km, max_km, multiplier in DISTANCE_MULTIPLIERS:
        if min_km <= distance_km <= max_km:
            return multiplier
    return Decimal('3.0')


def calculate_transport_fee(pickup_location,
                            delivery_location,
                            urgency):
    """
    Calculates transport fee using:
    - Google Maps real distance
    - Urgency base rate
    - Distance multiplier
    - Minimum fee enforcement

    Returns dict with full breakdown.
    """
    base_rate = URGENCY_RATES.get(urgency, URGENCY_RATES['medium'])
    minimum_fee = MINIMUM_FEES.get(urgency, MINIMUM_FEES['medium'])

    # Get real distance from Google Maps
    distance_km = get_distance_km(pickup_location, delivery_location)

    if distance_km is None:
        # Google Maps failed — use base rate × 1.5 as estimate
        estimated_fee = base_rate * Decimal('1.5')
        # Apply minimum fee
        final_fee = max(estimated_fee, minimum_fee)
        return {
            'transport_fee': final_fee,
            'distance_km': None,
            'base_rate': base_rate,
            'multiplier': Decimal('1.5'),
            'minimum_fee': minimum_fee,
            'minimum_applied': final_fee == minimum_fee,
            'error': (
                'Could not calculate distance — '
                'estimated fee used'
            )
        }

    multiplier = get_distance_multiplier(distance_km)
    calculated_fee = base_rate * multiplier

    # Apply minimum fee
    final_fee = max(calculated_fee, minimum_fee)
    minimum_applied = final_fee == minimum_fee and (
        final_fee > calculated_fee
    )

    return {
        'transport_fee': final_fee,
        'distance_km': round(distance_km, 1),
        'base_rate': base_rate,
        'multiplier': multiplier,
        'minimum_fee': minimum_fee,
        'minimum_applied': minimum_applied,
        'error': None
    }


def calculate_order_total(product_subtotal,
                          transport_fee):
    """
    Calculates full order breakdown with
    FarmLink 10% commission on everything.
    """
    product_subtotal = Decimal(str(product_subtotal))
    transport_fee = Decimal(str(transport_fee))

    subtotal = product_subtotal + transport_fee
    commission = subtotal * COMMISSION_RATE
    grand_total = subtotal + commission

    return {
        'product_subtotal': product_subtotal,
        'transport_fee': transport_fee,
        'commission': commission,
        'grand_total': grand_total,
    }