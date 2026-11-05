"""Windows refuses to replace a file another program has open at that moment (a reader, an antivirus scan): "Access is denied".
That is a passing state, so replacing a file waits and tries again instead of failing the whole task."""
import os,time

def replace_retry(tmp,path,tries=40,sleep=time.sleep):
 for attempt in range(tries):
  try:os.replace(tmp,path);return
  except PermissionError:
   if attempt==tries-1:raise
   sleep(0.05+attempt*0.02)
