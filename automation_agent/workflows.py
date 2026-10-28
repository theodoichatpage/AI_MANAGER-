"""Small explicit workflows used by the dashboard; action names are not screen clicks."""
def workflow(kind,app='chrome',url='https://example.com',hwnd=None):
 def action(name,**kw):return dict(action=name,target_app=app,**({'hwnd':hwnd} if hwnd else {}),**kw)
 open_steps=[action('OPEN_APP'),action('WAIT_WINDOW',timeout=45,retries=1),action('FOCUS_WINDOW')]
 if kind=='chrome_workflow':return open_steps+[action('OPEN_URL',url=url),action('WAIT_PAGE',url=url,timeout=30,retries=1),action('SCREENSHOT')]
 if kind=='capcut_workflow':return open_steps+[action('SCREENSHOT')]
 if kind=='safe_input':return [{'action':'OPEN_TEST_WINDOW'},{'action':'WAIT_WINDOW','target_app':'test','timeout':10},{'action':'FOCUS_WINDOW','target_app':'test'},{'action':'TYPE_TEXT','target_app':'test','selector':{'auto_id':'1001','control_type':'Edit'},'text':'AI MANAGER Automation Test'},{'action':'READ_ELEMENT','target_app':'test','selector':{'auto_id':'1001','control_type':'Edit'}},{'action':'SCREENSHOT','target_app':'test'}]
 if kind=='open':return open_steps
 if kind=='focus':return [action('FIND_WINDOW'),action('FOCUS_WINDOW')]
 if kind=='screenshot':return [action('FIND_WINDOW'),action('FOCUS_WINDOW'),action('SCREENSHOT')]
 if kind=='elements':return [action('FIND_WINDOW'),action('FIND_ELEMENT',selector={'control_type':'Edit'})]
 if kind=='find':return [action('LIST_WINDOWS')]
 if kind=='processes':return [{'action':'LIST_PROCESSES'}]
 if kind=='windows':return [{'action':'LIST_WINDOWS'}]
 if kind=='check':return [action('CHECK_PROCESS')]
 raise ValueError('Workflow test không hợp lệ')
