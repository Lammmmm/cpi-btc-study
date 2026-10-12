from common import *
import shutil

def main():
    e=pd.read_csv(OUT/'events_four.csv');s=pd.read_csv(OUT/'group_windows.csv');tr=pd.read_csv(OUT/'trades_all.csv')
    dictionary=[]
    for c in e:
        unit=''
        if c.endswith('_surprise_pp') or c.endswith('_sigma_pp'):unit='percentage points (0.1 = 0.1pp)'
        elif c.endswith('_actual') or c.endswith('_forecast'):unit='CPI percent level/change; not decimal rate'
        elif any(x in c for x in ['return','mfe','mae','sigma_c']):unit='decimal fractional price return (0.01=1%); sigma/z fields see SPECIFICATION'
        elif any(x in c for x in ['keep','fade','reverse5','_win','strong_first','complete']):unit='0/1 flag if numeric; trigger minute fields are minutes; missing is not false'
        elif any(x in c for x in ['price','p0','extreme']):unit='USDT per BTC'
        elif '_min' in c:unit='minutes since T0; missing trigger means untriggered if complete path'
        dictionary.append({'field':c,'dtype':str(e[c].dtype),'unit_or_meaning':unit,'nonmissing_n':int(e[c].notna().sum()),'missing_n':int(e[c].isna().sum())})
    save(pd.DataFrame(dictionary),'event_field_dictionary.csv')
    # Every window count and point estimate is checked independently of report rendering.
    members=pd.read_csv(OUT/'group_memberships.csv');errors=[]
    for _,r in s.iterrows():
        dates=set(members.loc[members.group_key.eq(r.group_key),'date']);x=e.loc[e.date.isin(dates),f'btc_return_{int(r.horizon_min)}m'].dropna()
        assert len(dates)==r.events_n and len(x)==r.valid_n
        assert int(x.gt(0).sum())==r.up_count and int(x.lt(0).sum())==r.down_count
        if len(x):errors.append(abs(x.mean()-r.release_return_mean))
    assert max(errors)<1e-10
    missing=[]
    for _,r in e.iterrows():
        for k in FIELDS:
            if pd.isna(r[k+'_actual']) or pd.isna(r[k+'_forecast']):missing.append({'date':r.date,'item':k+' actual/forecast','impact':'exclude only indicator/pair/model complete-case comparisons','status':'source not available; no imputation'})
    missing.extend([{'date':'2025-10 reference month','item':'CPI official release','impact':'not an event; 92 universe','status':'BLS did not collect survey data'}, {'date':'2021-02-10','item':'24h price path: 79 missing minutes','impact':'24h path/return excluded; <=4h retained','status':'original Binance daily archive missing 2021-02-11 03:41-04:59 UTC'}])
    for _,r in e[e.growth_strict.eq('unclassified')].iterrows():missing.append({'date':r.date,'item':'strict PIT growth state','impact':'growth unclassified; all BTC and CPI retained','status':'two-of-three deterioration not identified from certified inputs'})
    save(pd.DataFrame(missing),'missing_data.csv')
    shutil.copyfile(ORIGINAL/'results/source_manifest.csv',OUT/'original_source_manifest.csv');shutil.copyfile(ORIGINAL/'results/source_exclusion_audit.csv',OUT/'original_source_exclusions.csv')
    jdump({'events':len(e),'fields':len(e.columns),'window_groups':len(s),'windows_point_estimates_max_error':max(errors),'trade_scenario_records':len(tr),'independent_events':92,'primary_tests':18,'statistical_seed':SEED,'bootstrap_resamples':BOOT,'not_unseen_holdout':True},OUT/'numerical_audit.json')
    print('Aggregate point estimates independently reconciled',len(s),flush=True)

if __name__=='__main__':main()
