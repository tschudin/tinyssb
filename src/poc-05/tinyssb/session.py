#

# tinyssb/session.py
# 2022-04-14 <christian.tschudin@unibas.ch>
import bipf
from . import packet, util
from .dbg import *

__app__ = [
    'instances',
    'create_inst',
    'update_game',
    'start',
    'send',
    'set_callback',
    'close'
]

class Application:

    def __init__(self, nd, log, callback=None):
        self.node = nd
        self.window = None
        self.callback = callback  # client(s), currently we ignore ports
        self.instances = {}
        self.log = log
        self.next_inst_id = 0

        self.__load_instances()

    def create_inst(self, remote_fid, with_, name=None):
        local_fid = self.node.ks.new(self.next_inst_id)
        n = bipf.dumps(self.next_inst_id)
        n += bytes(16 - len(n))
        self.node.repo.mk_child_log(self.log.fid,
            self.node.ks.get_signFct(self.log.fid), local_fid,
            self.node.ks.get_signFct(local_fid), n)

        p = { 'id': self.next_inst_id,'il': local_fid,'w': with_}
        if name is not None:
            p['n'] = name
        self.window = SlidingWindow(self.node, self.next_inst_id, local_fid, remote_fid)
        if remote_fid is not None:
            p['ir'] = remote_fid
            # self.window.start(self.callback)
            self.send(p, packet.PKTTYPE_set)
        p.pop('id')
        self.instances[str(self.next_inst_id)] = p
        self.next_inst_id += 1

    def add_remote_fid(self, inst_id, remote_fid):
        p = self.instances[str(inst_id)]
        p['remote_fid'] = remote_fid
        if self.window.id_number == inst_id:
            self.window.add_remote(remote_fid)
            self.window.start(self.callback)
            self.send(p, packet.PKTTYPE_set)
        self.instances[str(inst_id)]['remote_fid'] = remote_fid

    def update_game(self, inst_id, local_fid, remote_fid, with_, name):
        p = {'id': inst_id}
        if local_fid is not None:
            p['l'] = local_fid
        if remote_fid is not None:
            p['r'] = remote_fid
        if with_ is not None:
            p['w'] = with_
        if name is not None:
            p['n'] = name
        self.send(p, packet.PKTTYPE_set)

    def start(self, inst_id):
        if self.window.id_number != inst_id:
            inst = self.instances.get(str(inst_id))
            self.window = SlidingWindow(self.node, inst_id, inst['local_fid'], inst['remote_fid'])
        self.window.start(self.callback)

    def send(self, msg, typ=packet.PKTTYPE_plain48):
        if bipf.encodingLength(msg) > 48:
            self.window.write_blob_chain(bipf.dumps([msg]))
        else:
            self.window.write_typed_48B(typ, bipf.dumps([msg]))

    def set_callback(self, callback):
        self.callback = callback
        if self.window is not None:
            self.window.set_upcall(callback)

    def close(self):
        pass

    def __load_instances(self):
        for i in range(1, len(self.log)+1):
            pkt = self.log[i]
            if pkt.typ[0] == packet.PKTTYPE_delete:
                inst_id = pkt.payload[:32]
                deleted = self.instances.pop(inst_id)
                # TODO delete logs associated with it
            elif pkt.typ[0] == packet.PKTTYPE_set:
                self.__extract_instance(bipf.loads(pkt.payload))
            elif pkt.typ[0] == packet.PKTTYPE_chain20:
                pkt.undo_chain(lambda h: self.node.repo.fetch_blob(h))
                self.__extract_instance(bipf.loads(pkt.chain_content))
                
    def __extract_instance(self, payload):
        inst_id = payload.get('id')
        inst = self.instances.get('inst_id')
        if inst is None:
            inst = {'inst_id': inst_id }

        local_fid = payload.get('l')
        if local_fid is not None:
            inst['local_fid'] = local_fid
        assert inst['local_fid'] is not None

        current_local_fid = payload.get('cl')
        if current_local_fid is not None:
            inst['current_local_fid'] = current_local_fid
            
        remote_fid = payload.get('r')
        if remote_fid is not None:
            inst['remote_fid'] = remote_fid
        assert inst['remote_fid'] is not None

        current_remote_fid = payload.get('cr')
        if current_remote_fid is not None:
            inst['current_remote_fid'] = current_remote_fid
            
        with_ = payload.get('w')
        if with_ is not None:
            inst['with'] = with_
        assert inst['with'] is not None

        name = payload.get('n')
        if name is not None:
            inst['name'] = name
        dbg(GRA, f"Inst = {inst}")

    # def __add_instance_field(self, payload, inst, letter, key):
    #     tmp = payload.get(letter)
    #     if tmp is not None:
    #         inst[key] = tmp


class SlidingWindow:

    def __init__(self, nd, id_number, local_fid, remote_fid):
        self.nd = nd
        self.id_number = id_number
        self.lfd = nd.repo.get_log(local_fid)
        self.lfdsign = lambda msg: nd.ks.sign(local_fid, msg)
        # TinySSB 0.1 only allows one remote feed
        self.rfd = None
        if remote_fid is not None:
            self.rfd = nd.repo.get_log(remote_fid)
        self.pfd = None # pending feed (oldest unacked cont feed), test needed
        self.upcall = None # client(s), currently we ignore ports
        self.started = False
        self.window_length = 7

    def add_remote(self, remote_fid):
        self.rfd = self.nd.repo.get_log(remote_fid)

    def register(self, port, client):
        self.upcall = lambda buf: client.upcall(buf)

    def deregister(self, port):
        self.upcall = None

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
        if pkt.typ[0] == [packet.PKTTYPE_contdas]:
            # self.rfd.remove(pkt.fid)
            # self.rfd[pkt.payload[:32]] = self.nd.repo.get_log(pkt.payload[:32])
            self.rfd = self.nd.repo.get_log(pkt.payload[:32])
            # self.nd.repo.del_log(pkt.fid)
            return
        if pkt.typ[0] == packet.PKTTYPE_iscontn:
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
            return
        if pkt.typ[0] == packet.PKTTYPE_acknldg:
            dbg(GRE, f"SESS: processing ack")
            if self.pfd == None:
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
            return
        if pkt.typ[0] == packet.PKTTYPE_plain48:
            # print("sliding: doing upcall")
            if self.upcall != None:
                self.upcall(pkt.payload)
        
    def set_upcall(self, upcall):
        self.upcall = upcall

    def start(self, callback=None):
        # does upcalls for all content received so far,
        # including acknowledging (and indirectly free) segments
        # FIXME: what about child logs?
        i = 1
        # for feed in self.rfd:
        while i <= len(self.rfd):
            pkt = self.rfd[i]
            self._process(pkt)
            if pkt.typ[0] == packet.PKTTYPE_contdas:
                i = 1  # restart loop for continuation segment
            else:
                i += 1
        if callback is None:
            # FIXME callback should be called AS WELL AS on_incoming
            callback = self.on_incoming
        self.rfd.set_append_cb(callback)
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
