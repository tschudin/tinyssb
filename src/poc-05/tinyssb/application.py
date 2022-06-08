# tinyssb/application.py
# 2022-05-30 <et.mettaz@unibas.ch>

"""
__app__ = [
    'instances',
    'create_inst',
    'delete_inst',
    'start_inst',
    'add_remote_fid',
    'update_inst',
    'write_in_log',
    'send',
    'set_callback',
    'terminate_inst'
]
"""

import bipf
from . import packet
from .dbg import *
from .exception import NotFoundTinyException
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

    def create_inst(self, remote_fid, with_=None, name=None):
        """
        Create a new instance (game).
        'with' is the fid of the remote feed. It can be null (use-case: chat app with 'note-to-self').
        The 3 fields can be added / updated later (see add_remote_fid() and update_inst()).
        """
        local_fid = self.node.ks.new(self.next_inst_id)
        while self.instances.get(str(self.next_inst_id)) is not None:
            self.next_inst_id += 1
        assert bipf.encodingLength(self.next_inst_id) < 48  # Must fit in 48B for 'delete'
        n = bipf.dumps(self.next_inst_id)
        n += bytes(16 - len(n))
        self.node.repo.mk_child_log(self.log.fid, self.node.ks.get_signFct(self.log.fid),
            local_fid, self.node.ks.get_signFct(local_fid), n)

        p = { 'id': self.next_inst_id, 'il': local_fid, 'l': local_fid }
        if with_ is not None:
            p['w'] = with_
        if name is not None:
            p['n'] = name
        self.window = SlidingWindow(self, self.node, self.next_inst_id, local_fid, remote_fid, self.callback)
        if remote_fid is not None:
            p['ir'] = remote_fid
            p['r'] = remote_fid
            self.window.start()
            self.write_in_log(bipf.dumps(p), packet.PKTTYPE_set)
        ret = str(p.pop('id'))
        self.instances[str(self.next_inst_id)] = p
        self.next_inst_id += 1
        return ret

    def delete_inst(self, inst_id):
        """ Delete an instance """
        self.terminate_inst(inst_id)

        i = self.instances.pop(str(inst_id))
        fid = i['il']
        while fid != bytes(32):
            log = self.node.repo.get_log(fid)
            pkt = log[log.frontS]
            assert pkt.typ[0] == packet.PKTTYPE_contdas

            self.node.ks.remove(fid)
            # Delete feed
            fid = pkt.payload[:32]

        self.write_in_log(bipf.dumps({ 'id': inst_id }), packet.PKTTYPE_delete)

    def start_inst(self, inst_id):
        """ Load and start a game/instance """
        if self.window.id_number != inst_id:
            inst = self.instances.get(str(inst_id))
            if inst is None:
                raise NotFoundTinyException(f"There is no instance with id = {inst_id}")
            self.window = SlidingWindow(self, self.node, inst_id, inst['l'], inst['r'], self.callback)
        self.window.start()

    def add_remote_fid(self, inst_id, initial_remote_fid):
        """ Add remote fid if it wasn't known at instance creation. Call max once per instance """
        if self.instances.get(str(inst_id)).get('ir') is not None:
            self.update_inst(inst_id, initial_remote_fid)
            return  # error: this method should be for the initial rfid only
        p = self.instances[str(inst_id)]
        p['ir'] = initial_remote_fid
        if self.window.id_number == inst_id:
            self.window.add_remote(initial_remote_fid)
            self.window.start()
            self.write_in_log(bipf.dumps(p), packet.PKTTYPE_set)
        self.instances[str(inst_id)]['ir'] = initial_remote_fid
        self.instances[str(inst_id)]['r'] = initial_remote_fid

    def update_inst(self, inst_id, remote_fid, with_=None, name=None, local_fid=None):
        """ Update any field (except initial feeds) """
        inst = self.instances.get(str(inst_id))
        if inst is None:
            raise NotFoundTinyException(f"There is no instance with id = {inst_id}")
        p = { 'id': inst_id }
        if local_fid is not None:
            p['l'] = local_fid
            inst['l'] = local_fid
        if remote_fid is not None:
            p['r'] = remote_fid
            inst['r'] = remote_fid
        if with_ is not None:
            p['w'] = with_
            inst['w'] = with_
        if name is not None:
            p['n'] = name
            inst['n'] = name
        self.write_in_log(bipf.dumps(p), packet.PKTTYPE_set)

    def write_in_log(self, msg, typ=packet.PKTTYPE_plain48):
        """ Write in this app's log (ex. for inst. creation or field update) """
        if len(msg) > 48:
            self.node.write_blob_chain(self.log.fid, msg)
        else:
            msg = msg + bytes(48 - len(msg))
            self.node.write_typed_48B(self.log.fid, typ, msg)

    def send(self, msg):
        """ Send data to the other participant by writing in the local feed """
        if self.window is not None and not self.window.started:
            self.window.start()
        if len(msg) > 48:
            self.window.write_blob_chain(self.log.fid, msg)
        else:
            msg = msg + bytes(48 - len(msg))
            self.window.write_plain_48B(self.log.fid, msg)

    def set_callback(self, callback):
        """ Set callback for received messages """
        self.callback = callback
        if self.window is not None:
            self.window.set_upcall(callback)

    def terminate_inst(self, inst_id):
        """ Terminate a game or instance (write a final 'end_of_file' message) """
        if self.instances.get(str(inst_id)) is None:
            raise NotFoundTinyException(f"There is no instance with id = {inst_id}")
        if self.window.id_number == inst_id:
            self.window.close()
        fid = self.instances[str(inst_id)]['il']
        self.node.repo.get_log(fid).write_eof(lambda msg: self.node.ks.sign(fid, msg))

    def __load_instances(self):
        for i in range(1, len(self.log)+1):
            pkt = self.log[i]
            if pkt.typ[0] == packet.PKTTYPE_delete:
                inst_id = bipf.loads(pkt.payload)['id']
                self.instances.pop(inst_id)
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
