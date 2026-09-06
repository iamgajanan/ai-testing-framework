from __future__ import annotations
import argparse, json, os, sys
from .core.test_runner import TestRunner

def build_parser():
    parser=argparse.ArgumentParser(description='Universal AI-powered web test runner'); sub=parser.add_subparsers(dest='command')
    run_p=sub.add_parser('run',help='Run a test suite'); _add_run_args(run_p)
    gen_p=sub.add_parser('generate',help='Generate a test suite from a live URL'); gen_p.add_argument('--url',required=True); gen_p.add_argument('--output',default='tests/generated_suite.json'); gen_p.add_argument('--browser',default='chromium',choices=['chromium','firefox','webkit']); gen_p.add_argument('--base-url',default=''); gen_p.add_argument('--max-pages',type=int,default=1); gen_p.add_argument('--ai-provider',choices=['openai','none'],default='none'); gen_p.add_argument('--config',default=None); gen_p.add_argument('--login-json',default=None,help='JSON file describing login for authenticated crawling')
    plan_p=sub.add_parser('plan',help='Plan browser workflows from an app description'); plan_p.add_argument('--description',required=True); plan_p.add_argument('--workflow',action='append',default=[]); plan_p.add_argument('--output',default='reports/plan.json'); plan_p.add_argument('--ai-provider',choices=['openai','none'],default='none'); plan_p.add_argument('--ai-model',default='gpt-4o-mini')
    data_p=sub.add_parser('data',help='Generate realistic deterministic or AI test data'); data_p.add_argument('--fields',required=True,help='JSON array of field descriptors'); data_p.add_argument('--count',type=int,default=1); data_p.add_argument('--output',default='reports/test_data.json'); data_p.add_argument('--ai-provider',choices=['openai','none'],default='none'); data_p.add_argument('--ai-model',default='gpt-4o-mini')
    _add_run_args(parser); return parser

def _add_run_args(p):
    p.add_argument('--file',default=None); p.add_argument('--browser',default='chromium',choices=['chromium','firefox','webkit']); p.add_argument('--test',dest='test_id',default=None); p.add_argument('--base-url',default=''); p.add_argument('--output',default='reports'); p.add_argument('--config',default=None); p.add_argument('--ai-provider',choices=['openai','none'],default=None); p.add_argument('--workers',type=int,default=None); p.add_argument('--format',dest='formats',nargs='+',choices=['html','json','pdf','all'],default=None)

def _write_github_summary(results,output_dir,workers=1):
    path=os.environ.get('GITHUB_STEP_SUMMARY')
    if not path:return
    total=len(results); passed=sum(r.status=='PASS' for r in results); failed=total-passed; dur=sum(r.duration for r in results); rate=passed/total*100 if total else 0; lines=['## 🤖 AI Test Report','',f'| Total | Passed | Failed | Pass Rate | Duration | Mode |','|---|---|---|---|---|---|',f'| {total} | {passed} | {failed} | {rate:.1f}% | {dur:.1f}s | {workers} workers |']
    for r in results: lines.append(f'| `{r.id}` | {r.name} | {r.status} | {r.duration:.2f}s | | |')
    try: open(path,'a',encoding='utf-8').write('\n'.join(lines)+'\n')
    except OSError: pass

def _cmd_run(args):
    if not args.file: print('ERROR: --file is required for the run command.',file=sys.stderr); return 2
    formats=['html','json','pdf'] if args.formats and 'all' in args.formats else args.formats; runner=TestRunner(config=args.config,base_url=args.base_url)
    if args.ai_provider:runner.set_ai_provider(args.ai_provider)
    try: results=runner.run(args.file,browser=args.browser,test_id=args.test_id,output_dir=args.output,formats=formats,workers=args.workers)
    except Exception as exc: print(f'ERROR: {exc}',file=sys.stderr); return 2
    passed=sum(r.status=='PASS' for r in results); failed=len(results)-passed; print(f'Tests: {len(results)} | Passed: {passed} | Failed: {failed}'); print(f'HTML report: {args.output}/test_report.html'); _write_github_summary(results,args.output,args.workers or 1); return 0 if failed==0 else 1

def _cmd_generate(args):
    from .ai.test_generator import TestGenerator
    generator=TestGenerator(args.ai_provider or 'none'); print(f'Discovering up to {args.max_pages} page(s) from {args.url} ...')
    try:
        if args.login_json:
            login=json.loads(open(args.login_json,encoding='utf-8').read()); path=generator.generate_authenticated(args.url,args.output,login,browser=args.browser,base_url=args.base_url,max_pages=args.max_pages)
        else:path=generator.generate(args.url,args.output,browser=args.browser,base_url=args.base_url,max_pages=args.max_pages)
    except Exception as exc: print(f'ERROR: {exc}',file=sys.stderr); return 2
    print(f'✅ Generated test suite written to: {path}'); return 0

def _cmd_plan(args):
    from .ai.agentic import AgenticAI
    result=AgenticAI(args.ai_provider,args.ai_model).plan(args.description,args.workflow); out=args.output; os.makedirs(os.path.dirname(out) or '.',exist_ok=True); json.dump(result,open(out,'w',encoding='utf-8'),indent=2); print(out); return 0

def _cmd_data(args):
    from .ai.agentic import AgenticAI
    fields=json.loads(args.fields); result=AgenticAI(args.ai_provider,args.ai_model).generate_data(fields,args.count); out=args.output; os.makedirs(os.path.dirname(out) or '.',exist_ok=True); json.dump({'data':result},open(out,'w',encoding='utf-8'),indent=2); print(out); return 0

def main():
    args=build_parser().parse_args()
    if args.command=='generate':return _cmd_generate(args)
    if args.command=='plan':return _cmd_plan(args)
    if args.command=='data':return _cmd_data(args)
    return _cmd_run(args)

if __name__=='__main__': raise SystemExit(main())
