import socket
from os import path, remove

UDP_IP = "0.0.0.0" # listen to everything
UDP_PORT = 52347 # port
write_cmd = 'write'
delete_cmd = 'delete'

folder = r'/var/lib/homebridge/'

write_len = len(write_cmd)
del_len = len(delete_cmd)

sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

while True:
	data, addr = sock.recvfrom(512)
	if data[0:write_len] == write_cmd:
		cmd = data.split(':')
		print 'sub folder:',cmd[1]
		print 'file:',cmd[2]
		print 'contents:',cmd[3]
		print
		f = open(folder+cmd[1]+'/'+cmd[2],'w')
		f.write(cmd[3]+'\n')
		f.close()
	elif data[0:del_len] == delete_cmd:
		cmd = data.split(':')
		print 'sub folder:',cmd[1]
		print 'file:',cmd[2]
		print 'delete'
		print
		if path.isfile(folder+cmd[1]+'/'+cmd[2]):
			remove(folder+cmd[1]+'/'+cmd[2])
