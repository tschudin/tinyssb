#!/usr/bin/env python3

# tinyChat.py
# 2022-04-06 <christian.tschudin@unibas.ch>

import hashlib
import json
import pure25519
import sys
import _thread
import time

from tinyssb import io, node, packet, repository, util
from tinyssb.dbg import *


# ----------------------------------------------------------------------

class Replicator:
    # answers replication requests, issues ARQs, fetches blob chains

    def __init__(self, nd, myFeed):
        self.nd = nd
        self.myFeed = myFeed
        self.pending_chains = []
        self.next_timeout = [0]
    
    def incoming_want_request(self, demx, buf, neigh):
        # dbg(GRA, f'RCV want@dmx={demx.hex()}')
        buf = buf[7:]
        while len(buf) >= 24:
            fid = buf[:32]
            seq = int.from_bytes(buf[32:36], 'big')
            # if fid != cfg['fid']: # only return this node's log
            #     dbg(RED, '    ignored (request for wrong fid)')
            #     break
            h = util.hex(fid)[:20]
            try:
                feed = self.nd.repo.get_log(fid)
                if feed:
                    x = feed[seq].wire
                    neigh.face.enqueue(feed[seq].wire)
                    # dbg(GRA, f'    have {h}.[{seq}], will send {x.hex()[:10]}')
            except:
                # dbg(GRA, f"    no entry for {h}.[{seq}]")
                pass
            buf = buf[36:]

    def incoming_blob_request(self, demx, buf, neigh):
        # dbg(GRA, f'RCV blob@dmx={util.hex(demx)}')
        buf = buf[7:]
        while len(buf) >= 22:
            hptr = buf[:20]
            cnt = int.from_bytes(buf[20:22], 'big')
            try:
                while cnt > 0:
                    blob = self.nd.repo.get_blob(hptr)
                    if not blob:
                        break
                    # dbg(GRA, f'    blob {util.hex(hptr)}, will send')
                    neigh.face.enqueue(blob)
                    cnt -= 1
                    hptr = blob[-20:]
            except Exception as e:
                print(e)
                # dbg(GRA, f"    no entry for {h}.[{seq}]")
                pass
            buf = buf[22:]

    def incoming_logentry(self, d, feed, buf, n):
        # dbg(GRA, f'RCV pkt@dmx={util.hex(d)}, try to append it')
        pkt = feed.append(buf)
        if not pkt:
            dbg(RED, "    verification failed")
            return
        self.nd.arm_dmx(d) # remove current DMX handler, request was satisfied
        h = util.hex(feed.fid)[:20]
        # dbg(GRE, f"    append {h}.[{len(feed)}]")
        self.request_latest(feed)
        # set timeout to 1sec more than production interval
        self.next_timeout[0] = time.time() + 6
        # FIXME: instead of eager blob request, make this policy-dependend
        # prepare for first blob in chain:
        if pkt.typ[0] == packet.PKTTYPE_chain20:
            pkt.undo_chain(lambda h: nd.repo.get_blob(h))
            self.request_chain(pkt)

    def incoming_chainedblob(self, cnt, h, buf, n):
        if len(buf) != 120: return
        # dbg(GRA, f"RCV blob@dmx={util.hex(h)} / chained")
        self.nd.arm_blob(h) # remove current blob handler, expected blob was received
        self.nd.repo.add_blob(buf)
        hptr = buf[-20:]
        if hptr != bytes(20):
            # rearm a blob handler for the next blob in the chain:
            # dbg(GRA, f"    awaiting next blob {util.hex(hptr)}")
            cnt -= 1
            if cnt == 0: # aks for next batch of blob
                d = packet._dmx(b'blobs')
                wire = d + hptr + int(4).to_bytes(2, 'big')
                for f in self.nd.faces:
                    f.enqueue(wire)
                    # dbg(GRA, f"SND blob chain request to dmx={d.hex()} for {hptr.hex()}")
                cnt = 4
            self.nd.arm_blob(hptr,
                        lambda buf,n: self.incoming_chainedblob(cnt,hptr,buf,n))
        else:
            # dbg(GRA, f"    end of chain was reached")
            pass

    def arm_for_front(self, feed):
        if feed == self.myFeed: return
        seq, prevhash = feed.getfront()
        nextseq = (seq+1).to_bytes(4, 'big')
        pktdmx = packet._dmx(feed.fid + nextseq + prevhash)
        # dbg(GRA, f"+dmx pkt@{util.hex(pktdmx)} for {util.hex(feed.fid)[:20]}.[{seq+1}]")
        self.nd.arm_dmx(pktdmx,
                        lambda buf,n: self.incoming_logentry(pktdmx, feed, buf, n))

    def request_latest(self, feed):
        self.arm_for_front(feed)
        seq = len(feed)+1
        want_dmx = packet._dmx(feed.fid + b'want')
        wire = want_dmx + feed.fid + seq.to_bytes(4, 'big')
        # does not need padding to 128B, it's not a log entry or blob
        d = util.hex(want_dmx)
        h = util.hex(feed.fid)[:20]
        for f in self.nd.faces:
            f.enqueue(wire)
            # dbg(GRA, f"SND {len(wire)} want request to dmx={d} for {h}.[{seq}]")

    def request_chain(self, pkt):
        print("request_chain", pkt.fid.hex()[:8], pkt.seq,
              pkt.chain_nextptr.hex() if pkt.chain_nextptr else None)
        hptr = pkt.chain_nextptr
        if hptr == None: return
        # dbg(GRA, f"+blob @{util.hex(hptr)}")
        self.nd.arm_blob(hptr,
                    lambda buf,n: self.incoming_chainedblob(4,hptr,buf,n))
        d = packet._dmx(b'blobs')
        wire = d + hptr + int(4).to_bytes(2, 'big')
        for f in self.nd.faces:
            f.enqueue(wire)
            # dbg(GRA, f"SND blob chain request to dmx={d.hex()} for {hptr.hex()}")

    def arq_loop(self):
        # dbg(GRA, f"This is Replication for node {util.hex(self.myFeed.fid)[:20]}")
        # prepare to serve incoming requests for logs I have
        for fid in self.nd.repo.listlog(): 
            want_dmx = packet._dmx(fid + b'want')
            # dbg(GRA, f"+dmx want@{util.hex(want_dmx)} for {util.hex(fid)[:20]}...")
            self.nd.arm_dmx(want_dmx,
                        lambda buf,n: self.incoming_want_request(want_dmx, buf, n))

        # prepare to serve blob requests
        blob_dmx = packet._dmx(b'blobs')
        # dbg(GRA, f"+dmx blob@{util.hex(blob_dmx)}")
        self.nd.arm_dmx(blob_dmx,
                        lambda buf,n: self.incoming_blob_request(blob_dmx, buf, n))
        while True: # periodic ARQ
            now = time.time()
            if self.next_timeout[0] < now:
                for fid in self.nd.repo.listlog():
                    if fid == self.myFeed.fid: continue
                    feed = self.nd.repo.get_log(fid)
                    self.request_latest(feed)
                rm = []
                for pkt in self.pending_chains:
                    pkt.undo_chain(lambda h: self.nd.repo.get_blob(h))
                    if pkt.content_is_complete():
                        rm.append(pkt)
                    else: # FIXME: should have a max retry count
                        self.request_chain(pkt)
                for r in rm:
                    self.pending_chains.remove(pkt)
                self.next_timeout[0] = now + 9
                time.sleep(10)
            else:
                time.sleep(self.next_timeout[0] - now)

    def start(self):
        print("  starting thread with replicator loop")
        _thread.start_new_thread(self.arq_loop, tuple())
        

