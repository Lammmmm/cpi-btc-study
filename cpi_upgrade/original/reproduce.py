"""One command, frozen-data offline reproduction by default. No credentials required."""
import argparse,subprocess,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def script(name):
 print('RUN',name,flush=True)
 subprocess.run([sys.executable,str(ROOT/'src'/name)],cwd=ROOT,check=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--refresh',action='store_true',help='Fetch missing original inputs over internet; cached originals stay frozen.');ap.add_argument('--skip-report',action='store_true');a=ap.parse_args()
 if a.refresh:
  script('acquire.py');script('acquire_growth.py')
 for s in ['clean.py','growth.py','backtest.py','summarize.py']:
  script(s)
 # Verify frozen Coinbase responses, not refetch them in offline mode.
 if a.refresh:script('crossvenue.py')
 else:
  sys.path.insert(0,str(ROOT/'src'));from crossvenue import verify;verify()
 for s in ['additional.py','validate.py','enhancements.py','audit.py']:
  script(s)
 if not a.skip_report:script('make_report.py')
 print('PASS: all auditable outputs in results/; report.md and report.pdf generated unless --skip-report.')
if __name__=='__main__':main()
