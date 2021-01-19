from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ['username','is_active','is_superuser']
    fieldsets=((None, {'fields':('is_active','username','password','is_superuser')}),('Other', {'fields':('email','switches')}))
    search_fields =['username']
    list_filter=['is_superuser','is_active']
    ordering=['is_superuser','is_active','username']
    
admin.site.register(CustomUser, CustomUserAdmin)
