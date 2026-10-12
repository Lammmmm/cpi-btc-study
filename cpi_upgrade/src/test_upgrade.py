"""Accounting and independent source/path tests, not historical trade data generation."""
import sys,unittest,hashlib,json
from zoneinfo import ZoneInfo
from lxml import html
from common import *
from paths_upgrade import bucket,exclusive
from trading import get_trade
sys.path.append(str(ORIGINAL/'src'))
from clean import load_day
from backtest import calc

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.t0=pd.Timestamp('2024-01-11T13:30Z');idx=pd.date_range(self.t0-pd.Timedelta(minutes=60),self.t0+pd.Timedelta(minutes=400),freq='min')
        self.d=pd.DataFrame(100.,index=idx,columns=['open','high','low','close'])
    def test_not_profitable_when_only_baseline_retained(self):
        self.d.loc[self.t0:self.t0+pd.Timedelta(minutes=14)]=101.
        self.d.loc[self.t0+pd.Timedelta(minutes=15):self.t0+pd.Timedelta(minutes=59)]=101.
        self.d.loc[self.t0+pd.Timedelta(minutes=29):]=100.5
        r=calc(self.d,self.t0,15,30)
        self.assertEqual(r['keep'],1);self.assertLess(r['gross_return'],0)
        tr=get_trade(self.d,self.t0,15,16,30,1)
        self.assertEqual(tr['entry_min'],16);self.assertAlmostEqual(tr['entry_price'],101.)
        self.assertLess(tr['net_return'],0)
    def test_touch_is_not_five_minute_reversal(self):
        self.d.loc[self.t0:self.t0+pd.Timedelta(minutes=14)]=101.
        self.d.loc[self.t0+pd.Timedelta(minutes=15):]=100.5
        self.d.loc[self.t0+pd.Timedelta(minutes=20),'low']=99.
        r=calc(self.d,self.t0,15,60)
        self.assertEqual(r['fade100_touch'],1);self.assertEqual(r['reverse5_touch'],0)
    def test_reverse_entry_uses_next_minute_open(self):
        self.d.loc[self.t0:self.t0+pd.Timedelta(minutes=14)]=101.
        self.d.loc[self.t0+pd.Timedelta(minutes=15):]=100.5
        self.d.loc[self.t0+pd.Timedelta(minutes=24),'close']=99.
        self.d.loc[self.t0+pd.Timedelta(minutes=24),'low']=99.
        self.d.loc[self.t0+pd.Timedelta(minutes=26)]=98.5
        r=calc(self.d,self.t0,15,60)
        self.assertEqual(r['first_reverse5_min'],25)
        tr=get_trade(self.d,self.t0,25,26,86,-1)
        self.assertEqual(tr['entry_price'],98.5)
        self.assertEqual(tr['entry_utc'],(self.t0+pd.Timedelta(minutes=26)).isoformat())
    def test_missing_bar_rejects_executable_trade(self):
        self.d=self.d.drop(self.t0+pd.Timedelta(minutes=40))
        self.assertIsNone(get_trade(self.d,self.t0,25,26,86,-1))
    def test_exit_must_follow_entry(self):
        self.assertIsNone(get_trade(self.d,self.t0,240,241,240,-1))
    def test_short_rebound_loss_and_excursions(self):
        self.d.loc[self.t0+pd.Timedelta(minutes=16)]=99.
        tr=get_trade(self.d,self.t0,15,16,60,-1)
        self.assertLess(tr['gross_return'],0);self.assertLess(tr['mae'],0);self.assertGreaterEqual(tr['mfe'],0)
    def test_float_tenths_and_missing(self):
        self.assertEqual(bucket(.099999999999),'小幅偏热');self.assertEqual(bucket(-.19999999999),'暴冷');self.assertEqual(bucket(np.nan),'缺失')
    def test_timezone_dst(self):
        for date,utc in [('2024-01-11','13:30'),('2024-07-11','12:30')]:
            t=pd.Timestamp(date+' 08:30',tz=ZoneInfo('America/New_York')).tz_convert('UTC')
            self.assertEqual(t.strftime('%H:%M'),utc)

class FrozenDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e=pd.read_csv(OUT/'events_four.csv');cls.p=pd.read_csv(OUT/'paths.csv');cls.t=pd.read_csv(OUT/'trades_all.csv')
    def test_universe_and_missing_cpi(self):
        e=self.e;self.assertEqual(len(e),92);self.assertEqual(e.date.nunique(),92)
        self.assertEqual(e.groupby('year').size().to_dict(),{2019:12,2020:12,2021:12,2022:12,2023:12,2024:12,2025:11,2026:9})
        r=e[e.date.eq('2025-12-18')].iloc[0]
        for k in ['headline_mom','core_mom']:
            self.assertTrue(pd.isna(r[k+'_actual']));self.assertTrue(pd.isna(r[k+'_forecast']))
    def test_all_windows_and_matrix_accounting(self):
        self.assertEqual(len(self.p),1380);self.assertEqual(int(self.e.price_path_complete_240m.sum()),92);self.assertEqual(int(self.e.price_path_complete_1440m.sum()),91)
        self.assertEqual(len(self.p[self.p.status.ne('ok')]),3)
        for tag in ['mom','yoy','hy_cm']:self.assertEqual(int(self.e.groupby(tag+'_pair').size().sum()),92)
        self.assertEqual(int(self.e.groupby('joint_exclusive').size().sum()),92)
    def test_reversal_is_subset_of_touch(self):
        p=self.p[self.p.status.eq('ok')]
        self.assertTrue((p.reverse5_touch<=p.fade100_touch).all());self.assertTrue((p.fade100_touch<=p.fade50_touch).all())
    def test_all_entry_and_exit_prices_independent(self):
        for date,trs in self.t.groupby('date'):
            d=bars(date)
            for _,tr in trs.iterrows():
                self.assertAlmostEqual(tr.entry_price,float(d.loc[pd.Timestamp(tr.entry_utc),'open']),places=6)
                self.assertAlmostEqual(tr.exit_price,float(d.loc[pd.Timestamp(tr.exit_utc),'open']),places=6)
                self.assertGreaterEqual(tr.entry_min,tr.signal_min);self.assertGreater(tr.exit_min,tr.entry_min)
                if tr.execution_lag_min==1:self.assertGreater(tr.entry_min,tr.signal_min)
                self.assertAlmostEqual(tr.net_return,tr.direction*(tr.exit_price/tr.entry_price-1)-.0024,places=10)
    def test_reversal_and_delay_have_no_future_trigger(self):
        e=self.e.set_index('date');t=self.t
        for date,ev in e.iterrows():
            d=bars(date);t0=pd.Timestamp(ev.t0_utc)
            actual=next((m for m in range(20,241,5) if ev.btc_first_direction*(float(d.loc[t0+pd.Timedelta(minutes=m-1),'close'])-ev.p0)<0),None)
            recorded=ev.first_reverse5_min_240m
            self.assertTrue((actual is None and pd.isna(recorded)) or actual==recorded)
        for _,tr in t[t.family.eq('B')].iterrows():
            self.assertEqual(tr.signal_min,e.loc[tr.date,'first_reverse5_min_240m'])
            self.assertEqual(tr.direction,-e.loc[tr.date,'btc_first_direction'])
        for _,tr in t[t.family.eq('C')].iterrows():
            rev=e.loc[tr.date,'first_reverse5_min_240m'];self.assertTrue(pd.isna(rev) or rev>tr.signal_min)
            self.assertGreater(tr.direction*e.loc[tr.date,f'btc_return_{int(tr.signal_min)}m'],0)
    def test_original_zip_vs_all_new_returns(self):
        errors=[]
        for _,e in self.e.iterrows():
            date=e.date;t0=pd.Timestamp(e.t0_utc);d=load_day(date)
            nxt=(pd.Timestamp(date)+pd.Timedelta(days=1)).date().isoformat();d=pd.concat([d,load_day(nxt)]).sort_index()
            for h in HORIZONS:
                if not e[f'price_path_complete_{h}m']:continue
                ret=float(d.loc[t0+pd.Timedelta(minutes=h-1),'close']/d.loc[t0-pd.Timedelta(minutes=1),'close']-1)
                errors.append(abs(ret-e[f'btc_return_{h}m']))
        self.assertLess(max(errors),1e-10)
        save(pd.DataFrame([{'max_raw_return_error':max(errors),'valid_returns':len(errors)}]),'independent_raw_return_audit.csv')
    def test_official_sha256_all184(self):
        rows=[]
        for p in sorted((ORIGINAL/'raw/btc').glob('*.zip')):
            official=Path(str(p)+'.CHECKSUM').read_text().split()[0];got=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(got,official);rows.append({'file':p.name,'sha256':got,'official_sha256':official,'match':got==official})
        self.assertEqual(len(rows),184);save(pd.DataFrame(rows),'raw_sha256_audit.csv')
    def test_actuals_from_bls_without_copying_csv(self):
        count=0
        for _,e in self.e.iterrows():
            h=html.fromstring((ORIGINAL/'raw/bls'/f'cpi_{e.date}.html').read_bytes());found={}
            for tr in h.xpath('//table//tr'):
                cells=[' '.join(c.text_content().split()) for c in tr.xpath('./th|./td')]
                if cells and cells[0] in ['All items','All items less food and energy'] and cells[0] not in found:found[cells[0]]=cells
            for label,key in [('All items','headline'),('All items less food and energy','core')]:
                cs=found[label];pairs=[('mom',cs[-1]),('yoy',cs[5])] if len(cs)==10 else [('mom',cs[-2]),('yoy',cs[-1])]
                for period,text in pairs:
                    if text in ['-','—','']:self.assertTrue(pd.isna(e[key+'_'+period+'_actual']))
                    else:self.assertEqual(float(text.replace(',','')),e[key+'_'+period+'_actual']);count+=1
        self.assertEqual(count,366)
    def test_prediction_chronology(self):
        p=pd.read_csv(OUT/'prediction_events.csv')
        self.assertTrue((p.train_last_date<p.date).all());self.assertTrue(p.probability.between(0,1).all())
    def test_roll_standardization_uses_only_prior_events(self):
        for k in FIELDS:
            vals=self.e[k+'_surprise_pp'].to_numpy()
            for i in range(12,len(vals)):
                prior=vals[:i][np.isfinite(vals[:i])][-24:];sigma=np.std(prior,ddof=1) if len(prior)>=12 else np.nan
                if np.isfinite(sigma):self.assertAlmostEqual(sigma,self.e.iloc[i][k+'_rolling_prior_sigma_pp'],places=10)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]);result=unittest.TextTestRunner(verbosity=1).run(suite)
    jdump({'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'success':result.wasSuccessful(),'seed':SEED},OUT/'test_results.json')
    raise SystemExit(0 if result.wasSuccessful() else 1)
