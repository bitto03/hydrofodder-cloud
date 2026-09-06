from django import forms
from .models import Device, RelaySchedule
class DeviceForm(forms.ModelForm):
    class Meta: model=Device; fields=['name']
class RelayScheduleForm(forms.ModelForm):
    class Meta:
        model=RelaySchedule
        fields=['relay','name','interval_seconds','run_seconds','start_at','enabled']
        widgets={'start_at': forms.DateTimeInput(attrs={'type':'datetime-local'})}
    def __init__(self,*args,device=None,**kwargs):
        super().__init__(*args,**kwargs)
        if device: self.fields['relay'].queryset=device.relays.all()
