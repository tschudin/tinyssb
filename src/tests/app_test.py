# tests/app_test.py
# 2022-05-25 <et.mettaz@unibas.ch>
import unittest

import api
from tinyssb import util

class AppTestCase(unittest.TestCase):

    key1 = util.fromhex('1e032749b2414f9a424772e78d7cbe1fef1fea3464188e907c29fcf31eed52e1')
    key2 = util.fromhex('747da564ff00bf71684bf58775212248c354757b43d2fd5db52dcbc292537c04')
    key3 = util.fromhex('f23df21ca47b3666467222b1037af24162f231f5bb3559822336510af4fae8ed')
    key4 = util.fromhex('b1b64e45bc892ebbe95e0a355a197d967f8389f0426f0056029b375e2e3daf1b')
    key5 = util.fromhex('e523a5d864aba515518b711d3bfff3b9052a54d69c82d91d7eb31aa50f0ead70')
    key6 = util.fromhex('0bff3d95af22c60bd817e772fb7fcdcf1d9f9e736e676cc8bc1db21d3bb20f7b')

    @classmethod
    def setUp(cls):
        api.erase_all()
        peer = api.generate_id("Charlie")
        cls.app = peer.add_app('chess', cls.key1)

    def test_void_app(self):
        self.assertEqual({}, self.app.instances)

    def test_create_inst(self):
        self.app.create_inst(None, self.key1)
        expected = {'0': {'il': self.app.instances.get('0').get('il'),
                          'w': self.key1}}
        expected['0']['l'] = expected['0']['il']
        self.assertEqual(expected, self.app.instances)
        
        self.app.create_inst(self.key2, self.key3, "An arbitrary long string that "
                                                   "can be use to describe the game")
        expected['1'] = {'il': self.app.instances.get('1').get('il'),
                         'ir': self.key2, 'r': self.key2, 'w': self.key3,
                         'n': "An arbitrary long string that can be use to describe the game"}
        expected['1']['l'] = expected['1']['il']
        self.assertEqual(expected, self.app.instances)

    def test_add_remote(self):
        self.app.create_inst(None, self.key1)
        expected = {'0': {'il':self.app.instances.get('0').get('il'), 'w':self.key1}}
        expected['0']['l'] = expected['0']['il']
        self.assertEqual(expected, self.app.instances)

        self.app.add_remote_fid('0', self.key3)
        expected['0']['ir'] = self.key3
        expected['0']['r'] = self.key3
        self.assertEqual(expected, self.app.instances)

    def test_update(self):
        self.app.create_inst(self.key1, self.key2)
        expected = {'0': {'il': self.app.instances.get('0').get('il'),
                          'ir': self.key1, 'r': self.key1, 'w': self.key2}}
        expected['0']['l'] = expected['0']['il']
        self.assertEqual(expected, self.app.instances)

        self.app.update_game('0', self.key3, None, self.key4, "A name")
        expected['0']['l'] = self.key3
        expected['0']['w'] = self.key4
        expected['0']['n'] = "A name"
        self.assertEqual(expected, self.app.instances)

        self.app.update_game('0', None, self.key5, self.key6, None)
        expected['0']['r'] = self.key5
        expected['0']['w'] = self.key6
        self.assertEqual(expected, self.app.instances)

    def test_load(self):
        self.app.create_inst(self.key1, self.key2)
        self.app.update_game('0', self.key3, None, self.key4, "A name")
        self.app.update_game('0', None, self.key5, self.key6, None)

        peer = api.load_identity("Charlie")
        self.assertIsNotNone(peer.directory['apps']['chess'])
        expected = {'0': {'il': self.app.instances.get('0').get('il'),
                          'ir': self.key1, 'l': self.key3, 'r': self.key5,
                          'w': self.key6, 'n': "A name"}}
        self.assertEqual(expected, peer.launch_app("chess").instances)

if __name__=='__main__':
    unittest.main()

# eof
