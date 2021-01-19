
from django.shortcuts import render
from django.http import HttpResponse, Http404, HttpResponseRedirect, JsonResponse
from .models import Switch, Port, Switch_type, Device, Vlan
from users.models import CustomUser
from django.urls import reverse
from .forms import SwitchForm, SwitchForm_without_IP, Dev, VlanForm, auxForm
from netmiko import ssh_exception, ConnectHandler
import paramiko
import re
import os
import json
import subprocess
import sys

from django.contrib.auth import authenticate,login, logout

# Create your views here.

def index(request,context={}):
	print(request.user)
	if request.user.is_authenticated:
		context={
			'switches':request.user.switches.all()
		}
		print(request.user.switches.all())
		return render(request, 'switches/index.html', context)
	else:
		return HttpResponseRedirect('/')

def add_switch(request):
	print(request.user)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	form=SwitchForm(request.POST or None)
	form_dev=Dev(request.POST or None)
	context={'form':form,'form_dev':form_dev,'error':''}
	if form['IP'].value() and form['username'].value() and form['password'].value():
		try:
			search=Switch.objects.get(IP=form['IP'].value())
			if search:
				if not search in request.user.switches.all():
					if search.username==form['username'].value() and search.password==form['password'].value() and search.device==Device.objects.get(id=int(form_dev['device'].value())):
						request.user.switches.add(search)
						return HttpResponseRedirect('/switches/')
		except:
			pass

	if form['IP'].value() and form['username'].value() and form_dev.is_valid():
		if form['password'].value()=="":
			the_switch=Switch(username=form['username'].value(),password="",IP=form['IP'].value())
		else:
			form.save()
			the_switch=Switch.objects.get(IP=form['IP'].value())
		context['switch']=the_switch
		the_switch.device=Device.objects.get(id=int(form_dev['device'].value()))
		the_switch.save()
		request.user.switches.add(the_switch)
		admin_user=CustomUser.objects.get(username='admin')
		admin_user.switches.set(Switch.objects.all())
		return HttpResponseRedirect('/switches/')
	return render(request, 'switches/switch_add.html',context)

def detail(request, Switch_id, context={}):
	print(request.user)
	if not request.user.is_authenticated:	
		return HttpResponseRedirect('/')
	try:
		the_switch=Switch.objects.get(id=Switch_id)
	except:
		return HttpResponseRedirect('/')
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	ports=Port.objects.filter(switch_id=Switch_id)
	ports=ports.order_by('number')
	vlans=Vlan.objects.filter(switch_id=Switch_id)
	
	ports_vlan={}
	ports_state={'up':[],'down':[],'admin_down':[]}
	ports_duplex={'NONE':[],'FULL':[],'HALF':[]}
	#
	for port in ports:
		if port.vlan in ports_vlan.keys():
			ports_vlan[port.vlan].append(port.number)
		else:
			ports_vlan[port.vlan]=[port.number]
	#
	for port in ports:
		if port.link_state and port.port_state:
			ports_state['up'].append(port.number)
		else:
			if port.port_state:
				ports_state['down'].append(port.number)
			else:
				ports_state['admin_down'].append(port.number)
	#
	for port in ports:
		if port.duplex=="FULL":
			ports_duplex['FULL'].append(port.number)
		elif port.duplex=='HALF':
			ports_duplex['HALF'].append(port.number)
		else:
			ports_duplex['NONE'].append(port.number)

	if not ports:
		return data_refresh(request,Switch_id)
	context['cpu_values']='values/data'+str(Switch_id)+'.json'
	context['vlans']=vlans.order_by('vlan_name')
	context['ports']=ports
	context['switch']=Switch.objects.get(id=Switch_id)
	context['used_vlans']=[p.vlan for p in ports]
	context['ports_vlan']=ports_vlan
	context['ports_state']=ports_state
	context['ports_duplex']=ports_duplex

	return render(request, 'switches/detail.html', context)

def delete_switch(request,Switch_id):
	print(request.user)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	context={
		'switch':Switch.objects.get(id=Switch_id)
	}
	return render(request, 'switches/switch_delete.html',context)

def del_switch_confirmed(request,Switch_id):
	print(request.user)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	all_switches=Switch.objects.all()
	if Switch_id not in [i.id for i in all_switches]:
		pass
	else:
		if the_switch:
			if request.user==CustomUser.objects.get(username='admin'):
				print(str(the_switch),'deleted!')
				the_switch.delete()
			else:
				if len([1 for i in CustomUser.objects.all() if the_switch in i.switches.all()])>1:
					request.user.switches.remove(the_switch)
				else:
					print(str(the_switch),'deleted!')
					the_switch.delete()
	return HttpResponseRedirect('/switches')

def try_telnet(my_device,context):
	my_device['device_type']=my_device['device_type']+'_telnet'
	try:
		client=ConnectHandler(**my_device,timeout=5)
	except(ssh_exception.NetMikoAuthenticationException):
		context['error']='user'
	except(ssh_exception.NetMikoTimeoutException):
		context['error']='not_reachable'
	except:
		context['error']='unknown'
	if not context['error']:
		return client
	return context['error']

