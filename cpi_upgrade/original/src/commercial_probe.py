from acquire import jobs_run
jobs_run([
('commercial/unit_prices_2024.pdf','https://databento-media.s3-website-us-east-1.amazonaws.com/media/unit-pricing-draft-2024-04-01.pdf'),
('commercial/unit_prices_probe.json','https://hist.databento.com/v0/metadata.list_unit_prices?dataset=GLBX.MDP3'),
('commercial/nq_repo_contents.json','https://api.github.com/repos/psakhil-nq/intraday-edge-decomposition/contents'),
('commercial/ism_april2020.html','https://www.prnewswire.com/news-releases/pmi-at-41-5-april-2020-manufacturing-ism-report-on-business-301050619.html'),
('commercial/ism_nov2022.html','https://www.prnewswire.com/news-releases/manufacturing-pmi-at-49-november-2022-manufacturing-ism-report-on-business-301690752.html'),
('commercial/ism_dec2022.html','https://www.prnewswire.com/news-releases/manufacturing-pmi-at-48-4-december-2022-manufacturing-ism-report-on-business-301712602.html')],6)
