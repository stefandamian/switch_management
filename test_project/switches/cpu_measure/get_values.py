import os
import sys
from netmiko import ConnectHandler, ssh_exception
import time as t
import json

#arg_list:[ switch_id, device_type, ip, username, password ]

def try_telnet(my_device):
	my_device['device_type']=my_device['device_type']+'_telnet'
	context=0
	try:
		client=ConnectHandler(**my_device,timeout=5)
	except:
		context=1
	if not context:
		return client
	return context

def get_client(my_device):
	returned={}
	ssh=False
	try:
		client=ConnectHandler(**my_device,timeout=5)
		ssh=True
	except:
		returned=try_telnet(my_device)
	if returned.__class__==str:
		return returned
	else:
		if ssh:
			print('ssh')
		elif returned:
			print('telnet')
			client=returned
		return client


#start
def main():
	arg=sys.argv[1:]
	path='/home/stefan/Desktop/site/test_project/switches/cpu_measure/'

	running_file=open(path+'running.json','r')
	run=json.load(running_file)
	running_file.close()
	if len(arg) in [4,5]:
		if int(arg[0]) in run:
			pass
		else:
			run.append(int(arg[0]))
			running_file=open(path+'running.json','w')
			json.dump(run,running_file)
			running_file.close()

			my_device={"device_type":arg[1], 'host':arg[2], 'username':arg[3]}
			if arg[4:]:
				my_device['password']=arg[4]
			else:
				my_device['password']=''
			client=get_client(my_device)
			if not client==1:
				for i in range(25):
					try:
						data=client.send_command('show cpu-monitoring').split('\n')[10:]
						cpu_val=sum([float(i.split()[1]) for i in data])
					except:
						break
					try:
						input_file=open(path+'values/data'+arg[0]+'.json','r')
					except(FileNotFoundError):
						input_file=open(path+'values/data'+arg[0]+'.json','w')
						values=[]
					else:
						values=json.load(input_file)
					input_file.close()
					if len(values)>14:
						values=values[1:]
					my_time=t.localtime()
					time_string = t.strftime('%m/%d/%Y '+str(my_time.tm_hour+3)+':%M:%S', my_time)
					values.append({"time":time_string,"cpu":"{0:.2f}".format(cpu_val)})
					print(values[-1])
					output_file=open(path+'values/data'+arg[0]+'.json','w')
					json.dump(values,output_file)
					output_file.close()
					t.sleep(5)

				client.disconnect()
			
			running_file=open(path+'running.json','r')
			run=json.load(running_file)
			running_file.close()
			run.remove(int(arg[0]))
			running_file=open(path+'running.json','w')
			json.dump(run,running_file)
			running_file.close()
			print(arg[2],'cpu_monitorizing off')
	else:
		print('bad_arg')

if __name__ == '__main__':
	main()

