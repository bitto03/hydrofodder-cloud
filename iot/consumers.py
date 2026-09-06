from channels.generic.websocket import AsyncJsonWebsocketConsumer
from .models import Device
from channels.db import database_sync_to_async
class DeviceConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user=self.scope['user']; self.device_id=self.scope['url_route']['kwargs']['device_id']
        if not user.is_authenticated or not await self.owns_device(user.id,self.device_id):
            await self.close(code=4403); return
        self.group=f'device_{self.device_id}'
        await self.channel_layer.group_add(self.group,self.channel_name); await self.accept()
    async def disconnect(self,code):
        if hasattr(self,'group'): await self.channel_layer.group_discard(self.group,self.channel_name)
    async def device_message(self,event): await self.send_json(event['payload'])
    @database_sync_to_async
    def owns_device(self,user_id,device_id): return Device.objects.filter(id=device_id,owner_id=user_id).exists()
