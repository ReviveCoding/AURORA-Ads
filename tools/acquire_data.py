#!/usr/bin/env python3
"""Cache-aware public data acquisition scaffold. Default: offline plan, no network.

This utility does not train AURORA, extract archives, accept terms implicitly,
or verify scientific suitability. Inspect publisher terms and schema separately.
Only standard-library modules are required. Version2 hardens path and HTTP completion checks. Network integration remains untested
in the design environment; local helper tests are included.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import math
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024 ** 3


def safe_relative(value: str) -> Path:
    if not isinstance(value,str) or not value or any(ord(ch)<32 for ch in value):
        raise ValueError('Invalid relative path')
    raw=value.split('/')
    reserved={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
    if any(part in {'','.','..'} or part.endswith((' ','.')) or part.split('.')[0].upper() in reserved for part in raw):
        raise ValueError('Unsafe or nonportable relative path')
    if any(ch in value for ch in ('\\',':','*','?','<','>','|','"')):
        raise ValueError('Unsafe path characters')
    return Path(*raw)


def no_symlink(path: Path) -> None:
    for item in [path,*path.parents]:
        if item.is_symlink():
            raise ValueError('Refusing a symlink path')


def validate_range(header: str, offset: int) -> tuple[int,int]:
    match=re.fullmatch(r'bytes ([0-9]+)-([0-9]+)/([0-9]+)',header)
    if not match: raise ValueError('Invalid Content-Range')
    start,end,total=map(int,match.groups())
    if start!=offset or end<start or total<=end:
        raise ValueError('Invalid continuation geometry')
    return end,total


class ByteMeter:
    def __init__(self,limit: int):
        if limit<=0: raise ValueError('Byte quota must be positive')
        self.limit=limit; self.used=0
    def charge(self,n: int):
        if n<0: raise ValueError('Negative byte count')
        self.used+=n
        if self.used>self.limit:
            raise ValueError('Acquisition network-byte quota exhausted; partial preserved')


def safe_url(url: str) -> str:
    p = urlparse(url)
    h = (p.hostname or '').lower()
    valid = h in {'huggingface.co', 'ailab.criteo.com', 'go.criteo.net',
                  'criteostorage.blob.core.windows.net'}
    valid = valid or h.endswith('.huggingface.co') or h.endswith('.hf.co')
    if p.scheme != 'https' or not valid or p.username or p.password or p.port not in {None, 443}:
        raise ValueError(f'Unapproved HTTPS source host: {h}')
    return url


class SourceRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = build_opener(SourceRedirect())


def open_url(url: str, headers: dict[str, str] | None = None):
    safe_url(url)
    hdr = {'User-Agent': 'AURORA-Ads-research-acquisition/1.0', 'Accept-Encoding': 'identity'}
    hdr.update(headers or {})
    return OPENER.open(Request(url, headers=hdr), timeout=60)


def get_json(url: str) -> dict[str, Any]:
    with open_url(url) as response:
        content = response.read(16 * 1024 * 1024 + 1)
        if len(content) > 16 * 1024 * 1024:
            raise ValueError('Metadata response exceeded size limit')
        return json.loads(content)


def atomic_json(path: Path, value: Any) -> None:
    no_symlink(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:
        json.dump(value,f,ensure_ascii=False,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        tmp=Path(f.name)
    os.replace(tmp,path)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while data := f.read(4 * 1024 * 1024):
            h.update(data)
    return h.hexdigest()


def inspect_file(path: Path, expected_sha: str | None, expected_size: int | None) -> dict[str, Any]:
    no_symlink(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    n = path.stat().st_size
    if n <= 0 or (expected_size is not None and n != expected_size):
        raise ValueError(f'Size mismatch for {path.name}: {n} vs {expected_size}')
    actual = sha256(path)
    if expected_sha and actual.lower() != expected_sha.lower():
        raise ValueError(f'Checksum mismatch for {path.name}; existing file was not modified')
    with path.open('rb') as f:
        prefix = f.read(256).lstrip().lower()
    if prefix.startswith((b'<!doctype html', b'<html')):
        raise ValueError('HTML page received instead of a dataset payload')
    return {'path': str(path.resolve()), 'bytes': n, 'sha256': actual,
            'checksum_basis': 'publisher_hash_matched' if expected_sha else 'locally_recorded_only',
            'schema_crc_admission': 'PENDING_NOT_PERFORMED_BY_DOWNLOADER'}


class LinkReader(HTMLParser):
    def __init__(self):
        super().__init__(); self.links: list[tuple[str, str]] = []; self.href = None; self.text = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href'); self.text = []
    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)
    def handle_endtag(self, tag):
        if tag == 'a' and self.href is not None:
            self.links.append((self.href, ' '.join(self.text).strip()))
            self.href = None; self.text = []


def resolve_landing_html(html: str, spec: dict[str, Any]) -> str:
    parser = LinkReader(); parser.feed(html)
    candidates = []
    for href, text in parser.links:
        url = urljoin(spec['source_page'], href)
        if (urlparse(url).hostname == spec['landing_link_host']
                and spec['landing_link_text'].lower() in text.lower()):
            candidates.append(url)
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) != 1:
        raise ValueError('Publisher download anchor missing/ambiguous. Review source manually; no guessed mirror.')
    # The official page still advertises its own legacy HTTP endpoint. Upgrade
    # only the exact configured publisher host to TLS; never allow HTTP transfer.
    candidate = candidates[0]
    parsed = urlparse(candidate)
    if parsed.scheme == 'http' and parsed.hostname == spec['landing_link_host'] and parsed.port is None and not parsed.username and not parsed.password:
        candidate = parsed._replace(scheme='https').geturl()
    return safe_url(candidate)


def resolve_sources(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if spec['acquisition'] == 'manual':
        return [], {'status': 'MANUAL_SOURCE_REQUIRED', 'page': spec['source_page']}
    if spec['acquisition'] == 'landing_page':
        with open_url(spec['source_page']) as r:
            html_bytes = r.read(4 * 1024 * 1024 + 1)
        if len(html_bytes) > 4 * 1024 * 1024:
            raise ValueError('Landing page exceeds limit')
        url = resolve_landing_html(html_bytes.decode('utf-8', errors='replace'), spec)
        return [{'path': spec['filename'], 'url': url, 'expected_sha256': spec.get('expected_sha256'),
                 'expected_size': spec.get('expected_size')}], {
                    'status': 'LANDING_RESOLVED', 'landing_sha256': hashlib.sha256(html_bytes).hexdigest(),
                    'source_page': spec['source_page'], 'url': url}
    if spec['acquisition'] != 'hf':
        raise ValueError('Unknown acquisition method')
    repo = spec['repo_id']
    info = get_json(f'https://huggingface.co/api/datasets/{repo}?blobs=true')
    revision = info.get('sha', '')
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Could not pin full repository revision')
    siblings = {s['rfilename']: s for s in info.get('siblings', [])}
    result = []
    for requested in spec['files']:
        name = requested['path']; safe_relative(name)
        if name not in siblings:
            raise ValueError(f'Required publisher file missing: {name}')
        meta = siblings[name]; lfs = meta.get('lfs') or {}
        publisher_sha = requested.get('expected_sha256') or lfs.get('sha256')
        if requested.get('expected_sha256') and lfs.get('sha256') and requested['expected_sha256'] != lfs['sha256']:
            raise ValueError('Publisher content changed from design hash. Explicit source revision review required.')
        size = requested.get('expected_size') or lfs.get('size') or meta.get('size')
        result.append({'path': name, 'expected_sha256': publisher_sha, 'expected_size': size,
                       'url': f'https://huggingface.co/datasets/{repo}/resolve/{revision}/{quote(name, safe="/")}'})
    return result, {'status': 'REVISION_PINNED', 'repo_id': repo, 'revision': revision}


def download_file(url: str, dest: Path, expected_sha: str | None, expected_size: int | None,
                  max_bytes: int, reserve_bytes: int, meter: ByteMeter | None = None) -> dict[str, Any]:
    no_symlink(dest)
    if max_bytes <= 0: raise ValueError('Invalid file byte ceiling')
    if dest.exists():
        return inspect_file(dest, expected_sha, expected_size) | {'action': 'REUSED'}
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + '.part')
    sidecar = part.with_name(part.name + '.json')
    no_symlink(part); no_symlink(sidecar)
    offset = 0; headers = {}; old = {}
    if part.exists():
        if not sidecar.exists():
            raise ValueError('Orphan partial file: manual review required, not deleted')
        old = json.loads(sidecar.read_text(encoding='utf-8'))
        if old.get('canonical_url') != url or old.get('expected_sha256') != expected_sha:
            raise ValueError('Partial source identity differs; manual review required')
        offset = part.stat().st_size
        if offset and not expected_sha and (not old.get('etag') or old['etag'].startswith('W/')):
            raise ValueError('Cannot safely resume without pinned hash or strong ETag; partial preserved')
        if offset:
            headers['Range'] = f'bytes={offset}-'
            if old.get('etag'):
                headers['If-Range'] = old['etag']
    with open_url(url, headers) as response:
        status = response.getcode()
        if offset and status == 206:
            cr = response.headers.get('Content-Range', '')
            range_end,range_total=validate_range(cr,offset)
            if not expected_sha and response.headers.get('ETag') != old.get('etag'):
                raise ValueError('Resumed source ETag changed')
            mode = 'ab'
        elif status == 200:
            # Server ignored Range/If-Range: safely restart the same .part, never overwrite final.
            offset = 0; mode = 'wb'
        else:
            raise ValueError(f'Unexpected HTTP status {status}')
        if 'text/html' in response.headers.get('Content-Type', '').lower():
            raise ValueError('Publisher returned HTML rather than dataset bytes')
        remaining = response.headers.get('Content-Length')
        total = offset + int(remaining) if remaining else expected_size
        if status == 206:
            if total is not None and total != range_total:
                raise ValueError('Content-Range/Length mismatch')
            total=range_total
        if total is not None and total > max_bytes:
            raise ValueError('Source exceeds configured byte ceiling')
        if expected_size is not None and total is not None and total != expected_size:
            raise ValueError('HTTP length disagrees with pinned publisher metadata')
        free = shutil.disk_usage(dest.parent).free
        expected_remaining = (total-offset) if total is not None else max_bytes-offset
        if free < expected_remaining + reserve_bytes:
            raise ValueError('Insufficient disk space plus reserve')
        # Only canonical source URL is recorded; do not persist signed CDN query strings.
        atomic_json(sidecar, {'canonical_url': url, 'expected_sha256': expected_sha,
                             'etag': response.headers.get('ETag'), 'expected_size': expected_size})
        written = offset; last_disk_check = written
        with part.open(mode) as f:
            while True:
                # At most one extra byte is read to detect an overlong response.
                read_size=min(4*1024*1024, max_bytes-written+1)
                if meter is not None: read_size=min(read_size,meter.limit-meter.used+1)
                if read_size<=0: raise ValueError('Payload quota exhausted')
                block=response.read(read_size)
                if not block: break
                if meter is not None: meter.charge(len(block))
                written += len(block)
                if written > max_bytes:
                    raise ValueError('Download crossed byte ceiling')
                f.write(block)
                if written-last_disk_check >= 256*1024*1024:
                    if shutil.disk_usage(dest.parent).free < reserve_bytes:
                        raise ValueError('Disk reserve breached; partial file retained')
                    last_disk_check = written
            f.flush(); os.fsync(f.fileno())
    if total is not None and written != total:
        raise ValueError('Premature EOF: received size differs from declared complete object')
    inspected = inspect_file(part, expected_sha, expected_size if expected_size is not None else total)
    os.replace(part, dest)
    sidecar.unlink(missing_ok=True)
    inspected['path'] = str(dest.resolve()); inspected['action'] = 'DOWNLOADED'
    return inspected


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', type=Path, default=ROOT/'config/datasets.json')
    ap.add_argument('--profile', choices=['core', 'extended'], default='core')
    ap.add_argument('--only', nargs='*', default=None)
    ap.add_argument('--data-root', type=Path, default=Path.home()/'.local/share/aurora-ads/data')
    ap.add_argument('--cache-overrides', type=Path)
    ap.add_argument('--accept-license', action='append', default=[])
    ap.add_argument('--max-download-gib', type=float, default=5)
    ap.add_argument('--apply', action='store_true', help='Explicitly enable network and downloads')
    args = ap.parse_args()
    if not math.isfinite(args.max_download_gib) or args.max_download_gib<=0:
        ap.error('max-download-gib must be finite and positive')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    selected = [s for s in manifest['datasets'] if args.profile in s['profiles'] and
                (args.only is None or s['id'] in args.only)]
    if not selected:
        ap.error('No matching source')
    if not args.apply:
        print(json.dumps({'mode': 'OFFLINE_PLAN_NO_NETWORK', 'data_root': str(args.data_root),
                          'sources': [{k: s.get(k) for k in ['id','license','source_page','acquisition','approx_download_bytes']}
                                      for s in selected]}, ensure_ascii=False, indent=2))
        return 0
    needed = {s['license'] for s in selected} - set(args.accept_license)
    if needed:
        ap.error('Read source terms, then explicitly acknowledge: ' + ', '.join(sorted(needed)))
    overrides = json.loads(args.cache_overrides.read_text()) if args.cache_overrides else {}
    no_symlink(args.data_root.expanduser())
    root = args.data_root.expanduser().resolve(); root.mkdir(parents=True, exist_ok=True)
    reserve = int(manifest.get('minimum_disk_reserve_gib', 20) * GIB)
    byte_budget = int(args.max_download_gib*GIB); newly_downloaded = 0
    meter=ByteMeter(byte_budget)
    ledger: dict[str, Any] = {'started_at_unix': time.time(), 'status':'RUNNING', 'source_results':[],
                             'license_acknowledgments':args.accept_license,
                             'notice':'Acquisition only; schema/CRC/clock/model qualification is separate.'}
    run_path = root/'manifests'/f'acquisition_{time.time_ns()}.json'
    mutex=root/'.acquisition.lock'
    no_symlink(mutex)
    try:
        fd=os.open(mutex,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:
        ap.error('Another or stale acquisition lock exists; review it, do not auto-delete')
    os.write(fd,str(os.getpid()).encode()); os.close(fd)
    for spec in selected:
        item = {'id': spec['id'], 'source_page':spec['source_page'], 'license':spec['license'], 'files':[]}
        try:
            lock_path = root/'manifests'/(spec['id']+'.source_lock.json')
            spec_hash = hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
            requested = spec.get('files') or ([{'path':spec['filename'], 'expected_sha256':spec.get('expected_sha256'), 'expected_size':spec.get('expected_size')}] if spec.get('filename') else [])
            all_overridden = bool(requested) and all(spec['id']+'/'+f['path'] in overrides for f in requested)
            if all_overridden:
                resolved = [dict(f) for f in requested]
                item['source_identity'] = {'status':'LOCAL_OVERRIDE_NO_NETWORK', 'revision':'UNKNOWN_UNLESS_PRIOR_MANIFEST_PROVIDED'}
            elif lock_path.exists():
                lock = json.loads(lock_path.read_text())
                if lock['spec_hash'] != spec_hash:
                    raise ValueError('Existing source lock is for a different manifest. New namespace/review required.')
                resolved = lock['files']; item['source_identity'] = lock['source_identity']
            else:
                resolved, identity = resolve_sources(spec)
                item['source_identity'] = identity
                if resolved:
                    atomic_json(lock_path, {'spec_hash': spec_hash, 'source_identity': identity, 'files':resolved})
            if not resolved:
                key = spec['id']+'/source'
                if key not in overrides:
                    raise ValueError('BLOCKED_SOURCE: official manual acquisition and explicit local override required')
                item['files'].append(inspect_file(Path(overrides[key]).expanduser(),None,None)|{'action':'MANUAL_LOCAL'})
            per_source_total = 0
            for file in resolved:
                key = spec['id']+'/'+file['path']
                dest = root/'raw'/safe_relative(spec['id'])/safe_relative(file['path'])
                if key in overrides:
                    result = inspect_file(Path(overrides[key]).expanduser(), file.get('expected_sha256'), file.get('expected_size'))|{'action':'LOCAL_OVERRIDE'}
                else:
                    remaining_budget = byte_budget-meter.used
                    remaining_source = spec['max_total_download_bytes']-per_source_total
                    if not dest.exists() and remaining_budget <= 0:
                        raise ValueError('Global new-download budget exhausted')
                    result = download_file(file['url'],dest,file.get('expected_sha256'),file.get('expected_size'),
                                           remaining_source,reserve,meter=meter)
                per_source_total += result['bytes']
                if result['action'] == 'DOWNLOADED':
                    newly_downloaded += result['bytes']
                item['files'].append(result)
            item['status'] = 'ACQUIRED_PENDING_ADMISSION'
        except Exception as exc:
            item['status'] = 'BLOCKED'
            # No credentials or potentially signed request URLs in error ledger.
            item['error_type'] = type(exc).__name__
            item['error'] = 'Acquisition blocked; inspect local condition without persisting request tokens.'
            item['network_bytes_including_failed_attempts']=meter.used
        ledger['source_results'].append(item); atomic_json(run_path,ledger)
    ledger['status'] = 'COMPLETE' if all(x['status']=='ACQUIRED_PENDING_ADMISSION' for x in ledger['source_results']) else 'PARTIAL_OR_BLOCKED'
    ledger['finished_at_unix']=time.time(); ledger['new_download_bytes']=newly_downloaded; ledger['network_payload_bytes']=meter.used
    atomic_json(run_path,ledger)
    mutex.unlink()
    print(json.dumps({'status':ledger['status'],'ledger':str(run_path),'new_download_bytes':newly_downloaded},indent=2))
    return 0 if ledger['status']=='COMPLETE' else 2

if __name__ == '__main__':
    sys.exit(main())
