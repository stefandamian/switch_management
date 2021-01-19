from django.db import models

# Create your models here.


class Switch_type(models.Model):
	device_type=models.CharField(max_length=35,default='extreme_exos',unique=True)
	def __str__(self):
		return str(self.device_type)


class Device(models.Model):
	switch_type=models.ForeignKey(Switch_type, on_delete=models.CASCADE)
	company_name=models.CharField(max_length=35, default='Extreme networks')
	device_name=models.CharField(max_length=35,default='X450-G2')
	def type(self):
		return str(self.switch_type)
	def __str__(self):
		return ' '.join([str(self.company_name),str(self.device_name)])

class Switch(models.Model):
	IP=models.GenericIPAddressField(protocol='IPv4', unique=True)
	device=models.ForeignKey(Device, on_delete=models.CASCADE,null=True)
	username=models.CharField(max_length=25)
	password=models.CharField(max_length=25)
	ports_number=models.PositiveSmallIntegerField(default=0)
	def __str__(self):
		return str(self.IP)
	def device_name(self):
		return str(Device.objects.get(id=self.device.id))
	def device_type(self):
		return self.device.type()

class Vlan(models.Model):
	switch=models.ForeignKey(Switch, on_delete=models.CASCADE)
	vlan_name=models.CharField(max_length=35)
	VID=models.PositiveSmallIntegerField(null=True)
	def __str__(self):
		return str(self.vlan_name)

class Port(models.Model):
	switch=models.ForeignKey(Switch, on_delete=models.CASCADE)
	vlan=models.CharField(max_length=35, default='No Vlan')
	number=models.PositiveSmallIntegerField()
	port_state=models.BooleanField()
	link_state=models.BooleanField()
	speed=models.PositiveSmallIntegerField(default=100)
	duplex=models.CharField(max_length=10)
	tag=models.BooleanField(default=0)
	def __str__(self):
		return str(self.switch)+', port '+str(self.number)
	def set(self):
		return self.number%2


