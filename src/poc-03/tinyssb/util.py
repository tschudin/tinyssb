#

# tinyssb/util.py

import base64
import sys

if sys.implementation.name == 'micropython':
    import binascii
    fromhex = binascii.unhexlify
    hex = lambda b: binascii.hexlify(b).decode()
else:
    fromhex = lambda h: bytes.fromhex(h)
    hex = lambda b: b.hex()

b64 = lambda b: base64.b64encode(b).decode()

# because micropython json.dumps() does not have the 'indent' keyword ...
def json_pp(d, indent=''):
    indent += '  '
    if d == None:      return "null"
    if type(d) == int: return str(d)
    if type(d) == str: return '"' + d + '"'
    if type(d) == list:
        jsonstr = '[\n'
        cnt = 1
        for i in d:
            jsonstr += indent + json_pp(i, indent)
            jsonstr += ',\n' if cnt < len(d) else  '\n'
            cnt += 1
        jsonstr += indent[:-2] + ']'
        return jsonstr
    if type(d).__name__ in ['dict', 'OrderedDict']:
        jsonstr = '{\n'
        cnt = 1
        for k,v in d.items():
            jsonstr += indent + '"' + k + '": ' + json_pp(v, indent)
            jsonstr += ',\n' if cnt < len(d) else '\n'
            cnt += 1
        jsonstr += indent[:-2] + '}'
        return jsonstr
    return "??"

# eof
