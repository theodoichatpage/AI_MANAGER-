"""One-click setup; dependencies installed once in a private local venv."""
import os,subprocess,sys,venv
from pathlib import Path

def main():
 if sys.platform!='win32':raise SystemExit('This Windows package requires Windows 10/11.')
 if sys.version_info<(3,10):raise SystemExit('Python 3.10+ is required. Install Python, then open MO_AI_MANAGER.bat again.')
 base=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'AI_MANAGER/runtime-v02';python=base/'Scripts/python.exe'
 root=Path(__file__).resolve().parent.parent
 if not python.exists():
  print('Setting up AI MANAGER runtime (first launch only)...',flush=True);venv.EnvBuilder(with_pip=True).create(base)
 probe=subprocess.run([str(python),'-c','import psutil,pywinauto,PIL,win32gui,win32job'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 if probe.returncode:
  print('Installing free Windows automation libraries. Internet is required on first launch.',flush=True)
  subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','-r',str(root/'requirements-windows.txt')],check=True)
 report_home=Path(os.environ.get('AI_MANAGER_HOME',str(Path.home()/'.ai_manager')))/'automation'
 report_home.mkdir(parents=True,exist_ok=True)
 with (report_home/'windows_api_contract.json').open('w',encoding='utf8') as report:
  check=subprocess.run([str(python),'-m','automation_agent.windows_api_contract'],cwd=str(root),stdout=report,stderr=subprocess.STDOUT)
 if check.returncode:print('Windows API contract FAIL. See Windows Agent diagnostics; unsupported APIs are not treated as PASS.',flush=True)
 # Desktop app: icon + Start menu + start with Windows, then Manager runs in the background in its own window.
 subprocess.run([str(python),str(root/'install_app.py')],cwd=str(root))
 return subprocess.call([str(base/'Scripts/pythonw.exe'),str(root/'app_launcher.pyw')],cwd=str(root))
if __name__=='__main__':
 try:raise SystemExit(main())
 except subprocess.CalledProcessError:raise SystemExit('Setup failed. Check Internet access and reopen MO_AI_MANAGER.bat. See the error above.')
