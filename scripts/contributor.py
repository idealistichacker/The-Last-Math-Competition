#!/usr/bin/env python3
"""Fail-closed, standard-library contribution coordinator. No daemon, no stored secrets."""
from __future__ import annotations
import argparse
import contextlib
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

UPSTREAM = 'The-Last-Math-Competition/The-Last-Math-Competition'
FORK = 'idealistichacker/The-Last-Math-Competition'
OWNER = 'idealistichacker'
ID_RE = re.compile(r'(?<!\d)[0-9]{11}(?!\d)')
PUSH_TIMEOUT_SECONDS = 120

class GateError(RuntimeError):
    pass

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def run(args, cwd, timeout=300):
    child_env={k:v for k,v in os.environ.items() if k not in {'GH_TOKEN','GITHUB_TOKEN'}}
    child_env.update({'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'Never','GCM_GUI_PROMPT':'0','PYTHONUTF8':'1'})
    if 'tectonic' in Path(str(args[0])).stem.lower(): child_env['SOURCE_DATE_EPOCH']='0'
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=timeout, env=child_env)
    if result.returncode:
        raise GateError(f'Command failed ({result.returncode}): {args[0]}\n{result.stdout[-6000:]}\n{result.stderr[-6000:]}')
    return result.stdout.strip()

def git(root, *args, timeout=300):
    return run(['git', '-c', 'credential.helper=', '-c', 'credential.helper=manager', *args], root, timeout=timeout)

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    tmp.replace(path)

def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def token_from_helper(root):
    token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token: return token
    p=subprocess.run(['git','-c','credential.helper=','-c','credential.helper=manager','credential','fill'],input='protocol=https\nhost=github.com\n\n',
        cwd=root,capture_output=True,text=True,timeout=120,
        env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'Never','GCM_GUI_PROMPT':'0'})
    # Do not surface credential-helper stdout/stderr, even on failure.
    values=dict(line.split('=',1) for line in p.stdout.splitlines() if '=' in line)
    if p.returncode or not values.get('password'):
        raise GateError('No noninteractive GitHub credential available; no login window opened.')
    return values['password']

class GitHub:
    def __init__(self, token=None): self.token=token
    def request(self, route, method='GET', payload=None):
        if not route.startswith('/') or route.startswith('//'): raise GateError('Invalid API route')
        headers={'Accept':'application/vnd.github+json','User-Agent':'TLMC-contribution-coordinator',
                 'X-GitHub-Api-Version':'2022-11-28'}
        if self.token: headers['Authorization']='Bearer '+self.token
        data=None if payload is None else json.dumps(payload).encode()
        if data is not None: headers['Content-Type']='application/json'
        # Explicitly close each GitHub request: some Windows/TLS stacks have returned
        # truncated large API bodies on persistent connections. Only idempotent GETs are
        # retried, and only after Python reports an incomplete response body; mutations
        # remain one-shot and are reconciled by their stable marker instead.
        headers['Connection'] = 'close'
        attempts = 2 if method == 'GET' else 1
        for attempt in range(attempts):
            req=urllib.request.Request('https://api.github.com'+route,data=data,headers=headers,method=method)
            try:
                with urllib.request.urlopen(req,timeout=60) as r:
                    body=r.read()
                    return json.loads(body) if body else {}
            except urllib.error.HTTPError as e:
                # Never log request headers, bearer tokens, or potentially sensitive response text.
                raise GateError(f'GitHub {method} {route.split("?")[0]} returned HTTP {e.code}; no blind mutation retry.') from None
            except http.client.IncompleteRead:
                if attempt + 1 == attempts:
                    raise GateError(f'GitHub GET {route.split("?")[0]} returned an incomplete response twice; no partial snapshot saved.') from None
    def pages(self,route):
        result=[]
        for page in range(1,101):
            sep='&' if '?' in route else '?'
            batch=self.request(f'{route}{sep}per_page=100&page={page}')
            if not isinstance(batch,list): raise GateError('Expected GitHub list response')
            result+=batch
            if len(batch)<100: return result
        raise GateError('Pagination cap reached; cannot establish a complete duplicate snapshot')

def identity(api):
    user=api.request('/user')
    if user['login']!=OWNER: raise GateError('Unexpected GitHub identity; refusing publication')
    fork=api.request('/repos/'+FORK)
    if not fork.get('permissions',{}).get('push'): raise GateError('No fork push permission')
    return user, fork