def get_client(my_device,context):
	returned={}
	ssh=False
	try:
		client=ConnectHandler(**my_device,timeout=5)
		ssh=True
	except(ssh_exception.NetMikoAuthenticationException):
		returned=try_telnet(my_device,context)
	except(ssh_exception.NetMikoTimeoutException):
		returned=try_telnet(my_device,context)
	except:
		returned=try_telnet(my_device,context)
	if returned.__class__==str:
		return returned
	else:
		if ssh:
			print('ssh')
		elif returned:
			print('telnet')
			client=returned
		else:
			raise Http404('Error')
		return client

def get_data_vlan(my_device,client):
	if my_device in ['extreme_exos','extreme_exos_telnet']:
		data_vlan=client.send_command('show vlan')
		data_vlan=data_vlan.split('\n')[6:-15]
	else:
		data_vlan=''
		## to be added

	return data_vlan

def get_data_ports(my_device,client):
	if my_device in ['extreme_exos','extreme_exos_telnet']:
		data_ports=client.send_command('show ports no-refresh')
		data_ports=data_ports.split('\n')[5:-5]
		data_ports2=client.send_command('show ports all vlan')
		data_ports2=data_ports2.split('\n')[4:]

	else:
		data_ports=''
		## to be added

	return [data_ports,data_ports2]

def edit_data_vlan(my_device,data_vlans,Switch_id):
	the_switch=Switch.objects.get(id=Switch_id)
	vlans=Vlan.objects.filter(switch_id=Switch_id)
	if my_device in ['extreme_exos','extreme_exos_telnet'] and data_vlans:
		vlans_now=[]
		for data_vlan in data_vlans:
			data_vlan=data_vlan.split()
			vlans_now.append((data_vlan[0],int(data_vlan[1])))
		if vlans:
			for v in vlans:
				if (v.vlan_name,v.VID) in vlans_now:
					vlans_now.remove((v.vlan_name,v.VID))
				else:
					print('Switch',str(the_switch),'Deleted Vlan',str(v))
					v.delete()
		if vlans_now:
			for v in vlans_now:
				vlan=Vlan(switch_id=Switch_id, vlan_name=v[0],VID=v[1])
				vlan.save()
				print('Switch',str(the_switch),'Created Vlan',v)
	else:
		#to be added
		pass

def edit_data_ports(my_device,data_ports,Switch_id):
	the_switch=Switch.objects.get(id=Switch_id)
	ports=Port.objects.filter(switch_id=Switch_id)
	if my_device in ['extreme_exos','extreme_exos_telnet'] and data_ports:
		dp=[]
		for data_port in data_ports[1]:
			try:
				int(data_port.split()[0])
			except:
				dp[-1]+=data_port
			else:
				dp.append(data_port)
		data_ports[1]=dp
		dp={}
		for i,val in enumerate(data_ports[1]):
			if len(val.split())==3:
				port_tag=False
			else:
				port_tag=True
				print('port',str(i+1),''.join(['tagged in ']+val.split()[4:]))
			dp[i+1]=port_tag
		for data_port in data_ports[0]:
			if data_port:
				data_port=data_port.split()
				port_nr=int(data_port[0])
				if data_port[1]=='E' or data_port[1]=='D':
					port_state=data_port[1]=='E'
					port_vlan='no Vlan'
					port_link_state=data_port[2]=='A'
					port_speed=0
					port_duplex=''
				else:
					if len(data_port[2])==1:
						port_state=data_port[2]=='E'
						port_vlan=data_port[1]
						port_link_state=data_port[3]=='A'
						if len(data_port)>4:
							port_speed=int(data_port[4])
							port_duplex=data_port[5]
						else:
							port_speed=0
							port_duplex=''
					else:
						port_state=data_port[3]=='E'
						port_vlan=data_port[2]
#						notes[int(data_port[0])]=data_port[1] ####
						port_link_state=data_port[4]=='A'
						if len(data_port)>5:
							port_speed=int(data_port[5])
							port_duplex=data_port[6]
						else:
							port_speed=0
							port_duplex=''
				try:
					port=ports.get(number=port_nr, switch_id=Switch_id)
				except(Port.MultipleObjectsReturned):
					for i in ports.all():
						i.delete()
					port=None
				except(Port.DoesNotExist):
					port=None
				if port:
					port=ports.get(number=port_nr, switch_id=Switch_id)
					i=0
					if not port.vlan==port_vlan:
						print('Edited vlan',str(port))
						port.vlan=port_vlan
						i=1
					if not port.port_state==port_state:
						print('Edited port stat',str(port))
						port.port_state==port_state
						i=1
					if not port.link_state==port_link_state:
						print('Edited link stat',str(port))
						port.link_state=port_link_state
						i=1
					if not port.speed==port_speed:
						print('Edited speed',str(port))
						port.speed=port_speed
						i=1
					if not port.duplex==port_duplex:
						print('Edited duplex',str(port),)
						port.duplex=port_duplex
						i=1
					if not port.tag==dp[port_nr]:
						print('Edited tag stat',str(port))
						port.tag=dp[port_nr]
						i=1
					if i:
						
						port.save()
				else:
					port=Port(tag=port_tag,number=port_nr,vlan=port_vlan,switch_id=Switch_id,port_state=port_state,link_state=port_link_state,speed=port_speed,duplex=port_duplex)
					print('Created',str(port))
					port.save()
	else:
		pass
		## to be added

