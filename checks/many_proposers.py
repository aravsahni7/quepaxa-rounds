"""Friday check: does round 1 rate fall toward 0.5 with many proposers, and
does the reply rule decide which way it goes. Prints CSV. Run from the
project dir: python3 checks/many_proposers.py > results/fri_many_proposers.csv
"""
import sys; import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from sim import run_trial, per_round_rates
from sweep import wilson
print("n_prop,n_rec,spread,reply_mode,trials,r1,r1_lo,r1_hi,r2,r2_n,viol,undec")
for rm in ("max","first"):
  for n_prop in (8,12,20):
    for spread in (16.0,64.0):
        res=[run_trial(b*1_000_000+i,n_prop=n_prop,n_rec=5,spread=spread,reply_mode=rm) for b in range(4) for i in range(100)]
        n=len(res); h=sum(1 for x in res if x["first_round"]==1); lo,hi=wilson(h,n)
        _,r2n,r2=per_round_rates(res,2)[1]
        v=sum(1 for x in res if not x["agree"]); u=sum(1 for x in res if x["first_round"] is None)
        print(f"{n_prop},5,{spread:g},{rm},{n},{h/n:.4f},{lo:.4f},{hi:.4f},{'' if r2 is None else f'{r2:.4f}'},{r2n},{v},{u}",flush=True)
