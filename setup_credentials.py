import getpass,secrets,os
from werkzeug.security import generate_password_hash
user=input('Planner username [admin]: ').strip() or 'admin'
if not user.isascii() or not all(c.isalnum() or c in '_-' for c in user): raise SystemExit('Use letters, numbers, underscores or hyphens')
password=getpass.getpass('Password (at least 12 characters): ')
if len(password)<12 or password!=getpass.getpass('Repeat password: '): raise SystemExit('Password too short or mismatch')
fd=os.open('.env',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:
    f.write('PLANNER_USER='+user+'\nPLANNER_SECRET='+secrets.token_hex(32)+'\nPLANNER_PASSWORD_HASH='+generate_password_hash(password)+'\nPLANNER_DB=data/planner.sqlite\n')
