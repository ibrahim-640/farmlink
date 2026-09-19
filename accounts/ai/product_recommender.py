def get_product_recommendations(user, all_products, user_orders):
    """
    Takes the current buyer user, all available products,
    and the buyer's past orders.
    Returns a list of recommended products.
    """
    # Get product ids the buyer has already ordered
    ordered_ids = user_orders.values_list('product_id', flat=True)

    # Get categories the buyer has ordered from
    ordered_categories = all_products.filter(
        id__in=ordered_ids
    ).values_list('category', flat=True).distinct()

    # Recommend products from same categories not yet ordered
    recommendations = all_products.filter(
        is_available=True,
        category__in=ordered_categories
    ).exclude(
        id__in=ordered_ids
    ).order_by('-created_at')

    # If no history, just return latest available products
    if not recommendations.exists():
        recommendations = all_products.filter(
            is_available=True
        ).order_by('-created_at')[:6]

    return recommendations[:6]