def refresh(root,api,deep=False):
    items=api.pages('/repos/'+UPSTREAM+'/issues?state=all')
    pulls=api.pages('/repos/'+UPSTREAM+'/pulls?state=all')
    snapshot={'fetched_at':now(),'upstream':UPSTREAM,'items':items,'pulls':pulls,'deep':False}
    if deep:
        from concurrent.futures import ThreadPoolExecutor
        previous=load(root/'.local/audit/github-deep.json') if (root/'.local/audit/github-deep.json').exists() else {}
        old={p['number']:p for p in previous.get('pulls',[])}
        def enrich_pull(p):
            cached=old.get(p['number'],{})
            if (cached.get('head',{}).get('sha')==p['head']['sha'] and
                cached.get('base',{}).get('sha')==p.get('base',{}).get('sha') and 'files_index' in cached):
                p['files_index']=cached['files_index']
            else:
                files=api.pages(f"/repos/{UPSTREAM}/pulls/{p['number']}/files")
                if len(files)>=3000: raise GateError('GitHub PR file limit prevents complete duplicate audit')
                p['files_index']=[f['filename'] for f in files]
            return p
        def enrich_item(i):
            i['comments_index']=api.pages(f"/repos/{UPSTREAM}/issues/{i['number']}/comments") if i.get('comments',0) else []
            return i
        with ThreadPoolExecutor(max_workers=4) as pool:
            snapshot['pulls']=list(pool.map(enrich_pull,pulls))
            snapshot['items']=list(pool.map(enrich_item,items))
        snapshot['deep']=True
        save(root/'.local/audit/github-deep.json',snapshot)
    save(root/'.local/audit/github.json',snapshot)
    return snapshot

def mentioned_ids(item):
    text=(item.get('title') or '')+'\n'+(item.get('body') or '')
    text+='\n'+'\n'.join(str(f) for f in item.get('files_index',[]))
    text+='\n'+'\n'.join(c.get('body') or '' for c in item.get('comments_index',[]))
    return set(ID_RE.findall(text))

def duplicate_items(items, conjecture_id):
    return [i for i in items if conjecture_id in mentioned_ids(i)]

def solution_path(root, relative):
    root=root.resolve()
    lexical=Path(os.path.abspath(root/relative))
    if not lexical.is_relative_to(root): raise GateError('Submission path escapes checkout')
    cursor=root
    for part in lexical.relative_to(root).parts:
        cursor=cursor/part
        if cursor.is_symlink() or (hasattr(cursor,'is_junction') and cursor.is_junction()):
            raise GateError('Symlink/junction submission path')
    path=lexical.resolve()
    if not path.is_relative_to(root/'solutions') or path==root/'solutions':
        raise GateError('Submission must be a descendant of this checkout\'s solutions directory')
    parts=path.relative_to(root).parts
    if len(parts)!=3 or not ID_RE.fullmatch(parts[1]) or not re.fullmatch(r'idealistichacker_submission_\d{14}',parts[2]):
        raise GateError('Expected solutions/<11-digit-id>/idealistichacker_submission_<UTC timestamp>')
    if not path.is_dir(): raise GateError('Submission directory is missing')
    for file in path.rglob('*'):
        if file.is_symlink() or not file.resolve().is_relative_to(path): raise GateError('Symlink/escaping submission path')
    return path

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def text_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def content_hash(path):
    h=hashlib.sha256()
    for f in sorted(path.rglob('*')):
        if not f.is_file() or any(p in {'.lake','__pycache__'} for p in f.relative_to(path).parts): continue
        if (f.parent==path and f.name in {'review.json','validation.json'}) or f.suffix in {'.aux','.log','.out','.toc','.pyc'}: continue
        data=f.read_bytes()
        if f.suffix in {'.md','.json','.lean','.toml','.tex','.py','.txt','.yml','.yaml'} or f.name in {'lean-toolchain','.gitignore'}:
            data=data.replace(b'\r\n',b'\n')
        h.update(f.relative_to(path).as_posix().encode()+b'\0'+data+b'\0')
    return h.hexdigest()

def check_lean_source(text):
    # Conservative lexeme gate: false positives in comments are acceptable; actual kernel audit still required.
    prohibited=r'\b(sorry|admit|axiom|native_decide|unsafe|implemented_by|extern|run_tac|elab|macro)\b'
    match=re.search(prohibited,text)
    if match: raise GateError('Prohibited Lean token: '+match.group(0))

