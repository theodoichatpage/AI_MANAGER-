"""Native isolated Windows input surface, not an existing application document."""
def main():
 import win32api,win32con,win32gui
 instance=win32api.GetModuleHandle(None)
 wc=win32gui.WNDCLASS();wc.hInstance=instance;wc.lpszClassName='AIManagerAutomationTest';wc.lpfnWndProc={win32con.WM_DESTROY:lambda *args:win32gui.PostQuitMessage(0)};wc.hbrBackground=win32con.COLOR_WINDOW+1
 atom=win32gui.RegisterClass(wc)
 hwnd=win32gui.CreateWindow(atom,'AI MANAGER Automation Test',win32con.WS_OVERLAPPEDWINDOW,100,100,650,280,0,0,instance,None)
 win32gui.CreateWindowEx(win32con.WS_EX_CLIENTEDGE,'EDIT','',win32con.WS_CHILD|win32con.WS_VISIBLE|win32con.WS_TABSTOP|win32con.ES_MULTILINE,20,30,590,120,hwnd,1001,instance,None)
 win32gui.CreateWindow('STATIC','Safe test field — automation only types here.',win32con.WS_CHILD|win32con.WS_VISIBLE,20,170,590,30,hwnd,1002,instance,None)
 win32gui.ShowWindow(hwnd,win32con.SW_SHOW);win32gui.UpdateWindow(hwnd);win32gui.PumpMessages()
if __name__=='__main__':main()
