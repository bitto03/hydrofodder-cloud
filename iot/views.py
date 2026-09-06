import json
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .authentication import DeviceTokenAuthentication
from .forms import DeviceForm, RelayScheduleForm
from .models import Device, DeviceCredential, Relay, SensorReading, DeviceCommand, RelaySchedule, DeviceEvent
from .serializers import DeviceSerializer, SensorReadingSerializer, CommandSerializer


def _broadcast(device, payload):
    async_to_sync(get_channel_layer().group_send)(f'device_{device.id}', {'type':'device.message','payload':payload})

@login_required
def dashboard(request):
    devices = request.user.devices.prefetch_related('relays').order_by('name')
    selected = None
    if devices:
        selected_id = request.GET.get('device')
        selected = get_object_or_404(devices, id=selected_id) if selected_id else devices[0]
    latest = selected.sensor_readings.first() if selected else None
    schedules = selected.schedules.select_related('relay').order_by('relay__channel') if selected else []
    return render(request, 'iot/dashboard.html', {'devices':devices,'device':selected,'latest':latest,'schedules':schedules})

@login_required
def add_device(request):
    token=None
    if request.method=='POST':
        form=DeviceForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                device=form.save(commit=False); device.owner=request.user; device.save()
                Relay.objects.bulk_create([Relay(device=device, channel=i, name=f'Relay {i}') for i in range(1,5)])
                token=DeviceCredential.issue_for(device)
                DeviceEvent.objects.create(device=device,event_type='device_registered',message='Device registered by owner')
            return render(request,'iot/device_created.html',{'device':device,'token':token})
    else: form=DeviceForm()
    return render(request,'iot/add_device.html',{'form':form})

@login_required
def add_schedule(request, device_id):
    device=get_object_or_404(Device,id=device_id,owner=request.user)
    if request.method=='POST':
        form=RelayScheduleForm(request.POST,device=device)
        if form.is_valid():
            schedule=form.save(commit=False); schedule.device=device; schedule.next_run_at=schedule.start_at; schedule.save()
            messages.success(request,'Schedule saved.')
            return redirect(f'/?device={device.id}')
    else: form=RelayScheduleForm(device=device)
    return render(request,'iot/add_schedule.html',{'device':device,'form':form})

@login_required
@require_POST
def relay_command(request, device_id, channel):
    device=get_object_or_404(Device,id=device_id,owner=request.user,is_enabled=True)
    relay=get_object_or_404(Relay,device=device,channel=channel)
    try: body=json.loads(request.body or '{}'); desired=body['state']; assert isinstance(desired,bool)
    except Exception: return JsonResponse({'detail':'JSON body must contain boolean state'},status=400)
    relay.desired_state=desired; relay.save(update_fields=['desired_state','updated_at'])
    cmd=DeviceCommand.objects.create(device=device,relay=relay,requested_state=desired,requested_by=request.user)
    DeviceEvent.objects.create(device=device,event_type='relay_command_created',message=f'Relay {channel} desired={desired} command={cmd.id}')
    _broadcast(device,{'kind':'command','command_id':str(cmd.id),'channel':channel,'desired_state':desired,'status':cmd.status})
    return JsonResponse(CommandSerializer(cmd).data,status=202)

@api_view(['POST'])
@authentication_classes([DeviceTokenAuthentication])
@permission_classes([AllowAny])
def device_heartbeat(request):
    device=request.user.device
    device.last_seen=timezone.now(); device.firmware_version=str(request.data.get('firmware_version',''))[:40]; device.save(update_fields=['last_seen','firmware_version','updated_at'])
    _broadcast(device,{'kind':'status','online':True,'last_seen':device.last_seen.isoformat()})
    return Response({'ok':True,'server_time':timezone.now()})

@api_view(['POST'])
@authentication_classes([DeviceTokenAuthentication])
@permission_classes([AllowAny])
def device_telemetry(request):
    device=request.user.device
    serializer=SensorReadingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    reading=serializer.save(device=device)
    device.last_seen=timezone.now(); device.save(update_fields=['last_seen','updated_at'])
    _broadcast(device,{'kind':'telemetry','temperature_c':float(reading.temperature_c),'humidity_pct':float(reading.humidity_pct),'recorded_at':reading.recorded_at.isoformat()})
    return Response({'ok':True},status=201)

@api_view(['GET'])
@authentication_classes([DeviceTokenAuthentication])
@permission_classes([AllowAny])
def device_commands(request):
    device=request.user.device
    cmds=device.commands.filter(status=DeviceCommand.Status.PENDING).select_related('relay').order_by('created_at')[:20]
    data=[{'id':str(c.id),'relay_channel':c.relay.channel,'state':c.requested_state,'created_at':c.created_at} for c in cmds]
    return Response({'commands':data})

@api_view(['POST'])
@authentication_classes([DeviceTokenAuthentication])
@permission_classes([AllowAny])
def device_ack(request, command_id):
    device=request.user.device
    cmd=get_object_or_404(DeviceCommand,id=command_id,device=device)
    actual=request.data.get('actual_state')
    if not isinstance(actual,bool): return Response({'detail':'actual_state must be boolean'},status=400)
    success=bool(request.data.get('success',True))
    cmd.status=DeviceCommand.Status.ACK if success else DeviceCommand.Status.FAILED
    cmd.acknowledged_at=timezone.now(); cmd.error_message=str(request.data.get('error',''))[:255]; cmd.save(update_fields=['status','acknowledged_at','error_message'])
    cmd.relay.actual_state=actual; cmd.relay.save(update_fields=['actual_state','updated_at'])
    device.last_seen=timezone.now(); device.save(update_fields=['last_seen','updated_at'])
    _broadcast(device,{'kind':'relay_state','command_id':str(cmd.id),'channel':cmd.relay.channel,'desired_state':cmd.relay.desired_state,'actual_state':actual,'status':cmd.status})
    return Response(CommandSerializer(cmd).data)