def validate(root, relative, lake, tectonic, execute=True, offline_exact_dependencies=False):
    path=solution_path(root,relative); conjecture_id=path.parent.name
    required=['README.md','main.tex','main.pdf','reproduce.py','submission.json','review.json',
              'lean4/lean-toolchain','lean4/Main.lean','lean4/Check.lean']
    for name in required:
        if not (path/name).is_file(): raise GateError('Missing rule-3/quality artifact: '+name)
    if not any((path/'lean4'/name).is_file() for name in ('lakefile.toml','lakefile.lean')):
        raise GateError('Missing Lean Lake configuration: expected lean4/lakefile.toml or lean4/lakefile.lean')
    manifest=load(path/'submission.json')
    if manifest.get('id')!=conjecture_id or manifest.get('solver')!=OWNER or manifest.get('version')!=1:
        raise GateError('Invalid submission identity/schema')
    if manifest.get('verdict') not in {'proved','disproved'}: raise GateError('Verdict must be proved/disproved')
    if offline_exact_dependencies:
        reproduction = manifest.get('reproduction')
        if not isinstance(reproduction, dict) or not isinstance(reproduction.get('offline_exact_dependencies'), str) or not reproduction['offline_exact_dependencies'].strip():
            raise GateError('Offline exact-dependency validation requires an explicit package reproduction attestation')
    for key in ['title','statement_alignment','formal_scope','limitations']:
        if not isinstance(manifest.get(key),str) or len(manifest[key].strip())<20: raise GateError('Missing substantive '+key)
    source=root/'conjectures'/f'{conjecture_id}.md'
    if text_sha(source)!=manifest.get('source_sha256'): raise GateError('Conjecture content changed since analysis')
    if git(root,'hash-object',str(source))!=manifest.get('source_git_blob'): raise GateError('Source Git blob mismatch')
    toolchain=(path/'lean4/lean-toolchain').read_text().strip()
    if not re.fullmatch(r'leanprover/lean4:v\d+\.\d+\.\d+',toolchain): raise GateError('Lean toolchain must be pinned, no nightly/latest')
    if not (path/'main.pdf').read_bytes().startswith(b'%PDF-'): raise GateError('Not a PDF')
    for f in (path/'lean4').rglob('*.lean'):
        if '.lake' not in f.relative_to(path).parts: check_lean_source(f.read_text(encoding='utf-8'))
    theorems=manifest.get('theorems',[])
    if not theorems or not all(re.fullmatch(r'[A-Za-z_][\w.]*',t) for t in theorems): raise GateError('Explicit theorem names required')
    check=(path/'lean4/Check.lean').read_text()
    for theorem in theorems:
        if f'#print axioms {theorem}' not in check: raise GateError('Missing axiom audit for '+theorem)
    review=load(path/'review.json')
    if not isinstance(manifest.get('implementation_agent'),str) or not manifest['implementation_agent'].strip():
        raise GateError('Implementation agent identity required for independent review')
    if review.get('verdict')!='pass' or not review.get('reviewer') or review.get('reviewer')==manifest.get('implementation_agent'):
        raise GateError('Independent review is missing or not passed')
    for key in ['statement_alignment','mathematics','lean_bridge','reproduction','pdf_visual']:
        if review.get('checks',{}).get(key) is not True: raise GateError('Reviewer has not checked '+key)
    if review.get('content_sha256')!=content_hash(path): raise GateError('Review is stale: content changed')
    report={'checked_at':now(),'id':conjecture_id,'content_sha256':content_hash(path),'static':True,'executed':False}
    if execute:
        lake_path=Path(lake).resolve() if Path(lake).exists() else Path(shutil.which(lake) or lake)
        version=run([lake_path,'env','lean','--version'],path/'lean4',timeout=120)
        pin=toolchain.split(':v')[1]
        reported=re.search(r'\bversion\s+([^,\s)]+)',version)
        if not reported or reported.group(1)!=pin: raise GateError('Installed Lean does not match exact release pin')
        reproduce_command=[sys.executable,'reproduce.py','--lake',str(lake_path),'--repo',str(root.resolve())]
        if offline_exact_dependencies:
            reproduce_command.append('--skip-update')
        report['reproduce']=run(reproduce_command,path,timeout=300)
        report['lake_build']=run([lake_path,'build','Main'],path/'lean4',timeout=600)
        report['axioms']=run([lake_path,'env','lean','Check.lean'],path/'lean4',timeout=600)
        allowed={'propext','Classical.choice','Quot.sound'}
        for theorem in theorems:
            name=re.escape(theorem)
            empty=re.findall(r"^'"+name+r"' does not depend on any axioms\s*$",report['axioms'],re.MULTILINE)
            footprints=re.findall(r"^'"+name+r"' depends on axioms:\s*\[([^]]*)\]",report['axioms'],re.MULTILINE)
            if len(empty)+len(footprints)!=1:
                raise GateError('Missing, conflicting or duplicate axiom audit for '+theorem)
            if footprints and set(x.strip() for x in footprints[0].split(','))-allowed:
                raise GateError('Prohibited axiom footprint for '+theorem)
        # Compile actual LaTeX into a private directory; do not replace the reviewed PDF.
        out=root/'.local/pdf-check'/conjecture_id; out.mkdir(parents=True,exist_ok=True)
        report['latex']=run([tectonic,'--outdir',str(out.resolve()),'main.tex'],path,timeout=300)
        fresh=out/'main.pdf'
        if not fresh.is_file(): raise GateError('LaTeX did not produce PDF')
        # SOURCE_DATE_EPOCH and deterministic Tectonic source should yield identical bytes.
        if sha(fresh)!=sha(path/'main.pdf'): raise GateError('Submitted PDF differs from freshly compiled LaTeX')
        if content_hash(path)!=report['content_sha256']:
            raise GateError('Submission changed while validation was executing; review is stale')
        report['executed']=True
    save(root/'.local/validation'/f'{conjecture_id}.json',report)
    return report

