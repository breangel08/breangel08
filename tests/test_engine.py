import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError
from engine import assets, qa
from engine.adapters import get_adapter
from engine.adapters.claude import ClaudeReviewer
from engine.adapters.shopify import ShopifyAdapter
from engine.evidence import UnsafeURL, public_address
from engine.models import Brief, Review
from engine.service import Engine
from engine.store import Store, Conflict, digest, uid, now
from engine.fixtures import sample_art


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.engine=Engine(Store(self.tmp.name))
        self.env=patch.dict(os.environ,{'STUDIO_ENABLE_RESEARCH':'0'})
        self.env.start()
        self.capture=patch('engine.service.qa.capture_approved',return_value={'status':'BLOCKED','reason':'Unit test deliberately excludes browser; smoke test covers real capture','captures':[]})
        self.capture.start()

    def tearDown(self):
        self.engine.pool.shutdown(wait=True)
        self.capture.stop();self.env.stop();self.tmp.cleanup()

    def project(self,**kwargs):
        return self.engine.create(Brief(brand_name='Unit fixture',demo=True,**kwargs))

    def visual(self,**kwargs):
        p=self.project(**kwargs);self.engine.discover(p['id']);return self.engine.store.get(p['id'])

    def lock(self,**kwargs):
        p=self.visual(**kwargs);return self.engine.review(p['id'],Review(action='KEEP',version=p['active_design']))

    def report(self,status='PASS',gate=None):
        results={g:{'status':'PASS','checks':[]} for g in qa.GATES}
        defects=[]
        if gate:
            results[gate]={'status':status,'checks':[],'reason':'Deliberate unit-test injected result'}
            if status=='FAIL': defects=[qa.defect(gate,'expected fixture','injected failure')]
        return {'id':uid('qa_fixture_'),'build_id':'fixture','timestamp':now(),'path':'qa/test-fixture','status':status,'results':results,'defects':defects}

    def test_schema_rejects_invalid_palette_blank_brand_and_unsafe_font(self):
        for value in [{'brand_name':' '},{'brand_name':'x','palette':['blue']},{'brand_name':'x','fonts':["A';url(x)"]}]:
            with self.assertRaises(ValidationError): Brief(**value)

    def test_inferred_type_is_separate_from_target(self):
        p=self.project(instructions='Create an online store with checkout')
        self.assertEqual(p['classification']['website_type'],'FULL_ECOMMERCE_STORE')
        self.assertEqual(p['classification']['target'],'SHOPIFY')
        self.assertEqual(p['autonomy_level'],5)
        self.assertTrue(any(c['name']=='INTAKE_COMPLETE' for c in p['checkpoints']))

    def test_project_persistence_and_optimistic_concurrency(self):
        p=self.project();stale=copy.deepcopy(p)
        self.engine.store.save(p,('TEST_UPDATE',{}))
        with self.assertRaises(Conflict): self.engine.store.save(stale)
        second=Store(self.tmp.name).get(p['id'])
        self.assertEqual(second['brief'],p['brief'])
        self.assertEqual(second['approval_ledger'],p['approval_ledger'])
        self.assertTrue(self.engine.store.path(p['id']).is_relative_to(Path(self.tmp.name)/'fixtures'))

    def test_production_requires_visual_approval(self):
        p=self.project()
        with self.assertRaises(Conflict): self.engine.produce(p['id'])
        p=self.visual()
        with self.assertRaises(Conflict): self.engine.produce(p['id'])

    def test_visual_lock_is_versioned_and_integrity_checked(self):
        p=self.lock(content=[{'id':'hero_heading','text':'Authorized headline'}])
        locked=copy.deepcopy(p['design_lock'])
        self.assertEqual(digest(locked['spec']),locked['sha256'])
        self.assertTrue((self.engine.store.path(p['id'])/'approvals/design-lock-v1.json').exists())
        self.assertEqual(p['stage'],'DESIGN_LOCKED')
        self.engine.review(p['id'],Review(action='REVISE',version=1,feedback='The hero image is too large.'))
        after=self.engine.store.get(p['id'])
        self.assertIsNone(after['design_lock'])
        self.assertEqual(json.loads((self.engine.store.path(p['id'])/'approvals/design-lock-v1.json').read_text()),locked)
        old,new=after['design_versions'][0]['spec'],after['design_versions'][1]['spec']
        self.assertNotEqual(old['tokens']['image_scale'],new['tokens']['image_scale'])
        expected=copy.deepcopy(old);expected['tokens']['image_scale']=new['tokens']['image_scale']
        self.assertEqual(expected,new)
        with self.assertRaises(Conflict): self.engine.review(p['id'],Review(action='KEEP',version=1))

    def test_locked_palette_cannot_be_recolored_and_asset_roles_lock(self):
        p=self.visual(palette=['#f4f2ed','#242922','#4a5f42'])
        with self.assertRaises(ValueError): self.engine.review(p['id'],Review(action='REVISE',version=1,patches={'tokens.background':'#ffffff'}))
        self.engine.review(p['id'],Review(action='KEEP',version=1))
        with self.assertRaises(Conflict): assets.ingest(self.engine.store,p['id'],'hero.webp',sample_art(),'hero')

    def test_assets_inventory_exact_hash_dedup_and_upload_security(self):
        p=self.project();raw=sample_art()
        a=assets.ingest(self.engine.store,p['id'],'hero.webp',raw,'hero')
        self.assertEqual(a['sha256'],digest(raw));self.assertEqual(a['width'],1200)
        duplicate=assets.ingest(self.engine.store,p['id'],'again.webp',raw,'hero')
        self.assertTrue(duplicate['duplicate']);self.assertEqual(len(self.engine.store.get(p['id'])['assets']),1)
        with self.assertRaises(ValueError): assets.ingest(self.engine.store,p['id'],'bad.svg',b'<svg/>')
        with self.assertRaises(ValueError): assets.ingest(self.engine.store,p['id'],'bad.png',b'not an image')
        with self.assertRaises(ValueError): assets.assign(self.engine.store,p['id'],a['id'],'arbitrary')

    def test_unrecognized_feedback_is_pending_not_silently_applied(self):
        p=self.visual();self.engine.review(p['id'],Review(action='REVISE',version=1,feedback='The FAQ treatment is wrong and the footer feels generic.'))
        p=self.engine.store.get(p['id']);pending=[d for d in p['pending_decisions'] if d['status']=='OPEN']
        self.assertEqual(len(pending),2)
        self.assertTrue(all(d['blocking'] for d in pending))
        with self.assertRaises(Conflict): self.engine.review(p['id'],Review(action='KEEP',version=2))
        for d in pending: self.engine.resolve(p['id'],d['id'],'Withdraw this revision request')
        p=self.engine.review(p['id'],Review(action='KEEP',version=2))
        self.assertEqual(p['stage'],'DESIGN_LOCKED')

    def test_adapter_registry_and_unsupported_capability_blocking(self):
        self.assertEqual(get_adapter('CUSTOM_WEB').name,'CUSTOM_WEB')
        self.assertEqual(get_adapter('SHOPIFY').name,'SHOPIFY')
        with self.assertRaises(ValueError): get_adapter('WEBFLOW')
        p=self.lock(functionality=['authentication'])
        p=self.engine.produce(p['id']);self.assertEqual(p['stage'],'BLOCKED');self.assertFalse(p['builds'])
        d=p['pending_decisions'][0]
        with self.assertRaises(Conflict): self.engine.resolve(p['id'],d['id'],'Provide a compatible integration')

    def test_qa_failure_creates_defects_repair_then_retest(self):
        p=self.lock();fail=self.report('FAIL','functional');passed=self.report()
        with patch('engine.service.qa.run',side_effect=[fail,passed]): result=self.engine.produce(p['id'])
        self.assertEqual(result['stage'],'FINAL_REVIEW')
        self.assertEqual(len(result['builds'][-1]['repairs']),1)
        self.assertEqual(result['defects'][0]['status'],'RESOLVED')
        self.assertEqual(len(result['defects'][0]['repair_attempts']),1)

    def test_persistent_failure_never_becomes_release_candidate(self):
        p=self.lock()
        with patch('engine.service.qa.run',side_effect=[self.report('FAIL','visual') for _ in range(3)]): result=self.engine.produce(p['id'])
        self.assertEqual(result['stage'],'BLOCKED');self.assertIsNone(result['release_candidate'])
        self.assertEqual(len(result['builds'][-1]['repairs']),2)
        self.assertEqual(result['builds'][-1]['package']['status'],'DIAGNOSTIC_NOT_RELEASE_READY')
        with self.assertRaises(Conflict): self.engine.final_approve(p['id'],result['builds'][-1]['id'])
        with self.assertRaises(Conflict): self.engine.repair(p['id'])

    def test_qa_blocked_does_not_become_pass(self):
        p=self.lock()
        with patch('engine.service.qa.run',return_value=self.report('BLOCKED','accessibility')): result=self.engine.produce(p['id'])
        self.assertEqual(result['stage'],'BLOCKED');self.assertIsNone(result['release_candidate'])
        self.assertFalse(result['builds'][-1]['repairs'])

    def test_final_gate_checks_build_manifest_and_no_automatic_publication(self):
        p=self.lock()
        with patch('engine.service.qa.run',return_value=self.report()): result=self.engine.produce(p['id'])
        build=result['builds'][-1];path=self.engine.store.path(p['id'])/build['path']/'index.html'
        original=path.read_text();path.write_text(original+'tampered')
        with self.assertRaises(Conflict): self.engine.final_approve(p['id'],build['id'])
        path.write_text(original);approved=self.engine.final_approve(p['id'],build['id'])
        self.assertEqual(approved['stage'],'READY');self.assertFalse(approved['deployment']['published'])
        self.assertEqual(approved['approval_ledger'][-1]['gate'],'FINAL')

    def test_recovery_preserves_lock_and_detects_corruption(self):
        p=self.lock();new_engine=Engine(Store(self.tmp.name))
        try:
            result=new_engine.recover(p['id']);self.assertEqual(result['status'],'VERIFIED');self.assertEqual(result['next_operation'],'produce')
            self.assertEqual(new_engine.store.get(p['id'])['design_lock'],p['design_lock'])
            path=self.engine.store.path(p['id'])/p['design_lock']['prototype_path']/'index.html';path.write_text('corrupted')
            self.assertEqual(new_engine.recover(p['id'])['status'],'BLOCKED')
        finally: new_engine.pool.shutdown(wait=True)

    def test_job_claim_and_restart_recovery(self):
        p=self.project();job=self.engine.store.create_job(p['id'],'discover')
        with self.assertRaises(Conflict): self.engine.store.create_job(p['id'],'discover')
        self.assertTrue(self.engine.store.claim_job(job['id']));self.assertFalse(self.engine.store.claim_job(job['id']))
        self.engine.recover_jobs();self.assertEqual(self.engine.store.job(job['id'])['status'],'INTERRUPTED')
        result=self.engine.resume(p['id']);self.assertEqual(result['stage'],'VISUAL_REVIEW')

    def test_reference_private_network_and_nonweb_schemes_rejected(self):
        for url in ['http://127.0.0.1','http://169.254.169.254','http://[::1]','file:///etc/passwd','https://user:password@example.com','https://example.com:9000']:
            with self.assertRaises(UnsafeURL): public_address(url)

    def test_unauthorized_content_is_excluded(self):
        p=self.visual(content=[{'id':'hero_heading','text':'Unauthorized claims','permission':'UNAUTHORIZED'},{'id':'hero_body','text':'Authorized supplied text','permission':'SUPPLIED'}])
        spec=p['design_versions'][0]['spec'];self.assertNotIn('hero_heading',spec['content'])
        html=(self.engine.store.path(p['id'])/p['design_versions'][0]['prototype_path']/'index.html').read_text()
        self.assertNotIn('Unauthorized claims',html);self.assertIn('Authorized supplied text',html)

    def test_claude_not_configured_never_fakes_review(self):
        with patch.dict(os.environ,{},clear=True):
            result=ClaudeReviewer().review({})
        self.assertEqual(result['configuration'],'NOT_CONFIGURED');self.assertIsNone(result['consultation'])

    def test_shopify_native_structure_dynamic_bindings_and_validation_failures(self):
        p=self.lock(website_type='FULL_ECOMMERCE_STORE',target='SHOPIFY')
        adapter=ShopifyAdapter();out=self.engine.store.path(p['id'])/'native-test'
        adapter.build({**p,'_root':str(self.engine.store.path(p['id']))},p['design_lock']['spec'],out)
        self.assertTrue((out/'layout/theme.liquid').exists())
        self.assertIn("{% form 'product', product",(out/'sections/main-product.liquid').read_text())
        self.assertIn('cart.items',(out/'sections/main-cart.liquid').read_text())
        self.assertIn('product.price',(out/'snippets/product-card.liquid').read_text())
        # Static tests deliberately avoid invoking external tooling; real validator in smoke.
        with patch('engine.adapters.shopify.subprocess.run') as validate:
            validate.return_value.returncode=0;validate.return_value.stdout='fixture validation';validate.return_value.stderr=''
            self.assertEqual(adapter.validate(out)['status'],'PASS')
            (out/'templates/index.json').write_text('{bad json')
            self.assertEqual(adapter.validate(out)['status'],'FAIL')


    def test_unknown_nonnegotiable_requirement_blocks_approval(self):
        p=self.visual(requirements=[{'classification':'REQUIRED','text':'All text must follow an unspecified proprietary interactive transformation'}])
        pending=[d for d in p['pending_decisions'] if d['id'].startswith('rule_')]
        self.assertEqual(len(pending),1)
        with self.assertRaises(Conflict): self.engine.review(p['id'],Review(action='KEEP',version=1))
        self.engine.resolve(p['id'],pending[0]['id'],'Explicitly waive this requirement')
        p=self.engine.review(p['id'],Review(action='KEEP',version=1))
        self.assertEqual(p['stage'],'DESIGN_LOCKED')

    def test_structured_brand_guide_is_validated_and_original_preserved(self):
        p=self.project()
        guide=json.dumps({'palette':['#f4f2ed','#242922','#4a5f42'],'fonts':['Georgia','Arial'],'requirements':[{'classification':'FORBIDDEN','text':'No invented testimonials'}]}).encode()
        a=assets.ingest(self.engine.store,p['id'],'brand-guide.json',guide,'guide')
        p=self.engine.store.get(p['id'])
        self.assertEqual(a['sha256'],digest(guide));self.assertEqual(a['analysis']['status'],'EXTRACTED')
        self.assertEqual(p['brief']['palette'],['#f4f2ed','#242922','#4a5f42'])
        self.assertTrue(any(r['classification']=='LOCKED' and r['area']=='palette' for r in p['constitution']['rules']))

    def test_incomplete_qa_report_cannot_create_candidate(self):
        p=self.lock();report=self.report();del report['results']['accessibility']
        with patch('engine.service.qa.run',return_value=report):
            with self.assertRaises(ValueError): self.engine.produce(p['id'])
        self.assertIsNone(self.engine.store.get(p['id'])['release_candidate'])

    def test_altered_archive_is_rejected_at_final_gate(self):
        p=self.lock()
        with patch('engine.service.qa.run',return_value=self.report()): result=self.engine.produce(p['id'])
        build=result['builds'][-1];archive=self.engine.store.path(p['id'])/build['package']['path'];archive.write_bytes(b'corrupt')
        with self.assertRaises(Conflict): self.engine.final_approve(p['id'],build['id'])

    def test_unknown_schema_is_blocked_without_destroying_history(self):
        p=self.lock();ledger=copy.deepcopy(p['approval_ledger']);p['schema_version']=999;self.engine.store.save(p)
        r=self.engine.recover(p['id']);self.assertEqual(r['status'],'BLOCKED')
        self.assertEqual(self.engine.store.get(p['id'])['approval_ledger'],ledger)


    def test_api_auth_csrf_upload_size_and_evidence_execution_safety(self):
        from fastapi.testclient import TestClient
        from studio.app import create_app
        p=self.visual()
        self.engine.store.artifact(p['id'],'evidence/untrusted.html','<script>alert(1)</script>')
        with patch.dict(os.environ,{'STUDIO_TOKEN':'unit-fixture-token'}),TestClient(create_app(self.tmp.name)) as client:
            self.assertEqual(client.get('/api/projects').status_code,401)
            headers={'Authorization':'Bearer unit-fixture-token'}
            self.assertEqual(client.get('/api/projects',headers=headers).status_code,200)
            self.assertEqual(client.post('/api/projects',headers={**headers,'Origin':'https://evil.example'},json={'brand_name':'x'}).status_code,403)
            self.assertEqual(client.post('/api/projects',headers={**headers,'Content-Length':'99000000'},content=b'x').status_code,413)
            response=client.get(f"/api/projects/{p['id']}/files/evidence/untrusted.html",headers=headers)
            self.assertTrue(response.headers['content-type'].startswith('text/plain'))
            self.assertIn('attachment',response.headers['content-disposition'])
            preview=client.get(f"/api/projects/{p['id']}/files/design/v1/prototype/index.html",headers=headers)
            self.assertIn('sandbox allow-scripts',preview.headers['content-security-policy'])
            self.assertEqual(client.get(f"/api/projects/{p['id']}/files/%2e%2e/%2e%2e/studio.sqlite3",headers=headers).status_code,404)
            self.assertEqual(client.post('/api/session',json={'token':'unit-fixture-token'}).status_code,200)
            self.assertEqual(client.get('/api/projects').status_code,200)

    def test_credentials_rejected_in_intake_urls(self):
        with self.assertRaises(ValidationError): Brief(brand_name='x',references=[{'url':'https://name:secret@example.com'}])
        with self.assertRaises(ValidationError): Brief(brand_name='x',current_url='https://name:secret@example.com')


if __name__=='__main__': unittest.main()
