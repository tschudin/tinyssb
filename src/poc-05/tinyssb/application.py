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
from . import packet, util
from .dbg import *
from .exception import *
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
        """
        Create a new instance (game).
        'with' is the fid of the remote peer's `public` feed. It can be null
        (use-case: chat app with 'note-to-self'). In that case, remote_fid is
        discarded too (one can add a remote feed only if it is linked to a contact).
        The 3 fields can be added / updated later (see add_remote and update_inst).
        """
        local_fid = self.node.ks.new(self.next_inst_id)
        while self.instances.get(str(self.next_inst_id)) is not None:
            self.next_inst_id += 1
        assert bipf.encodingLength(self.next_inst_id) < 48  # Must fit in 48B for 'delete'
        n = bipf.dumps(self.next_inst_id)
        n += bytes(max(16 - len(n), 0))
        self.node.repo.mk_child_log(self.log.fid, self.node.ks.get_signFct(self.log.fid),
            local_fid, self.node.ks.get_signFct(local_fid), n)

        peer = { 'id': self.next_inst_id, 'il': local_fid, 'l': local_fid }
        if name is not None:
            peer['n'] = name
        self.window = SlidingWindow(self, self.node, self.next_inst_id, local_fid, remote_fid, self.callback)
        self.write_in_log(bipf.dumps(peer), packet.PKTTYPE_set)
        ret = str(peer.pop('id'))
        peer['w'] = {}
        self.instances[ret] = peer
        if with_ is not None:
            self.add_remote(self.next_inst_id, with_, remote_fid)
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

    def update_inst(self, inst_id, remote_fid, with_, name=None, local_fid=None):
        """
        Update any field (except initial feeds)
        To update a remote fid, one need its public id ('with_').
        See update_inst_remote in the opposite case.
        """
        inst = self.instances.get(str(inst_id))
        if inst is None:
            raise NotFoundTinyException(f"There is no instance with id = {inst_id}")
        p = { 'id': inst_id }
        if local_fid is not None:
            p['l'] = local_fid
            inst['l'] = local_fid
        if name is not None:
            p['n'] = name
            inst['n'] = name

        self.write_in_log(bipf.dumps(p), packet.PKTTYPE_set)
        if with_ is not None:
            self.add_remote(inst_id, with_, remote_fid)

    def add_remote(self, inst_id, with_, remote_fid=None):
        """ Add a member to an instance """
        if self.instances.get(str(inst_id)) is None:
            raise NotFoundTinyException(f"There is no instance with id = {inst_id}")
        if with_ is None:
            raise NullTinyException("with_ is None")

        hex_with = util.hex(with_)

        if self.window.id_number == inst_id:
            self.window.add_remote(remote_fid)
            self.window.start()

        for tmp in self.instances[str(inst_id)].get('w'):
            if tmp == hex_with:
                if self.instances[str(inst_id)]['w'][hex_with].get('ir') is None:
                    self.instances[str(inst_id)]['w'][hex_with]['ir'] = remote_fid
                self.instances[str(inst_id)]['w'][hex_with]['r'] = remote_fid
                update = { 'id': str(inst_id), 'w': with_, 'r': remote_fid }
                self.write_in_log(bipf.dumps(update), packet.PKTTYPE_set)
                return

        self.instances[str(inst_id)]['w'][hex_with] = { 'r': remote_fid, 'ir': remote_fid }
        update = { 'id': str(inst_id), 'w': with_, 'r': remote_fid }
        self.write_in_log(bipf.dumps(update), packet.PKTTYPE_set)

    def update_inst_with_old_remote(self, inst_id, new_remote_fid, old_remote_fid):
        """
        Update the remote fid of an instance.
        To use if one has the old remote fid but not the public id ('with_').
        """
        if self.instances.get(str(inst_id)) is None:
            raise NotFoundTinyException(f"There is no instance with id = {inst_id}")
        if new_remote_fid is None:
            raise NullTinyException("new_remote_fid is null")
        for tmp in self.instances[str(inst_id)].get('w'):
            if tmp['r'] == old_remote_fid or tmp['ir'] == old_remote_fid:
                self.add_remote(inst_id, tmp['w'], new_remote_fid)
                return
        raise TinyException("old_remote_fid is not found")

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

        if payload.get('w') is not None:
            hex_with = util.hex(payload['w'])
            assert payload['r'] is not None
            if self.instances[inst_id].get('w') is None:
                self.instances[inst_id]['w'] = {}
            if self.instances[inst_id]['w'].get(hex_with) is None:
                self.instances[inst_id]['w'][hex_with] = { 'r': payload['r'], 'ir': payload.get('r') }
            else:
                tmp = self.instances[inst_id]['w'][hex_with]
                if tmp.get('ir') is None:
                    tmp['ir'] = payload['r']
                tmp['r'] = payload['r']
            return

        for field in ['l', 'n']:
            tmp = payload.get(field)
            if tmp is not None:
                self.instances[inst_id][field] = tmp

        dbg(GRA, f"Inst = {self.instances[inst_id]}")

# eof