def data_refresh(request, Switch_id):
	print(request.user)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	ports=Port.objects.filter(switch_id=Switch_id)
	vlans=Vlan.objects.filter(switch_id=Switch_id)
	context={
		'ports': ports.order_by('number'),
		'switch': Switch.objects.get(id=Switch_id),
		'error':'',
		'vlans':vlans.order_by('vlan_name'),
	}
	#getting in the device
	my_device={"device_type":the_switch.device_type(), 'host':the_switch.IP, 'username':the_switch.username}
	my_device['password']=the_switch.password
	
	client=get_client(my_device,context)
	
	if client.__class__==str:
		context['error']=client
	else:
		#the actual refresh	
		data_vlan=get_data_vlan(my_device["device_type"],client)
		edit_data_vlan(my_device["device_type"],data_vlan,Switch_id)
		data_ports=get_data_ports(my_device["device_type"],client)
		edit_data_ports(my_device["device_type"],data_ports,Switch_id)

		#exit the device
		client.disconnect()

		the_switch.ports_number=sum([1 for i in Port.objects.filter(switch_id=Switch_id)])
		the_switch.save()

	if context['error']:
		return render(request, 'switches/detail.html', context)
	return HttpResponseRedirect('/switches/'+str(context['switch'].id))

def edit_switch(request,Switch_id):
	print(request)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	form=SwitchForm_without_IP(request.POST or None)
	form_dev=Dev(request.POST or None)
	context={
		'form':form,
		'form_dev':form_dev,
		'error':'',
		'switch':the_switch
	}
	if form['username'].value() and form_dev.is_valid():
		the_switch.username=form['username'].value()
		the_switch.password=form['password'].value()
		the_switch.device=Device.objects.get(id=int(form_dev['device'].value()))
		the_switch.save()
		return HttpResponseRedirect('/switches/'+str(context['switch'].id))
	return render(request, 'switches/switch_edit.html',context)


def change_state(Switch_id,numbers,context):
	the_switch=Switch.objects.get(id=Switch_id)
	
	#getting in the device
	my_device={"device_type":the_switch.device_type(), 'host':the_switch.IP, 'username':the_switch.username}
	my_device['password']=the_switch.password
	
	client=get_client(my_device,context)
	
	if client.__class__==str:
		context['error']=client
	else:
		if the_switch.device_type() in ['extreme_exos','extreme_exos_telnet']:
			for num in numbers:
				port=Port.objects.get(switch_id=Switch_id,number=num)
				if port.port_state:
					out=client.send_command('disable port '+str(port.number))
					print(out)
				else:
					out=client.send_command('enable port '+str(port.number))
					print(out)
				if out:
					context['error']="permission_denied"
				else:
					port.port_state=not port.port_state
					port.save()
				if context['error']:
					break;
		else:
			context['error']='not_supported'
		#refreshing	
		data_vlan=get_data_vlan(my_device["device_type"],client)
		edit_data_vlan(my_device["device_type"],data_vlan,Switch_id)
		data_ports=get_data_ports(my_device["device_type"],client)
		edit_data_ports(my_device["device_type"],data_ports,Switch_id)
		
		#exiting the device
		client.disconnect()

		the_switch.ports_number=sum([1 for i in Port.objects.filter(switch_id=Switch_id)])
		the_switch.save()



def change_port_state(request,Switch_id):
	print(request)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	ports=Port.objects.filter(switch_id=Switch_id)
	vlans=Vlan.objects.filter(switch_id=Switch_id)
	form=auxForm(request.POST or None)
	context={
		'ports': ports.order_by('number'),
		'switch': the_switch,
		'vlans':vlans.order_by('vlan_name'),
		'error':'',
		'form':form
	}
	print(form['numbers'].value())
	if form.is_valid():
		numbers=[int(i) for i in form['numbers'].value().split(',') if i]
		print(numbers)
		change_state(Switch_id,numbers,context)
	#	print('--------')
	#	print(request.__class__)
	#	print('--------')
	#	print(request.path_info)
	#	print('--------')
	if context['error']:
		return render(request, 'switches/detail.html', context)
	return HttpResponseRedirect('/switches/'+str(context['switch'].id))

def vlan_remove(Switch_id,numbers,context):
	the_switch=Switch.objects.get(id=Switch_id)
	
	#getting in the device
	my_device={"device_type":the_switch.device_type(), 'host':the_switch.IP, 'username':the_switch.username}
	my_device['password']=the_switch.password
	
	client=get_client(my_device,context)
	
	if client.__class__==str:
		context['error']=client
	else:
		if the_switch.device_type() in ['extreme_exos','extreme_exos_telnet']:
			for num in numbers:
				port=Port.objects.get(switch_id=Switch_id,number=num)
				out=''
				if port.vlan=="no Vlan":
					pass
				else:
					out=client.send_command('configure vlan '+port.vlan+' delete port '+str(port.number))
				if out:
					context['error']="permission_denied"
				else:
					port.vlan='no Vlan'
					port.save()
				if context['error']:
					break;
		else:
			context['error']='not_supported'
		#refreshing	
		data_vlan=get_data_vlan(my_device["device_type"],client)
		edit_data_vlan(my_device["device_type"],data_vlan,Switch_id)
		data_ports=get_data_ports(my_device["device_type"],client)
		edit_data_ports(my_device["device_type"],data_ports,Switch_id)
		
		#exiting the device
		client.disconnect()

		the_switch.ports_number=sum([1 for i in Port.objects.filter(switch_id=Switch_id)])
		the_switch.save()

