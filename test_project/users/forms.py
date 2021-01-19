from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):

    class Meta(UserCreationForm):
        model = CustomUser
        fields = ('username','switches','email','password')

class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = CustomUser
        fields = {'username', 'email','switches','password'}

class UserForm(forms.ModelForm):
	class Meta:
		model=CustomUser
		fields={
		'username','password'
		}

		
class UserFormSwitch(forms.ModelForm):
	class Meta:
		model=CustomUser
		fields={
			'switches'
		}
class confirm_pass(forms.Form):
	confirm_pass=forms.CharField(label='Confirm password',max_length=25)
