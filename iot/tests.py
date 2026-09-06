from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from .models import Device, DeviceCredential, Relay, DeviceCommand
class OwnershipAndDeviceApiTests(TestCase):
    def setUp(self):
        self.u1=User.objects.create_user(email='a@example.com',password='StrongPass123!')
        self.u2=User.objects.create_user(email='b@example.com',password='StrongPass123!')
        self.d=Device.objects.create(owner=self.u1,name='Unit A')
        for i in range(1,5): Relay.objects.create(device=self.d,channel=i,name=f'Relay {i}')
        self.token=DeviceCredential.issue_for(self.d)
    def test_other_user_cannot_command_device(self):
        c=Client(); c.force_login(self.u2)
        r=c.post(reverse('relay_command',args=[self.d.id,1]),data='{"state":true}',content_type='application/json')
        self.assertEqual(r.status_code,404)
    def test_owner_command_creates_pending_and_desired_state(self):
        c=Client(); c.force_login(self.u1)
        r=c.post(reverse('relay_command',args=[self.d.id,1]),data='{"state":true}',content_type='application/json')
        self.assertEqual(r.status_code,202); self.assertTrue(self.d.relays.get(channel=1).desired_state); self.assertEqual(DeviceCommand.objects.count(),1)
    def test_device_auth_and_telemetry(self):
        c=Client(); h={'HTTP_X_DEVICE_UID':str(self.d.uid),'HTTP_X_DEVICE_TOKEN':self.token}
        r=c.post('/api/device/telemetry/',data='{"temperature_c":28.4,"humidity_pct":72.5,"recorded_at":"2026-09-06T00:00:00Z"}',content_type='application/json',**h)
        self.assertEqual(r.status_code,201); self.assertEqual(self.d.sensor_readings.count(),1)