def port_vlan_remove(request,Switch_id):
	print(request)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	ports=Port.objects.filter(switch_id=Switch_id)
	vlans=Vlan.objects.filter(switch_id=Switch_id)
	form=auxForm(request.POST or None)
	context={
		'ports': ports.order_by('number'),
		'switch': the_switch,
		'vlans':vlans.order_by('vlan_name'),
		'error':'',
		'form':form
	}
	print(form['numbers'].value())
	if form.is_valid():
		numbers=[int(i) for i in form['numbers'].value().split(',') if i]
		print(numbers)
		vlan_remove(Switch_id,numbers,context)
	#	print('--------')
	#	print(request.__class__)
	#	print('--------')
	#	print(request.path_info)
	#	print('--------')
	if context['error']:
		return render(request, 'switches/detail.html', context)
	return HttpResponseRedirect('/switches/'+str(context['switch'].id))


def add_vlan(request,Switch_id):
	print(request)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	vlans=Vlan.objects.filter(switch_id=Switch_id)
	form=VlanForm(request.POST or None)
	vlans.order_by('VID')
	used_VID=[v.VID for v in vlans]
	used_Vnames=sorted([v.vlan_name for v in vlans])
	if used_VID==list(range(1,len(used_VID)+1)):
		unused=len(used_VID)+1
	else:
		for i in range(1,len(used_VID)+1):
			if i in used_VID:
				pass
			else:
				unused=i
	context={
		'form':form,
		'error':'',
		'switch':the_switch,
		'used_VID':used_VID,
		'used_names':used_Vnames,
		'first_unused':unused
	}
	print(context['used_names'])
	print(context['used_VID'])
	print(context['first_unused'])

	if form.is_valid():
		#
		print(form['VID'].value())
		print(form['vlan_name'].value())
		if form['vlan_name'].value() in context['used_names']:
			context['error']='used_vlan_name'
		elif int(form['VID'].value()) in context['used_VID']:
			context['error']='used_VID'
		elif ' ' in form['vlan_name'].value() or not re.search(r'\@?\!?\#?\$?\%?\^?\&?\*?',form['vlan_name'].value()).group()=='':
			context['error']='name_error'
		else:
			my_device={"device_type":the_switch.device_type(), 'host':the_switch.IP, 'username':the_switch.username}
			my_device['password']=the_switch.password
			
			client=get_client(my_device,context)
			
			if client.__class__==str:
				context['error']=client
			else:
				out=client.send_command('create vlan '+form['VID'].value())
				if out:
					print(out)
					print('permission_denied')
					context['error']:'permission_denied'
				else:
					out=client.send_command('configure vlan '+form['VID'].value()+' name '+form['vlan_name'].value())
					if out:
						print('name_error')
						context['error']='name_error'
						client.send_command('delete vlan '+form['VID'].value())
					else:
						#refresh
						data_vlan=get_data_vlan(my_device["device_type"],client)
						edit_data_vlan(my_device["device_type"],data_vlan,Switch_id)
						data_ports=get_data_ports(my_device["device_type"],client)
						edit_data_ports(my_device["device_type"],data_ports,Switch_id)
						
				client.disconnect()
				if not context['error']:
					return HttpResponseRedirect('/switches/'+str(the_switch.id))

	return render(request, 'switches/add_vlan.html', context)

def edit_vlan(request,Switch_id,VID):
	print(request)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	vlans=Vlan.objects.filter(switch_id=Switch_id)
	form=VlanForm(request.POST or None)
	vlans.order_by('VID')
	my_vlan=Vlan.objects.get(VID=VID,switch_id=Switch_id)
	used_VID=[v.VID for v in vlans if v.VID != my_vlan.VID]
	used_Vnames=sorted([v.vlan_name for v in vlans if v.vlan_name != my_vlan.vlan_name])

	context={
		'vlan':my_vlan,
		'form':form,
		'error':'',
		'switch':the_switch,
		'used_VID':used_VID,
		'used_names':used_Vnames,
	}
	if VID==1 or VID==4095:
		context['error']='permission_denied_admin'
		return detail(request,Switch_id,context)
	if form.is_valid():
		if form['vlan_name'].value()==my_vlan.vlan_name and form['VID'].value()==my_vlan.VID:
			pass
		else:	
			if form['vlan_name'].value() in context['used_names']:
				context['error']='used_vlan_name'
			elif int(form['VID'].value()) in context['used_VID']:
				context['error']='used_VID'
			elif ' ' in form['vlan_name'].value() or not re.search(r'\@?\!?\#?\$?\%?\^?\&?\*?',form['vlan_name'].value()).group()=='':
				context['error']='name_error'
			else:
				my_device={"device_type":the_switch.device_type(), 'host':the_switch.IP, 'username':the_switch.username}
				my_device['password']=the_switch.password
				
				client=get_client(my_device,context)
				
				if client.__class__==str:
					context['error']=client
				else:
					if int(form['VID'].value())==my_vlan.VID:
						print(form['vlan_name'].value())
						print('configure vlan '+str(VID)+' name '+form['vlan_name'].value())
						out=client.send_command('configure vlan '+str(VID)+' name '+form['vlan_name'].value())
						if out:
							context['error']='permission_denied'
					else:
						if the_switch.device_type() in ['extreme_exos','extreme_exos_telnet']:
							out=client.send_command('create vlan '+form['VID'].value())
							print('create vlan '+form['VID'].value())
							if out:
								context['error']='permission_denied'
							else:
								old_vlan_VID=my_vlan.VID
								my_vlan.VID=int(form['VID'].value())
								print('delete vlan '+str(old_vlan_VID))
								out=client.send_command('delete vlan '+str(old_vlan_VID))
								print('configure vlan '+str(my_vlan.VID)+' name '+form['vlan_name'].value())
								out=client.send_command('configure vlan '+str(my_vlan.VID)+' name '+form['vlan_name'].value())
								if out:
									print(out)
									context['error']='unknown'
									out=client.send_command('delete vlan '+form['VID'].value())
								else:
									old_vlan_name=my_vlan.vlan_name
									my_vlan.vlan_name=form['vlan_name'].value()
									ports=Port.objects.filter(switch_id=Switch_id,vlan=old_vlan_name)
									print(ports)
									if out:
										context['error']='unknown'
									else:
										for port in ports:
											if not port.tag:
												client.send_command('configure vlan '+str(my_vlan.VID)+' add port '+str(port.number))
												if out:
													context['error']='unknown'
													break
												port.vlan=my_vlan.vlan_name
												print(str(port.number)+' is untagged')
											else:
												client.send_command('configure vlan '+str(my_vlan.VID)+' add port '+str(port.number)+' tagged')
												if out:
													context['error']='unknown'
													break
												port.vlan=my_vlan.vlan_name
												print(str(port.number)+' is tagged')
						else:
							#to be added
							context['error']='not_supported'

					#refresh
					data_vlan=get_data_vlan(my_device["device_type"],client)
					edit_data_vlan(my_device["device_type"],data_vlan,Switch_id)
					data_ports=get_data_ports(my_device["device_type"],client)
					edit_data_ports(my_device["device_type"],data_ports,Switch_id)
							
					client.disconnect()
					if not context['error']:
						return HttpResponseRedirect('/switches/'+str(the_switch.id))

	return render(request, 'switches/edit_vlan.html', context)

