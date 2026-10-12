"""Package reproducible scientific inputs and outputs; omit nonessential page prose."""
from net import ROOT,shipped_input
from pathlib import Path
import zipfile,shutil,json,hashlib

def main():
 out=ROOT.parent/'deliverables';out.mkdir(exist_ok=True)
 shutil.copyfile(ROOT/'results/table_G_events.csv',out/'cpi_events.csv')
 with zipfile.ZipFile(out/'summary_tables.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted((ROOT/'results').glob('*')):
   if p.suffix in ['.csv','.json']:z.write(p,'results/'+p.name)
 with zipfile.ZipFile(out/'cpi_btc_reproducible.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted(ROOT.rglob('*')):
   if not p.is_file() or '__pycache__' in str(p) or p.name.endswith('.part'):continue
   rel=p.relative_to(ROOT)
   if rel.parts[0] in ['raw','data','fonts'] and not shipped_input(p):continue
   z.write(p,'cpi_study/'+str(rel))
 with zipfile.ZipFile(out/'cpi_btc_reproducible.zip') as z:
  names=z.namelist();assert sum(n.startswith('cpi_study/raw/btc/') and n.endswith('.zip') for n in names)==184
  assert sum(n.startswith('cpi_study/raw/bls/') for n in names)==92
  assert sum(n.startswith('cpi_study/raw/vintages/') for n in names)==368
  assert sum(n.startswith('cpi_study/raw/coinbase/') for n in names)==92
  assert sum(n.startswith('cpi_study/data/investing_') and n.endswith('.json') for n in names)==6
  assert not any(n.startswith(('cpi_study/raw/fees/','cpi_study/raw/commercial/','cpi_study/data/fees/')) for n in names)
  assert z.testzip() is None
 rows=[{'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(out.glob('*')) if p.is_file() and p.name!='deliverable_checksums.json']
 (out/'deliverable_checksums.json').write_text(json.dumps(rows,indent=2));print(rows)
if __name__=='__main__':main()
