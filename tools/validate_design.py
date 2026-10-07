#!/usr/bin/env python3
"""Validate machine-readable design and archive manifests; no ML execution."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).resolve().parents[1]


def validate(root: Path, check_hashes: bool=True) -> dict:
    c=json.loads((root/'config/contract.json').read_text(encoding='utf-8'))
    assert c['application_agents']==1 and c['tot_enabled'] is False and c['multi_agent_enabled'] is False
    assert c['live_ads_writes'] is False and c['heavy_gpu_jobs']==1
    assert c['repo_windows']==r'C:\Users\bjw-0\Downloads\AURORA-Ads'
    assert c['primary_r3']['model_snapshot_day']==41 and c['primary_r3']['refit_at_freeze'] is False
    assert c['policy']['pseudo_reward_updates_primary'] is False
    assert c['policy']['decision_days']>c['policy']['maturation_flush_days']
    assert c['policy']['practical_margin_normalized']==0.01
    dag=json.loads((root/'config/experiments.json').read_text(encoding='utf-8'))['nodes']
    ids=[n['id'] for n in dag]; assert len(ids)==len(set(ids))
    seen=set()
    for n in dag:
        assert set(n['requires']).issubset(seen), (n['id'],'not topologically sorted')
        assert n['status']=='PLANNED'; seen.add(n['id'])
    byid={n['id']:n for n in dag}
    def ancestors(i):
        return {j for p in byid[i]['requires'] for j in ({p}|ancestors(p))}
    assert 'E06' not in ancestors('E15_POLICY') and 'E11' not in ancestors('E15_AGENT')
    assert 'E10' not in ancestors('E15_POLICY') and 'E09' not in ancestors('E15_AGENT')
    assert 'E10' not in ancestors('E15_R3') and 'E03' not in ancestors('E15_R1')
    assert byid['E16']['trigger']=='all_declared_tracks_terminal'
    checked=0
    if check_hashes:
        manifest=json.loads((root/'PACKAGE_MANIFEST.json').read_text())
        for entry in manifest['files']:
            rel=PurePosixPath(entry['path'])
            assert not rel.is_absolute() and '..' not in rel.parts
            p=root.joinpath(*rel.parts)
            assert p.is_file() and not p.is_symlink(),str(p)
            assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],str(p)
            checked+=1
    return {'status':'DESIGN_CONTRACTS_VALID','nodes':len(dag),'hashed_files':checked,
            'ml_training_tested':False,'data_payloads_validated':False}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--no-hashes',action='store_true');a.add_argument('--root',type=Path,default=ROOT)
    ns=a.parse_args();print(json.dumps(validate(ns.root,not ns.no_hashes),indent=2))
