# tinyssb/application.py
# 2022-05-30 <et.mettaz@unibas.ch>

"""
__app__ = [
    'create_inst',
    'delete_inst',
    'terminate_inst',
    'resume_inst',
    'add_remote',
    'send',
    'set_callback'
]
"""

import bipf
from . import packet, util
from .exception import *
from .node import LOGTYPE_public, LOGTYPE_remote
from .session import SlidingWindow

class Application:

    def __init__(self, log_manager, log, callback=None):
        self.manager = log_manager
        self.window = None
        self.callback = callback
        self.instances = {}
        self.log = log
        self.next_inst_id = 0

        self.__load_instances()

    def create_inst(self, name=None):
        """
        Create a new instance (game).
        """
        # 1.0 (public), 2.1, 3.0, _, 4.1
        while self.instances.get(str(self.next_inst_id)) is not None:
            self.next_inst_id += 1

        # 1.0
        fid = self.manager.create_on_disk(self.log.fid, self.next_inst_id, LOGTYPE_public)

        # 3.0
        peer = { 'id': self.next_inst_id, 'il': fid, 'l': fid }
        if name is not None:
            peer['n'] = name
        self.manager.set_in_log(self.log.fid, bipf.dumps(peer))

        # 2.1
        ret = str(peer.pop('id'))
        peer['w'] = {}
        self.instances[ret] = peer


        # 4.1
        self.window = SlidingWindow(self, self.manager, self.next_inst_id, fid, self.callback)

        self.next_inst_id += 1
        return ret

    def delete_inst(self, inst_id):
        """
        Delete an instance and erase its data on disk
        """
        # 1.3, 2.1, 3.1, _ + terminate_inst

        self.terminate_inst(inst_id)

        # 2.1
        i = self.instances.pop(str(inst_id))

        # 1.3 and 3.1
        self.manager.delete_on_disk(i['il'], self.log.fid, bipf.dumps({ 'id': inst_id }))

    def terminate_inst(self, inst_id):
        """
        Terminate a game or instance (write a final 'end_of_file' message)
        Keep the data on disk as well as the inst in self.instances
        """
        # _, _, _, 4.1, 5.2
        if self.instances.get(str(inst_id)) is None:
            raise NotFoundTinyException(f"There is no instance with id = {inst_id}")

        # 4.1
        if self.window and self.window.id_number == inst_id:
            self.window.close()
        self.window = None

        # 5.2
        fid = self.instances[str(inst_id)]['il']
        self.manager.write_eof(fid)

    def resume_inst(self, inst_id):
        """ Load and start a game/instance """
        # _, _, _, 4,1
        # 1.1 and 2.1 are taken care of in __load_inst
        if self.window is not None and self.window.id_number != inst_id:
            self.window.close()
            self.window = None
        if self.window is None or self.window.id_number != inst_id:
            inst = self.instances.get(str(inst_id))
            if inst is None:
                raise NotFoundTinyException(f"There is no instance with id = {inst_id}")
            self.window = SlidingWindow(self, self.manager, inst_id, inst['l'], self.callback)
            for remote in inst.get('w'):
                self.window.add_remote(inst['w'][remote].get('r'))
        self.window.start()

    def add_remote(self, inst_id, remote_fid, with_):
        """ Add a member to an instance """
        # 1.2, 2.1, 3.0, 4.1, 5.1
        if self.instances.get(str(inst_id)) is None:
            raise NotFoundTinyException(f"There is no instance with id = {inst_id}")
        if with_ is None:
            raise NullTinyException("with_ is None")

        # 1.2
        self.manager.allocate_for_remote(remote_fid)

        # 4.1
        if self.window and self.window.id_number == inst_id:
            self.window.add_remote(remote_fid)
            self.window.start()

        # Not adding a member but updating its feed id
        hex_with = util.hex(with_)
        for tmp in self.instances[str(inst_id)].get('w'):
            if tmp == hex_with:
                # 2.1
                if self.instances[str(inst_id)]['w'][hex_with].get('ir') is None:
                    self.instances[str(inst_id)]['w'][hex_with]['ir'] = remote_fid
                self.instances[str(inst_id)]['w'][hex_with]['r'] = remote_fid

                # 3.0
                update = { 'id': str(inst_id), 'w': with_, 'r': remote_fid }
                self.manager.set_in_log(self.log.fid, bipf.dumps(update))
                return  # updated remote log

        # 2.1
        self.instances[str(inst_id)]['w'][hex_with] = { 'r': remote_fid, 'ir': remote_fid }

        # 3.0
        update = { 'id': str(inst_id), 'w': with_, 'r': remote_fid }
        self.manager.set_in_log(self.log.fid, bipf.dumps(update))

    def send(self, msg):
        """ Send data to the other participant by writing in the local feed """
        if self.window is not None and not self.window.started:
            self.window.start()
        self.window.write(msg)

    def set_callback(self, callback):
        """ Set callback for received messages """
        self.callback = callback
        if self.window is not None:
            self.window.set_callback(callback)

    def _update_inst(self, inst_id, remote_fid, with_, name=None, local_fid=None):
        """
        Update any field (except initial feeds)
        To update a remote fid, one need its public id ('with_').
        See update_inst_remote in the opposite case.
        """
        # _, 2.1, 3.0, 4.1
        inst = self.instances.get(str(inst_id))
        if inst is None:
            raise NotFoundTinyException(f"There is no instance with id = {inst_id}")

        # 2.1
        p = { 'id': inst_id }
        if local_fid is not None:
            p['l'] = local_fid
            inst['l'] = local_fid
        if name is not None:
            p['n'] = name
            inst['n'] = name

        # 3.0
        self.manager.set_in_log(self.log.fid, bipf.dumps(p))
        # self.write_in_log(bipf.dumps(p), packet.PKTTYPE_set)
        if with_ is not None:
            self.add_remote(inst_id, remote_fid, with_)

    def _update_inst_with_old_remote(self, inst_id, new_remote_fid, old_remote_fid):
        """
        Update the remote fid of an instance.
        To use if one has the old remote fid but not the public id ('with_').
        """
        if self.instances.get(str(inst_id)) is None:
            raise NotFoundTinyException(f"There is no instance with id = {inst_id}")
        if new_remote_fid is None:
            raise NullTinyException("new_remote_fid is null")
        peer = self.instances[str(inst_id)].get('w')
        for tmp in peer:
            if peer[tmp]['r'] == old_remote_fid or peer[tmp]['ir'] == old_remote_fid:
                self.add_remote(inst_id, new_remote_fid, util.fromhex(tmp))
                return
        raise TinyException("old_remote_fid is not found")

    def __load_instances(self):
        # 1.1, 2.1, _, _, _
        for i in range(1, len(self.log)+1):
            pkt = self.log[i]
            if pkt.typ[0] == packet.PKTTYPE_delete:
                inst_id = bipf.loads(pkt.payload)['id']
                out = self.instances.pop(inst_id)
                self.manager.deactivate_log(out['l'])
                for rem in out['w']:
                    self.manager.deactivate_log(rem['r'])
            elif pkt.typ[0] == packet.PKTTYPE_set:
                self.__extract_instance(bipf.loads(pkt.payload))
            elif pkt.typ[0] == packet.PKTTYPE_chain20:
                pkt.undo_chain(self.manager.get_blob_function())
                self.__extract_instance(bipf.loads(pkt.chain_content))

    def __extract_instance(self, payload):
        inst_id = str(payload['id'])
        if self.instances.get(inst_id) is None:
            # first entry for an inst must contain id and initial local feed
            self.instances[inst_id] = { 'il': payload.get('il'), 'l': payload.get('l'), 'w': {}}
            self.manager.activate_log(payload.get('l'), LOGTYPE_public)

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
                else:
                    self.manager.deactivate_log(tmp['ir'])
                tmp['r'] = payload['r']

            self.manager.activate_log(payload['r'], LOGTYPE_remote)
            return

        for field in ['l', 'n']:
            tmp = payload.get(field)
            if tmp is not None:
                self.instances[inst_id][field] = tmp
                if field == 'l':
                    self.manager.activate_log(tmp, LOGTYPE_public)

# eof
