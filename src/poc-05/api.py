# tinyssb/api.py
import os
import json

import cbor2

from tinyssb import util, start
from tinyssb import io, keystore, node, packet
from tinyssb import repository, session, symtab, util
from tinyssb.dbg import *
from tinyssb.start import *

"""
Nodejs :
  ssb-keys = [
    'generate', # (create_new_peer)
    'load_or_create_sync',  # with path to folder
    'sign_obj',
    'verify_obj'
  ]:
  only generate. load is not secure yet, and sign/verify are automatic
  
  ssb-validate = [
    'initial',  # return 'state'
    'append',  # takes <state, smth?, message>
    'create',  # takes <list_of_dest, fid, null?, content(?), timestamp>
  ]:
  First version: have only
  
  ssb-ref = [
    'isFeed'  # takes <fid>
  ]
  secret_stack = [
    'secretStack',  # takes <{appKey:"..."}>
    'stack',  # takes <{port, keys}>, return exampleApp
    'exampleApp.manifest',
    'exampleApp.address',
    'exampleApp.close'
  ]
"""

"""
What I want:
  clean
  generate id
  open id (stored in file system)
  add trust (for a given pk)
  list trusted peer (from file system)
  start session (with callback func as arg)
  send log (always to all trusted)
  send blob
  make child log
Later:
  add face
  set feed length
  close
"""

tinyssb = [
    'clean',
    'list_trusted',
    'generate_id',
    'open_id',
    'add_trust',
    'start_session',
    'send_log',
    'send_blob',
    'make_child_log'
]

def clean():
    """
    Delete all existing peers.
    :return: None
    """
    os.system("rm -rf data")

def list_trusted(by):
    with open(f"{start.DATA_FOLDER}{by}/config.json") as f:
        config = json.load(f)
    return config['alias']

def generate_id(name):
    """
    Create new peer (delete data if existing).
    Stores the data on the file system, make generic log, add udp_multicast as
    interface and start it (listen/read loops).
    Only trusted peer is self
    :param name: string
    :return: an instance of Node
    """
    ks, pk = create_keys(name)
    return start.mount_identity(name, ks, pk)

def open_id(local_name):
    """
    Launch a peer whose data is stored locally
    :param local_name: the name of the folder
    :return: instance of node
    :bug: use keystore load() and dump()
    """
    return start.load_identity(local_name)

def add_trust(local_node, public_key, alias=""):
    start.add_trust(local_node, public_key, alias)

def start_session(node, local_session_fid, remote_session_id, fct=None, window_length=0):
    """
    Tell tinyssb what to do with incoming messages.
    Also add reciprocity: the local log subscribes to the remote log
    :param node: local node
    :param local_session_fid: fid of local
    :param remote_session_id: fid to subscribe to
    :param window_length: number of entries in a log
    :param fct: callback function
    """
    # Get log, create it if needed
    remote_id_log = node.repo.get_log(remote_session_id)
    node.repo.get_log(local_session_fid).subscription += 1

    # Use remote's main feed
    node.sess = session.SlidingWindow(node, local_session_fid, remote_session_id)
    node.sess.start(fct)
    if window_length > 0:
        node.sess.window_length = window_length
    return node.sess

def send_log(session, msg):
    """
    Send a log message, that must be less than 48B
    :param msg: bytes array
    :bug: should send blob if too long
    """
    session.write_plain_48B(cbor2.dumps([msg]))

def send_blob(session, msg):
    session.write_blob_chain(cbor2.dumps(msg))

def send(session, msg):
    if len(msg) > 48:
        dbg(GRE, f"Sending Blob!!!")
        send_blob(session, msg)
    else:
        dbg(GRE, f"Sending Log")
        send_log(session, msg)


def make_child_log(node, session_name="session"):
    fid = node.me
    local_session_fid = node.ks.new(session_name)
    # Add usage session name?
    packets = node.repo.mk_child_log(fid, nd.ks.get_signFct(fid), local_session_fid,
                                     nd.ks.get_signFct(local_session_fid))
    packets = [node.repo.get_log(fid)[1]] + packets
    node.push(packets, True)  # Why push packets to a newly created feed: who follows it?

def close(node, name):
    folder_path = start.DATA_FOLDER + name + '/_backed/'
    os.system(f"mkdir -p {folder_path}")

    file_name = util.hex(node.me)
    file_path = folder_path + file_name
    try:
        node.ks.dump(file_path)
    except FileNotFoundError:
        dbg(GRE, f"File not found")
        os.system(f"mkdir -p {file_path}")
        node.ks.dump(file_path)

    # Close interfaces?
    # What else?

if __name__ == "__main__":
    # nd = load_identity("Charlie")
    if sys.argv[1] == 'C':
        my_name = "Charlie"
        friend_name = "David"
        clean()
        local_node = generate_id(my_name)
        remote_node = generate_id(friend_name)

        friend = util.hex(remote_node.me)
        add_trust(local_node, util.hex(remote_node.me), friend_name)
        add_trust(remote_node, util.hex(local_node.me), my_name)
        close(remote_node, friend_name)
    else:
        my_name = "David"
        friend_name = "Charlie"
        local_node = load_identity(my_name)
        friend = list(list_trusted(my_name).keys())[1]

    me = util.hex(local_node.me)

    # bob = util.fromhex(list(list_trusted('Charlie').keys())[1])

    dbg(BLU, f"{util.hex(local_node.me)} and {friend}")
    sess = {start_session(local_node, local_node.me, util.fromhex(friend), None, 5)}
                         # lambda m: print(f"Received: {m}"), 5)
    # send_blob(sess, bytes(1000))
    # dbg(YEL, f"Blob done")
    # for i in range(105):
    #     send_log(sess, bytes(str(i), 'utf-8'))
    dbg(YEL, f"Log done")
    while True:
        try:
            cmd = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("Exiting")
            break
        if cmd == 'q':
            break
        if cmd.startswith('add'):
            key = cmd.split(' ')[1]
            add_trust(local_node, key, cmd.split(' ')[2])
            sess.add(start_session(local_node, local_node.me, util.fromhex(key), None, 5))
        for s in sess:
            send(s, 'Hello!')
            send(s, cmd)
    close(local_node, my_name)
    pass
