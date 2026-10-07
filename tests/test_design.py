"""CPU-only checks for the design/helpers. No publisher network, ML models, or CUDA."""
from __future__ import annotations
import hashlib, io, json, shutil, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import acquire_data as a
import contract_reference as c
import prepare_runtime as p
import validate_design as v

class FakeResponse(io.BytesIO):
    def __init__(self,payload,status=200,headers=None):
        super().__init__(payload); self.status=status; self.headers=headers or {}
    def getcode(self): return self.status

class ProbabilityTests(unittest.TestCase):
    def test_conditional_exp_endpoints(self):
        for rate in (1e-9,.1,1000):
            self.assertEqual(c.conditional_exp_cdf(0,rate,7),0)
            self.assertEqual(c.conditional_exp_cdf(7,rate,7),1)
            self.assertEqual(c.conditional_exp_cdf(20,rate,7),1)
    def test_conditional_exp_small_rate_limit(self):
        self.assertAlmostEqual(c.conditional_exp_cdf(3,1e-12,7),3/7,places=10)
    def test_conditional_exp_invalid(self):
        for args in [(-1,1,7),(1,0,7),(1,1,0),(1,float('nan'),7)]:
            with self.assertRaises(ValueError): c.conditional_exp_cdf(*args)
    def test_probability_partition(self):
        masses=[.1,.2,.7];q=.3
        total=sum(c.delayed_probability(q,masses,event_bin=i,completed_bins=3) for i in range(3))
        total+=c.delayed_probability(q,masses,event_bin=None,completed_bins=3)
        self.assertAlmostEqual(total,1)
    def test_pending_is_not_negative(self):
        self.assertAlmostEqual(c.delayed_probability(.4,[.2,.8],event_bin=None,completed_bins=1),.92)
    def test_future_event_rejected(self):
        with self.assertRaises(ValueError): c.delayed_probability(.4,[.2,.8],event_bin=1,completed_bins=1)
    def test_mass_error(self):
        with self.assertRaises(ValueError): c.delayed_probability(.4,[.2,.2],event_bin=None,completed_bins=1)
    def test_probability_pushforward(self):
        self.assertEqual(c.projected_probabilities([.2,.3,.5],[0,0,1],2),[.5,.5])
    def test_all_rejected_mass(self):
        self.assertAlmostEqual(c.projected_probabilities([.2,.3,.5],[0,0,0],2)[0],1)
    def test_invalid_mapping(self):
        with self.assertRaises(ValueError): c.projected_probabilities([1],[3],2)
    def test_dr_hand_example(self):
        self.assertAlmostEqual(c.dr_value([0,1],[1,0],[.5,.5],[[.5,.5]]*2,[[.2,.8]]*2),.5)
    def test_dr_support_zero(self):
        with self.assertRaises(ValueError): c.dr_value([0],[1],[0],[[1]],[[.5]])
    def test_spend_charged_at_zero_scarcity(self):
        self.assertEqual(c.net_score(10,3,0),7)
    def test_net_score_all_costs(self):
        self.assertAlmostEqual(c.net_score(10,3,.2,2,.5,.1),5.3)
    def test_power_formula_margin(self):
        self.assertGreater(c.required_paired_worlds(.04,.01,.02),100)
        with self.assertRaises(ValueError): c.required_paired_worlds(.04,.01,.01)
    def test_power_nonfinite(self):
        with self.assertRaises(ValueError): c.required_paired_worlds(float('nan'),.01,.02)

