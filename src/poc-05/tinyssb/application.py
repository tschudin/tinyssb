# tinyssb/application.py
# 2022-05-30 <et.mettaz@unibas.ch>

__app__ = [
    'instances',
    'create_inst',
    'update_game',
    'start',
    'send',
    'set_callback',
    'close'
]

import bipf
from . import packet
from .dbg import *
from .session import SlidingWindow

class Application:

    def __init__(self, nd, log, callback=None):
        self.node = nd
        self.window = None
        self.callback = callback
        self.instances = {}
        self.log = log
        self.next_inst_id = 0

        self.__load_instances()

    def create_inst(self, remote_fid, with_, name=None):
        local_fid = self.node.ks.new(self.next_inst_id)
        n = bipf.dumps(self.next_inst_id)
        n += bytes(16 - len(n))
        self.node.repo.mk_child_log(self.log.fid, self.node.ks.get_signFct(self.log.fid),
            local_fid, self.node.ks.get_signFct(local_fid), n)

        p = { 'id': self.next_inst_id, 'il': local_fid, 'l': local_fid, 'w': with_ }
        if name is not None:
            p['n'] = name
        self.window = SlidingWindow(self.node, self.next_inst_id, local_fid, remote_fid)
        if remote_fid is not None:
            p['ir'] = remote_fid
            p['r'] = remote_fid
            # self.window.start(self.callback)
            self.send(bipf.dumps(p), packet.PKTTYPE_set)
        p.pop('id')
        self.instances[str(self.next_inst_id)] = p
        self.next_inst_id += 1

    def add_remote_fid(self, inst_id, initial_remote_fid):
        p = self.instances[str(inst_id)]
        p['ir'] = initial_remote_fid
        if self.window.id_number == inst_id:
            self.window.add_remote(initial_remote_fid)
            self.window.start(self.callback)
            self.send(bipf.dumps(p), packet.PKTTYPE_set)
        self.instances[str(inst_id)]['ir'] = initial_remote_fid
        self.instances[str(inst_id)]['r'] = initial_remote_fid

    def update_game(self, inst_id, local_fid, remote_fid, with_, name):
        p = { 'id': inst_id }
        if local_fid is not None:
            p['l'] = local_fid
            self.instances[inst_id]['l'] = local_fid
        if remote_fid is not None:
            p['r'] = remote_fid
            self.instances[inst_id]['r'] = remote_fid
        if with_ is not None:
            p['w'] = with_
            self.instances[inst_id]['w'] = with_
        if name is not None:
            p['n'] = name
            self.instances[inst_id]['n'] = name
        self.send(bipf.dumps(p), packet.PKTTYPE_set)

    def start(self, inst_id):
        if self.window.id_number != inst_id:
            inst = self.instances.get(str(inst_id))
            self.window = SlidingWindow(self.node, inst_id, inst['l'], inst['r'])
        self.window.start(self.callback)

    def send(self, msg, typ=packet.PKTTYPE_plain48):
        if len(msg) > 48:
            self.node.write_blob_chain(self.log.fid, msg)
        else:
            self.node.write_typed_48B(self.log.fid, typ, msg)

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
                deleted = self.instances.pop(inst_id)  # TODO delete logs associated with it
            elif pkt.typ[0] == packet.PKTTYPE_set:
                self.__extract_instance(bipf.loads(pkt.payload))
            elif pkt.typ[0] == packet.PKTTYPE_chain20:
                pkt.undo_chain(lambda h: self.node.repo.fetch_blob(h))
                self.__extract_instance(bipf.loads(pkt.chain_content))

    def __extract_instance(self, payload):
        inst_id = str(payload['id'])
        if self.instances.get(inst_id) is None:
            # first entry for an inst must contain id and initial local feed
            self.instances[inst_id] = { 'il': payload.get('il'), 'l': payload.get('l')}

        for field in ['l', 'ir', 'r', 'w', 'n']:
            tmp = payload.get(field)
            if tmp is not None:
                self.instances[inst_id][field] = tmp

        if self.instances[inst_id].get('r') is None and \
                self.instances[inst_id].get('ir') is not None:
            self.instances[inst_id]['r'] = self.instances[inst_id]['ir']

        dbg(GRA, f"Inst = {self.instances[inst_id]}")

# eof
