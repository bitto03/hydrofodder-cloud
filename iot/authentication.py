from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Device
class DevicePrincipal:
    def __init__(self, device): self.device=device; self.is_authenticated=True
class DeviceTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        uid=request.headers.get('X-Device-UID'); token=request.headers.get('X-Device-Token')
        if not uid or not token: raise AuthenticationFailed('Device credentials required')
        try: device=Device.objects.select_related('credential').get(uid=uid, is_enabled=True)
        except Device.DoesNotExist: raise AuthenticationFailed('Invalid device')
        if not hasattr(device,'credential') or not device.credential.verify(token): raise AuthenticationFailed('Invalid device credential')
        return (DevicePrincipal(device), None)