def common_dir(root):
    common=Path(git(root,'rev-parse','--git-common-dir'))
    if not common.is_absolute(): common=root/common
    return common.resolve()

@contextlib.contextmanager
def publish_lock(root):
    p=common_dir(root)/'tlmc-publish.lock'; p.parent.mkdir(parents=True,exist_ok=True)
    try: fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError: raise GateError('Publication lock exists; verify owning process before recovery')
    try:
        os.write(fd,json.dumps({'pid':os.getpid(),'started_at':now()}).encode()); os.close(fd)
        yield
    finally: p.unlink(missing_ok=True)

def require_clean_scope(root,relative,base):
    allowed=relative.rstrip('/')+'/'
    tracked=git(root,'diff','--name-only',f'{base}...HEAD').splitlines()
    dirty=git(root,'diff','--name-only','HEAD').splitlines()
    untracked=git(root,'ls-files','--others','--exclude-standard').splitlines()
    staged=git(root,'diff','--cached','--name-only').splitlines()
    if any(not name.startswith(allowed) for name in tracked+dirty+untracked+staged):
        raise GateError('Solution branch contains files outside its single submission directory')

def publish(root,args,api):
    if not args.execute: raise GateError('Publish requires --execute; run validate first')
    with publish_lock(root):
        identity(api)
        path=solution_path(root,args.submission); relative=path.relative_to(root).as_posix(); cid=path.parent.name
        marker=f'<!-- tlmc:{OWNER}:{cid} -->'
        snap=refresh(root,api,deep=True)
        existing=[p for p in snap['pulls'] if marker in (p.get('body') or '') and p['user']['login']==OWNER]
        if existing:
            print(json.dumps({'state':'already_submitted','url':existing[0]['html_url']})); return
        hits=duplicate_items(snap['items']+snap['pulls'],cid)
        # Triage/scoring batch PRs are also surfaced for manual-agent inspection, not silently discarded.
        if hits: raise GateError('Possible duplicate submissions/mentions: '+','.join(str(i['number']) for i in hits))
        limit=getattr(args, 'max_open_solution_prs', 1)
        if type(limit) is not int or limit < 1:
            raise GateError('max_open_solution_prs must be a positive integer')
        active=[p for p in snap['pulls'] if p['state']=='open' and p['user']['login']==OWNER]
        if len(active) >= limit:
            raise GateError(f'WIP limit: {len(active)} active upstream PR(s), maximum {limit}')
        origin=git(root,'remote','get-url','origin').removesuffix('.git')
        upstream=git(root,'remote','get-url','upstream').removesuffix('.git')
        if origin not in {'https://github.com/'+FORK,'git@github.com:'+FORK} or upstream not in {'https://github.com/'+UPSTREAM,'git@github.com:'+UPSTREAM}:
            raise GateError('Unexpected Git remote')
        git(root,'fetch','upstream','main')
        current_blob=git(root,'rev-parse',f'upstream/main:conjectures/{cid}.md')
        if current_blob!=load(path/'submission.json')['source_git_blob']:
            raise GateError('Latest upstream conjecture differs from the reviewed source')
        branch=git(root,'branch','--show-current')
        if branch!=f'solution/{cid}': raise GateError('Publish only from solution/<id> branch')
        require_clean_scope(root,relative,'upstream/main')
        report=validate(root,relative,args.lake,args.tectonic,
                        offline_exact_dependencies=getattr(args, 'offline_exact_dependencies', False))
        state=common_dir(root)/'tlmc-publication'/f'{cid}.attempt.json'
        if state.exists(): raise GateError('Previous PR write may be unresolved; reconcile remote marker before any retry')
        git(root,'add','--',relative)
        if git(root,'diff','--cached','--name-only'):
            git(root,'diff','--cached','--check')
            git(root,'commit','-m',f'Disprove conjecture {cid}' if load(path/'submission.json')['verdict']=='disproved' else f'Prove conjecture {cid}')
        if git(root,'status','--porcelain'): raise GateError('Working tree not clean after scoped commit')
        # Push is never forced. For these small packages, fail closed after a bounded no-progress interval; never retry this run.
        git(root,'push','-u','origin',branch,timeout=PUSH_TIMEOUT_SECONDS)
        snap=refresh(root,api,deep=True)
        if duplicate_items(snap['items']+snap['pulls'],cid): raise GateError('New duplicate appeared before PR creation')
        m=load(path/'submission.json')
        body=(marker+'\n\n'+(path/'README.md').read_text(encoding='utf-8')+
              '\n\n## Automated release verification\n'+
              f"Source Git blob: `{m['source_git_blob']}`. Content SHA-256: `{report['content_sha256']}`.\n"+
              'Independent review, exact reproduction, pinned Lean build, theorem axiom audit and actual LaTeX rebuild passed locally.\n'+
              'AI-assisted submission by idealistichacker; no affiliation claimed. This is a review request, not a claim of acceptance.\n')
        save(state,{'attempted_at':now(),'marker':marker,'head':git(root,'rev-parse','HEAD'),'status':'unresolved'})
        pr=api.request('/repos/'+UPSTREAM+'/pulls','POST',{'title':f"{m['verdict'].capitalize()} conjecture {cid}: {m['title']}",
            'head':OWNER+':'+branch,'base':'main','body':body,'maintainer_can_modify':True,'draft':False})
        state.unlink()
        save(root/'.local/publication'/f'{cid}.json',{'created_at':now(),'url':pr['html_url'],'number':pr['number'],'head':git(root,'rev-parse','HEAD')})
        print(json.dumps({'state':'awaiting_upstream_review','url':pr['html_url']}))

