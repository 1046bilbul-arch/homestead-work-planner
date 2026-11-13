import os, sqlite3, secrets, csv, io
from datetime import date, datetime
from functools import wraps
from flask import Flask, request, session, jsonify, render_template, abort, Response
from werkzeug.security import check_password_hash
app=Flask(__name__)
@app.get('/sw.js')
def service_worker():
    r=app.send_static_file('sw.js')
    r.headers['Service-Worker-Allowed']='/'
    return r

app.secret_key=os.environ['PLANNER_SECRET']
app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict', MAX_CONTENT_LENGTH=65536)
DB=os.environ.get('PLANNER_DB','data/planner.sqlite')
os.makedirs(os.path.dirname(os.path.abspath(DB)),exist_ok=True)
def db():
    c=sqlite3.connect(DB,timeout=10)
    c.row_factory=sqlite3.Row
    return c
with db() as c:
    c.execute('CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, name TEXT NOT NULL, detail TEXT, day TEXT, minutes INTEGER NOT NULL, start TEXT, finish TEXT, comments TEXT, customer TEXT, location TEXT, status TEXT, priority TEXT, travel INTEGER DEFAULT 0)')
def protected(f):
    @wraps(f)
    def wrapped(*a,**k):
        if not session.get('auth'): abort(401)
        if request.method not in ('GET','HEAD') and request.headers.get('X-CSRF-Token')!=session.get('csrf'): abort(403)
        return f(*a,**k)
    return wrapped
@app.after_request
def headers(r):
    if not request.path.startswith('/static/'): r.headers['Cache-Control']='no-store'
    r.headers['X-Content-Type-Options']='nosniff'
    r.headers['Referrer-Policy']='no-referrer'
    return r
@app.get('/')
def home(): return render_template('index.html')
@app.get('/session')
def state(): return jsonify(auth=bool(session.get('auth')),csrf=session.get('csrf'))
@app.post('/login')
def login():
    p=request.get_json()
    if not isinstance(p,dict): abort(400)
    if p.get('username')!=os.environ.get('PLANNER_USER','admin') or not check_password_hash(os.environ['PLANNER_PASSWORD_HASH'],str(p.get('password',''))): abort(401)
    session.clear()
    session.update(auth=True,csrf=secrets.token_hex(32))
    return jsonify(csrf=session['csrf'])
@app.post('/logout')
@protected
def logout():
    session.clear()
    return jsonify(ok=True)
@app.get('/api/tasks')
@protected
def tasks():
    with db() as c: return jsonify([dict(r) for r in c.execute('SELECT * FROM tasks ORDER BY day,start,id')])
def validate(p):
    if not isinstance(p,dict): raise ValueError('Invalid task')
    name=str(p.get('name','')).strip()
    if not name or len(name)>200: raise ValueError('Task name required')
    day=p.get('day') or ''
    if day: date.fromisoformat(day)
    start=p.get('start') or ''
    finish=p.get('finish') or ''
    if start or finish:
        a=datetime.strptime(start,'%H:%M'); b=datetime.strptime(finish,'%H:%M')
        minutes=int((b-a).total_seconds()/60)
    else: minutes=round(float(p['hours'])*60)
    travel=round(float(p.get('travel',0))*60)
    if not 0<minutes<=1440 or not 0<=travel<=1440: raise ValueError('Invalid duration')
    status=p.get('status','Planned')
    priority=p.get('priority','Normal')
    if status not in ('Planned','In progress','Completed','Postponed') or priority not in ('Normal','High','Urgent'): raise ValueError('Invalid status')
    return (name,str(p.get('detail','')),day,minutes,start,finish,str(p.get('comments','')),str(p.get('customer','')),str(p.get('location','')),status,priority,travel)
@app.route('/api/tasks',methods=['POST'])
@app.route('/api/tasks/<int:id>',methods=['PUT','DELETE'])
@protected
def save(id=None):
    with db() as c:
        if request.method=='DELETE':
            if not c.execute('DELETE FROM tasks WHERE id=?',(id,)).rowcount: abort(404)
        else:
            try: v=validate(request.get_json())
            except (ValueError,TypeError,KeyError,OverflowError): return jsonify(error='Check task date, name and duration'),400
            if id is None:
                id=c.execute('INSERT INTO tasks(name,detail,day,minutes,start,finish,comments,customer,location,status,priority,travel) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',v).lastrowid
            elif not c.execute('UPDATE tasks SET name=?,detail=?,day=?,minutes=?,start=?,finish=?,comments=?,customer=?,location=?,status=?,priority=?,travel=? WHERE id=?',(*v,id)).rowcount: abort(404)
    return jsonify(id=id)
@app.get('/api/export')
@protected
def export():
    with db() as c: rows=c.execute('SELECT * FROM tasks').fetchall()
    out=io.StringIO(); w=csv.writer(out)
    w.writerow(['id','name','detail','day','minutes','start','finish','comments','customer','location','status','priority','travel'])
    for r in rows: w.writerow([("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for v in r])
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=work-planner.csv'})
