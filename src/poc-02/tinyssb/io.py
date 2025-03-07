# tinyssb/io.py

import binascii
import os
import sys
import _thread

try:
    import pycom
    import machine
    import uselect as select
    import usocket as socket
    # def mk_addr(ip,port): return socket.getaddrinfo(ip,port)[0][-1]
    def mk_addr(ip,port): return (ip,port)
    import utime as time
    ticks_ms = time.ticks_ms
    ticks_add  = time.ticks_add
    ticks_diff = time.ticks_diff
    randint = machine.rng
except:
    import random
    if sys.implementation.name == 'micropython':
        import uselect as select
        import usocket as socket
        def mk_addr(ip,port): return socket.getaddrinfo(ip,port)[0][-1]
    else:
        import select
        import socket
        def mk_addr(ip,port): return (ip,port)
    import serial
    import time
    ticks_ms = lambda : round(time.time()*1000)
    ticks_add  = lambda t,d: t+d
    ticks_diff = lambda new,old: new-old
    randint = lambda : random.randint(0,65535)


from .dbg import *


# ----------------------------------------------------------------------

queue_lock = _thread.allocate_lock()

class FACE:

    def __init__(self):
        self.outqueue = []
        self.earliest_send = None

    def enqueue(self, pkt):
        global queue_lock
        queue_lock.acquire()
        self.outqueue.append(pkt)
        queue_lock.release()

    def dequeue(self):
        global queue_lock
        queue_lock.acquire()
        pkt = self.outqueue[0]
        del self.outqueue[0]
        queue_lock.release()
        return pkt

    # def recv(self, lim):


class NEIGHBOR:

    def __init__(self, face, sock):
        self.face = face
        self.sock = sock
        self.when = 0
        self.src = None

    # def send(self, pkt):  pass


# ----------------------------------------------------------------------

class LORA(FACE):

    def __init__(self):
        super().__init__()
        print("  creating face for LoRa")
        # Asia = LoRa.AS923
        # Australia = LoRa.AU915
        # Europe = LoRa.EU868
        # United States = LoRa.US915
        #  AS923 -- 0
        #  AU915 -- 1
        #  CN470 -- 2
        #  EU868 -- 5
        #  IN865 -- 7
        #  US915 -- 8
        try:
            import network
            self._lora = network.LoRa(mode = network.LoRa.LORA,
                                region     = network.LoRa.EU868,
                                tx_power   = 20, # 2,
                                power_mode = network.LoRa.ALWAYS_ON,
                                bandwidth  = network.LoRa.BW_250KHZ,
                                coding_rate= network.LoRa.CODING_4_7,
                                sf = 7)
            '''
            self._lora = network.LoRa(mode = network.LoRa.LORA,
                                region     = network.LoRa.EU868,
                                tx_power   = 2, # 2,
                                power_mode = network.LoRa.ALWAYS_ON,
                                bandwidth  = network.LoRa.BW_125KHZ,
                                coding_rate= network.LoRa.CODING_4_8,
                                      sf = 9)
            '''
            # self._lora.preamble(4)
            '''
                config        bps  FEC maxB   t/128B
            DR0 SF12/125kHz    250      59
            DR1 SF11/125kHz    440      59
            DR2 SF10/125kHz    980      59
            DR3 SF9/125kHz   1,760     123    545 ms (120B)
            DR4 SF8/125kHz   3,125 4/5 230    328 ms
            DR5 SF7/125kHz   5,470 4/5 230    187 ms

            DR6 SF7/250kHz  11,000 4/5 230     94 ms
            DR6 SF7/250kHz   9'110 4/6 230    112 ms
            DR6 SF7/250kHz   7'810 4/7 230    131 ms
            DR6 SF7/250kHz   6'840 4/8 230    150 ms

            DR7 FSK: 50kpbs 50,000     230

            https://www.thethingsnetwork.org/docs/lorawan/regional-parameters/
            The Thing Network - EU863-870, Uplink:

                868.1 - SF7BW125 to SF12BW125
                868.3 - SF7BW125 to SF12BW125 and SF7BW250
                868.5 - SF7BW125 to SF12BW125
                867.1 - SF7BW125 to SF12BW125
                867.3 - SF7BW125 to SF12BW125
                867.5 - SF7BW125 to SF12BW125
                867.7 - SF7BW125 to SF12BW125
                867.9 - SF7BW125 to SF12BW125
                868.8 - FSK

            TTN Downlink: above, plus 869.525 (SF9BW125)
            '''
            self._lora.frequency(867500000)
            self.mac = ':'.join(['{:02x}'.format(b) for b in \
                                                       self._lora.mac()])
            print("    LoRa MAC:     ", self.mac)
            print("    LoRa freq:    ", self._lora.frequency())
            print("    LoRa preamble:", self._lora.preamble())
            print("    LoRa sf:      ", self._lora.sf())
            print("    LoRa bw:      ",
                  ['125kHz', '250kHz', '500kHz'][self._lora.bandwidth()])
            print("    LoRa coding:  ",
                  ['4_5', '4_6', '4_7', '4_8'][self._lora.coding_rate()-1])

            self.rcv_sock = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
            self.rcv_sock.setblocking(False)
        except Exception as e:
            print("LoRa init failed", e)
            self.rcv_sock = None
        self.snd_sock = self.rcv_sock
        self.neigh = LORA_NEIGHBOR(self, self.snd_sock)
        self.neighbors = { 1: self.neigh }

    def recv(self, lim):
        print("    lora rcv", 
              self._lora.stats().rssi,
              self._lora.stats().snr)
        return (self.rcv_sock.recvfrom(lim)[0], self.neigh)

    def softstate_timer(self):
        pass

    def __str__(self):
        return "LoRa[" + self.mac + "]"

    pass