def create_issue(root,args,api):
    if not args.execute: raise GateError('Issue publication requires --execute')
    draft=load(Path(args.draft))
    if not re.fullmatch(r'[a-z0-9-]{8,80}',draft.get('key','')): raise GateError('Stable issue key required')
    if len(draft.get('title',''))<15 or len(draft.get('body',''))<150: raise GateError('Substantive issue title/body required')
    if draft.get('reviewed') is not True: raise GateError('Issue draft has not been reviewed')
    marker=f"<!-- tlmc-issue:{OWNER}:{draft['key']} -->"
    with publish_lock(root):
        identity(api)
        items=api.pages('/repos/'+UPSTREAM+'/issues?state=all')
        for item in items:
            if marker in (item.get('body') or '') or item['title'].casefold()==draft['title'].casefold():
                print(json.dumps({'state':'already_exists','url':item['html_url']})); return
        cutoff=dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=7)
        recent=[i for i in items if not i.get('pull_request') and i['user']['login']==OWNER
                and dt.datetime.fromisoformat(i['created_at'].replace('Z','+00:00'))>cutoff]
        if recent: raise GateError('Standalone issue limit: one per seven days; prefer updating existing thread')
        attempt=common_dir(root)/'tlmc-publication'/('issue-'+draft['key']+'.attempt.json')
        if attempt.exists(): raise GateError('Previous issue write may be unresolved; reconcile remote marker before retry')
        save(attempt,{'attempted_at':now(),'marker':marker,'status':'unresolved'})
        result=api.request('/repos/'+UPSTREAM+'/issues','POST',{'title':draft['title'],'body':marker+'\n\n'+draft['body']})
        attempt.unlink()
        save(root/'.local/publication'/('issue-'+draft['key']+'.json'),{'number':result['number'],'url':result['html_url'],'created_at':now()})
        print(json.dumps({'state':'created','url':result['html_url']}))


