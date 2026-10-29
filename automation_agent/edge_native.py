"""Read per-HWND Windows Shell properties; no browser DOM or credential access."""
import ntpath

def flag_values(args,key):
 out=[]
 for i,arg in enumerate(args):
  if arg==key and i+1<len(args):out.append(args[i+1])
  elif arg.startswith(key+'='):out.append(arg[len(key)+1:])
 return out

def canon(path):return ntpath.normcase(ntpath.normpath(str(path).strip().strip('"')))

def profile_from_properties(properties,command_args,process_args,root,profile):
 args=list(command_args);process=list(process_args)
 if any(a.lower() in ('--inprivate','--guest','--incognito') for a in args+process):return False
 if args and ntpath.basename(args[0]).lower()!='msedge.exe':return False
 for source in (args,process):
  dirs=flag_values(source,'--user-data-dir')
  if len(dirs)>1 or (dirs and canon(dirs[0])!=canon(root)):return False
 profiles=flag_values(args,'--profile-directory')
 if len(profiles)>1 or (profiles and profiles[0]!=profile):return False
 icon=str(properties.get('icon') or '').rsplit(',',1)[0].strip().strip('"')
 icon_matches=bool(icon) and ntpath.splitext(icon)[1].lower()=='.ico' and canon(ntpath.dirname(icon))==canon(ntpath.join(str(root),profile))
 return icon_matches or profiles==[profile]

def command_args(command):
 if not command:return []
 import ctypes
 from ctypes import wintypes
 shell=ctypes.WinDLL('shell32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 shell.CommandLineToArgvW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_int)]
 shell.CommandLineToArgvW.restype=ctypes.POINTER(wintypes.LPWSTR)
 kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
 count=ctypes.c_int();ptr=shell.CommandLineToArgvW(command,ctypes.byref(count))
 if not ptr:raise OSError('CommandLineToArgvW failed')
 try:return [ptr[i] for i in range(count.value)]
 finally:kernel.LocalFree(ctypes.cast(ptr,ctypes.c_void_p))

def window_profile_report(window,profile):
 from .edge_profiles import user_data_root,require_profile
 report={'hwnd':window['hwnd'],'pid':window['pid'],'profile':profile,'verified':False,'method':'Windows Shell properties'}
 try:
  require_profile(profile)
  import pythoncom,psutil,winreg,os
  from win32com.propsys import propsys,pscon
  root=user_data_root()
  # Reject unsupported enterprise profile roots rather than binding a same-name profile.
  for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
   try:
    with winreg.OpenKey(hive,r'SOFTWARE\Policies\Microsoft\Edge') as k:policy=winreg.QueryValueEx(k,'UserDataDir')[0]
   except OSError:continue
   if canon(os.path.expandvars(str(policy)))!=canon(root):report['unsupported_policy_root']=True;return report
  pythoncom.CoInitialize()
  try:
   store=propsys.SHGetPropertyStoreForWindow(window['hwnd'])
   def value(key):
    v=store.GetValue(key)
    return v.GetValue() if hasattr(v,'GetValue') else v
   props={'icon':value(pscon.PKEY_AppUserModel_RelaunchIconResource),'command':value(pscon.PKEY_AppUserModel_RelaunchCommand)}
   report['icon_present']=bool(props['icon']);report['command_present']=bool(props['command'])
   report['verified']=profile_from_properties(props,command_args(props['command']),psutil.Process(window['pid']).cmdline(),root,profile)
  finally:pythoncom.CoUninitialize()
 except Exception as exc:report['native_error']=type(exc).__name__
 return report
