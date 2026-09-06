from pathlib import Path
import argparse
import tempfile
from ai_testing_framework.core.models import Step, TestCase, Validation
from ai_testing_framework.core.test_runner import _run_test_isolated

parser=argparse.ArgumentParser(); parser.add_argument('--browser',default='chromium'); args=parser.parse_args()
root=Path(tempfile.mkdtemp(prefix='phase-c-artifacts-'))
test=TestCase(id='C-ART',name='Intentional failure artifact check',url='/',steps=[Step(action='wait',selector='body')],validations=[Validation(type='element_present',selector='#this-element-does-not-exist')])
config={"browser_name":args.browser,"headless":True,"timeout":5000,"ai_provider":"none","ai_model":"gpt-4o-mini","base_url":"http://127.0.0.1:8000","report_dir":str(root),"analyze_failures":False,"self_healing":False,"record_trace":True,"record_video":True}
result=_run_test_isolated(test,config)
assert result.status=='FAIL', result
assert result.trace and Path(result.trace).is_file(), result.trace
assert result.video and Path(result.video).is_file(), result.video
print(f"browser={args.browser}")
print(f"trace={result.trace}")
print(f"video={result.video}")