def status(api,number):
    base=f'/repos/{UPSTREAM}/pulls/{number}'
    p=api.request(base); reviews=api.pages(base+'/reviews'); comments=api.pages(f'/repos/{UPSTREAM}/issues/{number}/comments')
    inline=api.pages(base+'/comments')
    checks=api.request(f"/repos/{UPSTREAM}/commits/{p['head']['sha']}/check-runs")
    return {'number':number,'state':p['state'],'merged':p.get('merged',False),'url':p['html_url'],
            'head':p['head']['sha'],'reviews':reviews,'comments':comments,'inline_comments':inline,
            'checks':checks,'note':'No auto-merge: upstream write permission/review authority is not held.'}

def main(argv=None):
    # This coordinator may report Lean theorem types containing Unicode while Windows
    # consoles still use CP936; make its own output deterministic and machine-readable.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--repo',default='.')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor'); p=sub.add_parser('refresh'); p.add_argument('--deep',action='store_true')
    for command in ['validate','publish']:
        p=sub.add_parser(command); p.add_argument('submission'); p.add_argument('--lake',default='lake'); p.add_argument('--tectonic',default='tectonic')
        p.add_argument('--execute',action='store_true',help='Execute publication (validate always executes by default)')
        if command=='validate': p.add_argument('--static-only',action='store_true',help='Not sufficient for publication')
        p.add_argument('--offline-exact-dependencies',action='store_true',help='Use package-declared offline exact-dependency verification; never a generic network bypass.')
        if command=='publish':
            p.add_argument('--max-open-solution-prs',type=int,default=1,
                           help='Default is 1. A value above 1 requires explicit user authorization and a current upstream-rule review; every PR still passes all gates independently.')
    p=sub.add_parser('status'); p.add_argument('number',type=int)
    p=sub.add_parser('issue'); p.add_argument('draft'); p.add_argument('--execute',action='store_true')
    p=sub.add_parser('hash'); p.add_argument('submission')
    args=parser.parse_args(argv); root=Path(args.repo).resolve()
    try:
        git(root,'rev-parse','--show-toplevel')
        if args.command=='hash': print(content_hash(solution_path(root,args.submission))); return 0
        if args.command=='validate':
            print(json.dumps(validate(root,args.submission,args.lake,args.tectonic,not args.static_only,
                                      offline_exact_dependencies=args.offline_exact_dependencies),ensure_ascii=False,indent=2)); return 0
        if args.command in {'publish','issue'} and not args.execute:
            raise GateError('External publication requires --execute; credentials not read')
        api=GitHub(token_from_helper(root))
        if args.command=='doctor':
            u,f=identity(api); up=api.request('/repos/'+UPSTREAM)
            result={'checked_at':now(),'login':u['login'],'fork_permissions':f['permissions'],
                    'upstream_permissions':up['permissions'],'fork_auto_merge_enabled':f.get('allow_auto_merge',False),
                    'branch':git(root,'branch','--show-current'),'upstream_merge_requires_maintainer':not up['permissions'].get('push',False)}
            save(root/'.local/audit/doctor.json',result); print(json.dumps(result,indent=2))
        elif args.command=='refresh':
            snap=refresh(root,api,deep=args.deep); print(json.dumps({'fetched_at':snap['fetched_at'],'issues_and_prs':len(snap['items']),'pulls':len(snap['pulls'])}))
        elif args.command=='publish': publish(root,args,api)
        elif args.command=='issue': create_issue(root,args,api)
        elif args.command=='status':
            result=status(api,args.number); save(root/'.local/audit'/f'pr-{args.number}.json',result)
            print(json.dumps({k:result[k] for k in ['number','state','merged','url','head','note']},indent=2))
        return 0
    except (GateError,subprocess.TimeoutExpired,urllib.error.URLError,OSError,ValueError,KeyError) as exc:
        print(f'BLOCKED: {exc}',file=sys.stderr); return 2

if __name__=='__main__': sys.exit(main())
