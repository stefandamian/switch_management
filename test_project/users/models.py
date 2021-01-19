from django.db import models

from django.contrib.auth.models import AbstractUser
from django.db import models
from switches.models import Switch

class CustomUser(AbstractUser):
	switches=models.ManyToManyField(Switch)
	

