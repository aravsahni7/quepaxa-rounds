"""Friday check: round 1 and round 2 rates against start jitter, which is our
choice and not the post's. Prints CSV. Run from the project dir:
python3 checks/jitter.py > results/fri_jitter.csv
"""
import sys; import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from sim import run_trial, per_round_rates
from sweep import wilson
print("n_prop,n_rec,spread,reply_mode,start_jitter,trials,r1,r1_lo,r1_hi,r2,r2_n,viol")
for rm in ("max","first"):
  for n_prop in (3,5):
    for spread in (4.0,16.0,64.0):
      for jit in (0.0,0.5,1.0,2.0,4.0,8.0):
        res=[run_trial(b*1_000_000+i,n_prop=n_prop,n_rec=5,spread=spread,reply_mode=rm,start_jitter=jit) for b in range(4) for i in range(250)]
        n=len(res); h=sum(1 for x in res if x["first_round"]==1); lo,hi=wilson(h,n)
        _,r2n,r2=per_round_rates(res,2)[1]
        v=sum(1 for x in res if not x["agree"])
        print(f"{n_prop},5,{spread:g},{rm},{jit:g},{n},{h/n:.4f},{lo:.4f},{hi:.4f},{'' if r2 is None else f'{r2:.4f}'},{r2n},{v}",flush=True)
