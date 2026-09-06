import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Device', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('uid', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
            ('name', models.CharField(max_length=120)), ('firmware_version', models.CharField(blank=True, max_length=40)),
            ('last_seen', models.DateTimeField(blank=True, db_index=True, null=True)), ('is_enabled', models.BooleanField(default=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='devices', to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='DeviceCredential', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('token_hash', models.CharField(max_length=64)), ('created_at', models.DateTimeField(auto_now_add=True)), ('rotated_at', models.DateTimeField(blank=True, null=True)),
            ('device', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='credential', to='iot.device')),
        ]),
        migrations.CreateModel(name='Relay', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('channel', models.PositiveSmallIntegerField()), ('name', models.CharField(max_length=80)), ('desired_state', models.BooleanField(default=False)), ('actual_state', models.BooleanField(default=False)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relays', to='iot.device')),
        ], options={'ordering':['channel']}),
        migrations.CreateModel(name='SensorReading', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('temperature_c', models.DecimalField(decimal_places=2, max_digits=5)), ('humidity_pct', models.DecimalField(decimal_places=2, max_digits=5)),
            ('recorded_at', models.DateTimeField(db_index=True)), ('received_at', models.DateTimeField(auto_now_add=True)),
            ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sensor_readings', to='iot.device')),
        ], options={'ordering':['-recorded_at']}),
        migrations.CreateModel(name='DeviceCommand', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('requested_state', models.BooleanField()), ('status', models.CharField(choices=[('pending','Pending'),('sent','Sent'),('ack','Acknowledged'),('failed','Failed'),('expired','Expired')], db_index=True, default='pending', max_length=16)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('acknowledged_at', models.DateTimeField(blank=True, null=True)), ('error_message', models.CharField(blank=True, max_length=255)),
            ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commands', to='iot.device')),
            ('relay', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commands', to='iot.relay')),
            ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='RelaySchedule', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(blank=True, max_length=100)), ('interval_seconds', models.PositiveIntegerField(help_text='Repeat interval in seconds')), ('run_seconds', models.PositiveIntegerField(help_text='Relay ON duration in seconds')),
            ('start_at', models.DateTimeField()), ('enabled', models.BooleanField(default=True)), ('next_run_at', models.DateTimeField(db_index=True)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='iot.device')),
            ('relay', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='iot.relay')),
        ]),
        migrations.CreateModel(name='DeviceEvent', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('level', models.CharField(default='INFO', max_length=12)), ('event_type', models.CharField(db_index=True, max_length=60)), ('message', models.CharField(max_length=255)), ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='iot.device')),
        ]),
        migrations.AddConstraint(model_name='relay', constraint=models.UniqueConstraint(fields=('device','channel'), name='uniq_device_relay_channel')),
        migrations.AddConstraint(model_name='relay', constraint=models.CheckConstraint(condition=models.Q(('channel__gte',1),('channel__lte',4)), name='relay_channel_1_4')),
        migrations.AddIndex(model_name='device', index=models.Index(fields=['owner','created_at'], name='iot_device_owner_i_0c598e_idx')),
        migrations.AddIndex(model_name='sensorreading', index=models.Index(fields=['device','-recorded_at'], name='iot_sensor_device__2ef4a0_idx')),
        migrations.AddIndex(model_name='devicecommand', index=models.Index(fields=['device','status','created_at'], name='iot_device_device__307943_idx')),
        migrations.AddIndex(model_name='relayschedule', index=models.Index(fields=['enabled','next_run_at'], name='iot_relaysc_enabled_8e2660_idx')),
    ]