# ----------------------------------------------------------------------

class ChatBackend:

    def __init__(self, path, nd, fid, signFct, alias={}):
        self.nd = nd
        self.alias = alias
        self.mySign = signFct
        self.logs = [self.nd.repo.get_log(fid) for fid in self.nd.repo.listlog()]
        self.myFeed = self.nd.repo.get_log(fid)
        self.frontier = {l.fid:len(l) for l in self.logs}
        self.msgs = [] # lst of (header lines, body lines, time)
        self.read_mail()
        self.replicator = Replicator(nd, self.myFeed)
        self.replicator.start()

        # time.sleep(1) # download as much as possible before the REVAL
        # msgs = read_mail(logs, front)

    def _add_pending_chain(self, pkt):
        pkt.undo_chain(lambda h: self.nd.repo.get_blob(h))
        if pkt.content_is_complete(): return
        # print("add to pending", pkt.seq)
        for p in self.replicator.pending_chains:
            if p.fid == pkt.fid and p.seq == pkt.seq: return
        self.replicator.pending_chains.append(pkt)

    def read_mail(self): # update our list of messages
        msglst = []
        for l in self.logs:
            # print("read_mail", l.fid.hex(), len(l))
            for i in range(len(l)-1):
                try: # should detect chat messages, instead of trial
                    pkt = l[i+2] # skip first log entry (with number 1)
                    if not pkt.content_is_complete():
                        self._add_pending_chain(pkt)
                        # pkt.undo_chain(lambda h: myNode.repo.get_blob(h))
                    if pkt.content_is_complete():
                        s = pkt.get_content()
                    else:
                        s = b'\n\n<incomplete>'
                    s = s.decode().split('\n')
                    sndr = f"@{util.b64(l.fid)}.ed25519"
                    if l.fid in self.alias:
                        sndr = self.alias[l.fid] + f" ({sndr})"
                    hdrs = ['From: ' + sndr]
                    try:
                        pos = s.index('')
                        hlst, body = s[:pos], s[pos+1:]
                        senddate = 0
                        for i in hlst:
                            if i.startswith('Date: '):
                                try:    senddate = int(i[6:])
                                except: pass
                        if senddate != 0:
                            hlst = ['Date: ' + time.ctime(senddate)] + \
                                   [h for h in hlst if not h.startswith('Date: ')]
                        msglst.append( (hdrs+hlst, body, senddate) )
                    except:
                        msglst.append( (hdrs+["Subject:"], s, 0) )
                except Exception as e:
                    print(e)
                    pass
        msglst.sort(key=lambda t: t[2], reverse=True)
        # print(msglst)
        self.msgs = msglst
        return msglst

    def write_mail(self, msg):
        if len(msg) <= 48:
            pkt = self.myFeed.write_plain_48B(msg + bytes(48 - len(msg)),
                                              self.mySign)
            bufs = [pkt.wire]
        else:
            pkt, blobs = self.myFeed.prepare_chain(msg, self.mySign)
            bufs = self.nd.repo.persist_chain(pkt, blobs)[:1]
        self.nd.push(bufs) # policy Q: only send out pkt, not blobs

