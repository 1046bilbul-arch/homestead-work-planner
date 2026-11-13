import sqlite3,os
from pathlib import Path
from datetime import datetime,timedelta
src=Path(os.environ.get('PLANNER_DB','data/planner.sqlite'))
if not src.is_file(): raise SystemExit('Database missing')
folder=Path('backups');folder.mkdir(mode=0o700,exist_ok=True)
target=folder/('planner-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite')
with sqlite3.connect(src) as a,sqlite3.connect(target) as b: a.backup(b)
target.chmod(0o600)
for p in folder.glob('planner-*.sqlite'):
    if datetime.fromtimestamp(p.stat().st_mtime)<datetime.now()-timedelta(days=30): p.unlink()
print(target)
