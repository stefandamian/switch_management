from django.contrib import admin
from django.urls import path, include
from . import views

app_name='users'
from switches import views as views_switches
from users import views as views_user

urlpatterns = [
	path('switches/', include('switches.urls')),
	path('', views_user.my_login, name="login" ),
	path('register/', views_user.register, name="register")
]