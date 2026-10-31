"""Install AI Manager as a desktop app: icon, Desktop + Start menu shortcuts, start with Windows (in the background).
Safe to run again; it only (re)writes its own three shortcuts. `python install_app.py --remove` takes them away."""
import os,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
RUNTIME=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'AI_MANAGER'/'runtime-v02'/'Scripts'
ICON=ROOT/'assets'/'ai_manager.ico'
APPDATA=Path(os.environ.get('APPDATA',str(Path.home())))
PLACES={
 'desktop':(Path(os.environ.get('USERPROFILE',str(Path.home())))/'Desktop'/'AI Manager.lnk',''),
 'start':(APPDATA/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'AI Manager.lnk',''),
 'startup':(APPDATA/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'Startup'/'AI Manager (chay ngam).lnk','--background'),
}

def make_icon():
 if ICON.exists():return
 from PIL import Image,ImageDraw,ImageFont
 ICON.parent.mkdir(exist_ok=True);size=256
 img=Image.new('RGBA',(size,size),(0,0,0,0));d=ImageDraw.Draw(img)
 d.rounded_rectangle((8,8,size-8,size-8),radius=56,fill=(203,251,50,255))
 try:font=ImageFont.truetype('segoeuib.ttf',118)
 except OSError:font=ImageFont.load_default()
 box=d.textbbox((0,0),'AI',font=font);d.text(((size-box[2]-box[0])/2,(size-box[3]-box[1])/2-box[1]),'AI',font=font,fill=(11,11,12,255))
 img.save(ICON,sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])

def shortcut(path,args):
 pythonw=RUNTIME/'pythonw.exe'
 if not pythonw.exists():pythonw=Path(sys.executable).with_name('pythonw.exe')
 path.parent.mkdir(parents=True,exist_ok=True)
 q=lambda s:str(s).replace("'","''")
 script=("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');$s.TargetPath='%s';$s.Arguments='\"%s\" %s';"
         "$s.WorkingDirectory='%s';$s.IconLocation='%s';$s.Description='AI Manager';$s.Save()")%(q(path),q(pythonw),q(ROOT/'app_launcher.pyw'),args,q(ROOT),q(ICON))
 # -EncodedCommand (UTF-16) keeps Vietnamese names and paths intact.
 import base64
 r=subprocess.run(['powershell','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode()],capture_output=True,text=True,creationflags=0x08000000)
 if r.returncode:raise ValueError('Không tạo được lối tắt '+path.name+': '+(r.stderr or r.stdout).strip()[:200])

def installed():return {k:v[0].exists() for k,v in PLACES.items()}

def install():
 make_icon()
 for path,args in PLACES.values():shortcut(path,args)
 return installed()

def remove():
 for path,_ in PLACES.values():
  if path.exists():path.unlink()
 return installed()

if __name__=='__main__':print(remove() if '--remove' in sys.argv else install())
