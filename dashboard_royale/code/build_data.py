"""Build the aggregated data file behind the Dashboard Royale page (DuckDB over the released parquet)."""
import duckdb, json, math, sys
import pandas as pd
D = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/dr/data/'
con = duckdb.connect()
for name, path in {'pdv':'1_prepared_views/prepared_daily_view','prop':'1_prepared_views/property_day','pp':'1_prepared_views/player_period',
                   'md':'2_machine_decision/machine_day','gm':'2_machine_decision/game_math','cal':'2_machine_decision/calendar_day',
                   'mach':'2_machine_decision/machines','ops':'2_machine_decision/operations','ac':'2_machine_decision/action_catalog',
                   'lg':'3_guests/loyalty_ledger','wk':'2_machine_decision/floor_walkways'}.items():
    con.sql(f"create view {name} as select * from '{D}{path}.parquet'")
r = lambda x, n=2: None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), n)
months = ['2025-01','2025-02','2025-03','2025-04','2025-05','2025-06']
out = {'months': months}

# Machine x month (active days only). var = sum(payout_multiplier_variance * bet^2) in USD^2 -> luck z-scores add up.
mm = con.sql("""select md.machine_id, strftime(md.gaming_date,'%Y-%m') mo, count(*) d,
  sum(md.coin_in_cents)/100 ci, sum(md.house_win_cents)/100 hw, sum(md.theo_cents)/100 th,
  sum(gm.payout_multiplier_variance*md.sum_bet_squared)/10000 var,
  sum(md.available_seconds)/3600 ah, sum(md.scheduled_seconds)/3600 sh, sum(md.occupied_seconds)/3600 oh,
  sum(md.paid_spins) sp, sum(md.payout_positive_spins) ps
 from md join gm using(config_id) where md.active group by 1,2""").df()
meta = con.sql("""select p.machine_id, mode(p.zone_name) zone, mode(p.bank_id) bank, any_value(p.manufacturer) mfr, any_value(p.theme) theme,
  any_value(p.config_id) cfg, any_value(p.volatility_class) vol, any_value(p.configured_rtp)::double rtp, sum(p.faults_opened) faults_total
 from pdv p where p.active group by 1""").df()
fa = con.sql("select machine_id, strftime(gaming_date,'%Y-%m') mo, sum(faults_opened) f from pdv where active group by 1,2").df()
gmd = con.sql("select config_id, hit_probability::double hp from gm").df().set_index('config_id').hp.to_dict()
machines = []
for _, m in meta.sort_values('machine_id').iterrows():
    rows = mm[mm.machine_id == m.machine_id].set_index('mo')
    f = fa[fa.machine_id == m.machine_id].set_index('mo')
    per = []
    for mo in months:
        if mo in rows.index:
            x = rows.loc[mo]
            per.append([int(x.d), r(x.ci), r(x.hw), r(x.th), r(x['var'], 1), r(x.ah, 1), r(x.sh, 1), r(x.oh, 1), int(x.sp), int(x.ps), int(f.loc[mo].f) if mo in f.index else 0])
        else:
            per.append(None)
    machines.append({'id': m.machine_id, 'zone': m.zone, 'bank': m.bank, 'mfr': m.mfr, 'theme': m.theme, 'cfg': m.cfg, 'vol': m.vol,
                     'rtp': r(m.rtp, 3), 'hitCfg': r(gmd[m.cfg], 5), 'm': per})
out['machineFields'] = ['days','coinIn','houseWin','theo','var','availH','schedH','occH','spins','posSpins','faults']
out['machines'] = machines

# Property day
pdd = con.sql("""select gaming_date::varchar d, local_weekday wd, coalesce(events_active,'') ev, coin_in_usd::double ci, house_win_usd::double hw, theo_usd::double th,
  available_machine_hours ah, occupied_machine_hours oh, comp_cost_usd::double cc, faults_opened f, total_zone_entries_observed ent, pos_cash_usd::double pc
 from prop order by 1""").df()
out['days'] = [[x.d, x.wd, x.ev, r(x.ci, 0), r(x.hw, 0), r(x.th, 0), r(x.ah, 0), r(x.oh, 0), r(x.cc, 0), int(x.f), int(x.ent) if x.ent == x.ent else None] for x in pdd.itertuples()]
out['dayFields'] = ['date','weekday','events','coinIn','houseWin','theo','availH','occH','compCost','faults','entries']

# Forecast: train Jan-Apr, test May-Jun. Both forecasts frozen from training data only.
pdd['date'] = pd.to_datetime(pdd.d)
tr, te = pdd[pdd.date < '2025-05-01'], pdd[pdd.date >= '2025-05-01'].copy()
const = tr.ci.mean(); wkmean = tr.groupby('wd').ci.mean().to_dict()
te['base'] = const; te['wk'] = te.wd.map(wkmean)
mae_b = (te.base - te.ci).abs().mean(); mae_w = (te.wk - te.ci).abs().mean()
# train-period fit (in-sample) for context
out['forecast'] = {'train': [[x.d, r(x.ci, 0)] for x in tr.itertuples()],
                   'test': [[x.d, r(x.ci, 0), r(x.base, 0), r(x.wk, 0), x.wd] for x in te.itertuples()],
                   'weekdayMeans': {k: r(v, 0) for k, v in wkmean.items()}, 'constMean': r(const, 0),
                   'maeBaseline': r(mae_b, 0), 'maeWeekday': r(mae_w, 0),
                   'mapeBaseline': r(((te.base - te.ci) / te.ci).abs().mean() * 100, 2), 'mapeWeekday': r(((te.wk - te.ci) / te.ci).abs().mean() * 100, 2),
                   'biasWeekday': r((te.wk - te.ci).mean(), 0),
                   'byWeekday': {k: [r(g.ci.mean(), 0), r(g.wk.mean(), 0), r((g.wk - g.ci).abs().mean(), 0)] for k, g in te.groupby('wd')}}

