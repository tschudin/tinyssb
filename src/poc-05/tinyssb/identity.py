# tinyssb/identity.py
import json
import os

import bipf
import cbor2

from . import start, session, util, packet
from .dbg import *

__all__ = [
    'Identity'
]

class Identity:

    def __init__(self, node_, name, default_logs=None):
        self._node = node_
        self.name = name
        # the (local) feed I am currently writing to
        self.__current_feed = None

        # allows for an app with more than one peer
        self.__current_sessions = []

        self.directory = {'apps': {}, 'aliases': {}}
        self.aliases = self._node.repo.get_log(default_logs['aliases'])
        self.public = self._node.repo.get_log(default_logs['public'])
        self.apps = self._node.repo.get_log(default_logs['apps'])
        self.__load_contacts()
        self.sync()

    def get_root_directory(self):
        """
        Read the default feeds and return a list of accessible objects.
        Example:
        rd = identity.get_root_directory()
        ad = rd['apps']
        chess_games = ad['chess']

        Fill self.directory and return it
        :return: a dictionary
        """
        return self.directory

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
        # self.directory['aliases'][alias] = "abc"
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
        self._node.write_plain_48B(self.aliases.fid, buffer)
        self._node.peers.append(public_key)
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
                self._node.write_plain_48B(self.aliases.fid, bytes(16) + public_key)
                self._node.peers.remove(public_key)
                dbg(GRE, f"Unfollow: contact was deleted from contact list.")
                return
        raise NotFoundTinyException("Contact not deleted: not found in contact list.")

    def launch_app(self, app_name):
        key = self.directory['apps'][app_name]
        self.__current_feed = key
        # TODO loop to request new data ?

    def add_app(self, app_name, appID):
        """
        :param app_name: a (locally) unique name
        :param appID: a (globally) unique 32 bytes ID
        """
        if self.directory['apps'].get(app_name) is not None:
            raise AlreadyUsedTinyException(f"App {app_name} is already used")

        apps_log_fid = self.apps.fid
        fid = self._node.ks.new(app_name)
        an = cbor2.dumps(app_name)
        an += bytes(16 - len(an))
        self._node.repo.mk_child_log(apps_log_fid,
                                     self._node.ks.get_signFct(apps_log_fid), fid,
                                     self._node.ks.get_signFct(fid), an)
        self.directory['apps'][app_name] = fid
        self.__current_feed = fid

    def open_session(self, remote_session_id, fct=None,
                     window_length=0):
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
        remote_id_log = self._node.repo.get_log(remote_session_id)
        assert remote_id_log is not None
        dbg(GRE, f"{self.__current_feed} + {type(self.__current_feed)}")
        self._node.repo.get_log(self.__current_feed).subscription += 1

        # Use remote's main feed
        sess = session.Session(self._node, self.__current_feed, remote_session_id)
        sess.start(fct)
        if window_length > 0:
            sess.window_length = window_length
        self.__current_sessions.append(sess)

    def _send_log(self, msg):
        """
        Send a log message, that must be less than 48B
        :param msg: bytes array
        :bug: should send blob if too long
        """
        app = self.directory['apps'].get(app_name)
        if app is None:
            raise NotFoundTinyException(f"App {app_name} does not exist (already deleted?)")
        if appID != app['appID']:
            raise TinyException(f"AppID do not match '{app_name}'")

    def _send_blob(self, msg):
        for sess in self.__current_sessions:
            sess.write_blob_chain(cbor2.dumps(msg))

    def send(self, msg):
        if len(msg) > 48:
            dbg(GRE, f"Sending Blob!!!")
            self._send_blob(msg)
        else:
            dbg(GRE, f"Sending Log")
            self._send_log(msg)

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
            for s in self.__current_sessions:
                self.request_latest(s.rfd, comment)
        else:
            self._node.request_latest(self._node.repo,
                                      self._node.repo.get_log(friend_id), comment)

    def add_interface(self):
        pass

    def sync(self):
        dbg(RED, f"File name: {self.name}")
        folder_path = start.DATA_FOLDER + self.name + '/_backed/'
        os.system(f"mkdir -p {folder_path}")

        file_name = util.hex(self._node.me)
        file_path = folder_path + file_name
        try:
            self._node.ks.dump(file_path)
        except FileNotFoundError:
            dbg(GRE, f"File not found")
            os.system(f"mkdir -p {file_path}")
            self._node.ks.dump(file_path)
        # What else?

    def __load_contacts(self):
        """
        Read 'aliases' feed and fill the contact dictionary.
        :return: nothing
        """
        for i in range(1, len(self.aliases)+1):
            pkt = self.aliases[i]
            if pkt.typ[0] == packet.PKTTYPE_plain48:
                if pkt.payload[:16] == bytes(16):
                    fid = pkt.payload[16:]
                    to_delete = []
                    for key, value in self.directory['aliases'].items():
                        if value == fid:
                            to_delete.append(key)
                    for k in to_delete:
                        self.directory['aliases'].pop(k)

                    # pos = list(self.directory['aliases'].values()).index(fid)
                    # self.directory['aliases'].pop(list(self.directory['aliases'].keys()[pos]))
                else:
                    fid = pkt.payload[:32]
                    name = bipf.loads(pkt.payload[32:])
                    # dbg(GRE, f"{i}: {name}: {fid}; {self.directory['aliases'].get(name)}")
                    assert self.directory['aliases'].get(name) is None
                    self.directory['aliases'][name] = fid
