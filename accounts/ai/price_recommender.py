import numpy as np
from decimal import Decimal


def get_price_recommendation(product, orders):
    """
    Takes a Product instance and its related OrderQuerySet.
    Returns a dict with recommended price and message.
    """
    order_list = list(orders.values('total_price', 'quantity'))

    if len(order_list) < 3:
        return {
            'product': product,
            'recommended_price': float(product.price_per_unit),
            'current_price': float(product.price_per_unit),
            'message': 'Not enough sales data yet. Showing current price.',
            'confidence': 'Low',
        }

    # Calculate average price per unit from past orders
    prices = []
    for o in order_list:
        if o['quantity'] and o['quantity'] > 0:
            unit_price = float(o['total_price']) / float(o['quantity'])
            prices.append(unit_price)

    if not prices:
        return {
            'product': product,
            'recommended_price': float(product.price_per_unit),
            'current_price': float(product.price_per_unit),
            'message': 'Could not calculate recommendation.',
            'confidence': 'Low',
        }

    total_revenue = sum(float(o['total_price']) for o in order_list)
    total_quantity = sum(float(o['quantity']) for o in order_list if o['quantity'])
    avg_price = total_revenue / total_quantity if total_quantity else np.mean(prices)
    std_price = np.std(prices)

    # Recommend slightly above average if std is low (stable demand)
    if std_price < avg_price * 0.1:
        recommended = avg_price * 1.05  # 5% above average
        message = 'Demand is stable. You can slightly increase your price.'
        confidence = 'High'
    elif std_price < avg_price * 0.2:
        recommended = avg_price
        message = 'Moderate demand variation. Recommended price matches market average.'
        confidence = 'Medium'
    else:
        recommended = avg_price * 0.95  # 5% below average
        message = 'High price variation detected. Consider lowering price to attract buyers.'
        confidence = 'Low'

    return {
        'product': product,
        'recommended_price': round(recommended, 2),
        'current_price': float(product.price_per_unit),
        'message': message,
        'confidence': confidence,
    }