import pandas as pd
import numpy as np
from django.utils import timezone
from datetime import timedelta


def get_demand_forecast(product, orders):
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_orders = orders.filter(order_date__gte=thirty_days_ago)
    order_list = list(recent_orders.values('order_date', 'quantity'))

    if len(order_list) < 3:
        return {
            'product': product, 'forecast': 0, 'period': 'Next 7 days',
            'message': 'Not enough order history to generate forecast.',
            'confidence': 'Low',
        }

    df = pd.DataFrame(order_list)
    df['order_date'] = pd.to_datetime(df['order_date']).dt.date

    # Collapse multiple same-day orders into one daily total, THEN lay
    # that out on a real, gap-free calendar axis (zero-fill missing days).
    daily = df.groupby('order_date')['quantity'].sum()
    full_range = pd.date_range(daily.index.min(), timezone.now().date(), freq='D').date
    daily = daily.reindex(full_range, fill_value=0).astype(float)

    # Now index position IS calendar day, correctly spaced.
    x = np.arange(len(daily))
    y = daily.values
    slope, intercept = np.polyfit(x, y, 1)

    future_x = np.arange(len(daily), len(daily) + 7)
    forecast_values = np.maximum(slope * future_x + intercept, 0)
    total_forecast = round(float(forecast_values.sum()), 2)

    # Confidence from fit quality (R²), not just raw order count --
    # a product with 15 orders scattered wildly is a worse forecast
    # than one with 6 orders following a clean trend.
    residuals = y - (slope * x + intercept)
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    if r_squared >= 0.5 and len(order_list) >= 10:
        confidence = 'High'
    elif r_squared >= 0.2 and len(order_list) >= 5:
        confidence = 'Medium'
    else:
        confidence = 'Low'

    return {
        'product': product,
        'forecast': total_forecast,
        'period': 'Next 7 days',
        'message': f'Expected demand for {product.name} over the next 7 days.',
        'confidence': confidence,
    }