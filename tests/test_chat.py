import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from engine.chat import ChatEngine
from engine.models import Brief, Review
from engine.store import Store, Conflict


class ChatBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bridge = ChatEngine(self.root / 'data', [self.root / 'inputs'])
        (self.root / 'inputs').mkdir()
        self.p = self.bridge.create(Brief(brand_name='Fictional chat test', demo=True))

    def tearDown(self):
        self.bridge.close()
        self.temp.cleanup()

    def test_shared_studio_store_and_recovery(self):
        self.assertEqual(Store(self.root / 'data').get(self.p['id'])['brief']['brand_name'], 'Fictional chat test')
        self.assertEqual(self.bridge.engine.recover(self.p['id'])['next_operation'], 'discover')
        self.assertEqual(self.bridge.projects()[0]['id'], self.p['id'])

    def test_chat_cannot_bypass_visual_or_final_approval(self):
        with self.assertRaises(Conflict):
            self.bridge.review(self.p['id'], Review(action='KEEP', version=1), False)
        with self.assertRaises(Conflict):
            self.bridge.approve_final(self.p['id'], 'nonexistent', False)
        with self.assertRaises(Conflict):
            self.bridge.run(self.p['id'], 'produce')
        self.assertIsNone(self.bridge.status(self.p['id'])['design_lock'])

    def test_assets_are_exact_and_bounded(self):
        p=self.root/'inputs'/'copy.txt';p.write_text('Supplied fictional content')
        result=self.bridge.upload(self.p['id'],str(p),role='content')
        self.assertTrue(result['exact'])
        self.assertEqual((self.bridge.engine.store.path(self.p['id'])/result['path']).read_bytes(),p.read_bytes())
        outside=self.root/'outside.txt';outside.write_text('secret')
        with self.assertRaises(ValueError):self.bridge.upload(self.p['id'],str(outside))
        hidden=self.root/'inputs'/'.secret.txt';hidden.write_text('secret')
        alias=self.root/'inputs'/'alias.txt';alias.symlink_to(hidden)
        with self.assertRaises(ValueError):self.bridge.upload(self.p['id'],str(alias))

    def test_artifact_traversal_and_secret_exclusion(self):
        self.bridge.engine.store.artifact(self.p['id'],'qa/example.json',{'status':'BLOCKED'})
        actual=self.bridge.read_artifact(self.p['id'],'qa/example.json')
        self.assertIn('BLOCKED',actual['text'])
        self.assertIn('untrusted',actual['trust'])
        with self.assertRaises(ValueError):self.bridge.read_artifact(self.p['id'],'../../../../etc/passwd')
        hidden=self.bridge.engine.store.path(self.p['id'])/'.private.json';hidden.write_text('{"secret": true}')
        alias=self.bridge.engine.store.path(self.p['id'])/'qa'/'alias.json';alias.symlink_to(hidden)
        with self.assertRaises(ValueError):self.bridge.read_artifact(self.p['id'],'qa/alias.json')
        self.assertTrue(self.bridge.artifacts(self.p['id'])['files'])

    def test_keep_delegates_auto_production_without_self_certifying(self):
        # Delegate semantics only; real approval/state production is covered by protocol smoke.
        with patch.object(self.bridge.engine,'review',return_value={**self.p,'stage':'DESIGN_LOCKED'}), patch.object(self.bridge.engine,'queue') as queue:
            self.bridge.review(self.p['id'],Review(action='KEEP',version=1),True)
            queue.assert_called_once_with(self.p['id'],'produce')
        self.assertEqual(self.bridge.status(self.p['id'])['approval_ledger'], self.p['approval_ledger'])


if __name__ == '__main__':unittest.main()
