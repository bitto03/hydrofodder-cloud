from rest_framework import serializers
from .models import Device, Relay, SensorReading, RelaySchedule, DeviceCommand
class RelaySerializer(serializers.ModelSerializer):
    class Meta: model=Relay; fields=['id','channel','name','desired_state','actual_state','updated_at']
class DeviceSerializer(serializers.ModelSerializer):
    relays=RelaySerializer(many=True, read_only=True); online=serializers.BooleanField(source='is_online', read_only=True)
    class Meta: model=Device; fields=['id','uid','name','firmware_version','last_seen','online','relays']
class SensorReadingSerializer(serializers.ModelSerializer):
    class Meta: model=SensorReading; fields=['temperature_c','humidity_pct','recorded_at']
    def validate_temperature_c(self,v):
        if v < -40 or v > 80: raise serializers.ValidationError('Out of accepted range')
        return v
    def validate_humidity_pct(self,v):
        if v < 0 or v > 100: raise serializers.ValidationError('Humidity must be 0..100')
        return v
class ScheduleSerializer(serializers.ModelSerializer):
    class Meta: model=RelaySchedule; fields=['id','relay','name','interval_seconds','run_seconds','start_at','enabled','next_run_at']
class CommandSerializer(serializers.ModelSerializer):
    class Meta: model=DeviceCommand; fields=['id','relay','requested_state','status','created_at','acknowledged_at','error_message']
