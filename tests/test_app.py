import os,tempfile,unittest
from werkzeug.security import generate_password_hash
tmp=tempfile.TemporaryDirectory()
os.environ.update(PLANNER_DB=tmp.name+'/test.sqlite',PLANNER_SECRET='test-only',PLANNER_USER='test',PLANNER_PASSWORD_HASH=generate_password_hash('test-password'))
from app import app
class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.c=app.test_client()
        self.base='https://localhost'
        r=self.c.post('/login',json={'username':'test','password':'test-password'},base_url=self.base)
        self.assertEqual(r.status_code,200)
        self.h={'X-CSRF-Token':r.json['csrf']}
    def test_crud(self):
        p={'name':'Job','day':'2026-11-20','hours':2,'travel':0}
        r=self.c.post('/api/tasks',json=p,headers=self.h,base_url=self.base)
        self.assertEqual(r.status_code,200)
        url='/api/tasks/'+str(r.json['id'])
        p.update(day='2026-11-21',start='07:00',finish='10:30')
        self.assertEqual(self.c.put(url,json=p,headers=self.h,base_url=self.base).status_code,200)
        rows=self.c.get('/api/tasks',base_url=self.base).json
        self.assertEqual(rows[-1]['minutes'],210)
        self.assertEqual(self.c.delete(url,headers=self.h,base_url=self.base).status_code,200)
    def test_security(self):
        self.assertEqual(app.test_client().get('/api/tasks',base_url=self.base).status_code,401)
        self.assertEqual(self.c.post('/api/tasks',json={},base_url=self.base).status_code,403)
    def test_invalid(self):
        self.assertEqual(self.c.post('/api/tasks',json={'name':'x','hours':-1},headers=self.h,base_url=self.base).status_code,400)
    def test_home(self):
        self.assertEqual(self.c.get('/',base_url=self.base).status_code,200)
if __name__=='__main__':unittest.main()
