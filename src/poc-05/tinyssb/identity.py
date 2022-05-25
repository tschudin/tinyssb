# tinyssb/identity.py
import os

import bipf

from . import session, util, packet
from .exception import *
from .dbg import *

__all__ = [
    'Identity'
]
__id__ = [
    'list_contacts',
    'follow',
    'unfollow',
    'launch_app',
    'add_app',
    'delete_app',
    'open_session',
    'send',
    'request_latest',
    'add_interface',
    'sync'
]

class Identity:

    def __init__(self, root, name, default_logs=None):
        self.nd = root
        self.name = name

        self.aliases = self.nd.repo.get_log(default_logs['aliases'])
        self.public = self.nd.repo.get_log(default_logs['public'])
        self.apps = self.nd.repo.get_log(default_logs['apps'])
        self.directory = {'apps': {}, 'aliases': {}}

        # the (local) feed I am currently writing to
        self.__current_feed = default_logs['public']
        self.__current_app = None
        # allows for an app with more than one peer
        # TODO delete
        self.__current_sessions = []

        self.__load_contacts()
        self.__load_apps()
        self.sync()

    def list_contacts(self):
        """
        List contacts, key/values being fid/alias_name
        :return: a (python) list
        """
        return self.directory['aliases']

    def follow(self, public_key, alias):
        """
        Subscribe to the feed with the given pk
        :param public_key: bin encoded feedID
        :param alias: name to give to the peer
        :return: True if succeeded (if alias and public key were not yet in db)
        """
        if self.directory['aliases'].get(alias):
            raise AlreadyUsedTinyException(f"Follow: alias {alias} already exists.")
        for key, value in self.directory['aliases'].items():
            if value == public_key:
                raise AlreadyUsedTinyException(f"Public key is already in contact list.")
        self.directory['aliases'][alias] = public_key

        encoded_alias = bipf.dumps(alias)
        if len(encoded_alias) > 16:
            raise TooLongTinyException(f"Alias {alias} is too long")
        buffer = public_key + encoded_alias + bytes(16 - len(encoded_alias))
        dbg(MAG, f"Buffer: 16 >= {len(encoded_alias)}; 48 == {len(buffer)}; name = {bipf.loads(buffer[32:])}")
        self.nd.write_typed_48B(self.aliases.fid, packet.PKTTYPE_set, buffer)
        self.nd.peers.append(public_key)
        self.sync()

    def unfollow(self, public_key):
        """
        Unsubscribe from the feed with the given pk
        :param public_key: bin encoded feedID
        :return: True if succeeded
        """
        for key, value in self.directory['aliases'].items():
            if value == public_key:
                self.directory['aliases'].pop(key)
                self.nd.write_typed_48B(self.aliases.fid, packet.PKTTYPE_delete,bytes(16)+public_key)
                self.nd.peers.remove(public_key)
                dbg(GRE, f"Unfollow: contact was deleted from contact list.")
                return
        raise NotFoundTinyException("Contact not deleted: not found in contact list.")

    def launch_app(self, app_name):
        if self.directory['apps'].get(app_name) is None:
            raise NotFoundTinyException(f"App {app_name} not found.")
        self.__current_feed = self.directory['apps'][app_name]['fid']
        log = self.nd.repo.get_log(self.__current_feed)
        self.__current_app = session.Application(self.nd, log)
        return self.__current_app.instances
        # TODO loop to request new data ?

    def add_app(self, app_name, appID):
        """
        :param app_name: a (locally) unique name
        :param appID: a (globally) unique 32 bytes ID
        """
        if self.directory['apps'].get(app_name) is not None:
            raise AlreadyUsedTinyException(f"App {app_name} is already used")

        apps_log_fid = self.apps.fid
        fid = self.nd.ks.new(app_name)
        an = bipf.dumps(app_name)
        an += bytes(16 - len(an))
    
        for app in self.directory['apps']:
            if self.directory['apps'][app]['appID'] == appID:
                self.nd.write_typed_48B(apps_log_fid, packet.PKTTYPE_set,appID+an)
                entry = self.directory['apps'].pop(app)
                self.directory['apps'][app_name] = entry
                return None # changed app_name

        self.nd.repo.mk_child_log(apps_log_fid,
                                     self.nd.ks.get_signFct(apps_log_fid), fid,
                                     self.nd.ks.get_signFct(fid), an)
        self.nd.write_typed_48B(apps_log_fid, packet.PKTTYPE_set,appID+an)
        self.directory['apps'][app_name] = { 'fid':fid, 'appID': appID }
        self.__current_feed = fid
        log = self.nd.repo.get_log(self.__current_feed)
        self.__current_app=session.Application(self.nd,log)
        self.sync()
        return self.__current_app.instances

    def open_session(self, remote_session_id, fct=None, window_length=0):
        """
        Open a game or a session of an app.
        Our job is to keep track of the data to send, receive and write
        to the disc.
        It should accept a game_id (content in the app sub-feed), look for the
        participant(s), open a session with them (i.e. try to fetch data from their
        logs) and start an instance of session.Session

        :param remote_session_id: fid to subscribe to
        :param window_length: number of entries in a log
        :param fct: callback function
        :bug: buggy
        FIXME exchange public key for app sub-feed
        """
        dbg(GRE,
            f"Start session from \n{self.__current_feed} to \n{remote_session_id}\nwith"
            f" length = {window_length}")
        # Get log, create it if needed

        # remote_id_log = self.nd.repo.get_log(remote_session_id)
        # assert remote_id_log is not None
        # dbg(GRE, f"{self.__current_feed} + {type(self.__current_feed)}")
        # self.nd.repo.get_log(self.__current_feed).subscription += 1

        # Use remote's main feed
        log = self.nd.repo.get_log(self.__current_feed)
        app = session.Application(self.nd, log, remote_session_id)
        # sess.start(fct)
        # if window_length > 0:
        #     app.window_length = window_length
        self.__current_sessions.append(app)
        return app

    def delete_app(self, app_name, appID):
        """
        :param app_name: a (locally) unique name
        :param appID: a (globally) unique 32 bytes ID
        """
        app = self.directory['apps'].get(app_name)
        if app is None:
            raise NotFoundTinyException(f"App {app_name} does not exist (already deleted?)")
        if appID != app['appID']:
            raise TinyException(f"AppID do not match '{app_name}'")

        apps_log_fid = self.apps.fid
        an = bipf.dumps(app_name)
        an += bytes(16-len(an))
        old_log = self.nd.repo.get_log(app['fid'])
        old_log.write_eof(lambda msg: self.nd.ks.sign(app['fid'], msg))

        self.nd.write_typed_48B(apps_log_fid, packet.PKTTYPE_delete,appID+an)
        self.directory['apps'].pop(app_name)
        self.nd.ks.remove(app['fid'])

    def send(self, msg):
        if len(msg) > 48:
            dbg(GRE, f"Sending Blob!!!")
            self._send_blob(msg)
        else:
            dbg(GRE, f"Sending Log")
            self._send_log(msg)

    def _send_log(self, msg):
        """
        Send a log message, that must be less than 48B
        :param msg: bytes array
        :bug: should send blob if too long
        """
        for sess in self.__current_sessions:
            sess.write_48B(bipf.dumps([msg]))

    def _send_blob(self, msg):
        for sess in self.__current_sessions:
            sess.write_blob_chain(bipf.dumps(msg))

    def request_latest(self, friend_id=None, comment="api"):
        """
        Request the latest packet to be sent again.
        If no argument is used, request from all
        peers in the current session
        :param friend_id: bin encoded public key
        :param comment: bounded length comment
        :return:
        """
        if friend_id is None:
            repository = self.nd.repo
            for feed in self.nd.peers:
                self.nd.request_latest(repository, repository.get_log(feed), comment)
        else:
            self.nd.request_latest(self.nd.repo,
                                      self.nd.repo.get_log(friend_id), comment)

    def add_interface(self):
        pass

    def sync(self):
        folder_path = util.DATA_FOLDER + self.name + '/_backed/'
        os.system(f"mkdir -p {folder_path}")

        file_name = util.hex(self.nd.me)
        file_path = folder_path + file_name
        try:
            self.nd.ks.dump(file_path)
        except FileNotFoundError:
            dbg(GRE, f"File not found")
            os.system(f"mkdir -p {file_path}")
            self.nd.ks.dump(file_path)
        # What else?

    def __load_apps(self):
        """
        Read 'apps' feed and fill the corresponding dictionary.
        app_name is the only TODO
        """
        for i in range(1, len(self.apps)+1):
            pkt = self.apps[i]
            if pkt.typ[0] == packet.PKTTYPE_mkchild:
                fid = pkt.payload[:32]
                app_name = bipf.loads(pkt.payload[32:])
                # No checking for uniqueness: further mk_child will override feedID for an app
                if self.directory['apps'].get(app_name) is None:
                    self.directory['apps'][app_name] = { 'fid': fid }
                else:
                    self.directory['apps'][app_name]['fid'] = fid

            elif pkt.typ[0] == packet.PKTTYPE_set:
                appID = pkt.payload[:32]
                app_name = bipf.loads(pkt.payload[32:])
                # each 'set' must come after a 'mk_child'
                # (but there can be several 'set' for a 'mk_child')
                a = self.directory['apps'].get(app_name)
                if a is not None:
                    a['appID'] = appID
                else:
                    for a in self.directory['apps']:
                        if a.get('appID') == appID:
                            self.directory['apps'][app_name] = {'fid': a.get('fid'),
                                                                'appID': appID}
                            self.directory['apps'].pop(a)
                #         continue
                # assert self.directory['apps'].get(app_name) is not None
                # self.directory['apps'][app_name]['appID'] = appID

            elif pkt.typ[0] == packet.PKTTYPE_delete:
                appID = pkt.payload[:32]
                app_name = bipf.loads(pkt.payload[32:])

                to_delete = self.directory['apps'].get(app_name)
                assert to_delete is not None
                assert to_delete['appID'] == appID
                self.directory['apps'].pop(app_name)

    def __load_contacts(self):
        """
        Read 'aliases' feed and fill the contact dictionary.
        :return: nothing
        """
        for i in range(1, len(self.aliases)+1):
            pkt = self.aliases[i]
            if pkt.typ[0] == packet.PKTTYPE_delete:
                fid = pkt.payload[16:]
                to_delete = []
                for key, value in self.directory['aliases'].items():
                    if value == fid:
                        to_delete.append(key)
                for k in to_delete:
                    self.directory['aliases'].pop(k)
            if pkt.typ[0] == packet.PKTTYPE_set:
                fid = pkt.payload[:32]
                name = bipf.loads(pkt.payload[32:])
                # dbg(GRE, f"{i}: {name}: {fid}; {self.directory['aliases'].get(name)}")
                assert self.directory['aliases'].get(name) is None
                self.directory['aliases'][name] = fid
