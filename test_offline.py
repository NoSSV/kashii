from pathlib import Path
import logging
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scraper import GoraggioClient
from src.scoring import compute_daily_scores, compute_target_scores
from src.report import export_xlsx

CFG = {
    "store_id":"101219", "request_delay_seconds":0, "request_timeout_seconds":1, "max_retries":1,
    "low_sample_caps":{"500":57,"1000":62,"2000":72,"3000":82}, "source_url":"test"
}

HTML_ALL = '''<html><table class="tablesorter"><thead><tr><th></th><th>台番号</th><th>貸玉</th><th>機種名</th><th>BB回数</th><th>RB回数</th><th>前日最終スタート</th></tr></thead><tbody>
<tr><td></td><td>123</td><td>21.7</td><td>マイジャグラーV</td><td>30</td><td>28</td><td>120</td></tr>
</tbody></table></html>'''
HTML_UNIT = '''<html><table class="tablesorter"><thead><tr><th></th><th>台番号</th><th>累計スタート</th><th>BB回数</th><th>RB回数</th><th>ART回数</th><th>最大持玉</th><th>BB確率</th><th>RB確率</th><th>ART確率</th><th>合成確率</th><th>前日最終スタート</th></tr></thead><tbody>
<tr><td></td><td>123</td><td>7000</td><td>30</td><td>28</td><td>0</td><td>3200</td><td>1/233</td><td>1/250</td><td>-</td><td>1/120</td><td>120</td></tr>
</tbody></table></html>'''

log=logging.getLogger('t')
c=GoraggioClient(CFG,log)
h,r=c._extract_table(HTML_ALL)
x=c._canonicalize_row(h,r[0])
assert x['machine_no']==123 and x['bb']==30 and x['model']=='マイジャグラーV'
h,r=c._extract_table(HTML_UNIT)
x=c._canonicalize_row(h,r[0],forced_model='マイジャグラーV')
assert x['games']==7000 and x['max_hold']==3200 and x['rb_rate']==250

rows=[]
for d, shift in [('2026-09-14',0),('2026-09-13',1),('2026-09-12',2)]:
    for i,(g,bb,rb,mh) in enumerate([(7000,30,28,3200),(6500,25,20,1800),(900,8,7,2500)],123):
        rows.append({'data_date':d,'machine_no':i,'model':'マイジャグラーV','games':g,'bb':bb,'rb':rb,'art':0,'max_hold':mh,'diff':None,'output_rate':None,'bb_rate':None,'rb_rate':None,'combined_rate':None})
sc=compute_daily_scores(rows,CFG['low_sample_caps'])
low=[r for r in sc if r['machine_no']==125][0]
assert low['daily_score']<=62
t=compute_target_scores(sc,['2026-09-14','2026-09-13','2026-09-12'])
assert len(t)==3
export_xlsx(Path(__file__).resolve().parents[1]/'output'/'offline_test.xlsx',sc,['2026-09-14','2026-09-13','2026-09-12'],t,CFG)
print('offline tests OK')