# ----------------------------------------------------------------------

class ChatFrontend:
    
    help = {
        '-':     "move to previous message and print it",
        '?':     "print this help text",
        'header':"list up to 18 message headers",
        'mail':  "compose new mail",
        'next':  "move to next message and print it",
        'print': "print/show current mail message",
        'reply': "compose a reply to current message",
        'sync':  "sync up with new messages",
        'quit':  "terminates mail program (also: ^D, exit, xit)",
    }

    def __init__(self, backend, alias={}):
        self.backend = backend
        self.currhdr = 0 # where the current 18-line header window starts
        self.currmsg = 0
        self.alias  = alias
        self.cmd_table = {
            '-':      self.cmd_prev,
            'exit':   self.cmd_exit,
            '?':      self.cmd_help,
            'header': self.cmd_header,
            'mail':   self.cmd_mail,
            'next':   self.cmd_next,
            'print':  self.cmd_print,
            'reply':  self.cmd_reply,
            'sync':   self.cmd_sync,
            'quit':   self.cmd_exit,
            'xit':    self.cmd_exit,
        }

    def _countstr(self):
        s = 's' if len(self.backend.msgs) != 1 else ''
        return f"you have {len(self.backend.msgs)} message{s}"

    def _header_line(self, i):
        m = self.backend.msgs[i]
        s = [h for h in m[0] if h.startswith('Subject: ')]
        s = "<no subject>" if len(s) != 1 else s[0][9:]
        star = "*" if i == self.currmsg else " "
        return ("%4d%s" % ((i+1),star) + " " + s)[:79]

    def cmd_exit(self, arglst):
        print("\nby now")
        sys.exit(0)

    def cmd_header(self, arglst):
        if arglst[:1] == ['+']:
            self.currhdr += 18
            if self.currhdr >= len(self.backend.msgs) or \
                                       len(self.backend.msgs) - self.currhdr < 18:
                self.currhdr = len(self.backend.msgs) - 18
        if arglst[:1] == ['-']:
            self.currhdr -= 18
        if self.currhdr < 0:
            self.currhdr = 0
        print(self._countstr())
        for i in range(18):
            if self.currhdr + i >= len(self.backend.msgs):
                break
            print(self._header_line(self.currhdr + i))

    def cmd_help(self, arglst):
        print("UNIX Mail-like tinySSB chat")
        print("commands are:")
        for c in sorted(self.cmd_table.keys()):
            if c in self.help:
                print("  %-6s " % c, self.help[c])
        print("commands can be abbreviated")

    def _do_mail(self, subj):
        lines = []
        print("<< end message body with ^D at start of empty line")
        while True:
            try:
                t = input()
            except KeyboardInterrupt:
                print("\n<< aborted, no message sent")
                return
            except EOFError:
                break
            lines.append(t)
        hdrs = [f"Date: {int(time.time())}", "To: *", "Subject: " + subj]
        msg = ('\n'.join(hdrs) + '\n\n' + '\n'.join(lines)).encode()
        self.backend.write_mail(msg)
        print("<< message sent")

    def cmd_mail(self, arglst):
        print("To: *")
        try:
            s = input("Subject: ")
            self._do_mail(s)
        except (EOFError, KeyboardInterrupt):
            print("aborted")

    def cmd_next(self, arglst):
        if self.currmsg+1 >= len(self.backend.msgs):
            print("no more messages")
            return
        self.currmsg += 1
        self.cmd_print([])

    def cmd_prev(self, arglst):
        if self.currmsg <= 0:
            print("already at first message")
            return
        self.currmsg -= 1
        self.cmd_print([])

    def cmd_reply(self, arglst):
        if self.currmsg >= len(self.backend.msgs):
            print("no message to reply to")
            return
        s = ''
        for h in self.backend.msgs[self.currmsg][0]:
            if h.startswith('Subject: '):
                s = h[9:]
                break
        if not s.startswith('Re: '): s = "Re: " + s
        print("To: *")
        print("Subject: " + s)
        self._do_mail(s)

    def cmd_print(self, arglst):
        if self.currmsg >= len(self.backend.msgs):
            print("no message to show")
            return
        hdr, body, _ = self.backend.msgs[self.currmsg]
        # should do line wrapping (at pos 79) and paging (after 18 lines) ...
        print(f"--- #{self.currmsg+1}")
        for h in hdr:  print(h)
        print()
        for i in body: print(i)
        print("---")

    def cmd_sync(self, arglst):
        oldcnt = len(self.backend.msgs)
        msgs = self.backend.read_mail()
        if len(msgs) == oldcnt:
            print("sync: no new messages")
        else:
            d = len(msgs) - oldcnt
            print("sync:", d, "new message" + ("s" if d != 1 else ""))
            self.currmsg += d
            if self.currmsg >= len(msgs):
                self.currmsg = len(msgs)-1
        if self.currmsg < len(msgs):
            print(self._header_line(self.currmsg))

    def loop(self):
        print(self._countstr())
        while True:
            try:
                cmd = input("tinyChat> ")
            except (EOFError, KeyboardInterrupt):
                self.cmd_exit([])

            cmd = cmd.split(" ")
            if len(cmd) == 1 and cmd[0] == '': continue
            lst = [ c for c in self.cmd_table if c.startswith(cmd[0]) ]
            if lst == []:
                try:
                    i = int(cmd[0])
                except:
                    print("unknown command. Use ? to see list of commands")
                    continue
                if i < 1 or i > len(self.backend.msgs):
                    print("number out of range")
                    continue
                self.currmsg = i-1
                print(self._header_line(self.currmsg))
            elif len(lst) > 1:
                print("ambiguous command. Use ? to see list of commands")
            else:
                self.cmd_table[lst[0]](cmd[1:])

# ----------------------------------------------------------------------

def mksignfct(secret):
    sk = pure25519.SigningKey(secret)
    return lambda m: sk.sign(m)

def mkverifyfct(secret):
    def vfct(pk, s, msg):
        try:
            pure25519.VerifyingKey(pk).verify(s,msg)
            return True
        except Exception as e:
            print(e)
        return False
    return vfct

# ----------------------------------------------------------------------

if __name__ == '__main__':

    print("tinySSB Chat (tinyChat)")

    # FIXME: argv processing for faces, log file
    
    path = './data/' + sys.argv[1]
    with open(path + '/config.json') as f:
        cfg = json.load(f)
    for i in cfg:
        if not i in ['alias', 'name']:
            cfg[i] = util.fromhex(cfg[i])
    alias = {util.fromhex(k):v for k,v in cfg['alias'].items()}

    faces = [io.UDP_MULTICAST(('224.1.1.1',5000))]
    repo = repository.REPO(path, mkverifyfct(cfg['secret']))
    nd = node.NODE(faces, repo)
    nd.start()
    backend = ChatBackend(path, nd, cfg['feedID'],
                          mksignfct(cfg['secret']), alias)
    app = ChatFrontend(backend)
    app.loop()

# eof