class LORA_NEIGHBOR(NEIGHBOR):

    def __init__(self, face, sock):
        super().__init__(face, sock)
        self.is_broadcast = True
    
    def send(self, pkt):
        try:    self.sock.send(pkt) # can throw EAGAIN if sent too fast
        except: pass
        s = self.face._lora.stats()
        # print("air time:", s.tx_time_on_air)
        # should add duty cycling, but we only add jitter:
        #   (note: cannot send more then 1 pkt/s before EAGAIN)
        self.face.earliest_send = ticks_add(ticks_ms(),
                                            1000 + randint() % 50)

    pass

# ----------------------------------------------------------------------

class UDP_MULTICAST(FACE):
    
    def __init__(self, addr):
        super().__init__()
        print("  creating face for UDP multicast group")
        self.snd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.snd_sock.bind(mk_addr('0.0.0.0',0))
        if sys.implementation.name != 'micropython':
            self.snd_sock.setsockopt(socket.IPPROTO_IP,
                                     socket.IP_MULTICAST_TTL, 2)
            self.snd_sock.setsockopt(socket.SOL_IP,
                                     socket.IP_MULTICAST_IF,
                                     bytes(4))
        self.snd_addr = self.snd_sock.getsockname()
        
        self.rcv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rcv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rcv_sock.bind(mk_addr(*addr))
        try:
            #try:
            #    host = socket.gethostbyname(socket.gethostname() + '.local'
            mreq =  bytes([int(i) for i in addr[0].split('.')]) + bytes(4)
            if sys.implementation.name=='micropython' and \
                                                     sys.platform=='darwin':
                    self.rcv_sock.setsockopt(0, 12, mreq)
            else:
                self.rcv_sock.setsockopt(socket.IPPROTO_IP,
                                         socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception as e:
            print("error in setting UDP multicast", e)
        self.my_addr = addr
        print("    address is", addr)

        self.neigh = UDP_MULTICAST_NEIGHBOR(self, self.snd_sock)
        self.neighbors = { 1: self.neigh }

        # repeat sending a packet to the mc group until we receive one
        # that matches what we sent - for learning the outgoing interface
        n = os.urandom(8)
        while True:
            self.snd_sock.sendto(n, mk_addr(*addr))
            pkt,src = self.rcv_sock.recvfrom(8)
            if pkt == n:
                self.snd_addr = src
                break

    def recv(self, lim):
        r = self.rcv_sock.recvfrom(lim)
        if r == None: return None
        pkt, src = r
        if src == self.snd_addr: return None  # discard our own packets
        n = self.neigh
        n.when = time.time()
        n.src = src
        return (pkt,n)

    def __str__(self):
        return "UDPmulticast" + str(self.my_addr)

    pass


class UDP_MULTICAST_NEIGHBOR(NEIGHBOR):

    def __init__(self, face, sock):
        super().__init__(face, sock)
        self.is_broadcast = True
    
    def send(self, pkt):
        try:
            self.sock.sendto(pkt, mk_addr(*(self.face.my_addr)))
        except Exception as e:
            dbg(RED, "mc send error:", e)
        pass

    pass

# ----------------------------------------------------------------------

class KISS(FACE): # serial device

    FEND =  b'\xc0'
    FESC =  b'\xdb'
    TFEND = b'\xdc'
    TFESC = b'\xdd'

    def __init__(self, dev, sz=200):
        super().__init__()
        print("  creating KISS face")
        try:
            self.ser = serial.Serial(dev, 115200)
            # for k,v in self.ser.__dict__.items():
            #     print("  ", k, v)
        except Exception as e:
            print("    failed", e)
            self.ser = None
            return
        # self.snd_sock = self.ser.pipe_abort_write_w
        # self.rcv_sock = self.ser.pipe_abort_read_r
        self.snd_sock = self.rcv_sock = self.ser.fd
        self.dev = dev
        print("   ", dev)

        self.neigh = KISS_NEIGHBOR(self, self.snd_sock)
        self.neighbors = { 1: self.neigh }
        self.buf = bytearray(sz)
        self.buflen = 0
        self.escmode = False

    def recv(self, lim):
        # print("KISS rcv")
        while self.ser.in_waiting > 0:
            c = self.ser.read(1)
            if c == None or len(c) == 0:
                print("KISS rcv empty ?")
                return None
            if c == self.FEND:
                self.escmode = False
                if self.buflen == 0: return None
                buf = bytes(self.buf[:self.buflen])
                self.buflen = 0
                return (buf, self.neigh)
            if c == self.FESC:
                self.escmode = True
                continue
            if self.escmode:
                if c in [self.TFESC, self.TFEND]:
                    if self.buflen < len(self.buf):
                        self.buf[self.buflen] = self.FESC[0] if c == self.TFESC \
                                           else self.FEND[0]
                        self.buflen += 1
                self.escmode = False
                continue
            if self.buflen < len(self.buf):
                self.buf[self.buflen] = c[0]
                self.buflen += 1
        return None

    def __str__(self):
        return "KISS@" + str(self.dev)

    pass


class KISS_NEIGHBOR(NEIGHBOR):

    def __init__(self, face, sock):
        super().__init__(face, sock)
        self.is_broadcast = True
    
    def send(self, pkt):
        # print("KISS send", len(pkt))
        try:
            k =  bytearray(pkt)
            k = k.replace(self.face.FESC, self.face.FESC+self.face.TFESC)
            k = k.replace(self.face.FEND, self.face.FESC+self.face.TFEND)
            pkt = bytes(self.face.FEND + k + self.face.FEND)
            self.face.ser.write(pkt)
        except Exception as e:
            dbg(RED, "KISS send error:", e)
        self.face.earliest_send = ticks_add(ticks_ms(),
                                            500 + randint() % 50)
    pass

# ----------------------------------------------------------------------

class UDP_UNICAST(FACE):
    
    def __init__(self, addr):
        super().__init__()
        print("  creating face for UDP unicast")
        self.snd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.snd_sock.bind(mk_addr('0.0.0.0',0))
        self.rcv_sock = self.snd_sock
        self.peer_addr = addr
        print("    peer address is", addr)

        self.neigh = UDP_UNICAST_NEIGHBOR(self, self.snd_sock)
        self.neighbors = { 1: self.neigh }

    def recv(self, lim):
        r = self.rcv_sock.recvfrom(lim)
        if r == None: return None
        pkt, src = r
        n = self.neigh
        n.when = time.time()
        n.src = src
        return (pkt,n)

    def __str__(self):
        return "UDPmulticast" + str(self.peer_addr)

    pass


class UDP_UNICAST_NEIGHBOR(NEIGHBOR):

    def __init__(self, face, sock):
        super().__init__(face, sock)
        # self.is_broadcast = True
    
    def send(self, pkt):
        try:
            self.sock.sendto(pkt, mk_addr(*(self.face.peer_addr)))
        except Exception as e:
            dbg(RED, "UDP send error:", e)
        pass

    pass

# ----------------------------------------------------------------------

class IOLOOP:

    def __init__(self, faces, on_rx):
        self.faces = faces
        self.on_rx = on_rx
        self.poll = select.poll()
        for fc in faces:
            try:
                self.poll.register(fc.rcv_sock, select.POLLIN)
                if fc.snd_sock != fc.rcv_sock: # not LoRa
                    self.poll.register(fc.snd_sock, 0)
            except Exception as e:
                print('poll registration error', fc, e)
                pass

    def run(self):
        sleep_time = 100
        while True:
            lst = self.poll.poll(sleep_time)

            for r in lst:
                for fc in self.faces:
                    if r[1] & select.POLLIN != 0: # new packet available
                        if r[0] == fc.rcv_sock or \
                          (type(r[0])==int and type(fc.rcv_sock)!=int and r[0] == fc.rcv_sock.fileno()):
                            pn = fc.recv(250)
                            if pn: self.on_rx(*pn) # (pkt, neigh)
                    if r[1] & select.POLLOUT != 0: # next pkt can be sent
                        if len(fc.outqueue) > 0 and (r[0] == fc.snd_sock or \
                            (type(r[0])==int and type(fc.snd_sock) != int and r[0] == fc.snd_sock.fileno())):
                            pkt = fc.dequeue()
                            for n in fc.neighbors.values():
                                # dbg(GRA, "sending", len(pkt), 'bytes')
                                try:
                                    n.send(pkt) # may change 'earliest_send'
                                except Exception as e:
                                    dbg(RED, "send error:", e)

            sleep_time = 1000
            now = ticks_ms() # time()
            for fc in self.faces:
                if fc.earliest_send != None:
                    d = ticks_diff(fc.earliest_send, now)
                    if d < sleep_time:
                        sleep_time = max(d,0)
                        fc.earliest_send = None
                if len(fc.outqueue) > 0 and fc.earliest_send == None:
                    # print("** enable POLLOUT", fc.snd_sock, 'qlen=', len(fc.outqueue))
                    if fc.rcv_sock == fc.snd_sock: # LoRa
                        self.poll.modify(fc.snd_sock,
                                         select.POLLIN | select.POLLOUT)
                    else:
                        self.poll.modify(fc.snd_sock, select.POLLOUT)
                else:
                    # print("** disable POLLOUT", fc.snd_sock)
                    if fc.rcv_sock == fc.snd_sock: # LoRa
                        self.poll.modify(fc.snd_sock, select.POLLIN)
                    else:
                        self.poll.modify(fc.snd_sock, 0)

    pass


# eof