def delete_vlan(request,Switch_id,VID):
	print(request)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	the_vlan=Vlan.objects.get(switch_id=Switch_id,VID=VID)
	ports=Port.objects.filter(switch_id=Switch_id)
	vlans=Vlan.objects.filter(switch_id=Switch_id)
	context={
		'vlans':vlans.order_by('vlan_name'),
		'ports':ports.order_by('number'),
		'switch':the_switch,
		'used_vlans':[p.vlan for p in ports],
		'error':''
	}
	if VID==1 or VID==4095:
		context['error']='permission_denied_admin'
	else:
		my_device={"device_type":the_switch.device_type(), 'host':the_switch.IP, 'username':the_switch.username}
		my_device['password']=the_switch.password
		
		client=get_client(my_device,context)
		
		if client.__class__==str:
			context['error']=client
		else:
			if my_device['device_type'] in ['extreme_exos','extreme_exos_telnet']:
				out=client.send_command('delete vlan '+str(VID))
				if out:
					if 'The specified VLAN list does not contain any valid' in out:
						context['error']='need_refresh'
					else:
						context['error']='permission_denied'
			else:
				#to be added
				context['error']='not_supported'
			#refresh
			data_vlan=get_data_vlan(my_device["device_type"],client)
			edit_data_vlan(my_device["device_type"],data_vlan,Switch_id)
			data_ports=get_data_ports(my_device["device_type"],client)
			edit_data_ports(my_device["device_type"],data_ports,Switch_id)

			client.disconnect()
	
	if context['error']:
		return render(request, 'switches/detail.html', context)
	return HttpResponseRedirect('/switches/'+str(context['switch'].id))

def add_port_to_vlan(Switch_id,VID,numbers,context):
	the_switch=Switch.objects.get(id=Switch_id)
	
	#getting in the device
	my_device={"device_type":the_switch.device_type(), 'host':the_switch.IP, 'username':the_switch.username}
	my_device['password']=the_switch.password
	
	client=get_client(my_device,context)
	
	if client.__class__==str:
		context['error']=client
	else:
		if the_switch.device_type() in ['extreme_exos','extreme_exos_telnet']:
			for num in numbers:
				port=Port.objects.get(switch_id=Switch_id,number=num)
				out=''
				if port.vlan=="no Vlan":
					out=client.send_command('configure vlan '+str(VID)+' add port '+str(port.number))
				elif Vlan.objects.get(switch_id=Switch_id,vlan_name=port.vlan).VID==VID:
					pass
				else:
					out=client.send_command('configure vlan '+port.vlan+' delete port '+str(port.number))
					if not out:
						out=client.send_command('configure vlan '+str(VID)+' add port '+str(port.number))

				if out:
					context['error']="permission_denied"
				else:
					port.vlan=Vlan.objects.get(switch_id=Switch_id,VID=VID).vlan_name
					port.save()
				if context['error']:
					break;
		else:
			pass
		#refreshing	
		data_vlan=get_data_vlan(my_device["device_type"],client)
		edit_data_vlan(my_device["device_type"],data_vlan,Switch_id)
		data_ports=get_data_ports(my_device["device_type"],client)
		edit_data_ports(my_device["device_type"],data_ports,Switch_id)
		
		#exiting the device
		client.disconnect()

		the_switch.ports_number=sum([1 for i in Port.objects.filter(switch_id=Switch_id)])
		the_switch.save()

