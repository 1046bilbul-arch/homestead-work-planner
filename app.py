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
    if 'end_day' not in [r[1] for r in c.execute('PRAGMA table_info(tasks)')]:
        c.execute("ALTER TABLE tasks ADD COLUMN end_day TEXT DEFAULT ''")
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
    end_day=p.get('end_day') or day
    if end_day:
        date.fromisoformat(end_day)
        if not day or end_day < day: raise ValueError('Invalid date range')
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
    return (name,str(p.get('detail','')),day,minutes,start,finish,str(p.get('comments','')),str(p.get('customer','')),str(p.get('location','')),status,priority,travel,end_day)
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
                id=c.execute('INSERT INTO tasks(name,detail,day,minutes,start,finish,comments,customer,location,status,priority,travel,end_day) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',v).lastrowid
            elif not c.execute('UPDATE tasks SET name=?,detail=?,day=?,minutes=?,start=?,finish=?,comments=?,customer=?,location=?,status=?,priority=?,travel=?,end_day=? WHERE id=?',(*v,id)).rowcount: abort(404)
    return jsonify(id=id)
@app.get('/api/export')
@protected
def export():
    with db() as c: rows=c.execute('SELECT * FROM tasks').fetchall()
    out=io.StringIO(); w=csv.writer(out)
    w.writerow(['id','name','detail','day','minutes','start','finish','comments','customer','location','status','priority','travel','end_day'])
    for r in rows: w.writerow([("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for v in r])
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=work-planner.csv'})

@app.get('/api/calendar.pdf')
@protected
def calendar_pdf():
    from calendar import monthrange
    from datetime import timedelta
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, A3, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    try:
        d=date.fromisoformat(request.args.get('day',date.today().isoformat()))
    except ValueError:
        abort(400)
    monthly=request.args.get('period')=='month'
    full=request.args.get('detail','full')=='full'
    first=d.replace(day=1) if monthly else d-timedelta(days=d.weekday())
    count=monthrange(d.year,d.month)[1] if monthly else 7
    paper=A3 if request.args.get('paper')=='A3' else A4
    size=landscape(paper) if monthly else paper
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=size,rightMargin=32,leftMargin=32,topMargin=32,bottomMargin=36)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Job',fontSize=11,leading=15,spaceAfter=6))
    styles.add(ParagraphStyle(name='DayBlock',fontSize=12,leading=16,textColor=colors.white))
    def para(s,style='Job'):
        return Paragraph(escape(str(s)).replace('\\n','<br/>'),styles[style])
    with db() as c:
        rows=[dict(r) for r in c.execute("SELECT * FROM tasks WHERE day<>'' AND day<=? AND COALESCE(NULLIF(end_day,''),day)>=? ORDER BY day,start,id",(str(first+timedelta(days=count-1)),str(first)))]
    title=first.strftime('%B %Y') if monthly else first.strftime('%d %b %Y')+' – '+(first+timedelta(days=6)).strftime('%d %b %Y')
    story=[para('HOMESTEAD | WORK PLANNER','Title'),para(title,'Heading2')]
    for i in range(count):
        day=first+timedelta(days=i)
        heading=Table([[para(day.strftime('%A %d %B'),'DayBlock')]],colWidths=[doc.width])
        heading.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#303438')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        heading.keepWithNext=True
        story.append(heading)
        jobs=[r for r in rows if r['day']<=str(day)<=(r['end_day'] or r['day'])]
        if not jobs: story.append(para('No scheduled work'))
        for r in jobs:
            story.append(Paragraph('<b>'+escape(r['name'])+'</b>',styles['Job']))
            timing=(r['start']+' – '+r['finish']) if r['start'] else f"{r['minutes']/60:g} h"
            story.append(para(' | '.join(filter(None,[timing,r['customer'],r['location'],r['status'],r['priority']]))))
            if full:
                for label,k in [('Details','detail'),('Comments','comments')]:
                    if r[k]: story.append(para(label+': '+r[k]))
                if r['travel']: story.append(para(f"Travel: {r['travel']/60:g} h"))
            story.append(Spacer(1,5))
        story.append(Spacer(1,10))
    def footer(canvas,doc):
        canvas.setFont('Helvetica',9)
        canvas.drawString(32,20,'Homestead Smart Solutions | Simple. Control.')
        canvas.drawRightString(size[0]-32,20,str(doc.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return Response(out.getvalue(),mimetype='application/pdf',headers={'Content-Disposition':f'attachment; filename=planner-{first}.pdf'})