# Zone x config theo per available hour (location effect controlling for game math)
zc = con.sql("""select zone_name z, config_id c, count(distinct machine_id) n, sum(theo_usd)::double th, sum(available_hours) ah
 from pdv where active group by 1,2""").df()
out['zoneConfig'] = [[x.z, x.c, int(x.n), r(x.th / x.ah, 2)] for x in zc.itertuples()]

# Walkway closure natural experiment
we = con.sql("""select case when zone_name='Back Forty' then 'Back Forty' else 'Other zones' end g,
 case when gaming_date < '2025-03-03' then 'before' when gaming_date < '2025-04-07' then 'closed' else 'after' end p,
 sum(theo_usd)::double / sum(available_hours) tph, sum(coin_in_usd)::double / sum(available_hours) cph, avg(zone_entries_observed) ent
 from pdv where active group by 1,2""").df()
out['walkway'] = {f'{x.g}|{x.p}': [r(x.tph, 2), r(x.cph, 1), r(x.ent, 0)] for x in we.itertuples()}
zw = con.sql("""select zone_name z, date_trunc('week', gaming_date)::varchar w, sum(theo_usd)::double / sum(available_hours) tph, avg(zone_entries_observed) ent
 from pdv where active group by 1,2 order by 2""").df()
out['zoneWeek'] = [[x.z, x.w, r(x.tph, 2), r(x.ent, 0)] for x in zw.itertuples()]

# Fault tickets: manufacturer x local hour, and weekly
oh = con.sql("""select m.manufacturer mf, hour(o.opened_at_local) h, count(*) n, avg(epoch(o.work_started_at_utc-o.opened_at_utc))/3600 wait,
 avg(epoch(o.available_at_utc-o.opened_at_utc))/3600 down from ops o join mach m using(machine_id) where o.event_type='fault_repair' group by 1,2""").df()
out['faultHour'] = [[x.mf, int(x.h), int(x.n), r(x.wait, 2), r(x.down, 2)] for x in oh.itertuples()]

# Comps: weekly points per comp dollar (redemptions), comp cost, redemptions
cw = con.sql("""select date_trunc('week', event_at_utc - interval 6 hour)::varchar w, -sum(points_delta)::double / nullif(sum(face_value_cents)/100.0,0) ppd,
 sum(economic_cost_cents)/100.0 cost, count(*) n from lg where event_type <> 'award' and event_at_utc < '2025-06-30 13:00:00' group by 1 order by 1""").df()
out['compWeek'] = [[x.w, r(x.ppd, 2), r(x.cost, 0), int(x.n)] for x in cw.itertuples()]

# Players: month x opening tier x home region, with player-month 'ahead' counts
pg = con.sql("""select period_month mo, opening_tier t, home_region g, count(*) pm, sum(case when tracked_net_usd>0 then 1 else 0 end) ahead,
 sum(case when tracked_coin_in_usd>0 then 1 else 0 end) played,
 sum(tracked_coin_in_usd)::double ci, sum(tracked_payout_usd)::double po, sum(tracked_net_usd)::double net, sum(theo_usd)::double th,
 sum(comp_cost_usd)::double cc, sum(comp_face_value_usd)::double cf, sum(tracked_contribution_usd)::double contrib
 from pp group by 1,2,3""").df()
out['players'] = [[x.mo, x.t, x.g, int(x.pm), int(x.played), int(x.ahead), r(x.ci, 0), r(x.po, 0), r(x.net, 0), r(x.th, 0), r(x.cc, 0), r(x.cf, 0), r(x.contrib, 0)] for x in pg.itertuples()]
out['playerFields'] = ['month','tier','region','playerMonths','played','ahead','coinIn','payout','net','theo','compCost','compFace','contribution']
# Concentration (full window, player level), overall and by region
cc = con.sql("""with p as (select player_id, any_value(home_region) g, any_value(opening_tier) t, sum(theo_usd)::double th, sum(tracked_net_usd)::double net
  from pp group by 1 having sum(tracked_coin_in_usd)>0),
 r as (select *, ntile(100) over (order by th desc) pc from p)
 select g, pc, count(*) n, sum(th) th, sum(-net) loss, sum(case when net>0 then 1 else 0 end) ahead from r group by 1,2""").df()
out['concentration'] = [[x.g, int(x.pc), int(x.n), r(x.th, 0), r(x.loss, 0), int(x.ahead)] for x in cc.itertuples()]

# Action catalog
a = con.sql("select action_type_id, name, unit, unit_cost_cents/100.0 c, recurring_cost_cents_per_day/100.0 rc, lead_days, downtime_minutes, quantity_limit, coalesce(incompatibility_group,'') ig, notes from ac").df()
out['actions'] = [[x.action_type_id, x.name, x.unit, r(x.c, 0), r(x.rc, 0), int(x.lead_days), int(x.downtime_minutes), int(x.quantity_limit), x.ig, x.notes] for x in a.itertuples()]
json.dump(out, open(sys.argv[2] if len(sys.argv) > 2 else '/home/claude/drd/data.json', 'w'), separators=(',', ':'))
print('ok', 'MAE baseline', out['forecast']['maeBaseline'], 'weekday', out['forecast']['maeWeekday'])
