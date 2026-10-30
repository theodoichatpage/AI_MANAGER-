"""The fixed extension folder follows the latest release; bad ZIPs never touch it."""
import io,json,tempfile,unittest,zipfile
from pathlib import Path
import extension_updater as eu

def release_zip(version,extra=None,top=None):
 buf=io.BytesIO();top=top or 'VIDEO_IMAGE_STUDIO_ChatGPT_Extension_v'+version+'/'
 with zipfile.ZipFile(buf,'w') as z:
  z.writestr(top+'manifest.json',json.dumps({'version':version,'background':{}}));z.writestr(top+'background.js','// '+version)
  for k,v in (extra or {}).items():z.writestr(k,v)
 return buf.getvalue()

class Updater(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.target=Path(self.tmp.name)/'ext'
 def tearDown(self):self.tmp.cleanup()
 def fetcher(self,version,zipdata):
  def fetch(url,limit):
   if url.endswith('extensionRelease.ts'):return ('export const EXTENSION_VERSION = "%s";\nexport const EXTENSION_DOWNLOAD_URL = "/resources/VIDEO_IMAGE_STUDIO_ChatGPT_Extension_v%s.zip";'%(version,version)).encode()
   return zipdata
  return fetch
 def test_installs_then_updates_and_removes_stale_files(self):
  u=eu.ExtensionUpdater(self.target,extra=lambda:[],fetch=self.fetcher('0.5.3',release_zip('0.5.3',{'VIDEO_IMAGE_STUDIO_ChatGPT_Extension_v0.5.3/old.js':'x'})))
  self.assertEqual(u.check()['installed'],'0.5.3');self.assertTrue((self.target/'old.js').exists())
  u.fetch=self.fetcher('0.5.4',release_zip('0.5.4'))
  s=u.check();self.assertEqual(s['installed'],'0.5.4');self.assertIsNone(s['error']);self.assertFalse((self.target/'old.js').exists())
 def test_bad_zip_is_refused_and_folder_untouched(self):
  u=eu.ExtensionUpdater(self.target,extra=lambda:[],fetch=self.fetcher('0.5.3',release_zip('0.5.3')));u.check()
  u.fetch=self.fetcher('0.5.4',release_zip('0.5.4',{'../evil.js':'x'}))
  s=u.check();self.assertIn('ngoài thư mục',s['error']);self.assertEqual(s['installed'],'0.5.3')
  u.fetch=self.fetcher('0.5.4',release_zip('0.5.5'))
  self.assertTrue(u.check()['error']);self.assertEqual(eu.installed(self.target),'0.5.3')
class Folders(unittest.TestCase):
 def test_updates_the_folders_edge_loads_but_nothing_else(self):
  tmp=tempfile.TemporaryDirectory();root=Path(tmp.name)
  ours=root/'Downloads'/'bridge_v0.5.4';ours.mkdir(parents=True);(ours/'manifest.json').write_text(json.dumps({'name':eu.BRIDGE_NAME,'version':'0.5.4'}))
  other=root/'Downloads'/'other';other.mkdir(parents=True);(other/'manifest.json').write_text(json.dumps({'name':'Some other','version':'1.0.0'}))
  prof=root/'Edge'/'Profile 1';prof.mkdir(parents=True)
  (prof/'Secure Preferences').write_text(json.dumps({'extensions':{'settings':{'a':{'path':str(ours)},'b':{'path':str(other)},'c':{'path':'relative'}}}}))
  self.assertEqual(eu.edge_install_folders(root/'Edge'),[ours])
  def fetch(url,limit):
   if url.endswith('extensionRelease.ts'):return b'export const EXTENSION_VERSION = "0.5.8";\nexport const EXTENSION_DOWNLOAD_URL = "/resources/VIDEO_IMAGE_STUDIO_ChatGPT_Extension_v0.5.8.zip";'
   return release_zip('0.5.8')
  u=eu.ExtensionUpdater(root/'managed',fetch=fetch,extra=lambda:eu.edge_install_folders(root/'Edge'))
  s=u.check();self.assertIsNone(s['error']);self.assertEqual(eu.installed(ours),'0.5.8');self.assertEqual(eu.installed(root/'managed'),'0.5.8')
  self.assertEqual(json.loads((other/'manifest.json').read_text())['version'],'1.0.0','other extensions untouched')
  tmp.cleanup()
if __name__=='__main__':unittest.main()
