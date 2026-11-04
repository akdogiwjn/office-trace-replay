"""Verify official RPM checksums and exact runtime/debug ELF build IDs; no install."""
from pathlib import Path
import datetime,hashlib,json,re,stat,subprocess
ROOT=Path(__file__).resolve().parent
BASE='https://repo.openeuler.org/openEuler-24.03-LTS-SP3/debuginfo/aarch64/'

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def exact_read(stream,n):
    data=bytearray()
    while len(data)<n:
        b=stream.read(n-len(data))
        if not b:raise EOFError(f'truncated cpio, need {n}, got {len(data)}')
        data.extend(b)
    return bytes(data)

def extract_debugs(rpm,names):
    """Select only regular debug files by basename; never create archive symlinks."""
    out={}
    proc=subprocess.Popen(['rpm2cpio',str(rpm)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        while True:
            h=exact_read(proc.stdout,110)
            if h[:6] not in (b'070701',b'070702'):raise ValueError('unsupported cpio format')
            fields=[int(h[6+i*8:14+i*8],16) for i in range(13)]
            mode,size,namelen=fields[1],fields[6],fields[11]
            name=exact_read(proc.stdout,namelen).rstrip(b'\0').decode()
            exact_read(proc.stdout,(-(110+namelen))%4)
            if name=='TRAILER!!!':
                while proc.stdout.read(1024*1024):pass
                break
            if stat.S_ISREG(mode) and Path(name).name in names:
                dest=ROOT/'debugfiles'/Path(name).name
                dest.parent.mkdir(exist_ok=True)
                with dest.open('wb') as f:
                    remaining=size
                    while remaining:
                        chunk=exact_read(proc.stdout,min(1024*1024,remaining));f.write(chunk);remaining-=len(chunk)
                out[Path(name).name]={'path':str(dest.relative_to(ROOT)),'rpm_member':name}
            else:
                remaining=size
                while remaining:
                    chunk=exact_read(proc.stdout,min(1024*1024,remaining));remaining-=len(chunk)
            exact_read(proc.stdout,(-size)%4)
        stderr=proc.stderr.read().decode(errors='replace');rc=proc.wait()
        if rc:raise RuntimeError(f'rpm2cpio rc={rc}: {stderr}')
    finally:
        if proc.poll() is None:proc.kill();proc.wait()
        proc.stdout.close();proc.stderr.close()
    return out

def source_name(t):
    if t['package']['rc']:return None
    n,v,r,a,src=t['package']['stdout'].split('|')
    return src.removesuffix('.src.rpm').removesuffix('-'+v+'-'+r)+'-debuginfo'

inventory=json.loads((ROOT/'installed-targets.json').read_text())
targets=inventory['targets'];results=[]
for c in json.loads((ROOT/'candidates.json').read_text()):
    if not c['version_match']:continue
    pkg=ROOT/'packages'/Path(c['location']).name
    related=[t for t in targets if source_name(t)==c['name']]
    info={'package':c['name'],'version':c['version'],'arch':c['arch'],'url':BASE+c['location'],'metadata_sha256':c['checksum'],'expected_size':int(c['size']['package']),'targets':[]}
    if not pkg.exists() or pkg.stat().st_size!=info['expected_size']:
        info['status']='download_incomplete';results.append(info);continue
    info['download_sha256']=sha(pkg)
    if info['download_sha256']!=c['checksum']:
        info['status']='checksum_mismatch';results.append(info);continue
    names={}
    for t in related:
        m=re.search(r'\[\s*0\]\s+(\S+\.debug)',t['debuglink']['stdout'])
        if m:names[m.group(1)]=t
    extracted=extract_debugs(pkg,set(names))
    for name,t in names.items():
        d={'runtime_path':t['path'],'runtime_build_id':t['build_id'],'runtime_sha256':t['sha256'],'runtime_package':t['package']['stdout'],'debuglink':name}
        if name not in extracted:d['status']='debug_file_not_in_rpm'
        else:
            d.update(extracted[name]);debug=ROOT/d['path']
            notes=subprocess.run(['readelf','-n',str(debug)],capture_output=True,text=True,errors='replace',check=True).stdout
            m=re.search(r'Build ID: (\w+)',notes);d['debug_build_id']=m.group(1) if m else None
            sections=subprocess.run(['readelf','-SW',str(debug)],capture_output=True,text=True,check=True).stdout
            header=subprocess.run(['readelf','-h',str(debug)],capture_output=True,text=True,check=True).stdout
            d['has_symtab']='.symtab' in sections;d['has_debug_info']='.debug_info' in sections;d['is_aarch64']='AArch64' in header
            d['debug_sha256']=sha(debug)
            d['exact_build_id_match']=bool(d['debug_build_id'] and d['debug_build_id']==d['runtime_build_id'])
            d['status']='found_exact' if d['exact_build_id_match'] and d['has_symtab'] and d['is_aarch64'] else 'not_accepted'
        info['targets'].append(d)
    info['status']='verified' if len(info['targets'])==len(related) and all(d['status']=='found_exact' for d in info['targets']) else 'limited'
    results.append(info)
record={'schema':'docops-symbol-search-v1','searched_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image_id':inventory['image_id'],'repository':BASE,'repomd_sha256':sha(ROOT/'repomd.xml'),'primary_compressed_sha256':sha(ROOT/'primary.xml.zst'),'packages':results,'lxml':{'status':'no_matching_separate_debug_artifact_found','source':'https://pypi.org/pypi/lxml/6.1.2/json','release_asset_count':len(json.loads((ROOT/'lxml-pypi.json').read_text())['urls']),'debug_named_assets':[],'runtime_targets':[t for t in targets if '/lxml/' in t['path']]},'scope':{'runtime_changed':False,'symbols_installed':False,'perf_reexported':False,'workloads_or_profilers_started':False}}
(ROOT/'search-results.json').write_text(json.dumps(record,indent=2)+'\n')
for p in results:
    print(p['package'],p['status'])
    for t in p['targets']:print(' ',Path(t['runtime_path']).name,t['status'],t.get('debug_build_id'))
print('verified packages',sum(p['status']=='verified' for p in results),'of',len(results))
