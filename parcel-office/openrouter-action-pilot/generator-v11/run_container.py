"""One independent action/control cell using the imported ab4 Pi/relay architecture.

No model calls until explicitly invoked with a model, provider and key-file.
The fresh-chat content reviews use the desktop tools instead of this runner.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid
from zoneinfo import ZoneInfo
from generate import build, ROOT
from outcome import execute, score

def sh(*args, timeout=120, check=True):
    r=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    if check and r.returncode: raise RuntimeError(f'{args[0]} failed: {r.stderr[-1800:]}')
    return r

def save(path, value): path.write_text(json.dumps(value,indent=2))

def run(a):
    sh('docker','info',timeout=15)
    sh('docker','image','inspect',a.image,timeout=15)
    if not a.key_file.is_file(): raise ValueError('Key file is required.')
    if not a.relay.is_file(): raise ValueError('Imported ab4 relay.py is required.')
    if a.out.exists(): raise ValueError('Output directory must be fresh.')
    a.out.mkdir(parents=True)
    stage=Path(tempfile.mkdtemp(prefix='nq-desk-'))
    project='nq-'+uuid.uuid4().hex[:10]; name=project+'-agent'; volume=project+'-drive'
    meta={'model_id':a.model_id,'provider':a.provider,'image':a.image,'thinking':a.thinking,'max_requests':a.max_requests,'clock':'advancing clock starting at 09:05 depot time','execution':'session-boundary cutoff','started_utc':datetime.now(timezone.utc).isoformat(),'error':None,'spend_limit_usd':a.spend_limit,'automatic_retries':False}
    base=['docker','compose','-f',str(stage/'compose.json'),'-p',project]
    volume_created=False; services_started=False; built=False
    try:
        build(a.pack,a.out/'state',stage/'drive','http://desk-office:8000',revision=None); built=True
        times=json.loads((a.out/'state/service.json').read_text())
        config=stage/'pi-config'; config.mkdir(); state=stage/'pi-state'; state.mkdir(); relay=stage/'relay'; relay.mkdir(); logs=a.out/'relay'; logs.mkdir()
        for p in (config,state): p.chmod(0o777)
        save(relay/'config.json',{'models':{a.model_id:{'provider':a.provider}},'max_requests':a.max_requests,'max_output_tokens':a.max_output,'retries':0,'spend_limit_usd':a.spend_limit,'log_path':'/relay-log/relay.jsonl'})
        save(config/'models.json',{'providers':{'gateway':{'baseUrl':'http://relay:8080/v1','api':'openai-completions','apiKey':'internal','authHeader':True,'models':[{'id':a.model_id,'name':a.model_id,'contextWindow':a.context_window,'maxTokens':a.max_output,'input':['text'],'reasoning':True}]}}})
        target=datetime.fromisoformat(times.get('state_as_of',times['run_date']+'T09:05:00')).replace(tzinfo=ZoneInfo(times['timezone']))
        meta['clock']='advancing clock starting at '+target.isoformat()
        clock=stage/'clock'; clock.write_text(f"{int(target.timestamp()-time.time()):+d}\n")
        # Same moving-clock implementation as ab4; model and office see the same depot date.
        common={'image':a.image,'read_only':True,'user':f'{os.getuid()}:{os.getgid()}','cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],'pids_limit':64,'mem_limit':'256m','cpus':1.0,'tmpfs':['/tmp:rw,noexec,nosuid,size=16m']}
        ro=lambda src,dst:f'{src}:{dst}:ro'
        compose={'services':{
          'desk-office':{**common,'command':['python3','/opt/service/desk.py','--data','/data','--bind','0.0.0.0','--port','8000'],'environment':{'TZ':times['timezone']},'volumes':[ro(ROOT/'service.py','/opt/service/desk.py'),ro(ROOT/'operations.py','/opt/service/operations.py'),f"{a.out/'state'}:/data",ro(clock,'/etc/faketimerc')],'networks':['internal'],'healthcheck':{'test':['CMD','python3','-c',"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"],'interval':'1s','timeout':'2s','retries':30}},
          'relay':{**common,'command':['python3','/opt/service/relay.py'],'environment':{'RELAY_CONFIG':'/config/config.json','OPENROUTER_SECRET_FILE':'/run/secrets/model_key'},'volumes':[ro(a.relay,'/opt/service/relay.py'),ro(relay/'config.json','/config/config.json'),f'{logs}:/relay-log'],'secrets':['model_key'],'networks':['internal','egress'],'healthcheck':{'test':['CMD','python3','-c',"import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"],'interval':'1s','timeout':'2s','retries':30}}
        },'networks':{'internal':{'internal':True},'egress':{}},'secrets':{'model_key':{'file':str(a.key_file)}}}
        save(stage/'compose.json',compose)
        sh('docker','volume','create',volume); volume_created=True
        sh('docker','run','--rm','--network','none','--user','0','--mount',f'type=bind,src={stage / "drive"},dst=/src,readonly','--mount',f'type=volume,src={volume},dst=/dst',a.image,'sh','-c','cp -a /src/. /dst/ && chown -R 10001:10001 /dst')
        sh(*base,'up','-d','--wait',timeout=180); services_started=True
        args=['docker','run','--rm','--name',name,'--hostname','depot-desk-01','--network',project+'_internal','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges:true','--pids-limit','256','--memory','2g','--cpus','2','--tmpfs','/tmp:rw,nosuid,size=256m','--tmpfs','/home/depot-agent/.pi:rw,nosuid,nodev,size=64m,uid=10001,gid=10001','--mount',f'type=bind,src={config},dst=/run/pi-config','--mount',f'type=bind,src={state},dst=/run/pi-state','--mount',f'type=bind,src={clock},dst=/etc/faketimerc,readonly','--mount',f'type=volume,src={volume},dst=/home/depot-agent/Shared Drive','--workdir','/home/depot-agent/Shared Drive','--env','PI_CODING_AGENT_DIR=/run/pi-config','--env','PI_OFFLINE=1','--env','PI_SKIP_VERSION_CHECK=1','--env','PI_TELEMETRY=0','--env',f"TZ={times['timezone']}",a.image,'pi','--mode','json','--no-extensions','--no-skills','--no-prompt-templates','--no-themes','--no-context-files','--no-approve','--session','/run/pi-state/session.jsonl','--model','gateway/'+a.model_id,'--thinking',a.thinking,'--system-prompt',(a.out/'state/action-system.txt').read_text(),'--',(a.out/'state/action-trigger.txt').read_text()]
        if a.preflight:
            # Exercise the same isolated desk, but never call the model relay.
            manifest=json.loads((a.out/'state/manifest.json').read_text())
            program="import subprocess, pathlib, socket, json; from datetime import datetime; print('Clock:',datetime.now().isoformat()); assert not pathlib.Path('/data/office.sqlite').exists(); assert not pathlib.Path('/run/secrets/model_key').exists(); c=['python3','Tools/desk.py']; subprocess.run(c+['overview'],check=True); subprocess.run(c+['record',"+repr(manifest['exception_id'])+"],check=True); subprocess.run(c+['update',"+repr(manifest['exception_id'])+",'--storage-until',"+repr(times['extension'])+",'--note','Collection appointment; prior permission absent'],check=True); subprocess.run(c+['summary'],check=True); subprocess.run(c+['submit'],check=True)"
            args=args[:args.index(a.image)+1]+['python3','-c',program]
            meta['preflight']=True
        with (a.out/'pi.jsonl').open('w') as stdout,(a.out/'pi.stderr.txt').open('w') as stderr:
            try: meta['exit_code']=subprocess.run(args,stdout=stdout,stderr=stderr,timeout=a.timeout).returncode
            except subprocess.TimeoutExpired:
                meta['timed_out']=True; sh('docker','kill',name,check=False)
        sh(*base,'stop','desk-office',timeout=30)
        execute(a.out/'state',times['cutoff']); outcome=score(a.out/'state'); outcome['technical_failure']=meta.get('exit_code')!=0 or bool(meta.get('timed_out')); save(a.out/'result.json',outcome)
    except Exception as e:
        meta['error']=f'{type(e).__name__}: {e}'
    finally:
        if (stage/'compose.json').exists():
            r=sh(*base,'logs','--no-color',check=False); (a.out/'services.log').write_text(r.stdout+r.stderr)
            sh(*base,'down','--remove-orphans','--timeout','5',check=False)
        sh('docker','rm','-f',name,check=False)
        if volume_created:
            dest=a.out/'drive-after'; dest.mkdir()
            sh('docker','run','--rm','--network','none','--user',f'{os.getuid()}:{os.getgid()}','--mount',f'type=volume,src={volume},dst=/src,readonly','--mount',f'type=bind,src={dest},dst=/dst',a.image,'sh','-c','cp -r /src/. /dst/',check=False)
            sh('docker','volume','rm',volume,check=False)
        if (stage/'pi-state/session.jsonl').exists(): shutil.copy2(stage/'pi-state/session.jsonl',a.out/'session.jsonl')
        meta['finished_utc']=datetime.now(timezone.utc).isoformat(); save(a.out/'meta.json',meta); shutil.rmtree(stage)
    return meta

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--pack',type=Path,default=ROOT/'pack.toml'); p.add_argument('--out',type=Path,required=True); p.add_argument('--key-file',type=Path,required=True); p.add_argument('--model-id',required=True); p.add_argument('--provider',required=True); p.add_argument('--max-output',type=int,required=True); p.add_argument('--context-window',type=int,default=1000000); p.add_argument('--max-requests',type=int,default=200); p.add_argument('--timeout',type=int,default=1800); p.add_argument('--thinking',default='high'); p.add_argument('--image',default='nq-depot-agent:0.1'); p.add_argument('--relay',type=Path,default=ROOT/'model_relay.py'); p.add_argument('--spend-limit',type=float,default=5.0,help='stop subsequent relay requests after this billed USD threshold; one in-flight request may exceed it'); p.add_argument('--preflight',action='store_true',help='exercise desk in the agent container without any model request'); a=p.parse_args()
    for k in ('pack','out','key_file','relay'): setattr(a,k,getattr(a,k).resolve())
    result=run(a); print(json.dumps(result,indent=2)); raise SystemExit(1 if result['error'] else 0)
