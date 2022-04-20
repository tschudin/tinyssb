#

# tinyssb/session.py
# 2022-04-14 <christian.tschudin@unibas.ch>

from tinyssb import packet, util
from tinyssb.dbg import *


class SlidingWindowClient:

    def __init__(self, slw, port):
        self.slw = slw
        self.port = port
        self.slw.register(port, self)

    def upcall(self, buf48):
        pass

    def write(self, buf48):
        pass

    def __del__(self):
        self.slw.deregister(port)
        self.slf = None

    pass


class SlidingWindow:

    def __init__(self, nd, localFID, remoteFID):
        self.nd = nd
        self.lfd = nd.repo.get_log(localFID)
        self.lfdsign = lambda msg: nd.ks.sign(localFID, msg)
        self.rfd = nd.repo.get_log(remoteFID)
        self.pfd = None # pending feed (oldest unacked cont feed), test needed
        self.upcall = None # client(s), currently we ignore ports
        self.started = False

    def register(self, port, client):
        self.upcall = lambda buf: client.upcall(buf)

    def deregister(self, port):
        self.upcall = None

    def write_plain_48B(self, buf48):
        self.write_typed_48B(packet.PKTTYPE_plain48, buf48)

    def write_typed_48B(self, typ, buf48):
        # check for overlength, start new feed continuation if necessary
        buf48 = buf48 + bytes(48-len(buf48))
        if len(self.lfd) > 7: # a very small segment size of 8 entries
            oldFID = self.lfd.fid
            dbg(GRA, f"SESS: ending feed {oldFID.hex()[:20]}..")
            pk = self.nd.ks.new('continuation')
            sign2 = lambda msg: self.nd.ks.sign(pk, msg)
            seq, prevhash = self.lfd.getfront()
            seq += 1
            nextseq = seq.to_bytes(4, 'big')
            pktdmx = packet._dmx(self.lfd.fid + nextseq + prevhash)
            # dbg(GRA, f"-dmx pkt@{util.hex(pktdmx)} for {util.hex(self.lfd.fid)[:20]}.[{seq}]")
            self.nd.arm_dmx(pktdmx)
            pkts = self.nd.repo.mk_continuation_log(self.lfd.fid,
                                                    self.lfdsign,
                                                    pk, sign2)
            
            self.lfd = self.nd.repo.get_log(pkts[1].fid)
            if self.nd.sess.pfd == None:
                self.nd.sess.pfd = oldFID
            self.lfdsign = sign2
            dbg(GRA, f"  ... continued as feed {self.lfd.fid.hex()[:20]}..")
            self.nd.push(pkts, True)
        self.nd.write_typed_48B(self.lfd.fid, typ, buf48, self.lfdsign)

    def on_incoming(self, pkt):
        # dbg(BLU, f"SESS: incoming {pkt.fid[:20].hex()}:{pkt.seq} {pkt.typ}")
        if self.started:
            self._process(pkt)
        else:
            print("not started yet")

    def _process(self, pkt):
        # print("SESS _processing")
        if pkt.typ == bytes([packet.PKTTYPE_contdas]):
            self.rfd = self.nd.repo.get_log(pkt.payload[:32])
            self.nd.repo.del_log(pkt.fid)
            return
        if pkt.typ[0] == packet.PKTTYPE_iscontn:
            # dbg(GRE, f"SESS: processing iscontn")
            # should verify proof
            oldFID = pkt.payload[:32]
            msg = oldFID # + ??
            self.write_typed_48B(packet.PKTTYPE_acknldg,
                                 msg + bytes(48-len(msg)))
            return
        if pkt.typ[0] == packet.PKTTYPE_acknldg:
            dbg(GRE, f"SESS: processing ack")
            if self.pfd == None:
                print("no log to remove")
                return
            dbg(GRE, f"SESS: removing feed {self.pfd.hex()[:20]}..")
            f = self.nd.repo.get_log(self.pfd)
            if len(f) > 1 and f[-1].typ[0] == packet.PKTTYPE_contdas:
                self.pfd = f[-1].payload[:32]
            else:
                self.pfd = None
            self.nd.repo.del_log(f.fid)
            self.nd.ks.remove(f.fid)
            del f
            return
        if pkt.typ[0] == packet.PKTTYPE_plain48:
            # print("sliding: doing upcall")
            if self.upcall != None:
                self.upcall(pkt.payload)
        
    def set_upcall(self, upcall):
        self.upcall = upcall

    def start(self):
        # does upcalls for all content received so far,
        # including acknowledging (and indirectly free) segments
        i = 1
        while i <= len(self.rfd):
            pkt = self.rfd[i]
            self._process(pkt)
            if pkt.typ[0] == packet.PKTTYPE_contdas:
                i = 1 # restart loop for continuation segment
            else:
                i += 1
        self.rfd.set_append_cb(self.on_incoming)
        dbg(RED, "sess has started (catchup done, switching to live processing)")
        self.started = True

# eof
