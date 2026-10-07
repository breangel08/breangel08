"""Actual MCP subprocess transport plus real fixture discovery/build/QA/recovery."""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from engine.fixtures import CUSTOM_BRIEF, sample_art

ROOT=Path(__file__).resolve().parents[1]


async def main():
    checks=[]
    def check(name, condition):
        if not condition:raise AssertionError(name)
        checks.append({'name':name,'status':'PASS'});print('PASS:',name,flush=True)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp); image=root/'hero.webp';image.write_bytes(sample_art())
        params=StdioServerParameters(command=sys.executable,args=['-m','engine.mcp','--data-dir',str(root/'data'),'--asset-root',str(root)],env={**os.environ,'PYTHONPATH':str(ROOT),'STUDIO_ENABLE_RESEARCH':'0'})
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                catalog=await session.list_tools();names={t.name for t in catalog.tools}
                check('Real MCP handshake and tool schemas',len(names)==14 and 'website_review' in names)
                async def call(name,args=None,failed=False):
                    result=await session.call_tool(name,args or {})
                    if failed:
                        check('MCP rejects unauthorized operation: '+name,bool(result.isError));return None
                    if result.isError:raise AssertionError(str(result.content))
                    if result.structuredContent is not None:return result.structuredContent
                    return json.loads(result.content[0].text)
                brief={**CUSTOM_BRIEF,'brand_name':'MCP fictional smoke fixture','references':[]}
                p=await call('website_create',{'brief':brief});pid=p['id']
                check('Chat brief and platform persist',p['brief']['brand_name']==brief['brand_name'] and p['classification']['target']=='CUSTOM_WEB')
                await call('website_run',{'project_id':pid,'operation':'produce'},failed=True)
                asset=await call('website_ingest_asset',{'project_id':pid,'file_path':str(image),'role':'hero'})
                check('Chat exact asset ingestion',asset['exact'] and asset['bytes']==len(image.read_bytes()))
                job=await call('website_run',{'project_id':pid,'operation':'discover'})
                async def wait(job_id):
                    for _ in range(240):
                        value=await call('website_job',{'job_id':job_id})
                        if value['status']=='FAILED':raise AssertionError(value)
                        if value['status']=='SUCCEEDED':return value
                        await asyncio.sleep(1)
                    raise AssertionError('MCP job retry threshold exceeded')
                await wait(job['id'])
                p=await call('website_status',{'project_id':pid})
                check('Chat discovers genuine visual authority',p['stage']=='VISUAL_REVIEW' and p['design_versions'][-1]['captures']['status']=='PASS')
                await call('website_review',{'project_id':pid,'review':{'action':'KEEP','version':p['active_design']},'human_approved':False},failed=True)
                # Explicit fictional test review; never grants approval to customer projects.
                p=await call('website_review',{'project_id':pid,'review':{'action':'KEEP','version':p['active_design'],'feedback':'Explicit fictional MCP test approval'},'human_approved':True})
                check('Chat keeps immutable lock and starts real production',p['design_lock']['locked'] and bool(p['status']['active_jobs']))
                await wait(p['status']['active_jobs'][0]['id'])
                p=await call('website_status',{'project_id':pid})
                check('MCP build earns candidate through eight real QA gates',p['stage']=='FINAL_REVIEW' and len(p['qa']['results'])==8 and all(r['status']=='PASS' for r in p['qa']['results'].values()))
                bid=p['release_candidate']['build_id']
                await call('website_approve_final',{'project_id':pid,'build_id':bid,'human_approved':False},failed=True)
                p=await call('website_approve_final',{'project_id':pid,'build_id':bid,'human_approved':True})
                check('Chat final approval prepares release without publication',p['stage']=='READY' and not p['deployment']['published'])
                artifacts=await call('website_artifacts',{'project_id':pid});check('Chat exposes actual review/package artifacts',any(f['relative_path'].endswith('.zip') for f in artifacts['files']))
                await call('website_read_artifact',{'project_id':pid,'relative_path':'../../../../etc/passwd'},failed=True)
                lock=p['design_lock'];ledger=p['approval_ledger']
        # New process, same store: true MCP restart rather than an in-memory assertion.
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                result=await session.call_tool('website_recover',{'project_id':pid});recovery=result.structuredContent or (json.loads(result.content[0].text) if not result.isError else {})
                if result.isError: raise AssertionError(str(result.content))
                check('MCP restart recovers persisted next operation',not result.isError and recovery['status']=='VERIFIED' and recovery['next_operation']=='download')
                result=await session.call_tool('website_status',{'project_id':pid});p=result.structuredContent or (json.loads(result.content[0].text) if not result.isError else {})
                if result.isError: raise AssertionError(str(result.content))
                check('Chat approvals and locks survive process restart',p['design_lock']==lock and p['approval_ledger']==ledger)
    report={'status':'PASS','count':len(checks),'checks':checks,'real_stdio':True,'real_browser_qa':True,'real_process_restart':True,'fixture_only_approvals':True}
    (ROOT/'test-results').mkdir(exist_ok=True);(ROOT/'test-results'/'mcp-smoke-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':asyncio.run(main())
