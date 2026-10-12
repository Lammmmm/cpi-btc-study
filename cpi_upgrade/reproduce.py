#!/usr/bin/env python3
"""Offline one-command rebuild from original raw archives through final statistics/PDFs."""
from pathlib import Path
import argparse,subprocess,sys,json,hashlib

ROOT=Path(__file__).resolve().parent
def run(script,args=(),cwd=None):
    subprocess.run([sys.executable,str(script),*args],cwd=cwd or ROOT,check=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true',help='optional public download of missing original inputs; no paid data purchase');p.add_argument('--skip-original',action='store_true',help='reuse frozen original clean/event files');p.add_argument('--skip-report',action='store_true');p.add_argument('--xlsx',action='store_true',help='also regenerate convenience workbook in an artifact-tool Node environment');a=p.parse_args()
    original=ROOT/'original' if (ROOT/'original').exists() else ROOT.parent/'cpi_study'
    if not a.skip_original:
        args=['--skip-report']+(['--refresh'] if a.refresh else [])
        run(original/'reproduce.py',args,cwd=original)
    for name,args in [('paths_upgrade.py',[]),('trading.py',[]),('groups.py',[]),('trading.py',['--summarize']),('validation_stats.py',[]),('prediction.py',[]),('review_inputs.py',[]),('test_upgrade.py',[]),('output_audit.py',[]),('workbook_payload.py',[])]:run(ROOT/'src'/name,args)
    if not a.skip_report:run(ROOT/'src/reporting.py')
    if a.xlsx:
        import os
        node=os.environ.get('CODEX_PRIMARY_RUNTIME_NODE','node');subprocess.run([node,str(ROOT/'src/build_workbook.mjs'),str(ROOT)],check=True)
    checks={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'results').glob('*.csv')}
    (ROOT/'results/reproduction_checksums.json').write_text(json.dumps(checks,indent=2))
    print('Complete: all statistical CSVs rebuilt; PDF reports unless --skip-report. XLSX snapshots can be independently checked against CSVs.')
if __name__=='__main__':main()
