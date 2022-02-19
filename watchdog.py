import time
# from time import time.sleep, time
from os import stat, path, system
from datetime import datetime
from RPi import GPIO
import socket
from CONFIG import config

newts_reboot = 0
newts = 0
restart_log=[-1,-1,-1]
power_cycle_needed_thresh = 100 # seconds: if 3 restarts occur within 100 seconds, request power cycle
min_time_for_powercycles = 86400 # 24 hours - max 2 powercycles within 24 hrs

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(7, GPIO.OUT)		# heartbeat LED
GPIO.setup(8, GPIO.OUT)		# reboot LED
GPIO.setup(11, GPIO.IN)		# reboot switch

cfg = config(r'/var/lib/homebridge/config.ini','ALL')
is_master = cfg.is_master
UDP_IP = cfg.destIP
UDP_PORT = cfg.destUDP
UDP_IP_2 = cfg.destIP2
UDP_PORT_2 = cfg.destUDP2

sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

if path.isfile(r'/var/lib/homebridge/input_reboot/1'):
	system(r'sudo rm /var/lib/homebridge/input_reboot/1')
if path.isfile(r'/var/lib/homebridge/input_reboot/reboot'):
	system(r'sudo rm /var/lib/homebridge/input_reboot/reboot')
if path.isfile(r'/var/lib/homebridge/input_reboot/shutdown'):
	system(r'sudo rm /var/lib/homebridge/input_reboot/shutdown')
if path.isfile(r'/var/lib/homebridge/holdoff_watchdog'):
	system(r'sudo rm /var/lib/homebridge/holdoff_watchdog')

GPIO.output(8, GPIO.LOW)

def stop_controller():
	still_processes_running = True
	while(still_processes_running):
		system('ps aux | grep \'controller.py\' > pid_log.txt')

		f = open('pid_log.txt','r')
		lines = f.readlines()
		f.close()

		i=0
		nEOF = 1
		while nEOF and ((lines[i].find('root') == -1) or (lines[i].find('grep') != -1)):
			i+=1
			if i == len(lines):
				nEOF = 0
				i-=1
		if nEOF:
			j=4
			while lines[i][j] == ' ':
				j+=1

			pid = lines[i][j:].split(' ')[0]

			print 'Stopping PID '+pid+'...'
			system('sudo kill -TERM '+pid)
			time.sleep(1)

		else:
			print 'Finished searching for controller.py processes...'
			print
			still_processes_running = False
	# system('ps aux | grep \'sudo python /var/lib/homebridge/controller.py\' > /var/lib/homebridge/pid_log.txt')

	# f = open('/var/lib/homebridge/pid_log.txt','r')
	# lines = f.readlines()
	# f.close()

	# k=0
	# nEOF = 1
	# while not(lines[k][0] == 'r' and lines[k][1] == 'o' and lines[k][2] == 'o' and lines[k][3] == 't') and nEOF:
	# 	k+=1
	# 	if k == len(lines):
	# 		nEOF = 0
	# 		k-=1
	# if nEOF:
	# 	j=4
	# 	while lines[k][j] == ' ':
	# 		j+=1

	# 	pid = lines[k][j:].split(' ')[0]
		
	# 	print 'Stopping PID '+pid+'...'
	# 	system('sudo kill -TERM '+pid)
	
