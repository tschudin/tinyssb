import unittest

import api
from tinyssb import util
from tinyssb.exception import *

class IdentityTestCase(unittest.TestCase):
    @classmethod
    def setUp(cls):
        api.erase_all()
        cls.peer=api.generate_id("Charlie")
        cls.key1=util.fromhex('da5066b203a02b2cabc00f9d9e6fb096058bfa01d0aef146d3856388964df56d')
        cls.key2=util.fromhex('5920e93bd6ebbaa57a3a571d3bc1eeb850f4948fde07e08bcd25ce49820978aa')

    def test_follow(self):
        self.peer.follow(self.key1,"Petra")

    def test_list_contacts(self):
        self.peer.follow(self.key1,"Petra")
        self.peer.follow(self.key2,"Alejandra")
        self.assertEqual(self.peer.list_contacts(), {'Petra':self.key1,'Alejandra':self.key2})

    def test_failed_follow(self):
        self.peer.follow(self.key1,"Petra")
        with self.assertRaises(AlreadyUsedTinyException):
            self.peer.follow(self.key1,"Ellen")
        with self.assertRaises(AlreadyUsedTinyException):
            self.peer.follow(self.key2,"Petra")

    def test_unfollow(self):
        self.peer.follow(self.key1,"Petra")
        self.assertDictEqual(self.peer.list_contacts(),{"Petra":self.key1})
        self.peer.unfollow(self.key1)
        self.assertEqual(len(self.peer.list_contacts()),0)

    def test_failed_unfollow(self):
        with self.assertRaises(NotFoundTinyException):
            self.peer.unfollow(self.key1)
        self.peer.follow(self.key1,"Petra")
        with self.assertRaises(NotFoundTinyException):
            self.peer.unfollow(self.key2)

    def test_add_app(self):
        self.assertEqual(self.peer.add_app("chess", self.key1), {})
        self.assertEqual(len(self.peer.directory['apps']), 1)
        self.assertIsNotNone(self.peer.directory['apps']['chess'])

    def test_add_app_fail(self):
        self.peer.add_app("chess", self.key1)
        with self.assertRaises(AlreadyUsedTinyException):
            self.peer.add_app("chess", self.key2)

    def test_change_app_name(self):
        self.peer.add_app("chess", self.key1)
        self.assertIsNotNone(self.peer.directory['apps']['chess'])
        # change the app name to "chat"
        self.peer.add_app("chat", self.key1)
        self.assertEqual(len(self.peer.directory['apps']), 1)
        self.assertIsNone(self.peer.directory['apps'].get('chess'))
        self.assertIsNotNone(self.peer.directory['apps']['chat'])

    def test_launch_app(self):
        self.peer.add_app("chess", self.key1)
        self.assertEqual(len(self.peer.launch_app("chess")), 0)

    def test_delete_app(self):
        self.peer.add_app("chess", self.key1)
        self.assertIsNotNone(self.peer.directory['apps']['chess'])
        self.peer.delete_app("chess", self.key1)
        self.assertEqual(len(self.peer.directory['apps']), 0)

    def test_delete_app_fail(self):
        self.peer.add_app("chess", self.key1)
        with self.assertRaises(NotFoundTinyException):
            self.peer.delete_app("chat", self.key1)
        with self.assertRaises(TinyException):
            self.peer.delete_app("chess",self.key2)
        self.assertEqual(len(self.peer.directory['apps']), 1)

if __name__=='__main__':
    unittest.main()
