import hashlib, secrets, uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class Device(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=120)
    firmware_version = models.CharField(max_length=40, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True, db_index=True)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [models.Index(fields=['owner','created_at'])]
    @property
    def is_online(self):
        if not self.last_seen: return False
        return (timezone.now() - self.last_seen).total_seconds() <= settings.DEVICE_OFFLINE_SECONDS
    def __str__(self): return f'{self.name} ({self.uid})'

class DeviceCredential(models.Model):
    device = models.OneToOneField(Device, on_delete=models.CASCADE, related_name='credential')
    token_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    @staticmethod
    def hash_token(token): return hashlib.sha256(token.encode()).hexdigest()
    @classmethod
    def issue_for(cls, device):
        token = secrets.token_urlsafe(32)
        obj, _ = cls.objects.update_or_create(device=device, defaults={'token_hash': cls.hash_token(token), 'rotated_at': timezone.now()})
        return token
    def verify(self, token): return secrets.compare_digest(self.token_hash, self.hash_token(token))

class Relay(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='relays')
    channel = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=80)
    desired_state = models.BooleanField(default=False)
    actual_state = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['device','channel'], name='uniq_device_relay_channel'), models.CheckConstraint(condition=models.Q(channel__gte=1, channel__lte=4), name='relay_channel_1_4')]
        ordering=['channel']

class SensorReading(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='sensor_readings')
    temperature_c = models.DecimalField(max_digits=5, decimal_places=2)
    humidity_pct = models.DecimalField(max_digits=5, decimal_places=2)
    recorded_at = models.DateTimeField(db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes=[models.Index(fields=['device','-recorded_at'])]
        ordering=['-recorded_at']

class DeviceCommand(models.Model):
    class Status(models.TextChoices):
        PENDING='pending','Pending'; SENT='sent','Sent'; ACK='ack','Acknowledged'; FAILED='failed','Failed'; EXPIRED='expired','Expired'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='commands')
    relay = models.ForeignKey(Relay, on_delete=models.CASCADE, related_name='commands')
    requested_state = models.BooleanField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    class Meta:
        indexes=[models.Index(fields=['device','status','created_at'])]

class RelaySchedule(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='schedules')
    relay = models.ForeignKey(Relay, on_delete=models.CASCADE, related_name='schedules')
    name = models.CharField(max_length=100, blank=True)
    interval_seconds = models.PositiveIntegerField(help_text='Repeat interval in seconds')
    run_seconds = models.PositiveIntegerField(help_text='Relay ON duration in seconds')
    start_at = models.DateTimeField()
    enabled = models.BooleanField(default=True)
    next_run_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes=[models.Index(fields=['enabled','next_run_at'])]

class DeviceEvent(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='events')
    level = models.CharField(max_length=12, default='INFO')
    event_type = models.CharField(max_length=60, db_index=True)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
