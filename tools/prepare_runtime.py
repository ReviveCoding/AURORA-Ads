#!/usr/bin/env python3
"""Prepare one WSL-native runtime namespace; no installs, network, training or GPU tests."""
from __future__ import annotations
import argparse, json, os, platform, shutil, tempfile
from pathlib import Path

DIRS=('data','cache','envs','runs','state','tmp','exports')


def atomic_json(path: Path, value: dict) -> None:
    no_symlink(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as f:
        json.dump(value,f,ensure_ascii=False,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        temp=Path(f.name)
    os.replace(temp,path)


def no_symlink(path: Path) -> None:
    for p in [path,*path.parents]:
        if p.is_symlink(): raise ValueError('Symlink components are not accepted for runtime creation')


def prepare(repo: Path, runtime: Path, apply: bool=False) -> dict:
    no_symlink(repo); no_symlink(runtime)
    repo=repo.resolve(strict=True)
    if not (repo/'docs/FINAL_SPEC.md').is_file(): raise ValueError('Not an AURORA v2 repository')
    parent=runtime
    while not parent.exists(): parent=parent.parent
    if shutil.disk_usage(parent).free < 20*1024**3:
        raise ValueError('Runtime filesystem has less than20GiB free reserve')
    marker=runtime/'AURORA_RUNTIME.json'
    no_symlink(marker)
    if runtime.exists() and any(runtime.iterdir()):
        if not marker.is_file(): raise ValueError('Nonempty runtime without AURORA marker; unchanged')
        prior=json.loads(marker.read_text())
        if prior.get('repo_wsl') != str(repo): raise ValueError('Runtime belongs to a different repository')
    result={'status':'PREPARED_NO_ML_ENV' if apply else 'PLAN_ONLY', 'repo_wsl':str(repo),
            'runtime_wsl':str(runtime), 'python':platform.python_version(),
            'data_wsl':str(runtime/'data'),'cache_wsl':str(runtime/'cache'),
            'env_wsl':str(runtime/'envs/core'), 'gpu_qualification':'NOT_RUN',
            'training_started':False, 'local_model_downloads':False}
    if apply:
        runtime.mkdir(parents=True,exist_ok=True)
        for d in DIRS:
            no_symlink(runtime/d); (runtime/d).mkdir(exist_ok=True)
        atomic_json(marker,result)
        no_symlink(repo/'.local'); atomic_json(repo/'.local/runtime.json',result)
    return result


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',type=Path,required=True); ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()
    if platform.system() != 'Linux' or 'microsoft' not in platform.release().lower():
        ap.error('This helper is for WSL2, not native Windows or a generic Linux host.')
    runtime=Path.home()/'.local/share/aurora-ads'
    if str(runtime).startswith('/mnt/'):
        ap.error('Runtime must be WSL native storage, not a mounted Windows volume')
    print(json.dumps(prepare(args.repo,runtime,args.apply),ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
