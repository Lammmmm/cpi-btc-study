from net import fetch
from acquire import jobs_run
jobs=[
('alfred_probe.csv','https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=UNRATE&cosd=2018-01-01&coed=2019-01-10&vintage_date=2019-01-10'),
('fred_vintage_probe.csv','https://fred.stlouisfed.org/graph/?g=&id=UNRATE&cosd=2018-01-01&coed=2019-01-10&fq=Monthly&fam=avg&fgst=lin&fgsnd=2020-02-01&line_index=1&line_id=UNRATE&cosd=2018-01-01&coed=2019-01-10&vintage_date=2019-01-10'),
('alfred_probe2.csv','https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=PCEC96&cosd=2018-01-01&coed=2019-01-10&vintage_date=2019-01-10'),
('investing_ism.html','https://www.investing.com/economic-calendar/ism-1483'),
('investing_fomc.html','https://www.investing.com/economic-calendar/interest-rate-decision-168'),
('alfred_R_source.txt','https://raw.githubusercontent.com/onnokleen/alfred/master/R/get_alfred_series.R'),
('databento_pricing.html','https://databento.com/pricing'),
('github_nq_search.json','https://api.github.com/search/repositories?q=NQ+minute+data'),
]
jobs_run(jobs,8)