def add_port_vlan(request,Switch_id,VID):
	print(request)
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	ports=Port.objects.filter(switch_id=Switch_id)
	vlans=Vlan.objects.filter(switch_id=Switch_id)
	form=auxForm(request.POST or None)
	context={
		'ports': ports.order_by('number'),
		'switch': the_switch,
		'vlans':vlans.order_by('vlan_name'),
		'error':'',
		'form':form
	}
	print(form['numbers'].value())
	if form.is_valid():
		numbers=[int(i) for i in form['numbers'].value().split(',') if i]
		print(numbers)
		add_port_to_vlan(Switch_id,VID,numbers,context)
	#	print('--------')
	#	print(request.__class__)
	#	print('--------')
	#	print(request.path_info)
	#	print('--------')
	else:
		context['error']='select_error'
	if context['error']:
		return detail(request,Switch_id,context)
	return HttpResponseRedirect('/switches/'+str(Switch_id))

def monitoring_cpu(request,Switch_id):
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	path=os.path.abspath('switches/cpu_measure')
	print(path)
	the_switch=Switch.objects.get(id=Switch_id)
	running_file=open(path+'/running.json','r')
	run=json.load(running_file)
	running_file.close()
	if not the_switch.id in run:
		process = subprocess.Popen(['python3',path+'/get_values.py',str(Switch_id),the_switch.device_type(),the_switch.IP,the_switch.username,the_switch.password])
		#print(process.communicate())
	else:
		print(the_switch.IP,'cpu_measure is on')
	return HttpResponseRedirect('/switches/'+str(Switch_id))

def get_json(request,Switch_id):
	if not request.user.is_authenticated:
		return HttpResponseRedirect('/')
	the_switch=Switch.objects.get(id=Switch_id)
	if not the_switch in request.user.switches.all():
		logout(request)
		return HttpResponseRedirect('/')
	path=os.path.abspath('switches/cpu_measure')
	print(path)
	try:	
		json_data = open(path+'/values/data'+str(Switch_id)+'.json')
	except:
		json_data=open(path+'/values/data'+str(Switch_id)+'.json','w')
		json.dump([],json_data)
		json_data.close()
		json_data = open(path+'/values/data'+str(Switch_id)+'.json')

	data = json.load(json_data)
	json_data.close()
	return JsonResponse(data, safe=False)

