import hashlib,json,os,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine_packs import install_pack,engine_path

class EnginePackTests(unittest.TestCase):
    def archive(self,path,files,hashes=None):
        platform='windows-x64' if os.name=='nt' else 'linux-x64'
        manifest=dict(engine='simpeg',protocol=1,platform=platform,
                      files=hashes or {k:hashlib.sha256(v).hexdigest() for k,v in files.items()})
        with zipfile.ZipFile(path,'w') as zipped:
            zipped.writestr('engine.json',json.dumps(manifest))
            for k,v in files.items():zipped.writestr(k,v)
    def test_install_and_integrity(self):
        with tempfile.TemporaryDirectory() as folder,patch('engine_packs.configure_runtime',return_value=Path(folder)):
            archive=Path(folder)/'pack.zip';exe='ERTEngine.exe' if os.name=='nt' else 'ERTEngine'
            self.archive(archive,{exe:b'test worker'})
            self.assertEqual(install_pack(archive),'simpeg');self.assertTrue(engine_path('simpeg').is_file())
            self.archive(archive,{exe:b'corrupted'},hashes={exe:'0'*64})
            with self.assertRaises(ValueError):install_pack(archive)
            self.assertEqual(engine_path('simpeg').read_bytes(),b'test worker')
    def test_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as folder,patch('engine_packs.configure_runtime',return_value=Path(folder)):
            archive=Path(folder)/'pack.zip'
            for name in ['../outside','/absolute','C:/outside','dir\\outside']:
                self.archive(archive,{name:b'unsafe'})
                with self.subTest(name=name),self.assertRaises(ValueError):install_pack(archive)

if __name__=='__main__':unittest.main()
