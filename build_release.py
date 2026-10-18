"""Package already migrated and tested files for connector-safe binary transport."""
from pathlib import Path
import hashlib,io,json,zipfile
ROOT=Path(__file__).resolve().parent
names=['sumptuary_laws.db']+[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'data/round2').iterdir()) if p.is_file()]
manifest={'version':'round2-2026-10-17','files':{},'chunks':[]}
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name in names:
        data=(ROOT/name).read_bytes();manifest['files'][name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
        entry=zipfile.ZipInfo(name,date_time=(2026,10,17,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,data,compresslevel=9)
data=buf.getvalue();manifest['archive_sha256']=hashlib.sha256(data).hexdigest()
dest=ROOT/'release_chunks';dest.mkdir(exist_ok=True)
for i,offset in enumerate(range(0,len(data),262144)):
    part=data[offset:offset+262144];name=f'part_{i:03d}.bin';(dest/name).write_bytes(part)
    manifest['chunks'].append({'file':name,'sha256':hashlib.sha256(part).hexdigest(),'bytes':len(part)})
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
print('payload',len(data),'bytes;',len(manifest['chunks']),'chunks')
