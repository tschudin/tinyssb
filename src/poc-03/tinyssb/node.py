# tinyssb/node.py   -- node (peering and replication) behavior


import binascii
import hashlib
import _thread

from . import io, util
from .dbg import *


class NODE:  # a node in the tinySSB forwarding fabric

    def __init__(self, faces,repo):
        self.faces = faces
        self.repo  = repo
        self.dmxt  = {}    # DMX  ~ dmx_tuple  DMX filter bank
        self.blbt  = {}    # hptr ~ blob_obj  blob filter bank
        self.user  = {}    # fid  ~ user_obj  the users I serve (soc graph)
        self.peer  = {}    # fid  ~ peer_obj  other nodes
        self.timers = []

    def start(self):
        self.ioloop = io.IOLOOP(self.faces, self.on_rx)
        print('  starting thread with IO loop')
        _thread.start_new_thread(self.ioloop.run, tuple())

    def arm_dmx(self, dmx, fct=None):
        if not fct:
            if dmx in self.dmxt: del self.dmxt[dmx]
        else:
            # print('  fct', fct)
            self.dmxt[dmx] = fct

    def arm_blob(self, hptr, fct=None):
        if not fct:
            if hptr in self.blbt: del self.blbt[hptr]
        else:
            self.blbt[hptr] = fct

    def on_rx(self, buf, neigh): # all tSSB packet reception logic goes here!
        # dbg(GRE, "<< buf", len(buf), binascii.hexlify(buf[:20]), "...")
        # if neigh.src:
        #     print("   src", neigh.src)
        '''
        if len(buf) == 128:
          buf = try to uncloak
        if hash(buf) in self.blob:
            ...
        '''
        dmx = buf[:7]
        if dmx in self.dmxt:
            # print('  call', self.dmxt[dmx])
            self.dmxt[dmx](buf, neigh)
        else:
            hptr = hashlib.sha256(buf).digest()[:20]
            if hptr in self.blbt:
                self.blbt[hptr](buf, neigh)
            else:
                # dbg(GRA, "no dmxt or blbt entry found for", util.hex(dmx))
                # print("   ?msg", buf[8:56].replace(b'\x00',b''))
                pass

    def push(self, pkt_lst):
        for f in self.faces:
            for pkt in pkt_lst:
                # print(f"enqueue {util.hex(hashlib.sha256(pkt).digest()[:20])}")
                f.enqueue(pkt)

    def on_tick():
        pass


# eof
