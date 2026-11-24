import io,queue,threading,unittest
from types import SimpleNamespace
from unittest.mock import patch
from dashboard import TkDashboard
from voice_interface import KeyboardVoiceInterface
class Widget:
    def __init__(self,parent=None,**kw):
        self.children=[];self.value='';self.kw=kw
        if parent:parent.children.append(self)
    def pack(self,**kw):pass
    def destroy(self):pass
    def winfo_children(self):return self.children[:]
    def insert(self,index,value):self.value+=value
    def get(self):return self.value
    def delete(self,first,last):self.value=self.value[:int(first)]
    def config(self,**kw):self.kw.update(kw)
    def bind(self,*args):pass
    def focus_set(self):pass

def find(parent,text):
    for c in reversed(parent.children):
        if c.kw.get('text')==text:return c
        result=find(c,text)
        if result:return result
class TouchTests(unittest.TestCase):
    def setup_dialog(self):
        app=TkDashboard.__new__(TkDashboard)
        app.tk=SimpleNamespace(Frame=Widget,Label=Widget,Button=Widget,Entry=Widget)
        w=Widget();app.modal=w;app.dialog=lambda title:w
        e=threading.Event();app.news_dialog(e);return app,w,e
    def test_search(self):
        app,w,e=self.setup_dialog()
        find(w,'Search').kw['command']();self.assertFalse(e.is_set())
        find(w,'Find news').kw['command']();self.assertFalse(e.is_set())
        for c in 'tampa':find(w,c).kw['command']()
        find(w,'Space').kw['command']();find(w,'x').kw['command']()
        find(w,'Delete').kw['command']();find(w,'Find news').kw['command']()
        self.assertEqual(app.news_choice,'tampa');self.assertTrue(e.is_set())
    def test_hot_topics(self):
        app,w,e=self.setup_dialog();find(w,'Hot topics').kw['command']()
        self.assertEqual(app.news_choice,'');self.assertTrue(e.is_set())
    def test_cancel(self):
        app,w,e=self.setup_dialog();find(w,'Search').kw['command']();find(w,'Cancel').kw['command']()
        self.assertIsNone(app.news_choice);self.assertTrue(e.is_set())
    def test_eof(self):
        for exits in (False,True):
            v=KeyboardVoiceInterface.__new__(KeyboardVoiceInterface);v.exit_on_eof=exits;v.lines=queue.Queue()
            with patch('sys.stdin',io.StringIO('')):v._reader()
            self.assertEqual(v.lines.empty(),not exits)
