from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from .models import RelaySchedule, DeviceCommand, DeviceEvent, Relay

@shared_task
def turn_relay_off(relay_id):
    relay=Relay.objects.select_related('device').get(id=relay_id)
    relay.desired_state=False; relay.save(update_fields=['desired_state','updated_at'])
    DeviceCommand.objects.create(device=relay.device,relay=relay,requested_state=False)
    DeviceEvent.objects.create(device=relay.device,event_type='schedule_off',message=f'Relay {relay.channel} OFF queued')

@shared_task
def enqueue_due_schedules():
    now=timezone.now(); count=0
    for s in RelaySchedule.objects.select_related('relay','device').filter(enabled=True,next_run_at__lte=now)[:500]:
        s.relay.desired_state=True; s.relay.save(update_fields=['desired_state','updated_at'])
        DeviceCommand.objects.create(device=s.device,relay=s.relay,requested_state=True)
        DeviceEvent.objects.create(device=s.device,event_type='schedule_due',message=f'Schedule {s.id} queued relay ON')
        turn_relay_off.apply_async(args=[s.relay_id], countdown=s.run_seconds)
        s.next_run_at=now+timedelta(seconds=s.interval_seconds); s.save(update_fields=['next_run_at','updated_at']); count+=1
    return count