while True:
	notrestarted = 1
	lastts_reboot = newts_reboot
	lastts = newts
	newts_reboot = stat('/var/lib/homebridge/input_reboot').st_mtime
	newts = stat('/var/lib/homebridge/heartbeat').st_mtime
	time.sleep(0.1)
	if path.isfile(r'/var/lib/homebridge/holdoff_watchdog'):
		watchdog_timeout = 1
	elif path.isfile(r'/var/lib/homebridge/extend_watchdog'):
		system(r'sudo rm /var/lib/homebridge/extend_watchdog')
		watchdog_timeout = 20
		print 'watchdog extended'
	else:
		watchdog_timeout = 5

	if newts_reboot != lastts_reboot:
		if path.isfile(r'/var/lib/homebridge/input_reboot/1'):
			system('sudo shutdown -r +1 "Rebooting in 1 minute, use sudo shutdown -c to cancel"')
			print 'Reboot command received'
			if is_master:	# echo reboot command to slave units
				sock.sendto('write:input_reboot/:1:', (UDP_IP, UDP_PORT))
				sock.sendto('write:input_reboot/:1:', (UDP_IP_2, UDP_PORT_2))
			time.sleep(1)
			system(r'sudo rm /var/lib/homebridge/input_reboot/1')
			##int_lights
			time.sleep(40)
			stop_controller()
			time.sleep(1)
			system("nohup sudo python /var/lib/homebridge/turn_off_int_lights.py &")
			#
		elif path.isfile(r'/var/lib/homebridge/input_reboot/reboot'):
			GPIO.output(7, GPIO.HIGH)	# heartbeat LED
			print 'Immediate reboot command received'
			if is_master:	# echo reboot command to slave units
				sock.sendto('write:input_reboot/:reboot:', (UDP_IP, UDP_PORT))
				sock.sendto('write:input_reboot/:reboot:', (UDP_IP_2, UDP_PORT_2))
			time.sleep(1)
			system(r'sudo rm /var/lib/homebridge/input_reboot/reboot')
			##int_lights
			stop_controller()
			time.sleep(1)
			system("nohup sudo python /var/lib/homebridge/turn_off_int_lights.py &")
			time.sleep(4)
			#
			system('sudo reboot')
		elif path.isfile(r'/var/lib/homebridge/input_reboot/sreboot'):
			GPIO.output(7, GPIO.HIGH)	# heartbeat LED
			print 'Immediate single reboot command received'
			time.sleep(1)
			system(r'sudo rm /var/lib/homebridge/input_reboot/sreboot')
			##int_lights
			stop_controller()
			time.sleep(1)
			system("nohup sudo python /var/lib/homebridge/turn_off_int_lights.py &")
			time.sleep(4)
			#
			system('sudo reboot')
		elif path.isfile(r'/var/lib/homebridge/input_reboot/shutdown'):
			GPIO.output(7, GPIO.HIGH)	# heartbeat LED
			print 'Immediate shutdown command received'
			if is_master:	# echo shutdown command to slave unit
				sock.sendto('write:input_reboot/:shutdown:', (UDP_IP, UDP_PORT))
				sock.sendto('write:input_reboot/:shutdown:', (UDP_IP_2, UDP_PORT_2))
			time.sleep(1)
			system(r'sudo rm /var/lib/homebridge/input_reboot/shutdown')
			##int_lights
			stop_controller()
			time.sleep(1)
			system("nohup sudo python /var/lib/homebridge/turn_off_int_lights.py &")
			time.sleep(4)
			#
			system('sudo shutdown -h now')
		elif path.isfile(r'/var/lib/homebridge/input_reboot/sshutdown'):
			GPIO.output(7, GPIO.HIGH)	# heartbeat LED
			print 'Immediate single shutdown command received'
			time.sleep(1)
			system(r'sudo rm /var/lib/homebridge/input_reboot/sshutdown')
			##int_lights
			stop_controller()
			time.sleep(1)
			system("nohup sudo python /var/lib/homebridge/turn_off_int_lights.py &")
			time.sleep(4)
			#
			system('sudo shutdown -h now')
		elif path.isfile(r'/var/lib/homebridge/input_reboot/restart_controller'):
			watchdog_timeout = 20
			print 'Script restart command received'
			if is_master:	# echo restart script command to slave unit
				sock.sendto('write:input_reboot/:restart_controller:', (UDP_IP, UDP_PORT))
				sock.sendto('write:input_reboot/:restart_controller:', (UDP_IP_2, UDP_PORT_2))
			time.sleep(1)
			system(r'sudo rm /var/lib/homebridge/input_reboot/restart_controller')
			system('/usr/local/bin/start_controller')
		elif path.isfile(r'/var/lib/homebridge/input_reboot/single_restart_controller'):
			watchdog_timeout = 20
			print 'Script restart command received'
			time.sleep(1)
			system(r'sudo rm /var/lib/homebridge/input_reboot/single_restart_controller')
			system('/usr/local/bin/start_controller')
				
	i = 0
	while not(newts > lastts) and notrestarted and (not path.isfile(r'/var/lib/homebridge/holdoff_watchdog')):
		print str(6-i)+'...'
		time.sleep(1)
		newts = stat('/var/lib/homebridge/heartbeat').st_mtime
		time.sleep(0.1)
		if path.isfile(r'/var/lib/homebridge/extend_watchdog'):
			system(r'sudo rm /var/lib/homebridge/extend_watchdog')
			watchdog_timeout = 20
			print 'watchdog extended'
		else:
			watchdog_timeout = 5

		i+=1
		if i == 6:
			time_now = time.time()
			if time_now < (restart_log[1] + power_cycle_needed_thresh):	# restart_log[1]: 3 restarts before pwr cycle
				f = open(r'/var/lib/homebridge/restart_history','r')
				restart_history = f.readlines()
				f.close()
				print 'restart_history:',restart_history
				if time_now > (float(restart_history[1][:-1]) + min_time_for_powercycles):	# restart_history[1]: 2 powercycles allowed within 24hr period
					print 'requesting powercycle'
					##int_lights
					stop_controller()
					time.sleep(1)
					system("nohup sudo python /var/lib/homebridge/turn_off_int_lights.py &")
					#time.sleep(4)
					#
					sock.sendto('write:input_control/:wd_powercycle:', (UDP_IP, UDP_PORT))	# send on to slave
					now = datetime.now()
					errorlog = open(r'/var/lib/homebridge/crash.log','a')
					errorlog.write(now.strftime("%d/%m/%Y %H:%M:%S - "))
					errorlog.write('Controller crashed immediately three times in a row - power cycling...')
					errorlog.write('\n')
					errorlog.close()

					# update restart history
					f = open(r'/var/lib/homebridge/restart_history','w')
					f.write(str(time_now))
					f.write('\n')
					f.write(restart_history[0])
					f.write(restart_history[1])
					f.close()

					system('sudo shutdown -h now')

				else:
					now = datetime.now()
					errorlog = open(r'/var/lib/homebridge/crash.log','a')
					errorlog.write(now.strftime("%d/%m/%Y %H:%M:%S - "))
					errorlog.write('Max number of power cycles reached within 24hr period. Waiting...')
					errorlog.write('\n')
					errorlog.close()
					while time_now < (float(restart_history[1][:-1]) + min_time_for_powercycles):
						print 'time_now:',time_now
						print 'waiting for:',(float(restart_history[1][:-1]) + min_time_for_powercycles)
						time.sleep(5)
						time_now = time.time()
				
			else:
				still_processes_running = True
				msg = 'Restarted controller.py'
				while(still_processes_running):
					system('ps aux | grep \'controller.py\' > pid_log.txt')

					f = open('pid_log.txt','r')
					lines = f.readlines()
					f.close()

					i=0
					nEOF = 1
					while nEOF and ((lines[i].find('root') == -1) or (lines[i].find('grep') != -1)):
						i+=1
						if i == len(lines):
							nEOF = 0
							i-=1
					if nEOF:
						j=4
						while lines[i][j] == ' ':
							j+=1

						pid = lines[i][j:].split(' ')[0]

						print 'Stopping PID '+pid+'...'
						system('sudo kill -TERM '+pid)
						time.sleep(1)

					else:
						print 'Finished searching for controller.py processes...'
						print
						still_processes_running = False

				# system('ps aux | grep \'sudo python /var/lib/homebridge/controller.py\' > /var/lib/homebridge/pid_log.txt')

				# f = open('/var/lib/homebridge/pid_log.txt','r')
				# lines = f.readlines()
				# f.close()

				# k=0
				# nEOF = 1
				# while not(lines[k][0] == 'r' and lines[k][1] == 'o' and lines[k][2] == 'o' and lines[k][3] == 't') and nEOF:
				# 	k+=1
				# 	if k == len(lines):
				# 		nEOF = 0
				# 		k-=1
				# if nEOF:
				# 	j=4
				# 	while lines[k][j] == ' ':
				# 		j+=1

				# 	pid = lines[k][j:].split(' ')[0]
					
				# 	print 'Stopping PID '+pid+'...'
				# 	system('sudo kill -TERM '+pid)
				# 	#msg = 'Restarted controller.py'
				# 	#print 'Restarting controller.py...'
				# 	#print
				# #else:
				# 	#msg = 'Started controller.py as it was not running'
				# 	#print 'Starting controller.py...'
				# 	#print

				# system('ps aux | grep \'python /var/lib/homebridge/controller.py\' > /var/lib/homebridge/pid_log.txt')

				# f = open('/var/lib/homebridge/pid_log.txt','r')
				# lines = f.readlines()
				# f.close()

				# k=0
				# nEOF = 1
				# while not(lines[k][0] == 'r' and lines[k][1] == 'o' and lines[k][2] == 'o' and lines[k][3] == 't') and nEOF:
				# 	k+=1
				# 	if k == len(lines):
				# 		nEOF = 0
				# 		k-=1
				# if nEOF:
				# 	j=4
				# 	while lines[k][j] == ' ':
				# 		j+=1

				# 	pid = lines[k][j:].split(' ')[0]
					
				# 	print 'Stopping PID '+pid+'...'
				# 	system('sudo kill -TERM '+pid)
				# 	msg = 'Restarted controller.py'
				# 	print 'Restarting controller.py...'
				# 	print
				# else:
				# 	msg = 'Started controller.py as it was not running'
				# 	print 'Starting controller.py...'
				# 	print
				
				GPIO.setup(10, GPIO.OUT)	# error LED
				GPIO.output(10, GPIO.HIGH)
				
				alert = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Crash_Alert_MotionDetected','w')
				alert.write('1')
				alert.close()
				
				now = datetime.now()
				errorlog = open(r'/var/lib/homebridge/crash.log','a')
				errorlog.write(now.strftime("%d/%m/%Y %H:%M:%S - "))
				errorlog.write(msg)
				errorlog.write('\n')
				errorlog.close()
				
				time.sleep(2)
				
				system("nohup sudo python /var/lib/homebridge/controller.py &")
				notrestarted = 0
				restart_log[2]=restart_log[1]
				restart_log[1]=restart_log[0]
				restart_log[0]=time_now
				print restart_log

	if notrestarted:
		GPIO.output(7, GPIO.HIGH)	# heartbeat LED
		time.sleep(1)
		GPIO.output(7, GPIO.LOW)
	else:
		time.sleep(2)
	for i in range(watchdog_timeout):
		if is_master and (not(GPIO.input(11))):	# button pressed
			GPIO.output(8, GPIO.HIGH)
			time.sleep(0.25)
			GPIO.output(8, GPIO.LOW)
			time.sleep(2.75)
			if not(GPIO.input(11)):	# if button still pressed after 3 seconds, shutdown
				GPIO.output(7, GPIO.HIGH)	# heartbeat LED
				print 'Immediate shutdown command received'
				sock.sendto('write:input_reboot/:shutdown:', (UDP_IP, UDP_PORT))	# send on to slave
				sock.sendto('write:input_reboot/:shutdown:', (UDP_IP_2, UDP_PORT_2))	# send on to slave
				GPIO.output(8, GPIO.HIGH)
				time.sleep(0.25)
				GPIO.output(8, GPIO.LOW)
				time.sleep(0.25)
				GPIO.output(8, GPIO.HIGH)
				time.sleep(0.25)
				GPIO.output(8, GPIO.LOW)
				time.sleep(0.25)
				GPIO.output(8, GPIO.HIGH)
				print 'Shutting down...'
				system('sudo shutdown -h now')
			else:	# else reboot
				GPIO.output(7, GPIO.HIGH)	# heartbeat LED
				print 'Immediate reboot command received'
				sock.sendto('write:input_reboot/:reboot:', (UDP_IP, UDP_PORT))	# send on to slave
				sock.sendto('write:input_reboot/:reboot:', (UDP_IP_2, UDP_PORT_2))	# send on to slave
				time.sleep(1)
				print 'Rebooting...'
				system('sudo reboot')
				
		time.sleep(1)