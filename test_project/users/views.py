from django.shortcuts import render
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.contrib.auth import authenticate,login, logout
from users.forms import CustomUserCreationForm, CustomUserChangeForm, UserForm
from users.models import CustomUser
from switches.models import Switch
from switches.views import index
import time
# Create your views here.


def my_login(request):
	form=UserForm(request.POST or None)
	context={
		'form':form,
		'error':''
	}
	logout(request)
	if form['username'].value() in [u.username for u in CustomUser.objects.all()]:
		my_user=CustomUser.objects.get(username=form['username'].value())
		if my_user.check_password(form['password'].value()):
			user=authenticate(username=my_user.username,password=form['password'].value())
			if user:
				login(request,user)
				return HttpResponseRedirect('/switches')
		else:
			context['error']='wrong_password'
	else:
		if form['username'].value():
			context['error']='wrong_username'
	return render(request,'switches/user_login.html',context)


def register(request):
	form=CustomUserCreationForm(request.POST or None)
	context={
		'form':form,
		'error':'',
	}
	if form['username'].value() in [u.username for u in CustomUser.objects.all()]:
		context['error']='username_used'
		return render(request, 'switches/user_add.html', context)
	if form['username'].value() and form['password1'].value() and form['password2'].value():
		print('true')
		print(form['password1'].value())
		print(form['password2'].value())
		if form['password1'].value()==form['password2'].value():
			my_user=CustomUser(username=form['username'].value())
			my_user.set_password(form['password1'].value())
			my_user.save()
			return HttpResponseRedirect('/')
		else:
			context['error']='conf_password_error'
		print(context['error'])

	return render(request, 'switches/user_add.html', context)

def my_logout(request):
	print('logging out',request.user)
	logout(request)
	return HttpResponseRedirect('/')