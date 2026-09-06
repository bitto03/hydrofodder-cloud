import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hydrofodder.settings')
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
import iot.routing

django_asgi_app = get_asgi_application()
application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(URLRouter(iot.routing.websocket_urlpatterns)),
})
