# tinyssb/identity.py
import os

import bipf

from . import util, packet, application
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
    'send',
    'request_latest',
    'add_interface',
    'sync'
]

class Identity:

    def __init__(self, root, name, default_logs=None):
        self.nd = root
        self.name = name

        self.aliases = default_logs['aliases']
        self.public = default_logs['public']
        self.apps = default_logs['apps']
        self.directory = {'apps': {}, 'aliases': {}}

        self.__current_app = None

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
        self.nd.write_typed_48B(self.aliases, packet.PKTTYPE_set, buffer)
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
                self.nd.write_typed_48B(self.aliases, packet.PKTTYPE_delete, bytes(16)+public_key)
                self.nd.peers.remove(public_key)
                dbg(GRE, f"Unfollow: contact was deleted from contact list.")
                return
        raise NotFoundTinyException("Contact not deleted: not found in contact list.")

    def launch_app(self, app_name):
        if self.directory['apps'].get(app_name) is None:
            raise NotFoundTinyException(f"App {app_name} not found.")
        log = self.nd.repo.get_log(self.directory['apps'][app_name]['fid'])
        self.__current_app = application.Application(self.nd, log)
        return self.__current_app
        # TODO loop to request new data ?

    def add_app(self, app_name, appID):
        """
        :param app_name: a (locally) unique name
        :param appID: a (globally) unique 32 bytes ID
        """
        if self.directory['apps'].get(app_name) is not None:
            raise AlreadyUsedTinyException(f"App {app_name} is already used")

        fid = self.nd.ks.new(app_name)
        an = bipf.dumps(app_name)
        an += bytes(16 - len(an))
    
        for app in self.directory['apps']:
            if self.directory['apps'][app]['appID'] == appID:
                self.nd.write_typed_48B(self.apps, packet.PKTTYPE_set, appID + an)
                entry = self.directory['apps'].pop(app)
                self.directory['apps'][app_name] = entry
                return None # changed app_name

        self.nd.repo.mk_child_log(self.apps,
                                  self.nd.ks.get_signFct(self.apps), fid,
                                  self.nd.ks.get_signFct(fid), an)
        self.nd.write_typed_48B(self.apps, packet.PKTTYPE_set, appID + an)
        self.directory['apps'][app_name] = { 'fid': fid, 'appID': appID }
        log = self.nd.repo.get_log(fid)
        self.__current_app = application.Application(self.nd, log)
        self.sync()
        return self.__current_app

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

        an = bipf.dumps(app_name)
        an += bytes(16-len(an))
        old_log = self.nd.repo.get_log(app['fid'])
        old_log.write_eof(lambda msg: self.nd.ks.sign(app['fid'], msg))

        self.nd.write_typed_48B(self.apps, packet.PKTTYPE_delete, appID + an)
        self.directory['apps'].pop(app_name)
        self.nd.ks.remove(app['fid'])

    def write_public(self, msg):
        if len(msg) > 48:
            dbg(GRE, f"Sending Blob!!!")
            self.nd.write_blob_chain(self.public, bipf.dumps(msg))
        else:
            dbg(GRE, f"Sending Log")
            self.nd.write_plain_48B(self.public, bipf.dumps(msg))

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
        """
        apps_feed = self.nd.repo.get_log(self.apps)
        for i in range(1, len(apps_feed)+1):
            pkt = apps_feed[i]
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
        aliases_feed = self.nd.repo.get_log(self.aliases)
        for i in range(1, len(aliases_feed)+1):
            pkt = aliases_feed[i]
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
                assert self.directory['aliases'].get(name) is None
                self.directory['aliases'][name] = fid
