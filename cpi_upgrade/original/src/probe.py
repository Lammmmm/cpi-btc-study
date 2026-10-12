from net import fetch
from concurrent.futures import ThreadPoolExecutor,as_completed
urls={
'bls_archive.html':'https://www.bls.gov/bls/news-release/cpi.htm',
'macro_readme.md':'https://raw.githubusercontent.com/superpilot69/fred-us-macro-open-data/main/README.md',
'consensus.json':'https://raw.githubusercontent.com/superpilot69/fred-us-macro-open-data/main/data/investing-us-macro-consensus.json',
'macro_metadata.json':'https://raw.githubusercontent.com/superpilot69/fred-us-macro-open-data/main/metadata/dataset-metadata.json',
'investing_yoy.html':'https://www.investing.com/economic-calendar/cpi-733',
'bls_2024_example.html':'https://www.bls.gov/news.release/archives/cpi_01112024.htm',
'binance_example.zip':'https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-11.zip',
'alfred_example.csv':'https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&file_type=json',
}
with ThreadPoolExecutor(max_workers=8) as ex:
 fs={ex.submit(fetch,u,n):n for n,u in urls.items()}
 for f in as_completed(fs):
  try:b=f.result();print(fs[f],len(b),b[:160],flush=True)
  except Exception as e:print(fs[f],repr(e),flush=True)
