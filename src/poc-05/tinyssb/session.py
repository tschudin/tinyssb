#

# tinyssb/session.py
# 2022-04-14 <christian.tschudin@unibas.ch>

from . import packet, util
from .dbg import *
from .exception import UnexpectedPacketTinyException

class SlidingWindow:

    def __init__(self, nd, id_number, local_fid, remote_fid, callback=None):
        self.nd = nd
        self.id_number = id_number
        self.lfd = nd.repo.get_log(local_fid)
        self.lfdsign = lambda msg: nd.ks.sign(local_fid, msg)
        # TinySSB 0.1 only allows one remote feed
        self.rfd = None
        if remote_fid is not None:
            self.rfd = nd.repo.get_log(remote_fid)
        self.pfd = None # pending feed (oldest unacked cont feed), test needed
        self.callback = None # client(s), currently we ignore ports
        self.started = False
        self.window_length = 100

    def add_remote(self, remote_fid):
        self.rfd = self.nd.repo.get_log(remote_fid)

    def set_callback(self, callback):
        self.callback = callback

    def write_plain_48B(self, buf48):
        self.write_typed_48B(packet.PKTTYPE_plain48, buf48)

    def write_typed_48B(self, typ, buf48):
        # check for overlength, start new feed continuation if necessary
        buf48 = buf48 + bytes(48-len(buf48))
        if len(self.lfd) > self.window_length:  # a very small segment size of 8 entries
            oldFID = self.lfd.fid
            dbg(GRA, f"SESS: ending feed {util.hex(oldFID)[:20]}..")
            pk = self.nd.ks.new('continuation')
            sign2 = lambda msg: self.nd.ks.sign(pk, msg)
            pkts = self.nd.repo.mk_continuation_log(self.lfd.fid,
                                                    self.lfdsign,
                                                    pk, sign2)
            # dbg(GRA, f"-dmx pkt@{util.hex(pkts[0].dmx)} for {util.hex(self.lfd.fid)[:20]}.[{seq}]")
            self.nd.arm_dmx(pkts[0].dmx)
            self.lfd = self.nd.repo.get_log(pkts[1].fid)
            if self.nd.sess.pfd == None:
                self.nd.sess.pfd = oldFID
            self.lfdsign = sign2
            dbg(GRA, f"  ... continued as feed {util.hex(self.lfd.fid)[:20]}..")
            self.nd.push(pkts, True)
        self.nd.write_typed_48B(self.lfd.fid, typ, buf48, self.lfdsign)

    def write_blob_chain(self, buf):
        self.nd.write_blob_chain(self.lfd.fid, buf, self.lfdsign)

    def on_incoming(self, pkt):
        dbg(BLU, f"SESS: incoming {pkt.fid[:20].hex()}:{pkt.seq} {pkt.typ}")
        if self.started:
            self._process(pkt)
        else:
            print("not started yet")

    def _process(self, pkt):
        # print("SESS _processing")
        if pkt.typ[0] == packet.PKTTYPE_contdas:
            # self.rfd.remove(pkt.fid)
            # self.rfd[pkt.payload[:32]] = self.nd.repo.get_log(pkt.payload[:32])
            self.rfd = self.nd.repo.get_log(pkt.payload[:32])
            # self.nd.repo.del_log(pkt.fid)
        elif pkt.typ[0] == packet.PKTTYPE_iscontn:
            # dbg(GRE, f"SESS: processing iscontn")
            # should verify proof
            oldFID = pkt.payload[:32]
            oldFeed = self.nd.repo.get_log(oldFID)
            # print(oldFeed.getfront)
            # oldFeed.getfront[0]
            # pkt.payload[32:36]
            if not oldFeed.getfront[0] == pkt.payload[32:36]:
                dbg(RED, f"Continue feed: sequence number doesn't match:"
                         f" {oldFeed.getfront[0]} vs {pkt.payload[32:36]}")
                return
            # FIXME one could check the hash too, but it is now computed on
            #  the last bytes of the signature which is not stored
            msg = oldFID # + ??
            self.write_typed_48B(packet.PKTTYPE_acknldg,
                                 msg + bytes(48-len(msg)))
        elif pkt.typ[0] == packet.PKTTYPE_acknldg:
            dbg(GRE, f"SESS: processing ack")
            if self.pfd is None:
                print("no log to remove")
                return
            dbg(GRE, f"SESS: removing feed {util.hex(self.pfd)[:20]}..")
            f = self.nd.repo.get_log(self.pfd)
            if len(f) > 1 and f[-1].typ[0] == packet.PKTTYPE_contdas:
                self.pfd = f[-1].payload[:32]
            else:
                self.pfd = None
            self.nd.repo.del_log(f.fid)
            self.nd.ks.remove(f.fid)
            del f
        elif pkt.typ[0] == packet.PKTTYPE_chain20:
            pkt.undo_chain(lambda h: self.nd.repo.fetch_blob(h))
            self.callback(pkt.chain_content)
        elif pkt.typ[0] == packet.PKTTYPE_ischild:
            pass
        elif pkt.typ[0] == packet.PKTTYPE_mkchild:
            raise UnexpectedPacketTinyException
        else:  # plain, set or delete
            self.callback(pkt.payload)

    def start(self):
        # does upcalls for all content received so far,
        # including acknowledging (and indirectly free) segments
        i = 1
        while i <= len(self.rfd):
            pkt = self.rfd[i]
            self._process(pkt)
            if pkt.typ[0] == packet.PKTTYPE_contdas:
                i = 1  # restart loop for continuation segment
            else:
                i += 1
        self.rfd.set_append_cb(self.on_incoming)
        dbg(RED, "sess has started (catchup done, switching to live processing)")
        self.started = True

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
        self.slw.deregister(self.port)
        self.slf = None

    pass
# eof
