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
  u=eu.ExtensionUpdater(self.target,self.fetcher('0.5.3',release_zip('0.5.3',{'VIDEO_IMAGE_STUDIO_ChatGPT_Extension_v0.5.3/old.js':'x'})))
  self.assertEqual(u.check()['installed'],'0.5.3');self.assertTrue((self.target/'old.js').exists())
  u.fetch=self.fetcher('0.5.4',release_zip('0.5.4'))
  s=u.check();self.assertEqual(s['installed'],'0.5.4');self.assertIsNone(s['error']);self.assertFalse((self.target/'old.js').exists())
 def test_bad_zip_is_refused_and_folder_untouched(self):
  u=eu.ExtensionUpdater(self.target,self.fetcher('0.5.3',release_zip('0.5.3')));u.check()
  u.fetch=self.fetcher('0.5.4',release_zip('0.5.4',{'../evil.js':'x'}))
  s=u.check();self.assertIn('ngoài thư mục',s['error']);self.assertEqual(s['installed'],'0.5.3')
  u.fetch=self.fetcher('0.5.4',release_zip('0.5.5'))
  self.assertTrue(u.check()['error']);self.assertEqual(eu.installed(self.target),'0.5.3')
if __name__=='__main__':unittest.main()
