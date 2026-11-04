"""Prepare analysis-only debug symbols; runtime image and recorded data stay unchanged."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.parse
import datetime
import os

from pilot import HERE, sha

# Exact installed package version, independently obtained with dpkg-query in candidate-05.
PACKAGES={'4ff4496e386713bd4653311a5224feeac80026b4':('libpng16-16-dbgsym','1.6.39-2+deb12u6'),
          'd578f7589e9ca0f402951aaf752986f4a14616d4':('libmagickcore-6.q16-6-dbgsym','8:6.9.11.60+dfsg-1.6+deb12u15')}


def fetch(url,path):
    cp=subprocess.run(['curl','-fL','--max-time','35',url,'-o',str(path)],capture_output=True,text=True)
    if cp.returncode:
        return cp.stderr[-1200:]
    return None


def valid_build_id(path,buildid):
    cp=subprocess.run(['readelf','-n',str(path)],capture_output=True,text=True)
    return cp.returncode==0 and 'Build ID: '+buildid in cp.stdout


def main(destination,profiles,base=None):
    os.sched_setaffinity(0,{9})
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=False)
    original=Path(base).resolve() if base else HERE/'symbols'
    index=json.loads((original/'index.json').read_text())
    index['schema']='docops-supplemental-symbols-v1'
    index['initial_index_sha256']=sha(original/'index.json')
    index['initial_index_path']=str(original/'index.json')
    index['fetched_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows={r['build_id']:dict(r)for r in index['files']}
    for row in rows.values():
        if row['status']=='downloaded':
            path=destination/row['path'];path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original/row['path'],path)
    targets={}
    for profile in profiles:
        profile=Path(profile);data=json.loads(profile.read_text())
        builds={line.split(' ',1)[1]:line.split(' ',1)[0]for line in (profile.parent/'buildids.txt').read_text().splitlines()}
        for row in data['functions']:
            dso=row['dso']
            if row['function']=='[unknown]' and row['share_roi']>=.003 and dso in builds:
                # Debian symbols only. Custom Python/PyPI objects cannot be substituted by distro builds.
                if dso.startswith('/usr/lib/') or dso.startswith('/usr/bin/'):
                    targets[builds[dso]]=dso
    for buildid,(package,version)in PACKAGES.items():
        if buildid not in targets and buildid in rows:
            targets[buildid]=rows[buildid]['runtime_path']
    for buildid,dso in targets.items():
        if rows.get(buildid,{}).get('status')=='downloaded':continue
        path=destination/'.build-id'/buildid[:2]/(buildid[2:]+'.debug');path.parent.mkdir(parents=True,exist_ok=True)
        url=f'https://debuginfod.debian.net/buildid/{buildid}/debuginfo'
        error=fetch(url,path);source={'url':url}
        if error and buildid in PACKAGES:
            package,version=PACKAGES[buildid]
            metadata=destination/(package+'.json')
            metaurl='https://snapshot.debian.org/mr/binary/'+package+'/'+urllib.parse.quote(version,safe='')+'/binfiles'
            error=fetch(metaurl,metadata)
            if not error:
                candidates=[r for r in json.loads(metadata.read_text())['result']if r['architecture']=='arm64']
                if len(candidates)!=1:raise ValueError('ambiguous debug package')
                digest=candidates[0]['hash'];deb=destination/(package+'.deb')
                fileurl='https://snapshot.debian.org/file/'+digest;error=fetch(fileurl,deb)
                if not error:
                    if hashlib.sha1(deb.read_bytes()).hexdigest()!=digest:raise ValueError('snapshot package SHA1 mismatch')
                    members=subprocess.check_output(['ar','t',str(deb)],text=True).splitlines()
                    data_member=next(name for name in members if name.startswith('data.tar'))
                    compressed=subprocess.check_output(['ar','p',str(deb),data_member])
                    with tarfile.open(fileobj=io.BytesIO(compressed),mode='r:*')as archive:
                        wanted='usr/lib/debug/.build-id/'+buildid[:2]+'/'+buildid[2:]+'.debug'
                        member=next((m for m in archive.getmembers()if m.name.removeprefix('./')==wanted),None)
                        if member is None:raise ValueError('package has no requested build-id')
                        path.write_bytes(archive.extractfile(member).read())
                    source.update(snapshot_metadata_url=metaurl,snapshot_metadata_sha256=sha(metadata),
                                  package_url=fileurl,package_sha1=digest,package_sha256=sha(deb),
                                  package=package,version=version,architecture='arm64')
        row=dict(build_id=buildid,runtime_path=dso,**source)
        if error:
            row.update(status='failed',error=error)
        else:
            if not valid_build_id(path,buildid):raise ValueError('debug build-id mismatch: '+dso)
            row.update(status='downloaded',path=str(path.relative_to(destination)),bytes=path.stat().st_size,
                       sha256=sha(path),build_id_verified=True)
        rows[buildid]=row;index['files']=list(rows.values())
        (destination/'index.json').write_text(json.dumps(index,indent=2)+'\n')
        print(dso,row['status'],flush=True)
    (destination/'index.json').write_text(json.dumps(index,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--profile',type=Path,action='append',default=[])
    parser.add_argument('--base',type=Path)
    args=parser.parse_args();main(args.destination,args.profile,args.base)
