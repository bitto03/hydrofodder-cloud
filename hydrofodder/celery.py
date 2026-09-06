import os
from celery import Celery
from celery.schedules import crontab
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hydrofodder.settings')
app = Celery('hydrofodder')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.conf.beat_schedule = {'scan-due-schedules': {'task': 'iot.tasks.enqueue_due_schedules', 'schedule': 5.0}}
