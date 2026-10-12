from common import *

def records(df,cols=None):
    if cols:df=df[cols]
    return json.loads(df.to_json(orient='records',force_ascii=False))

def main():
    e=pd.read_csv(OUT/'events_four.csv');e['monthly_complete']=e[['headline_mom_actual','headline_mom_forecast','core_mom_actual','core_mom_forecast']].notna().all(axis=1).astype(int);e['four_complete']=e[[k+s for k in FIELDS for s in ['_actual','_forecast']]].notna().all(axis=1).astype(int)
    columns=['date','year','monthly_complete','four_complete']+[k+'_sign' for k in FIELDS]+[k+'_bucket5' for k in FIELDS]
    columns += [k+s for k in FIELDS for s in ['_forecast','_actual','_surprise_pp']]
    columns += [f'btc_return_{h}m' for h in HORIZONS]+['strong_first_03','keep_240m','fade50_touch_240m','fade100_touch_240m','reverse5_touch_240m','reverse5_end_240m','first_reverse5_min_240m']
    columns += ['A_15_to60_net_return','A_15_to240_net_return','B_hold60_net_return','B_to240_net_return','C30_hold60_net_return','C60_hold240_net_return','growth_strict','growth_snapshot','policy_stage','joint_exclusive','t0_utc','url']+[k+'_forecast_source' for k in FIELDS]+[k+'_forecast_availability' for k in FIELDS]
    p={'events':records(e,columns),'event_columns':columns,'windows':records(pd.read_csv(OUT/'group_windows.csv')),'strategies':records(pd.read_csv(OUT/'strategy_groups.csv')),'memberships':records(pd.read_csv(OUT/'group_memberships.csv')),'primary_tests':records(pd.read_csv(OUT/'hypothesis_tests_primary.csv')),'prediction':records(pd.read_csv(OUT/'prediction_metrics.csv')),'model_tests':records(pd.read_csv(OUT/'prediction_incremental_tests.csv')),'robustness':records(pd.read_csv(OUT/'robustness.csv')),'matrix_tests':records(pd.read_csv(OUT/'matrix_exploratory_tests.csv'))}
    jdump(p,OUT/'workbook_payload.json');print('Workbook payload prepared',len(p['windows']),len(p['strategies']),flush=True)

if __name__=='__main__':main()
