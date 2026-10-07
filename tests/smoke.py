"""Real browser + HTTP + restart smoke. All artifacts are isolated fictional data."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
from engine.fixtures import sample_art
from engine.qa import launch
from engine.store import Store

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'test-results'
EVIDENCE.mkdir(exist_ok=True)


def smoke():
    checks=[]
    def check(name,condition,detail=None):
        if not condition: raise AssertionError(name+': '+str(detail))
        checks.append({'name':name,'status':'PASS','detail':detail});print('PASS:',name,flush=True)
    with tempfile.TemporaryDirectory(prefix='studio-smoke-') as temp:
        with socket.socket() as sock: sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        token='smoke-fixture-token-not-a-production-secret'
        env={**os.environ,'STUDIO_DATA_DIR':str(Path(temp)/'data'),'STUDIO_TOKEN':token,'STUDIO_ENABLE_RESEARCH':'0'}
        log=(EVIDENCE/'smoke-server.log').open('w')
        def start():
            proc=subprocess.Popen([sys.executable,'run.py','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
            for _ in range(100):
                try:
                    if httpx.get(base+'/api/health',trust_env=False).status_code==200: return proc
                except httpx.ConnectError: time.sleep(.1)
            raise RuntimeError('Studio startup failed')
        proc=start()
        def stop():
            proc.terminate()
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired: proc.kill();proc.wait()
        client=httpx.Client(base_url=base,headers={'Authorization':'Bearer '+token},trust_env=False,timeout=60)
        def project(pid): return client.get('/api/projects/'+pid).json()
        def wait_stage(pid,stage,timeout=150):
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                p=project(pid)
                if p['stage']==stage and not p['status']['working']: return p
                if p['stage']=='BLOCKED' and not p['status']['working']:
                    (EVIDENCE/'smoke-blocked-project.json').write_text(json.dumps(p,indent=2))
                    raise AssertionError('Blocked workflow: '+json.dumps(p.get('defects',[]))[:6000])
                if p.get('last_error'): raise AssertionError(p['last_error'])
                time.sleep(.35)
            raise AssertionError(f'Expected {stage}, got {p["stage"]}: '+json.dumps(p.get('blockers')))
        try:
            check('Studio starts',client.get('/api/health').status_code==200)
            check('Workspace state requires authentication',httpx.get(base+'/api/projects',trust_env=False).status_code==401)
            check('Cross-origin mutation rejected',client.post('/api/projects',headers={'Origin':'https://evil.example'},json={'brand_name':'bad'}).status_code==403)
            with sync_playwright() as pw:
                browser=launch(pw);context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(base);page.get_by_label('Workspace token').fill(token);page.get_by_role('button',name='Sign in',exact=True).click()
                page.get_by_role('heading',name='Your next website starts here').wait_for()
                page.get_by_role('link',name='New website',exact=True).first.click()
                page.get_by_label('Brand / project name').fill('Quiet Practice — smoke fixture')
                page.locator('input[name=website_type][value=SERVICE_WEBSITE]').check()
                page.get_by_label('Where should it live?').select_option('CUSTOM_WEB')
                page.get_by_label('Project instructions',exact=True).fill('Clearly fictional test project. Editorial composition. Preserve approved copy and exact image. No invented claims.')
                page.get_by_label('Business goal',exact=True).fill('Accept project enquiries')
                page.get_by_label('Target audience',exact=True).fill('Fictional test audience')
                page.get_by_label('Inspiration URL').fill('https://reference.example.invalid/')
                page.get_by_label('Reference role').select_option('composition')
                page.get_by_role('button',name='Add another inspiration site').click()
                page.get_by_label('Inspiration URL').nth(1).fill('https://second-reference.example.invalid/')
                page.get_by_label('Reference role').nth(1).select_option('navigation')
                image=Path(temp)/'fictional-hero.webp';image.write_bytes(sample_art())
                page.locator('#intake-files').set_input_files(str(image))
                page.get_by_label('Products / services',exact=True).fill('Spatial studies\nCreative direction')
                page.get_by_label('Required functionality',exact=True).fill('contact form\nnavigation\nresponsive\nseo')
                page.get_by_label('Absolutes',exact=True).fill('Use supplied copy and exact image')
                page.get_by_label('Hard NOs',exact=True).fill('No invented testimonials or statistics')
                page.get_by_label('Brand palette',exact=True).fill('#f4f1e9, #303b2d, #465d3d')
                page.get_by_text('Approved website copy',exact=True).click()
                page.get_by_label('Primary headline',exact=True).fill('A considered beginning.')
                page.get_by_label('Hero supporting copy',exact=True).fill('A fictional practice for spaces and creative direction.')
                page.get_by_label('About / narrative heading',exact=True).fill('A quieter practice.')
                page.get_by_label('About / narrative copy',exact=True).fill('This is fictional test content, supplied solely to exercise the production workflow.')
                page.get_by_label('Hero image alternative text',exact=True).fill('Fictional terracotta vessel artwork')
                page.get_by_label('SEO description',exact=True).fill('A fictional test website for production-engine validation.')
                page.get_by_role('button',name='Create project & begin').click()
                page.wait_for_url('**/#project/**',timeout=15000)
                pid=page.url.split('#project/')[1].split('/')[0]
                p=wait_stage(pid,'VISUAL_REVIEW')
                check('UI intake creates persistent project',p['brief']['brand_name']=='Quiet Practice — smoke fixture')
                check('Website type and target remain separate',p['classification']['website_type']=='SERVICE_WEBSITE' and p['classification']['target']=='CUSTOM_WEB')
                check('Multiple references and assigned roles persist',len(p['brief']['references'])==2 and p['brief']['references'][1]['role']=='navigation')
                check('Asset inventory and brand constraints persist',len(p['assets'])==1 and len(p['constitution']['rules'])>=5)
                check('Discovery completes actual checkpoints',all(any(c['name']==key for c in p['checkpoints']) for key in ['RESEARCH_COMPLETE','ARCHITECTURE_COMPLETE','STRATEGY_COMPLETE','VISUAL_READY']))
                check('Unavailable references remain honest',all(r['status']=='UNAVAILABLE' for r in p['evidence']))
                check('Browser captures created',p['design_versions'][0]['captures']['status']=='PASS')
                response=client.post(f'/api/projects/{pid}/operations/produce')
                p=project(pid)
                check('Production before visual approval is rejected',response.status_code==409 and not p['builds'])
                # Clear the expected job error through an explicit non-destructive review.
                page.goto(base+'/#project/'+pid+'/visual');page.get_by_role('button',name='Revise',exact=True).click()
                page.locator('#feedback-text').fill('The hero image is too large. Keep all other decisions.')
                page.get_by_role('button',name='Submit revision',exact=True).click()
                page.locator("#feedback-dialog").wait_for(state="hidden",timeout=40000)
                p=project(pid)
                check('Natural-language surgical revision persists',p['active_design']==2 and p['design_versions'][1]['spec']['tokens']['image_scale']<p['design_versions'][0]['spec']['tokens']['image_scale'])
                old,new=p['design_versions'][0]['spec'],p['design_versions'][1]['spec']
                check('Unrelated approved design decisions remain intact',old['content']==new['content'] and old['tokens']['font']==new['tokens']['font'] and old['tokens']['background']==new['tokens']['background'])
                page.get_by_role('button',name='Keep & approve').click()
                p=wait_stage(pid,'FINAL_REVIEW')
                check('Gate 2 produces immutable design lock',p['design_lock']['locked'] and p['design_lock']['version']==2)
                check('Production runs only after approval',p['builds'][-1]['design_sha256']==p['design_lock']['sha256'])
                check('All eight real QA gates pass',set(p['qa']['results'])==set(['visual','functional','responsive','accessibility','performance','content_integrity','asset_integrity','platform_compliance']) and all(r['status']=='PASS' for r in p['qa']['results'].values()))
                check('Release candidate follows independent QA',p['release_candidate']['qa_id']==p['qa']['id'])
                build=p['builds'][-1];store=Store(Path(temp)/'data');path=store.path(pid)/build['path']/'index.html';original=path.read_text();path.write_text(original.replace('</main>','<p>1,000 invented satisfied clients</p></main>'))
                check('Tampered build cannot get final approval',client.post(f'/api/projects/{pid}/final-approval',json={'build_id':build['id']}).status_code==409)
                client.post(f'/api/projects/{pid}/operations/repair');p=wait_stage(pid,'FINAL_REVIEW')
                check('Real content/visual failures create defects',any(d['category']=='content_integrity' for d in p['defects']))
                check('Autonomous repair restores approved output and retests',all(d['status']=='RESOLVED' for d in p['defects']) and p['builds'][-1]['repairs'] and p['qa']['status']=='PASS')
                page.goto(base+'/#project/'+pid+'/final');page.get_by_role('button',name='Approve final website').click()
                page.get_by_role('link',name='Download approved release').wait_for(timeout=10000)
                p=project(pid);check('Gate 3 readies package without publication',p['stage']=='READY' and not p['deployment']['published'])
                check('Package integrity and manifest tested',p['builds'][-1]['package']['manifest_match']=='PASS')
                frame=page.frame_locator('#website-preview')
                frame.locator('h1').wait_for()
                frame.locator('img').first.wait_for()
                check('Authenticated sandbox preview loads stylesheet',frame.locator('body').evaluate("el=>getComputedStyle(el).backgroundColor === 'rgb(244, 241, 233)'"))
                check('Authenticated sandbox preview loads exact imagery',frame.locator('img').first.evaluate('el=>el.complete && el.naturalWidth>0'))
                preview_url=page.locator('#website-preview').get_attribute('src')
                check('Preview capability cannot expose server files',client.get(preview_url.rsplit('/',1)[0]+'/serve.py').status_code==404 and client.get('/preview/invalid/index.html').status_code==404)
                page.screenshot(path=str(EVIDENCE/'final-review-desktop.png'),full_page=True)
                page.goto(base+'/#projects');page.get_by_role('link',name='Quiet Practice').wait_for()
                page.screenshot(path=str(EVIDENCE/'projects-desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(EVIDENCE/'projects-mobile.png'),full_page=True)
                check('Studio responsive layout does not overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                axe=ROOT/'tools/shopify/node_modules/axe-core/axe.min.js';page.evaluate(axe.read_text());audit=page.evaluate("async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))}")
                (EVIDENCE/'studio-accessibility.json').write_text(json.dumps(audit,indent=2));check('Studio automated accessibility audit passes',not audit,audit)
                check('Studio has no browser runtime errors',not errors,errors)
                old_lock=p['design_lock'];old_approvals=p['approval_ledger'];stop()
                interrupted=store.create_job(pid,'resume');store.claim_job(interrupted['id']);proc=start()
                p=project(pid);check('Project survives application restart',p['stage']=='READY' and p['brief']['brand_name']=='Quiet Practice — smoke fixture')
                check('Approvals and locks survive recovery',p['design_lock']==old_lock and p['approval_ledger']==old_approvals)
                check('Interrupted job identified from persistent state',any(j['id']==interrupted['id'] and j['status']=='INTERRUPTED' for j in p['jobs']))
                recovery=client.post(f'/api/projects/{pid}/recovery').json();check('Recovery finds verified next action',recovery['status']=='VERIFIED' and recovery['next_operation']=='download')
                # Persist a compact evidence snapshot without any access tokens.
                (EVIDENCE/'smoke-project.json').write_text(json.dumps({'id':pid,'stage':p['stage'],'checkpoints':p['checkpoints'],'qa':p['qa'],'design_lock_sha256':p['design_lock']['sha256'],'approval_ledger':p['approval_ledger'],'recovery':recovery},indent=2))
                browser.close()
        finally: stop();client.close();log.close()
    result={'status':'PASS','checks':checks,'count':len(checks),'real_browser':True,'real_http':True,'restart_test':True}
    (EVIDENCE/'smoke-report.json').write_text(json.dumps(result,indent=2));return result

if __name__=='__main__':
    try: print(json.dumps(smoke(),indent=2))
    except Exception as error:
        (EVIDENCE/'smoke-failure.json').write_text(json.dumps({'status':'FAIL','error':str(error)},indent=2));raise
