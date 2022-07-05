# tinyssb/log_manager.py
# 2022-05-30 <et.mettaz@unibas.ch>
import _thread
import json
import os

import bipf
from tinyssb import packet, util
from tinyssb.dbg import *
from tinyssb.exception import *
from tinyssb.node import LOGTYPE_private, LOGTYPE_public, LOGTYPE_remote

class LogManager:

    def __init__(self, identity, node, default_logs):
        self.identity = identity
        self.node = node
        self.node.activate_log(default_logs['aliases'], LOGTYPE_private)
        self.node.activate_log(default_logs['apps'], LOGTYPE_private)
        self.node.activate_log(default_logs['public'], LOGTYPE_public)
        self.__save_key_lock = _thread.allocate_lock()

    def activate_log(self, fid, typ):
        self.node.activate_log(fid, typ)

    def deactivate_log(self, fid):
        self.node.deactivate_log(fid)

    def get_blob_function(self):
        return lambda h: self.node.repo.fetch_blob(h)

    def create_on_disk(self, parent_log_id, name, log_type): # 1.0
        """
        Create a new fid in disk
        :param parent_log_id: feed id of the feed where the make_child will be written
        :param name: the name of the new fid
        :param log_type: type of the fid (see add_log)
        :return: feed id of the new fid
        """
        assert log_type in [LOGTYPE_private, LOGTYPE_public]
        assert bipf.encodingLength(name) < 48  # Must fit in 48B for 'delete'

        fid = self.node.ks.new(name)
        n = bipf.dumps(name)
        n += bytes(max(16 - len(n), 0))
        packets = self.node.repo.mk_child_log(parent_log_id,
                            self.node.ks.get_signFct(parent_log_id), fid,
                            self.node.ks.get_signFct(fid), n)

        if log_type == LOGTYPE_public:
            self.node.push(packets)
        self.node.activate_log(fid, log_type)
        self.__save_keys()
        return fid

    def allocate_for_remote(self, fid): # 1.2
        self.node.repo.allocate_log(fid, 0, fid[:20])
        self.node.activate_log(fid, LOGTYPE_remote)

    def delete_on_disk(self, fid, parent_fid, data, all_logs=True): # 1.3 + 3.1
        log = self.get_log(fid)
        pkt = log[log.frontS]
        self.node.repo.del_log(log.fid)
        try: self.node.ks.remove(log.fid)
        except KeyError: pass  # remote log, we do not have the keys
        if pkt.typ[0] == packet.PKTTYPE_contdas and pkt.payload[:32] != bytes(32):
            fid = pkt.payload[:32]
            if all_logs:
                self.delete_on_disk(fid, parent_fid, data)
            else:
                del log
                return fid
        else:
            self.write_in_log(parent_fid, data, packet.PKTTYPE_delete)
            self.node.deactivate_log(fid)
        del log

    def set_in_log(self, fid, data): # 3.0
        """
        Set a value in a log.
        The data must be of type byte array (bipf.dumps() of bytes()),
        but can be of arbitrary length (will be padded in write_in_log)
        :param fid: feed id of the log to write to
        :param data: byte array, the value to set
        """
        assert self.node.logs[util.hex(fid)] != LOGTYPE_remote
        self.write_in_log(fid, data, packet.PKTTYPE_set)

    def write_in_log(self, fid, data, typ=packet.PKTTYPE_plain48): # 5.0
        """
        Write a packet in a fid.
        :param fid: feed id of the fid to write to
        :param data: the data to write (string)
        :param typ: the type of the packet
        """
        # assert self.logs[util.hex(fid)] == LOGTYPE_public
        if type(data) is str:
            data = bipf.dumps(data)
        if len(data) > 48:
            self.node.write_blob_chain(fid, data)
        else:
            data += bytes(48 - len(data))
            self.node.write_typed_48B(fid, data, typ)

    def create_continuation_log(self, local_fid):
        """
        Create a continuation feed on disk for the local instance Log
        :param local_fid: the current (deprecated) feed id
        :return: the new feed id
        """
        dbg(GRA, f"SESS: ending feed {util.hex(local_fid)[:20]}..")
        new_key = self.node.ks.new('continuation')
        new_sign = lambda msg: self.node.ks.sign(new_key, msg)
        packets = self.node.repo.mk_continuation_log(local_fid,
            lambda msg: self.node.ks.sign(local_fid, msg),
            new_key, new_sign)

        self.deactivate_log(local_fid)
        self.activate_log(packets[1].fid, LOGTYPE_public)
        self.node.arm_dmx(packets[0].dmx)
        self.node.push(packets)  # FIXME redundant with self.nd.write_typed_48B?
        return self.get_log(packets[1].fid)

    def add_remote(self, fid): # 5.1
        pass

    def get_log(self, fid):
        return self.node.repo.get_log(fid)

    def write_eof(self, fid):
        """
        Append an end_of_file packet to the feed.
        This closes the feed (but do not delete it)
        :param fid:
        :return:
        """
        self.node.repo.get_log(fid).write_eof(lambda msg: self.node.ks.sign(fid, msg))

    def __save_keys(self):
        """
        Flushes the keystore into disk for backup
        For security, saves it in a secondary file,
        then overrides the old version
        """
        file_path = util.DATA_FOLDER + self.identity.name + '/_backed/' + util.hex(self.node.me)
        self.__save_key_lock.acquire()
        self.node.ks.dump(file_path + ".part")

        try:
            os.system(f"mv {file_path}.part {file_path}")
        except Exception as ex:
            dbg(GRE, f"Problem in save_keys: {ex}")
        self.__save_key_lock.release()
        # dbg(BLU, f"Keys are saved")

    def __save_dmxt(self):
        """
        Saves all currently expected dmx to quickly restart later.
        For security, saves them in a secondary file,
        then overrides the old version
        :return the saved dmx:
        """
        dmx = {}
        for d in self.node.dmxt.keys():
            val = self.node.dmxt[d](None, None)
            if val is not None:
                dmx[util.hex(d)] = util.hex(val)
        prefix = f"{util.DATA_FOLDER}{self.identity.name}/_backed/"

        with open(prefix + "dmxt.json.part", "w") as f:
            f.write(util.json_pp(dmx))
        os.system(f"mv {prefix}dmxt.json.part {prefix}dmxt.json")
        # dbg(BLU, f"DMX are saved")
        return util.json_pp(dmx)

    def __load_dmxt(self):
        try:
            with open(f"{util.DATA_FOLDER}{self.identity.name}/_backed/dmxt.json", "r") as f:
                dmx = json.load(f)
        except FileNotFoundError:
            return # no dmx was saved
        for d, v in dmx.items():
            d = util.fromhex(d)
            feed = self.node.repo.get_log(util.fromhex(v))
            if feed is None:
                raise NotFoundTinyException(f"No feed for {v} ({util.fromhex(v)}): {self.node.repo.listlog()}")
            self.node.arm_dmx(d,
                lambda buf, n: self.node.incoming_logentry(d, feed, buf, n),
                "Reload dmx")

    def loop(self):
        self.node.start()
        self.__save_keys()
        time.sleep(2)
        self.__load_dmxt()

        while True:
            time.sleep(2)
            self.__save_dmxt()
            self.__save_keys()
        pass
