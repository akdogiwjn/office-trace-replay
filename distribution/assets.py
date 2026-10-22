#!/usr/bin/env python3
"""Verify/export/restore byte-identical offline assets; never use the network."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'distribution/large-assets.json'


def stream_hash(stream):
    digest, size = hashlib.sha256(), 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def file_matches(path, item):
    if not path.is_file() or path.stat().st_size != item['size_bytes']:
        return False
    with path.open('rb') as stream:
        return stream_hash(stream) == (item['sha256'], item['size_bytes'])


class Assets:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.manifest_bytes = (self.root / MANIFEST).read_bytes()
        self.manifest = json.loads(self.manifest_bytes)
        if self.manifest.get('schema_version') != 'office-offline-assets-v1':
            raise ValueError('unsupported offline asset manifest')
        self.files = self.manifest['files']
        self.objects = {}
        seen = set()
        for item in self.files:
            name = item['path']
            rel = PurePosixPath(name)
            if (not name or not rel.parts or rel.is_absolute() or '..' in rel.parts or rel.parts[0] == '.git'
                    or str(rel) != name or name in seen):
                raise ValueError('unsafe or repeated asset path: ' + name)
            seen.add(name)
            digest = item['sha256']
            if (len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)
                    or not isinstance(item['size_bytes'], int) or item['size_bytes'] < 0
                    or item['mode'] not in (0o644, 0o755)):
                raise ValueError('invalid asset specification: ' + name)
            if digest in self.objects and self.objects[digest]['size_bytes'] != item['size_bytes']:
                raise ValueError('conflicting object size')
            self.objects[digest] = item
            self.path(item)

    def path(self, item):
        path = self.root / item['path']
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('asset path escapes root: ' + item['path'])
        return path

    def verify(self):
        missing, different = [], []
        for item in self.files:
            path = self.path(item)
            if not path.exists():
                missing.append(item['path'])
            elif not file_matches(path, item):
                different.append(item['path'])
        return {'status': 'success' if not missing and not different else 'failed',
                'files': len(self.files), 'unique_objects': len(self.objects),
                'missing': missing, 'different': different}

    @staticmethod
    def atomic_copy(stream, path, mode=0o644):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
                temporary = Path(output.name)
                shutil.copyfileobj(stream, output, 1024 * 1024)
            temporary.chmod(mode)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def export(self, store, bundle):
        """Create a deduplicated local store and exclusive, deterministic TAR."""
        store, bundle = Path(store).resolve(), Path(bundle).resolve()
        if store.is_relative_to(self.root) or bundle.is_relative_to(self.root):
            raise ValueError('asset exports must be outside the source repository')
        if store.exists() or bundle.exists():
            raise FileExistsError('refusing to overwrite an asset store or bundle')
        result = self.verify()
        if result['status'] != 'success':
            raise ValueError('source assets missing/different: ' + json.dumps(result))
        store.mkdir(parents=True)
        (store / 'manifest.json').write_bytes(self.manifest_bytes)
        object_dir = store / 'objects/sha256'
        object_dir.mkdir(parents=True)
        for digest, item in self.objects.items():
            with self.path(item).open('rb') as stream:
                self.atomic_copy(stream, object_dir / digest)
            if not file_matches(object_dir / digest, item):
                raise ValueError('exported object differs: ' + digest)
        bundle.parent.mkdir(parents=True, exist_ok=True)
        with bundle.open('xb') as output, tarfile.open(fileobj=output, mode='w') as archive:
            sources = [('manifest.json', store / 'manifest.json')]
            sources.extend(('objects/sha256/' + digest, object_dir / digest)
                           for digest in sorted(self.objects))
            for name, source in sources:
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = source.stat().st_size, 0o644, 0
                with source.open('rb') as stream:
                    archive.addfile(info, stream)
        return {'status': 'success', 'store': str(store), 'bundle': str(bundle),
                'files': len(self.files), 'unique_objects': len(self.objects),
                'bundle_size_bytes': bundle.stat().st_size}

    def restore(self, bundle=None, store=None):
        if (bundle is None) == (store is None):
            raise ValueError('choose exactly one local bundle or object store')
        different = [item['path'] for item in self.files
                     if self.path(item).exists() and not file_matches(self.path(item), item)]
        if different:
            raise ValueError('existing files differ; refusing to overwrite: ' + ', '.join(different))
        archive = tarfile.open(bundle, 'r:*') if bundle is not None else None

        def open_member(name):
            if archive is None:
                path = Path(store).resolve() / name
                if not path.resolve().is_relative_to(Path(store).resolve()) or path.is_symlink():
                    raise ValueError('unsafe store member: ' + name)
                return path.open('rb')
            member = archive.getmember(name)
            if not member.isfile():
                raise ValueError('bundle member must be a regular file: ' + name)
            return archive.extractfile(member)

        try:
            if archive is not None:
                names = archive.getnames()
                expected = {'manifest.json'} | {'objects/sha256/' + x for x in self.objects}
                if set(names) != expected or len(names) != len(expected):
                    raise ValueError('unexpected or repeated bundle members')
            with open_member('manifest.json') as stream:
                if stream.read(len(self.manifest_bytes) + 1) != self.manifest_bytes:
                    raise ValueError('bundle/store belongs to a different manifest')
            # Validate every source object before creating any restored file.
            for digest, item in self.objects.items():
                with open_member('objects/sha256/' + digest) as stream:
                    if stream_hash(stream) != (digest, item['size_bytes']):
                        raise ValueError('asset object hash/size mismatch: ' + digest)
            restored = 0
            for item in self.files:
                path = self.path(item)
                if file_matches(path, item):
                    continue
                with open_member('objects/sha256/' + item['sha256']) as stream:
                    self.atomic_copy(stream, path, item['mode'])
                restored += 1
            result = self.verify()
            if result['status'] != 'success':
                raise ValueError('restored asset verification failed: ' + json.dumps(result))
            return {**result, 'restored_files': restored}
        finally:
            if archive is not None:
                archive.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify', 'restore', 'export'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--store', type=Path)
    args = parser.parse_args(argv)
    try:
        assets = Assets(args.root)
        if args.action == 'verify':
            result = assets.verify()
        elif args.action == 'export':
            if args.bundle is None or args.store is None:
                raise ValueError('export requires --store and --bundle')
            result = assets.export(args.store, args.bundle)
        else:
            result = assets.restore(args.bundle, args.store)
    except (OSError, ValueError, KeyError, tarfile.TarError) as exc:
        result = {'status': 'failed', 'error': str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
