"""Reconstruct byte-identical audited files from checked-in release chunks, offline."""
from pathlib import Path
import hashlib,io,json,os,zipfile

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def ensure_payload(root):
    root=Path(root).resolve();folder=root/'release_chunks'
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf8'))
    files=manifest['files']
    for name in files:
        target=(root/name).resolve()
        if not target.is_relative_to(root):raise ValueError('Unsafe release path')
    if all((root/name).is_file() and digest(root/name)==info['sha256'] for name,info in files.items()):return
    chunks=[]
    for part in manifest['chunks']:
        path=folder/part['file'];data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=part['sha256']:raise ValueError('Release chunk checksum mismatch: '+part['file'])
        chunks.append(data)
    archive=b''.join(chunks)
    if hashlib.sha256(archive).hexdigest()!=manifest['archive_sha256']:raise ValueError('Release archive checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        if set(z.namelist())!=set(files):raise ValueError('Release file manifest mismatch')
        for name,info in files.items():
            data=z.read(name)
            if len(data)!=info['bytes'] or hashlib.sha256(data).hexdigest()!=info['sha256']:raise ValueError('Payload checksum mismatch: '+name)
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+'.round2.tmp');temp.write_bytes(data);os.replace(temp,target)
if __name__=='__main__':ensure_payload(Path(__file__).resolve().parent)
