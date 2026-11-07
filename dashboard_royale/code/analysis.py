"""Reproduces every number cited in the write-up and Claims & Evidence appendix.
Usage: python analysis.py <path-to-dashboard-royale>/data/      (needs: pip install duckdb pandas)"""
import sys, duckdb, pandas as pd
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30)
D = sys.argv[1] if len(sys.argv) > 1 else 'data/'
con = duckdb.connect()
for n, p in {'pdv':'1_prepared_views/prepared_daily_view','prop':'1_prepared_views/property_day','pp':'1_prepared_views/player_period',
             'md':'2_machine_decision/machine_day','gm':'2_machine_decision/game_math','cal':'2_machine_decision/calendar_day',
             'mach':'2_machine_decision/machines','ops':'2_machine_decision/operations','lg':'3_guests/loyalty_ledger'}.items():
    con.sql(f"create view {n} as select * from '{D}{p}.parquet'")
def q(title, sql):
    print('\n## ' + title); print(con.sql(sql).df().to_string())
con.sql("""create table m as select md.machine_id, count(*) n_days, sum(md.coin_in_cents)/100 coin_in, sum(md.house_win_cents)/100 hw,
 sum(md.theo_cents)/100 theo, sqrt(sum(gm.payout_multiplier_variance*md.sum_bet_squared))/100 sd,
 sum(md.payout_positive_spins) pos, sum(md.paid_spins) spins, any_value(gm.hit_probability) p,
 sum(md.available_seconds)/sum(md.scheduled_seconds) avail, sum(md.available_seconds)/3600 ah
 from md join gm using(config_id) where md.active group by 1""")
q('C1 Bottom ten by house win, with luck z and hit-rate z', """select m.machine_id, n_days, round(hw) hw, round(theo) theo, round((hw-theo)/sd,2) luck_z,
 round((pos-spins*p)/sqrt(spins*p*(1-p)),1) hit_z, round(avail,4) avail, (select mode(zone_name) from pdv where pdv.machine_id=m.machine_id and active) zone,
 (select any_value(configured_rtp) from pdv where pdv.machine_id=m.machine_id) rtp from m order by hw limit 10""")
q('C2 Luck z distribution', "select count(*) n, round(stddev((hw-theo)/sd),3) sd_z, sum(case when (hw-theo)/sd < -2.33 then 1 else 0 end) below_m233, round(count(*)*0.0099,1) expected from m")
q('C3 M-1158 hit rate vs published', "select machine_id, round(pos/spins,4) hit, p, round(theo-hw) shortfall from m where machine_id='M-1158'")
q('C4 Theo per available hour by zone and game', """select config_id, zone_name, count(distinct machine_id) n, round(sum(theo_usd)/sum(available_hours),2) tph
 from pdv where active group by 1,2 having n>=3 order by 1,2""")
q('C5 Walkway closure natural experiment', """select case when zone_name='Back Forty' then 'Back Forty' else 'Other' end grp,
 case when gaming_date<'2025-03-03' then '1 before' when gaming_date<'2025-04-07' then '2 closed' else '3 after' end per,
 round(sum(theo_usd)/sum(available_hours),2) tph, round(avg(zone_entries_observed)) entries from pdv where active group by 1,2 order by 1,2""")
q('C6 Downtime by manufacturer', """select p.manufacturer, round(sum(p.available_hours)/sum(c.scheduled_seconds/3600),4) avail,
 round(sum(c.scheduled_seconds/3600)-sum(p.available_hours)) down_h, round(sum(p.faults_opened)*30.0/count(*),2) faults_per_machine_month,
 round((sum(c.scheduled_seconds/3600)-sum(p.available_hours))/6*sum(p.theo_usd)/sum(p.available_hours)) lost_theo_per_month
 from pdv p join cal c using(gaming_date) where p.active group by 1""")
q('C7 Fault wait by local hour', """select hour(opened_at_local) h, count(*) n, round(avg(epoch(work_started_at_utc-opened_at_utc))/3600,2) wait_h
 from ops where event_type='fault_repair' group by 1 order by 1""")
q('C8 Tracked players', """with p as (select player_id, sum(tracked_coin_in_usd) ci, sum(tracked_payout_usd) po, sum(tracked_net_usd) net, sum(theo_usd) th from pp group by 1 having sum(tracked_coin_in_usd)>0)
 select round(sum(ci)) coin_in, round(sum(po)) payout, round(sum(net)) net, round(sum(th)) theo from p""")
q('C9 Player-months ahead', "select round(sum(case when tracked_net_usd>0 then 1 else 0 end)/sum(case when tracked_coin_in_usd>0 then 1 else 0 end),4) share from pp")
q('C10 Concentration of theo', """with p as (select player_id, sum(theo_usd) th from pp group by 1 having sum(tracked_coin_in_usd)>0), r as (select *, ntile(100) over(order by th desc) pc from p)
 select round(sum(case when pc=1 then th end)/sum(th),3) top1, round(sum(case when pc<=10 then th end)/sum(th),3) top10 from r""")
q('C11 Points per comp dollar by week', """select date_trunc('week', event_at_utc - interval 6 hour) wk, round(-sum(points_delta)/nullif(sum(face_value_cents)/100.0,0),2) pts_per_dollar
 from lg where event_type<>'award' group by 1 order by 1""")
q('C12 Comp reinvestment by month (tracked)', "select period_month, round(sum(comp_cost_usd)) comp_cost, round(sum(theo_usd)) theo, round(sum(comp_cost_usd)/sum(theo_usd),4) reinv from pp group by 1 order by 1")
d = con.sql("select gaming_date, local_weekday wd, coin_in_usd::double ci from prop order by 1").df(); d['gaming_date'] = pd.to_datetime(d.gaming_date)
tr, te = d[d.gaming_date < '2025-05-01'], d[d.gaming_date >= '2025-05-01'].copy()
te['base'] = tr.ci.mean(); te['wk'] = te.wd.map(tr.groupby('wd').ci.mean())
print('\n## C13 Forecast holdout (train Jan-Apr, test May-Jun)')
print('MAE flat baseline:', round((te.base-te.ci).abs().mean()), ' MAE weekday model:', round((te.wk-te.ci).abs().mean()),
      ' reduction:', round(1-(te.wk-te.ci).abs().mean()/(te.base-te.ci).abs().mean(), 3))
