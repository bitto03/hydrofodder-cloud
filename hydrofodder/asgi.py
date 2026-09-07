import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application


os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "hydrofodder.settings",
)

# IMPORTANT:
# Initialize Django BEFORE importing iot.routing.
# iot.routing imports consumers, and consumers import Django models.
django_asgi_app = get_asgi_application()

# Import routing only after Django's app registry is ready.
import iot.routing


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,

        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(
                    iot.routing.websocket_urlpatterns
                )
            )
        ),
    }
)
