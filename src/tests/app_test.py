# tests/app_test.py
# 2022-05-25 <et.mettaz@unibas.ch>
import unittest

import tinyssb as tiny
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
        tiny.erase_all()
        peer = tiny.generate_id("Charlie")
        # only peers in contact list can be added
        peer.follow(cls.key2, "Alice")
        peer.follow(cls.key4, "Bob")
        peer.follow(cls.key6, "David")
        cls.app = peer.define_app('chess', cls.key1)

    def test_void_app(self):
        self.assertEqual({ }, self.app.instances)

    def test_create_inst(self):
        inst_id = self.app.create_inst()
        self.app.add_member(inst_id, self.key1, self.key2)
        expected = { inst_id: { 'il': self.app.instances.get(inst_id).get('il'),
            'm': { util.hex(self.key2): { 'ir': self.key1, 'r': self.key1 } }, 'n': 'Alice, me (0)' } }
        expected[inst_id]['l'] = expected[inst_id]['il']
        self.assertEqual(expected, self.app.instances)

        # self.app.create_inst(self.key2, self.key3, "An arbitrary long string that "  #                                            "can be used to describe the game")  # expected['1'] = { 'il': self.app.instances.get('1').get('il'), 'ir': self.key2, 'r': self.key2, 'm': self.key3,  #     'n': "An arbitrary long string that can be used to describe the game" }  # expected['1']['l'] = expected['1']['il']  # self.assertEqual(expected, self.app.instances)

    def test_add_remote(self):
        ret = self.app.create_inst()
        self.app.add_member(ret, self.key1, self.key2)
        expected = { ret: { 'il': self.app.instances.get(ret).get('il'),
            'm': { util.hex(self.key2):  { 'ir': self.key1, 'r': self.key1 } }, 'n': 'Alice, me (0)' } }
        expected[ret]['l'] = expected[ret]['il']
        self.assertEqual(expected, self.app.instances)

        self.app.update_remote_instance_feed(ret, self.key3, self.key2)
        expected[ret]['m'][util.hex(self.key2)]['r'] = self.key3
        self.assertEqual(expected, self.app.instances)

    def test_update(self):
        inst_id = self.app.create_inst()
        self.app.add_member(inst_id, self.key1, self.key2)
        expected = { inst_id: { 'il': self.app.instances.get(inst_id).get('il'),
            'm': { util.hex(self.key2): { 'ir': self.key1, 'r': self.key1 } }, 'n': 'Alice, me (0)' } }
        expected[inst_id]['l'] = expected[inst_id]['il']
        self.assertEqual(expected, self.app.instances)

        self.app.update_remote_instance_feed(inst_id, self.key4, self.key2)
        expected[inst_id]['m'][util.hex(self.key2)]['r'] = self.key4
        self.assertEqual(expected, self.app.instances)

        self.app.update_remote_instance_feed(inst_id, self.key5, self.key2)
        self.app.update_inst(inst_id, "A name", self.key3)
        expected[inst_id]['m'][util.hex(self.key2)]['r'] = self.key5
        expected[inst_id]['n'] = "A name"
        expected[inst_id]['l'] = self.key3
        self.assertEqual(expected, self.app.instances)

    def test_load(self):
        inst_id = self.app.create_inst()
        self.app.add_member(inst_id, self.key1, self.key2)
        self.app.update_remote_instance_feed(inst_id, self.key4, self.key2)
        self.app.update_inst(inst_id, "A name", self.key3)
        self.app.update_remote_instance_feed(inst_id, self.key5, self.key2)
        self.app.update_inst(inst_id, "Another name", self.key6)
        expected = { inst_id: { 'il': self.app.instances.get(inst_id).get('il'),
            'n': "Another name", 'l': self.key6,
            'm': { util.hex(self.key2): { 'ir': self.key1, 'r': self.key5 } } } }
        self.assertEqual(expected, self.app.instances)

        peer = tiny.load_identity("Charlie")
        self.assertIsNotNone(peer.directory['apps']['chess'])
        expected = { inst_id: { 'il': self.app.instances.get(inst_id).get('il'),
            'n': "Another name", 'l': self.key6,
            'm': { util.hex(self.key2): { 'ir': self.key1, 'r': self.key5 } } } }
        self.assertEqual(expected, peer.resume_app("chess").instances)

    def test_delete_inst(self):
        inst_id = self.app.create_inst()
        self.app.add_member(inst_id, self.key1, self.key2)
        self.app.update_remote_instance_feed(inst_id, self.key4, self.key2)
        self.app.update_inst(inst_id, "A name", self.key3)
        self.app.update_remote_instance_feed(inst_id, self.key5, self.key2)

        expected = { inst_id: { 'il': self.app.instances.get(inst_id).get('il'),
            'n': "A name", 'l': self.key3,
            'm': { util.hex(self.key2): { 'ir': self.key1, 'r': self.key5 } } } }
        self.assertEqual(expected, self.app.instances)
        self.app.delete_inst(inst_id)
        self.assertIsNone(self.app.instances.get(str(inst_id)))

    def test_add_multiple_players(self):
        inst_id = self.app.create_inst()
        self.app.add_member(inst_id, self.key1, self.key2)
        expected = { inst_id: { 'il': self.app.instances.get(inst_id).get('il'),
            'm': { util.hex(self.key2): { 'ir': self.key1, 'r': self.key1 } }, 'n': 'Alice, me (0)'} }
        expected[inst_id]['l'] = expected[inst_id]['il']
        self.assertEqual(expected, self.app.instances)

        self.app.add_member(inst_id, self.key3, self.key4)
        expected[inst_id]['m'][util.hex(self.key4)] = { 'ir': self.key3, 'r': self.key3 }
        expected[inst_id]['n'] = 'Bob, Alice, me (0)'
        self.assertEqual(expected, self.app.instances)

        self.app.add_member(inst_id, self.key5, self.key6)
        self.app.update_inst(inst_id, "A name", self.key3)
        expected[inst_id]['m'][util.hex(self.key6)] = { 'ir': self.key5, 'r': self.key5 }
        expected[inst_id]['n'] = "A name"
        expected[inst_id]['l'] = self.key3
        self.assertEqual(expected[inst_id]['n'], self.app.instances[inst_id]['n'])

    def test_create_with_multiple_players(self):
        inst_id = self.app.create_inst(['Alice', 'Bob', 'David'])
        expected = { inst_id: { 'il': self.app.instances.get(inst_id).get('il'),
            'n': 'David, Bob, Alice, me (0)',
            'm': { util.hex(self.key2): { 'ir': None, 'r': None },
            util.hex(self.key4): { 'ir': None, 'r': None },
            util.hex(self.key6): { 'ir': None, 'r': None } } }
        }
        expected[inst_id]['l'] = expected[inst_id]['il']
        self.assertEqual(expected[inst_id]['n'], self.app.instances[inst_id]['n'])

        self.app.update_inst(inst_id, None, self.key3)
        expected[inst_id]['l'] = self.key3
        self.assertEqual(expected[inst_id]['n'], self.app.instances[inst_id]['n'])

if __name__ == '__main__':
    unittest.main()

# eof
