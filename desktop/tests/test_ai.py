import io,json,os,sys,tempfile,unittest,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import asdict
from core import Settings
from ai_client import validate_proposal,request_reply,AssistantError,contains_key,MODEL
from ai_credentials import save_key,read_key,delete_key

def action(kind,**kwargs):return {'kind':kind,'step':None,'sample':None,'engines':[],'parameters':[],**kwargs}
def proposal(actions):return {'reply':'Proposed changes','actions':actions}

class AssistantTests(unittest.TestCase):
    def test_valid_combined_bounds_and_percent(self):
        changes=[{'name':name,'value':value} for name,value in dict(lower_resistivity=50,upper_resistivity=200,error_floor=.05).items()]
        result=validate_proposal(proposal([action('set_parameters',parameters=changes)]),Settings())
        self.assertEqual(result['settings'].error_floor,.05)
        self.assertEqual(result['settings'].lower_resistivity,50)
    def test_invalid_actions_and_science(self):
        cases=[action('shell'),action('navigate',step='terminal'),action('select_engines',engines=['unknown']),
               action('set_parameters',parameters=[{'name':'regularization','value':-1}]),
               action('set_parameters',parameters=[{'name':'max_iterations','value':2.5}]),
               action('set_parameters',parameters=[{'name':'robust_data','value':'yes'}]),
               action('set_parameters',parameters=[{'name':'error_floor','value':5}]),
               action('set_parameters',parameters=[{'name':'lower_resistivity','value':500}])]
        for item in cases:
            with self.subTest(item=item),self.assertRaises(AssistantError):validate_proposal(proposal([item]),Settings())
    def test_readonly_help_with_invalid_form(self):
        self.assertEqual(validate_proposal(proposal([action('navigate',step='configure')]),Settings(lower_resistivity=500))['patch'],{})
    def test_bounded_responses_request(self):
        output={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(proposal([action('navigate',step='results')]))}]}],
                'usage':{'input_tokens':10,'output_tokens':20,'total_tokens':30}}
        class Opener:
            def open(self,request,timeout):
                body=json.loads(request.data)
                assert body['model']==MODEL and body['store'] is False and timeout==30
                assert body['max_output_tokens']==1600 and body['reasoning']['effort']=='low'
                assert b'sk-test-secret' not in request.data
                assert len(body['input'])<=10
                return io.BytesIO(json.dumps(output).encode())
        result=request_reply('sk-test-secret','Show results',{'settings':asdict(Settings())},[],Opener())
        self.assertEqual(result['usage']['total_tokens'],30)
    def test_error_redaction(self):
        class Opener:
            def open(self,request,timeout):raise urllib.error.HTTPError('url',401,'sk-test-secret',{},io.BytesIO(b'{}'))
        with self.assertRaises(AssistantError) as caught:request_reply('sk-test-secret','Hi',{'settings':asdict(Settings())},[],Opener())
        self.assertNotIn('sk-test-secret',str(caught.exception))
    def test_incomplete_cannot_apply_actions(self):
        class Opener:
            def open(self,request,timeout):return io.BytesIO(b'{"status":"incomplete","output":[]}')
        with self.assertRaises(AssistantError):request_reply('test','Hi',{'settings':asdict(Settings())},[],Opener())
    def test_key_detection(self):self.assertTrue(contains_key('Please use sk-'+('x'*40)))
    @unittest.skipUnless(os.name=='nt','Windows Credential Manager')
    def test_windows_credential_roundtrip(self):
        target='ERTStudio/TestCredential/'+str(os.getpid())
        try:
            save_key('non-secret-test-value',target)
            self.assertEqual(read_key(target),'non-secret-test-value')
        finally:delete_key(target)
        self.assertIsNone(read_key(target))

if __name__=='__main__':unittest.main()
