from .models import Notification
from django.conf import settings

def notification_count(request):
    """
    Makes unread_count available in every template automatically.
    This is how the badge shows on every page without
    manually passing it in every view.
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
    else:
        unread_count = 0

    return {'unread_count': unread_count,
            # Make Google Maps key available in all templates
            'google_maps_key': settings.GOOGLE_MAPS_API_KEY,
            }