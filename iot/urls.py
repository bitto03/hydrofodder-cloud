from django.urls import path
from . import views
urlpatterns=[
    path('',views.dashboard,name='dashboard'),
    path('devices/add/',views.add_device,name='add_device'),
    path('devices/<int:device_id>/schedules/add/',views.add_schedule,name='add_schedule'),
    path('api/devices/<int:device_id>/relays/<int:channel>/command/',views.relay_command,name='relay_command'),
    path('api/device/heartbeat/',views.device_heartbeat),
    path('api/device/telemetry/',views.device_telemetry),
    path('api/device/commands/',views.device_commands),
    path('api/device/commands/<uuid:command_id>/ack/',views.device_ack),
]