'''
request __dict__
{'environ': 
	{'CLUTTER_IM_MODULE': 'xim', 
	'LS_COLORS': 'rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=30;41:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.Z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:', 
	'LC_MEASUREMENT': 'ro_RO.UTF-8', 
	'LESSCLOSE': '/usr/bin/lesspipe %s %s', 
	'LC_PAPER': 'ro_RO.UTF-8', 
	'LC_MONETARY': 'ro_RO.UTF-8', 
	'XDG_MENU_PREFIX': 'gnome-', 
	'LANG': 'en_US.UTF-8', 
	'DISPLAY': ':0', 
	'GNOME_SHELL_SESSION_MODE': 'ubuntu', 
	'COLORTERM': 'truecolor', 
	'DESKTOP_AUTOSTART_ID': '10eeac2904bb71938e156679987250309900000013250007', 
	'USERNAME': 'stefan', 
	'XDG_VTNR': '2', 
	'SSH_AUTH_SOCK': '/run/1000/keyring/ssh', 
	'S_COLORS': 'auto', 
	'LC_NAME': 'ro_RO.UTF-8', 
	'XDG_SESSION_ID': '2', 
	'USER': 'stefan', 
	'DESKTOP_SESSION': 'ubuntu', 
	'QT4_IM_MODULE': 'xim', 
	'TEXTDOMAINDIR': '/usr/share/locale/', 
	'GNOME_TERMINAL_SCREEN': '/org/gnome/Terminal/screen/063fa1ad_e7ba_4d9d_b0fb_d44443c8b323', 
	'PWD': '/home/stefan/Desktop/site/my_project', 
	'HOME': '/home/stefan', 
	'TEXTDOMAIN': 'im-config', 
	'SSH_AGENT_PID': '1431', 
	'QT_ACCESSIBILITY': '1', 
	'XDG_SESSION_TYPE': 'x11', 
	'XDG_DATA_DIRS': '/usr/share/ubuntu:/usr/local/share:/usr/share:/var/lib/snapd/desktop', 
	'XDG_SESSION_DESKTOP': 'ubuntu', 
	'LC_ADDRESS': 'ro_RO.UTF-8', 
	'LC_NUMERIC': 'ro_RO.UTF-8', 
	'GTK_MODULES': 'gail:atk-bridge', 
	'WINDOWPATH': '2', 
	'TERM': 'xterm-256color', 
	'SHELL': '/bin/bash', 
	'VTE_VERSION': '5202', 
	'QT_IM_MODULE': 'xim', 
	'XMODIFIERS': '@im=ibus', 
	'IM_CONFIG_PHASE': '2', 
	'XDG_CURRENT_DESKTOP': 'ubuntu:GNOME', 
	'GPG_AGENT_INFO': '/run/1000/gnupg/S.gpg-agent:0:1', 
	'GNOME_TERMINAL_SERVICE': ':1.60', 
	'XDG_SEAT': 'seat0', 
	'SHLVL': '1', 
	'LC_TELEPHONE': 'ro_RO.UTF-8', 
	'GDMSESSION': 'ubuntu', 
	'GNOME_DESKTOP_SESSION_ID': 'this-is-deprecated', 
	'LOGNAME': 'stefan', 
	'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/1000/bus', 
	'XDG_RUNTIME_DIR': '/run/1000', 
	'XAUTHORITY': '/run/1000/gdm/Xauthority', 
	'XDG_CONFIG_DIRS': '/etc/xdg/xdg-ubuntu:/etc/xdg', 
	'PATH': '/home/stefan/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin', 
	'LC_IDENTIFICATION': 'ro_RO.UTF-8', 
	'SESSION_MANAGER': 'local/stefan:@/tmp/.ICE-unix/1325,unix/stefan:/tmp/.ICE-unix/1325', 
	'LESSOPEN': '| /usr/bin/lesspipe %s', 
	'GTK_IM_MODULE': 'ibus', 
	'LC_TIME': 'ro_RO.UTF-8', 
	'OLDPWD': '/home/stefan', '_': '/usr/bin/python3', 'DJANGO_SETTINGS_MODULE': 'my_project.settings', 'TZ': 'UTC', 'RUN_MAIN': 'true', 
	'SERVER_NAME': 'stefan', 'GATEWAY_INTERFACE': 'CGI/1.1', 'SERVER_PORT': '8080', 'REMOTE_HOST': '', 'CONTENT_LENGTH': '', 'SCRIPT_NAME': '', 
	'SERVER_PROTOCOL': 'HTTP/1.1', 
	'SERVER_SOFTWARE': 'WSGIServer/0.2', 'REQUEST_METHOD': 'GET', 
	'PATH_INFO': '/switches/2/change_port_state/26', 
	'QUERY_STRING': '', 
	'REMOTE_ADDR': '172.29.17.72', 
	'CONTENT_TYPE': 'text/plain', 
	'HTTP_HOST': '172.29.17.72:8080', 
	'HTTP_USER_AGENT': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0', 
	'HTTP_ACCEPT': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 
	'HTTP_ACCEPT_LANGUAGE': 'en-US,en;q=0.5', 
	'HTTP_ACCEPT_ENCODING': 'gzip, deflate', 
	'HTTP_REFERER': 'http://172.29.17.72:8080/switches/2/change_port_state/28', 
	'HTTP_CONNECTION': 'keep-alive', 
	'HTTP_COOKIE': 'csrftoken=hn54Mv9ARBCpGm5RudHVb6k2ckggxsuQPRl3Zvqe9JnVTi2MvAImxfnpOyddarsf', 
	'HTTP_UPGRADE_INSECURE_REQUESTS': '1', 
	'wsgi.input': <django.core.handlers.wsgi.LimitedStream object at 0x7fcf680f1e48>, 
	'wsgi.errors': <_io.TextIOWrapper name='<stderr>' mode='w' encoding='UTF-8'>, 
	'wsgi.version': (1, 0), 'wsgi.run_once': False, 
	'wsgi.url_scheme': 'http', 
	'wsgi.multithread': True, 
	'wsgi.multiprocess': False, 
	'wsgi.file_wrapper': <class 'wsgiref.util.FileWrapper'>, 
	'CSRF_COOKIE': 'hn54Mv9ARBCpGm5RudHVb6k2ckggxsuQPRl3Zvqe9JnVTi2MvAImxfnpOyddarsf'}, 
	'path_info': '/switches/2/change_port_state/26', 
	'path': '/switches/2/change_port_state/26', 
	'META': {'CLUTTER_IM_MODULE': 'xim', 
			'LS_COLORS': 'rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=30;41:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.Z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:', 
			'LC_MEASUREMENT': 'ro_RO.UTF-8', 
			'LESSCLOSE': '/usr/bin/lesspipe %s %s', 
			'LC_PAPER': 'ro_RO.UTF-8', 
			'LC_MONETARY': 'ro_RO.UTF-8', 
			'XDG_MENU_PREFIX': 'gnome-', 
			'LANG': 'en_US.UTF-8', 
			'DISPLAY': ':0', 
			'GNOME_SHELL_SESSION_MODE': 'ubuntu', 
			'COLORTERM': 'truecolor', 
			'DESKTOP_AUTOSTART_ID': '10eeac2904bb71938e156679987250309900000013250007', 
			'USERNAME': 'stefan', 
			'XDG_VTNR': '2', 
			'SSH_AUTH_SOCK': '/run/1000/keyring/ssh', 
			'S_COLORS': 'auto', 
			'LC_NAME': 'ro_RO.UTF-8', 
			'XDG_SESSION_ID': '2', 
			'USER': 'stefan', 
			'DESKTOP_SESSION': 'ubuntu', 
			'QT4_IM_MODULE': 'xim', 
			'TEXTDOMAINDIR': '/usr/share/locale/', 
			'GNOME_TERMINAL_SCREEN': '/org/gnome/Terminal/screen/063fa1ad_e7ba_4d9d_b0fb_d44443c8b323', 
			'PWD': '/home/stefan/Desktop/site/my_project', 
			'HOME': '/home/stefan', 
			'TEXTDOMAIN': 'im-config', 
			'SSH_AGENT_PID': '1431', 
			'QT_ACCESSIBILITY': '1', 
			'XDG_SESSION_TYPE': 'x11', 
			'XDG_DATA_DIRS': '/usr/share/ubuntu:/usr/local/share:/usr/share:/var/lib/snapd/desktop', 
			'XDG_SESSION_DESKTOP': 'ubuntu', 
			'LC_ADDRESS': 'ro_RO.UTF-8', 
			'LC_NUMERIC': 'ro_RO.UTF-8', 
			'GTK_MODULES': 'gail:atk-bridge', 
			'WINDOWPATH': '2', 
			'TERM': 'xterm-256color', 
			'SHELL': '/bin/bash', 
			'VTE_VERSION': '5202', 
			'QT_IM_MODULE': 'xim', 
			'XMODIFIERS': '@im=ibus', 
			'IM_CONFIG_PHASE': '2',
			'XDG_CURRENT_DESKTOP': 'ubuntu:GNOME',
			'GPG_AGENT_INFO': '/run/1000/gnupg/S.gpg-agent:0:1',
			'GNOME_TERMINAL_SERVICE': ':1.60',
			'XDG_SEAT': 'seat0',
			'SHLVL': '1',
			'LC_TELEPHONE': 'ro_RO.UTF-8',
		    'GDMSESSION': 'ubuntu',
		    'GNOME_DESKTOP_SESSION_ID': 'this-is-deprecated',
		    'LOGNAME': 'stefan',
   	        'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/1000/bus',
	        'XDG_RUNTIME_DIR': '/run/1000',
	        'XAUTHORITY': '/run/1000/gdm/Xauthority',
	        'XDG_CONFIG_DIRS': '/etc/xdg/xdg-ubuntu:/etc/xdg',
	        'PATH': '/home/stefan/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin',
            'LC_IDENTIFICATION': 'ro_RO.UTF-8',
            'SESSION_MANAGER': 'local/stefan:@/tmp/.ICE-unix/1325,unix/stefan:/tmp/.ICE-unix/1325',
            'LESSOPEN': '| /usr/bin/lesspipe %s',
            'GTK_IM_MODULE': 'ibus',
            'LC_TIME': 'ro_RO.UTF-8',
            'OLDPWD': '/home/stefan',
            '_': '/usr/bin/python3',
            'DJANGO_SETTINGS_MODULE': 'my_project.settings',
            'TZ': 'UTC', 'RUN_MAIN': 'true', 'SERVER_NAME': 'stefan', 'GATEWAY_INTERFACE': 'CGI/1.1', 'SERVER_PORT': '8080', 'REMOTE_HOST': '', 'CONTENT_LENGTH': '', 'SCRIPT_NAME': '', 'SERVER_PROTOCOL': 'HTTP/1.1', 'SERVER_SOFTWARE': 'WSGIServer/0.2', 'REQUEST_METHOD': 'GET', 'PATH_INFO': '/switches/2/change_port_state/26', 'QUERY_STRING': '', 'REMOTE_ADDR': '172.29.17.72', 'CONTENT_TYPE': 'text/plain', 'HTTP_HOST': '172.29.17.72:8080', 'HTTP_USER_AGENT': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0', 'HTTP_ACCEPT': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'HTTP_ACCEPT_LANGUAGE': 'en-US,en;q=0.5', 'HTTP_ACCEPT_ENCODING': 'gzip, deflate', 'HTTP_REFERER': 'http://172.29.17.72:8080/switches/2/change_port_state/28', 'HTTP_CONNECTION': 'keep-alive', 'HTTP_COOKIE': 'csrftoken=hn54Mv9ARBCpGm5RudHVb6k2ckggxsuQPRl3Zvqe9JnVTi2MvAImxfnpOyddarsf', 'HTTP_UPGRADE_INSECURE_REQUESTS': '1', 'wsgi.input': <django.core.handlers.wsgi.LimitedStream object at 0x7fcf680f1e48>, 'wsgi.errors': <_io.TextIOWrapper name='<stderr>' mode='w' encoding='UTF-8'>, 'wsgi.version': (1, 0), 'wsgi.run_once': False, 'wsgi.url_scheme': 'http', 'wsgi.multithread': True, 'wsgi.multiprocess': False, 'wsgi.file_wrapper': <class 'wsgiref.util.FileWrapper'>, 'CSRF_COOKIE': 'hn54Mv9ARBCpGm5RudHVb6k2ckggxsuQPRl3Zvqe9JnVTi2MvAImxfnpOyddarsf'}, 'method': 'GET', 'content_type': 'text/plain', 'content_params': {}, '_stream': <django.core.handlers.wsgi.LimitedStream object at 0x7fcf680f1898>, '_read_started': False, 'resolver_match': ResolverMatch(func=switchs.views.change_port_state, args=(), kwargs={'Switch_id': 2, 'port_number': 26}, url_name=change_port_state, app_names=['switches'], namespaces=['switches'], route=switches/<int:Switch_id>/change_port_state/<int:port_number>), 'COOKIES': {'csrftoken': 'hn54Mv9ARBCpGm5RudHVb6k2ckggxsuQPRl3Zvqe9JnVTi2MvAImxfnpOyddarsf'}, 'session': <django.contrib.sessions.backends.db.SessionStore object at 0x7fcf680f1780>, 'user': <SimpleLazyObject: <django.contrib.auth.models.AnonymousUser object at 0x7fcf68025390>>, '_messages': <django.contrib.messages.storage.fallback.FallbackStorage object at 0x7fcf680f1d68>, 'csrf_processing_done': True, '_cached_user': <django.contrib.auth.models.AnonymousUser object at 0x7fcf68025390>}

	'''

