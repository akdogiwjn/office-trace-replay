from pathlib import Path
import subprocess,json
root=Path(__file__).resolve().parent
code=r"""
import subprocess,json,hashlib,re
paths=['/usr/lib64/libpng16.so.16.40.0','/usr/lib64/libMagickCore-7.Q16HDRI.so.10.0.2','/usr/lib64/libpixman-1.so.0.42.2','/usr/lib64/libfreeblpriv3.so','/usr/lib64/libjpeg.so.62.4.0','/usr/lib64/libfontconfig.so.1.12.1','/usr/lib64/libcairo.so.2.11800.0','/usr/lib64/pkcs11/p11-kit-trust.so','/usr/lib64/ImageMagick-7.1.2/modules-Q16HDRI/coders/png.so','/usr/lib64/ImageMagick-7.1.2/modules-Q16HDRI/coders/jpeg.so','/usr/lib64/libcrypto.so.3.0.12','/usr/lib64/libsqlite3.so.0.8.6','/opt/docops/venv/lib/python3.12/site-packages/lxml/etree.cpython-312-aarch64-linux-gnu.so','/opt/docops/venv/lib/python3.12/site-packages/lxml/_elementpath.cpython-312-aarch64-linux-gnu.so']
out=[]
for p in paths:
 d={'path':p}
 for key,cmd in [('package',['rpm','-qf','--qf','%{NAME}|%{VERSION}|%{RELEASE}|%{ARCH}|%{SOURCERPM}',p]),('notes',['readelf','-n',p]),('debuglink',['readelf','-p','.gnu_debuglink',p])]:
  r=subprocess.run(cmd,text=True,errors="replace",capture_output=True)
  if key=='notes':
   m=re.search(r'Build ID: (\w+)',r.stdout);d['build_id']=m.group(1) if m else None
  else:d[key]={'rc':r.returncode,'stdout':r.stdout.strip(),'stderr':r.stderr.strip()}
 try:
  with open(p,'rb') as f:d['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
 except OSError as e:d['file_error']=str(e)
 out.append(d)
print(json.dumps(out))
"""
img='sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164'
r=subprocess.run(['docker','--host','unix:///var/run/docker.sock','run','--rm','--network','none','--read-only','--entrypoint','/opt/docops/venv/bin/python3',img,'-c',code],capture_output=True,text=True)
(root/'inventory-stderr.txt').write_text(r.stderr)
print('docker rc',r.returncode, 'stderr',r.stderr[:2500])
if r.returncode==0:
 rows=json.loads(r.stdout); (root/'installed-targets.json').write_text(json.dumps({'image_id':img,'targets':rows},indent=2)+'\n')
 for x in rows:print(x['path'],x['package']['stdout'],x['build_id'])
else: print(r.stdout[:500])
raise SystemExit(r.returncode)