# eof

"""
Action for logs:

We have 3 types of logs:
- local, private fid (root, aliases, apps, 'chess', 'chat' etc)
- local, public fid (public, instance '0' of 'chess', inst '2' of 'chat', etc)
- remote fid (public logs from another peer, same as public)

NB: The root fid is a bit special because we do not keep a live trace of it as we
hardly use it at runtime.

For each fid, we have to take care of different aspects:
- the state on the disk, divided in 2 parts:
    - when created (on disk)
        1.0 creating a local fid
        1.1 allocating space for a remote fid
    3.0 when updated
    1.2 when loaded after restart
- the live trace of the state, in id.directory or app.instances
- possible communication, depending on the type:
    - sending new messages (public local)
    - receiving new messages (remote)
    - none (private local) [this needs to be enforced]
- In addition, some logs are used for current activities and are link to an 
    object of a class:
    - Application for the current app
    - SlidingWindow for the current instance (with one to many logs, one being local)

We then have those actions:
- disk management at the beginning
    1.0 create on disk
    1.1 load from disk (also remove log in node.logs)
    1.2 allocate disk for remote
    1.3 delete on disk
- runtime trace of 
    2.0 all apps and aliases in id.directory
    2.1 all instances of running app in application.instances
- updating app or instance state on disk
    3.0 set data on disk (with a 'set' or packet) [in the parent fid, which is private]
    3.1 [NB: done directly in 1.3] delete data on disk (with a 'delete' or packet) [in the parent fid, which is private]
- management of the current state
    4.0 current app in identity
    4.1 current instance in application
- network communication
    5.0 write a packet in local fid (disk) and propagate it
    5.1 add callback for the reception of a packet from remote
    5.2 write and end_of_file packet on disk and propagate it

Can 5.1 be done in 1.1 or 1.2? I think so

Currently, points 2.x, 4.x and most of 1.1 is tackled in application and identity.

Please note that 1.0 creates a fid but 3.0 writes to another one, the parents fid

5.0 is not conducted at start up, but must be made available for later use

Also keep track of node.logs!!<

Each fid should be tackled by one of the 1.x function every time
TinySSB is launched except the app subfeeds that has to be tackled 
when the app is launched / created. In addition, it must record its
type (public/private/remote) in LogManager.logs


"""
#  TODO deletion
#  TODO 5.1
#   Also, all of public feed's protocol