class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_safe_relative_normal(self): self.assertEqual(a.safe_relative('random/men/all.csv'),Path('random/men/all.csv'))
    def test_bad_portable_paths(self):
        for value in ('','/x','a/../b','a//b','./a','NUL.txt','x/COM1.csv','a.','a ','a:b','a\\b','a?b'):
            with self.subTest(value=value),self.assertRaises(ValueError): a.safe_relative(value)
    def test_https_allowlist(self):
        a.safe_url('https://huggingface.co/datasets/a/b')
        for url in ('http://huggingface.co/a','https://evil.example/a','https://huggingface.co:123/a','https://x:y@huggingface.co/a'):
            with self.assertRaises(ValueError): a.safe_url(url)
    def test_range_geometry(self): self.assertEqual(a.validate_range('bytes 3-5/6',3),(5,6))
    def test_range_invalid(self):
        for header in ('bytes 0-5/6','bytes 3-6/6','bytes 3-5/*','items 3-5/6'):
            with self.assertRaises(ValueError): a.validate_range(header,3)
    def test_quota_failed_read_counted(self):
        m=a.ByteMeter(3);m.charge(2)
        with self.assertRaises(ValueError): m.charge(2)
        self.assertEqual(m.used,4)
    def test_inspect_hash_and_html(self):
        path=self.root/'x';path.write_bytes(b'abc')
        result=a.inspect_file(path,hashlib.sha256(b'abc').hexdigest(),3)
        self.assertEqual(result['checksum_basis'],'publisher_hash_matched')
        path.write_bytes(b'<html>denied</html>')
        with self.assertRaises(ValueError):a.inspect_file(path,None,None)
    def test_full_download_mocked(self):
        dest=self.root/'x';meter=a.ByteMeter(100)
        with patch.object(a,'open_url',return_value=FakeResponse(b'abc',headers={'Content-Length':'3'})):
            result=a.download_file('https://huggingface.co/x',dest,hashlib.sha256(b'abc').hexdigest(),3,100,0,meter)
        self.assertEqual(dest.read_bytes(),b'abc');self.assertEqual(meter.used,3)
        self.assertEqual(result['schema_crc_admission'],'PENDING_NOT_PERFORMED_BY_DOWNLOADER')
    def test_premature_eof_rejected(self):
        dest=self.root/'x'
        with patch.object(a,'open_url',return_value=FakeResponse(b'ab',headers={'Content-Length':'3'})):
            with self.assertRaises(ValueError):a.download_file('https://huggingface.co/x',dest,None,None,100,0)
        self.assertFalse(dest.exists());self.assertTrue((self.root/'x.part').exists())
    def test_resume_with_hash(self):
        dest=self.root/'x';(self.root/'x.part').write_bytes(b'abc')
        digest=hashlib.sha256(b'abcdef').hexdigest()
        (self.root/'x.part.json').write_text(json.dumps({'canonical_url':'https://huggingface.co/x','expected_sha256':digest}))
        with patch.object(a,'open_url',return_value=FakeResponse(b'def',206,{'Content-Length':'3','Content-Range':'bytes 3-5/6'})):
            a.download_file('https://huggingface.co/x',dest,digest,6,100,0)
        self.assertEqual(dest.read_bytes(),b'abcdef')
    def test_resume_wrong_range_refused(self):
        dest=self.root/'x';(self.root/'x.part').write_bytes(b'abc')
        (self.root/'x.part.json').write_text(json.dumps({'canonical_url':'https://huggingface.co/x','expected_sha256':'a'*64}))
        with patch.object(a,'open_url',return_value=FakeResponse(b'def',206,{'Content-Length':'3','Content-Range':'bytes 0-2/6'})):
            with self.assertRaises(ValueError):a.download_file('https://huggingface.co/x',dest,'a'*64,6,100,0)
        self.assertEqual((self.root/'x.part').read_bytes(),b'abc')
    def test_resume_etag_change_refused(self):
        dest=self.root/'x';(self.root/'x.part').write_bytes(b'abc')
        (self.root/'x.part.json').write_text(json.dumps({'canonical_url':'https://huggingface.co/x','expected_sha256':None,'etag':'"old"'}))
        with patch.object(a,'open_url',return_value=FakeResponse(b'def',206,{'Content-Length':'3','Content-Range':'bytes 3-5/6','ETag':'"new"'})):
            with self.assertRaises(ValueError):a.download_file('https://huggingface.co/x',dest,None,6,100,0)
    def test_orphan_partial_preserved(self):
        dest=self.root/'x';(self.root/'x.part').write_bytes(b'abc')
        with self.assertRaises(ValueError):a.download_file('https://huggingface.co/x',dest,None,None,100,0)
        self.assertEqual((self.root/'x.part').read_bytes(),b'abc')
    def test_source_restart_200(self):
        dest=self.root/'x';(self.root/'x.part').write_bytes(b'abc')
        digest=hashlib.sha256(b'abcdef').hexdigest()
        (self.root/'x.part.json').write_text(json.dumps({'canonical_url':'https://huggingface.co/x','expected_sha256':digest}))
        with patch.object(a,'open_url',return_value=FakeResponse(b'abcdef',200,{'Content-Length':'6'})):
            a.download_file('https://huggingface.co/x',dest,digest,6,100,0)
        self.assertEqual(dest.read_bytes(),b'abcdef')
    def test_ambiguous_landing_link(self):
        spec={'source_page':'https://ailab.criteo.com/a','landing_link_host':'go.criteo.net','landing_link_text':'click here'}
        with self.assertRaises(ValueError):a.resolve_landing_html('<a href="https://go.criteo.net/1">click here</a><a href="https://go.criteo.net/2">click here</a>',spec)
    def test_single_landing_link(self):
        spec={'source_page':'https://ailab.criteo.com/a','landing_link_host':'go.criteo.net','landing_link_text':'click here'}
        self.assertEqual(a.resolve_landing_html('<a href="https://go.criteo.net/1">click here</a>',spec),'https://go.criteo.net/1')
    def test_symlink_rejected(self):
        target=self.root/'target';target.write_bytes(b'abc');link=self.root/'link';link.symlink_to(target)
        with self.assertRaises(ValueError):a.inspect_file(link,None,None)
    def test_offline_plan_no_network(self):
        args=['acquire_data.py','--manifest',str(ROOT/'config/datasets.json')]
        with patch.object(sys,'argv',args),patch.object(a,'open_url',side_effect=AssertionError('Network forbidden')),patch('sys.stdout',new_callable=io.StringIO) as out:
            self.assertEqual(a.main(),0)
        self.assertEqual(json.loads(out.getvalue())['mode'],'OFFLINE_PLAN_NO_NETWORK')

class RuntimeAndManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.repo=self.root/'repo';(self.repo/'docs').mkdir(parents=True);(self.repo/'docs/FINAL_SPEC.md').write_text('design')
        self.runtime=self.root/'runtime'
        self.disk=patch.object(p.shutil,'disk_usage',return_value=shutil._ntuple_diskusage(100*1024**3,0,100*1024**3));self.disk.start()
    def tearDown(self):self.disk.stop();self.temp.cleanup()
    def test_runtime_plan_no_write(self):
        result=p.prepare(self.repo,self.runtime,False)
        self.assertEqual(result['status'],'PLAN_ONLY');self.assertFalse(self.runtime.exists())
    def test_runtime_idempotent(self):
        p.prepare(self.repo,self.runtime,True);p.prepare(self.repo,self.runtime,True)
        self.assertTrue((self.runtime/'data').is_dir());self.assertTrue((self.repo/'.local/runtime.json').is_file())
    def test_foreign_runtime_preserved(self):
        self.runtime.mkdir();(self.runtime/'other.txt').write_text('keep')
        with self.assertRaises(ValueError):p.prepare(self.repo,self.runtime,True)
        self.assertEqual((self.runtime/'other.txt').read_text(),'keep')
    def test_runtime_owner_conflict(self):
        self.runtime.mkdir();(self.runtime/'AURORA_RUNTIME.json').write_text(json.dumps({'repo_wsl':'/other'}))
        with self.assertRaises(ValueError):p.prepare(self.repo,self.runtime,True)
    def test_marker_symlink_rejected(self):
        self.runtime.mkdir();target=self.root/'marker';target.write_text(json.dumps({'repo_wsl':str(self.repo)}))
        (self.runtime/'AURORA_RUNTIME.json').symlink_to(target)
        with self.assertRaises(ValueError):p.prepare(self.repo,self.runtime,True)
    def test_low_disk_stops(self):
        with patch.object(p.shutil,'disk_usage',return_value=shutil._ntuple_diskusage(10,5,5)):
            with self.assertRaises(ValueError):p.prepare(self.repo,self.runtime,True)
    def test_design_dag_contracts(self):
        self.assertEqual(v.validate(ROOT,False)['nodes'],27)
    def test_hash_validation_rejects_tamper(self):
        test=self.root/'manifest_repo';shutil.copytree(ROOT/'config',test/'config')
        (test/'x').write_bytes(b'changed')
        (test/'PACKAGE_MANIFEST.json').write_text(json.dumps({'files':[{'path':'x','sha256':'0'*64}]}))
        with self.assertRaises(AssertionError):v.validate(test,True)

if __name__=='__main__':unittest.main()
