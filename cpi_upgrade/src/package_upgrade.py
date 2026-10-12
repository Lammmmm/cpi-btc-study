"""Freeze all authorized project inputs/code/tables; no session metadata or private helpers."""
from common import *
import sys,zipfile,shutil
sys.path.append(str(ORIGINAL/'src'))
from net import shipped_input

def main():
    DEL.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'README.md',DEL/'CPI_回测复现_README.md')
    original=pd.read_csv(OUT/'original_source_manifest.csv');original.insert(0,'source_category','original frozen raw/derived input');original['file']='original/'+original['file'].astype(str)
    current=pd.read_csv(OUT/'provided_input_manifest.csv');current=current.rename(columns={'materialized_date':'read_on_date'});current['file']='inputs/'+current['file'].astype(str);current['source_category']='user provided research material'
    manifest=pd.concat([original,current],ignore_index=True);save(manifest,'source_manifest_combined.csv');shutil.copyfile(OUT/'source_manifest_combined.csv',DEL/'CPI_数据来源与完整性审计.csv')
    outputs=['CPI_BTC_Final_Report.md','CPI_BTC_Final_Report.pdf','CPI_4指标完整事件数据库.csv','CPI_总体核心交叉矩阵.xlsx','CPI_暴热暴冷专项研究.csv','CPI_第一波与反杀策略回测.csv','CPI_交易规律速查表.pdf','CPI_回测复现_README.md','CPI_数据来源与完整性审计.csv']
    jdump([{'file':name,'bytes':(DEL/name).stat().st_size,'sha256':hashlib.sha256((DEL/name).read_bytes()).hexdigest()} for name in outputs],OUT/'output_content_checksums.json')
    zpath=DEL/'CPI_BTC_完整代码数据与测试.zip'
    inputs=ROOT/'inputs' if (ROOT/'inputs').exists() else ROOT.parent/'cpi_upgrade_inputs'
    with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(ROOT.rglob('*')):
            if not p.is_file() or '__pycache__' in str(p):continue
            rel=p.relative_to(ROOT)
            if rel.parts[0] not in ['src','results','figures'] and p.name not in ['README.md','requirements.txt','SPECIFICATION.md','reproduce.py']:continue
            if rel.parts[0]=='results' and (p.name in ['workbook_payload.json','deliverable_checksums.json'] or p.suffix not in ['.csv','.json','.txt']):continue
            z.write(p,'cpi_upgrade/'+str(rel))
        for name in outputs:z.write(DEL/name,'cpi_upgrade/deliverables/'+name)
        for p in sorted(ORIGINAL.rglob('*')):
            if not p.is_file() or '__pycache__' in str(p) or p.name.endswith('.part'):continue
            rel=p.relative_to(ORIGINAL)
            if rel.parts[0] in ['raw','data','fonts'] and not shipped_input(p):continue
            if rel.parts[0] not in ['raw','data','fonts','src','results','input_schema'] and p.name not in ['README.md','requirements.txt','SPECIFICATION.md','reproduce.py']:continue
            z.write(p,'cpi_upgrade/original/'+str(rel))
        for p in sorted(inputs.iterdir()):
            if p.suffix in ['.md','.pdf','.csv','.py']:z.write(p,'cpi_upgrade/inputs/'+p.name)
    with zipfile.ZipFile(zpath) as z:
        names=z.namelist();assert sum(n.startswith('cpi_upgrade/original/raw/btc/') and n.endswith('.zip') for n in names)==184
        assert sum(n.startswith('cpi_upgrade/original/raw/bls/') for n in names)==92
        assert sum(n.startswith('cpi_upgrade/original/raw/vintages/') for n in names)==368
        assert sum(n.startswith('cpi_upgrade/original/data/btc_') and n.endswith('.csv.gz') for n in names)==92
        assert sum(n.startswith('cpi_upgrade/inputs/') for n in names)==10
        assert not any(n.startswith(('cpi_upgrade/original/raw/fees/','cpi_upgrade/original/raw/commercial/','cpi_upgrade/original/data/fees/')) for n in names)
        assert z.testzip() is None
    rows=[{'file':name,'bytes':(DEL/name).stat().st_size,'sha256':hashlib.sha256((DEL/name).read_bytes()).hexdigest()} for name in outputs+[zpath.name]]
    jdump(rows,OUT/'deliverable_checksums.json');print('Packaged',len(rows),'files; bundle',zpath.stat().st_size,'bytes',flush=True)

if __name__=='__main__':main()
