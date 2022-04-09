#!/usr/bin/env python3

# ftree_make.py
# 2022-04-09 <christian.tschudin@unibas.ch>

from collections import OrderedDict
import json
import pure25519
import sys

from tinyssb import packet, repository, util

# ----------------------------------------------------------------------

class KeyStore():
    def __init__(self):
        self.kv = OrderedDict()
    def add(self, sk, pk, nm):
        self.kv[pk] = (sk,nm)
    def __str__(self):
        out = OrderedDict()
        for pk,(sk,nm) in self.kv.items():
            out[util.hex(pk)] = { 'sk': util.hex(sk), 'name': nm }
        return util.json_pp(out)
        
def mksignfct(secret):
    def sign(m):
        sk = pure25519.SigningKey(secret)
        return sk.sign(m)
    return sign

def mkverifyfct(secret):
    def vfct(pk, s, msg):
        try:
            pure25519.VerifyingKey(pk).verify(s,msg)
            return True
        except Exception as e:
            print(e)
        return False
    return vfct

def print_template(lvl, f, is_first, has_continuation):
    e = '..'
    if 'end' in f and f['end']:
        e = ']]'
    elif 'cont' in f or has_continuation:
        e = '>>'
    nam = f['name'] if 'name' in f else '??'
    if is_first:
        if lvl == 0:
            print('    '* lvl + '  / ' + nam + e)
        else:
            print('    '* lvl + '  + ' + nam + e)
    else:
        print(    '    '* lvl + '  > ' + nam + e)
    if 'sub' in f:
        for s in f['sub']:
            print_template(lvl+1, s, True, False)
    if 'cont' in f:
        i = 0
        for s in f['cont']:
            if 'name' in f: s['name'] = f['name'] + '-contd-' + str(i)
            print_template(lvl, s, False, s != f['cont'][-1])
            i += 1

# ----------------------------------------------------------------------

def implement_template(repo, ks, pfx, templ,
                       parent, precursor, upperSignFct):

    sk, _ = pure25519.create_keypair()
    sk,pk = sk.sk_s[:32], sk.vk_s # we need just the bytes
    pfx =  pfx + '/' + templ['name'] if 'name' in templ else '?'
    ks.add(sk, pk, pfx)
    ret = (sk,pk)
    signFct = mksignfct(sk)
    retSignFct = signFct

    if parent != None:
        feed = repo.mk_child_log(parent[0], upperSignFct, pk, signFct)
        pkt = repo.get_log(parent[0])[-1]
    elif precursor != None:
        feed = repo.mk_continuation_log(precursor[0], upperSignFct,
                                        pk, signFct)
        pkt = repo.get_log(precursor[0])[-1]
    else: # root
        buf48 = templ['name'].encode() if 'name' in templ else b'root'
        feed = repo.mk_generic_log(pk, packet.PKTTYPE_plain48, buf48, signFct)
        pkt = feed[1]

    if 'sub' in templ:
        pseq = pkt.seq
        for s in templ['sub']:
            implement_template(repo, ks, pfx, s, (pk, pseq), None, signFct)
            pseq += 1
    if 'cont' in templ:
        i = 1
        for s in templ['cont']:
            if 'name' in templ:
                s['name'] = templ['name'] + '-contd-' + str(i)
            sk2,pk2 = implement_template(repo, ks, pfx, s, None,
                                         (pk,pkt.seq), signFct)
            signFct = mksignfct(sk2)
            pk = pk2
            pkt = repo.get_log(pk2)[-1]
            i += 1
    if 'end' in templ:
        pkt = feed.write_eof(retSignFct)

    return ret

# ----------------------------------------------------------------------

''' template for a feed:
    { name: name,       # optional
       sub: [],         list of subfeeds
      cont: [],         list of continuation feeds
    }
'''

demo_template_1 = {
    'name': 'root',
    'sub' : [
              {'name': 'apps',
               'sub' : [ {'name':'chat'}, {'name':'chess'} ]
              },
              {'name': 'main' }
            ]
}

demo_template_2 = {
    'name': 'root',
    'sub' : [
              { 'name': 'main',
                'sub':  [ {'name':'sub1', 'end':True}, {'name':'sub2'}],
                'cont': [ {}, {}, {} ] }
            ]
}

# ----------------------------------------------------------------------

if __name__ == '__main__':

    template = demo_template_2

    repo_path = sys.argv[1]  # will be extended with "_logs"
    repo = repository.REPO(repo_path, mkverifyfct(None))
    keystore = KeyStore()
    _, root_fid = implement_template(repo, keystore, '',
                                     template, None, None, None)

    print(sys.argv[0],
          f"- {len(keystore.kv)} feeds created in '{repo_path}/_logs'")
    
    print(
"""
--- visualization:

    / xx   'this is the root feed'
    + xx   'this is a sub feed'
    > xx   'this is a continuation feed'
    xx..   'feed can still be appended to'
    xx>>   'feed has a continuation'
    xx]]   'feed has ended'

""")

    print_template(0, template, True, False)

    # print('\n--- from disk\n')
    # print_feed_tree(repo, 0, root_fid, True)
    
    print('\n--- keystore\n')
    print(keystore)

# eof
