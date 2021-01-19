from django import forms



from .models import Switch, Port, Device, Vlan

class auxForm(forms.Form):
	numbers=forms.CharField(max_length=250)


class SwitchForm(forms.ModelForm):
	class Meta:
		model = Switch
		fields = {
			'IP','username','password'
		}

class SwitchForm_without_IP(forms.ModelForm):
	class Meta:
		model = Switch
		fields = {
			'username','password',
		}

class VlanForm(forms.ModelForm):
	class Meta:
		model=Vlan
		fields={
			'vlan_name','VID'
		}

class Dev(forms.Form):
	g=[(f.id,str(f)) for f in Device.objects.all()]
	device=forms.ChoiceField(label='Select Device',choices=[(f.id,str(f)) for f in Device.objects.all()])
