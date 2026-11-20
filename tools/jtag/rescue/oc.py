import socket,sys
s=socket.create_connection(("127.0.0.1",6666)); s.settimeout(600)
for c in sys.argv[1:]:
    s.sendall(c.encode()+b"\x1a"); b=b""
    while not b.endswith(b"\x1a"): b+=s.recv(4096)
    print(">",c); print(b[:-1].decode(errors="replace"))
