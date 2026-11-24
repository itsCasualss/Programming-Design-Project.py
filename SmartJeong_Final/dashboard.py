"""Gunmetal residential dashboard. All Tk operations stay on the UI thread."""
import queue
import threading
from datetime import datetime
import math
from friendly_dates import date_label,time_label

BG,INK,MUTED,ACCENT,LINE='#0b1016','#eef4fa','#9baab9','#45c5ff','#334351'
SERVICES=[('01','Schedule','The day ahead'),('02','Pills','Your reminders'),('03','Weather','Outside, today'),('04','News','A wider perspective')]

def blend(a,b,t):
    return '#'+''.join(f'{round(int(a[i:i+2],16)*(1-t)+int(b[i:i+2],16)*t):02x}' for i in (1,3,5))

def selected_service(current,title,body,state):
    if state in ('idle','startup','prompt','listening'):
        return None
    candidate=body.strip().lower() if state=='processing' else title.lower().removeprefix('demo ').strip()
    return candidate if candidate in ('schedule','pills','weather','news') else current

class TkDashboard:
    def __init__(self,display,stop,box=None):
        import tkinter as tk
        self.tk,self.display,self.stop,self.box=tk,display,stop,box
        self.root=tk.Tk();self.root.title('SmartJeong | Home');self.root.geometry(f'{min(1280,self.root.winfo_screenwidth())}x{min(800,self.root.winfo_screenheight())}');self.root.minsize(480,320)
        self.root.attributes('-fullscreen',bool(display.config.get('fullscreen',False)))
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.root.bind('<F11>',lambda e:self.root.attributes('-fullscreen',not self.root.attributes('-fullscreen')))
        self.root.bind('<Escape>',lambda e:self.close())
        self.root.bind('<Return>',lambda e:self.submit(''))
        self.canvas=tk.Canvas(self.root,bg=BG,highlightthickness=0);self.canvas.pack(fill='both',expand=True)
        self.active_service=None;self.state_name='startup';self.title='';self.content='';self.fade=.28;self.modal=None
        self.requests=queue.Queue();self.pending_event=None;self.news_choice=None
        if box and box.voice.__class__.__name__ != 'ScriptedVoiceInterface':display.choose_news=self.choose_news
        self.body=tk.Text(self.root,bg='#101820',fg=INK,insertbackground=ACCENT,wrap='word',relief='flat',
            font=('DejaVu Sans',14),padx=18,pady=12,spacing3=9,highlightthickness=1,highlightbackground=LINE)
        self.body.configure(state='disabled')
        self.scroll=tk.Scrollbar(self.root,command=self.body.yview);self.body.configure(yscrollcommand=self.scroll.set)
        self.body.tag_config('link',foreground=ACCENT,underline=True)
        self.body.tag_bind('link','<Button-1>',self.open_link)
        self.canvas.bind('<Configure>',self.resize)
        self.canvas.bind('<Button-1>',self.click)
        self.width,self.height=self.root.winfo_screenwidth(),self.root.winfo_screenheight();self.background=None;self.hits=[]
        self.root.after(40,self.poll)

    def open_link(self,event):
        import webbrowser
        index=self.body.index('@%d,%d'%(event.x,event.y))
        for tag in self.body.tag_names(index):
            if tag.startswith('url:'):webbrowser.open(tag[4:]);break

    def resize(self,event):
        from PIL import Image,ImageTk
        self.width,self.height=event.width,event.height
        # Render a low-resolution gradient once per resize, never per animation frame.
        image=Image.new('RGB',(160,100));pixels=image.load()
        for y in range(100):
            for x in range(160):
                glow=max(0,1-math.hypot((x-30)/150,(y-5)/110))
                pixels[x,y]=(int(7+31*glow),int(11+34*glow),int(16+38*glow))
        self.background=ImageTk.PhotoImage(image.resize((self.width,self.height),Image.Resampling.BILINEAR))
        self.draw()

    def draw(self):
        c=self.canvas;c.delete('all');w,h=self.width,self.height
        if self.background:c.create_image(0,0,image=self.background,anchor='nw')
        pad=20 if h<650 else 48;compact=h<650 or w<1000
        now=datetime.now(self.display.zone)
        def text(x,y,value,size=12,color=INK,anchor='nw',**kw):
            c.create_text(x,y,text=value,font=('DejaVu Sans',size),fill=color,anchor=anchor,**kw)
        if self.state_name in ('output', 'error', 'processing'):
            text(pad,18,self.title or 'Your briefing',20,ACCENT,
                 width=max(180,w-2*pad-170))
            text(w-pad,20,time_label(now),18,anchor='ne')
            c.create_line(pad,62,w-pad,62,fill=LINE)
            bottom=h-46
            self.body.place(x=pad,y=76,width=w-2*pad-22,height=max(60,bottom-90))
            self.scroll.place(x=w-pad-22,y=76,width=22,height=max(60,bottom-90))
            text(pad,bottom,'Return home',12,ACCENT)
            text(w-pad,bottom,'Close',12,ACCENT,anchor='ne')
            if self.state_name == 'output' and self.box:
                listening = getattr(self.box.voice, 'result_listening', None)
                if listening is not None and listening.is_set():
                    text(w//2,bottom+10,'Listening: say “Home”',9,MUTED,anchor='center')
            self.hits=[(pad,bottom-8,pad+180,h,lambda:self.submit('')),
                       (w-pad-100,bottom-8,w-pad,h,self.close)]
            return
        text(pad,24,'S M A R T J E O N G',14,ACCENT)
        text(w-pad,18,time_label(now),24,anchor='ne')
        text(w-pad,56,date_label(now),11,MUTED,anchor='ne')
        c.create_line(pad,86,w-pad,86,fill=LINE)
        c.create_line(pad,86,pad+88,86,fill=ACCENT,width=2)
        text(pad,101,'HOME  /  PERSONAL BRIEFING',9,ACCENT)
        heading={'idle':'Say "Hey Jarvis" to Wake','startup':'Welcome home, Pwincess Jeong.',
          'prompt':'Pwincess Jeong, what would you like me to assist you with?', 'listening':'Pwincess Jeong, what would you like me to assist you with?',
          'processing':'Bringing your briefing together.', 'output':'Your briefing.', 'error':'Let’s try that again.'}.get(self.state_name,'Your briefing.')
        text(pad,124,heading,17 if compact else min(34,max(22,w//39)),width=w-2*pad)
        subtitle={'idle':'A quieter way to stay connected.','startup':'Preparing your home dashboard.',
            'prompt':'Schedule, pills, weather or news.','listening':'Choose a service below, or say its name.',
            'processing':'One moment.','output':'Stay a while. Enter or Return home dismisses this briefing.',
            'error':'Check the details below, then try again.'}.get(self.state_name,'')
        text(pad,184 if not compact else 181,subtitle,10 if compact else 12,MUTED)
        top=220 if not compact else 212;card_h=112 if not compact else 78;gap=14;cw=(w-2*pad-3*gap)/4
        self.hits=[]
        for i,(number,title,detail) in enumerate(SERVICES):
            x=pad+i*(cw+gap);color=blend('#151e28',INK,self.fade)
            selected=title.lower()==self.active_service
            c.create_rectangle(x,top,x+cw,top+card_h,fill='#163347' if selected else '#141d26',
                outline=ACCENT if selected else blend('#1c2834',ACCENT,self.fade*.48),width=2 if selected else 1)
            if selected:
                c.create_rectangle(x,top+card_h-3,x+cw,top+card_h,fill=ACCENT,outline='')
                text(x+cw-12,top+9,'ACTIVE',8,ACCENT,anchor='ne')
            c.create_line(x+1,top+1,x+cw-1,top+1,fill=blend('#1c2834',ACCENT,self.fade*.65))
            text(x+16,top+9,number,9,blend('#141d26',ACCENT,self.fade))
            text(x+16,top+(30 if compact else 37),title,15 if compact else 21,INK if selected else color)
            if not compact:text(x+16,top+79,detail,10,blend('#141d26',MUTED,self.fade))
            self.hits.append((x,top,x+cw,top+card_h,lambda name=title.lower():self.submit(name)))
        bottom=h-44
        actions=[('Wake / Return home',lambda:self.submit('')),('Add event',lambda:self.settings('calendar')),('Add reminder',lambda:self.settings('reminders')),('Close',self.close)]
        for i,(label,action) in enumerate(actions):
            step=(w-2*pad)/4;x=pad+i*step;text(x,bottom,label,9 if compact else 10,ACCENT);self.hits.append((x,bottom-5,x+step-4,bottom+25,action))
        text(w-pad,bottom-19,'KEYBOARD' if self.display.config.get('input_mode','keyboard')=='keyboard' else 'VOICE',9,MUTED,anchor='ne')
        if self.state_name in ('output','error','processing'):
            y=top+card_h+14;text(pad,y,self.title,12,ACCENT)
            self.body.place(x=pad,y=y+27,width=w-2*pad-16,height=max(40,bottom-y-42))
            self.scroll.place(x=w-pad-16,y=y+27,width=16,height=max(40,bottom-y-42))
        else:self.body.place_forget();self.scroll.place_forget()

    def click(self,event):
        for x,y,r,b,action in self.hits:
            if x<=event.x<=r and y<=event.y<=b:action();return

    def submit(self,value):
        if self.modal or not self.box or self.state_name != self.box.state:
            return
        state = self.state_name
        if not value and state == 'output':
            self.box.result_dismissed.set()
            return
        if state not in ('idle', 'prompt', 'listening') or (value and state == 'idle'):
            return
        if not value and state != 'idle':
            value = 'return home'
        submit_touch = getattr(self.box.voice, 'submit_touch', None)
        if submit_touch is not None:
            submit_touch(value)
        elif hasattr(self.box.voice, 'lines'):
            self.box.voice.lines.put(value)

    def render(self,title,body,state):
        self.active_service=selected_service(self.active_service,title,body,state)
        self.title,self.content,self.state_name=title,body,state
        self.body.config(state='normal');self.body.delete('1.0','end');self.body.insert('1.0',body)
        import re
        for match in re.finditer(r'https://\S+',body):
            start=f'1.0+{match.start()}c';end=f'1.0+{match.end()}c'
            self.body.tag_add('link',start,end);self.body.tag_add('url:'+match.group(),start,end)
        self.body.config(state='disabled');self.body.yview_moveto(0)

    def dialog(self,title):
        if self.modal:return None
        window=self.tk.Toplevel(self.root);window.title(title);window.configure(bg=BG)
        x=self.root.winfo_rootx()+max(0,(self.width-640)//2)
        y=self.root.winfo_rooty()+max(0,(self.height-440)//2)
        window.geometry(f'640x440+{x}+{y}');window.transient(self.root);window.wait_visibility();window.grab_set();self.modal=window
        window.bind('<Escape>',lambda e:self.dismiss())
        window.protocol('WM_DELETE_WINDOW',self.dismiss)
        return window

    def dismiss(self):
        if self.modal:self.modal.destroy();self.modal=None
        if self.pending_event:self.pending_event.set()

    def label(self,parent,text):
        widget=self.tk.Label(parent,text=text,bg=BG,fg=INK,font=('DejaVu Sans',12),wraplength=580,justify='left')
        widget.pack(anchor='w',padx=24,pady=8);return widget

    def entry(self,parent,label,value=''):
        self.label(parent,label)
        widget=self.tk.Entry(parent,bg='#1b2733',fg=INK,insertbackground=ACCENT,font=('DejaVu Sans',14),relief='flat')
        widget.pack(fill='x',padx=24,ipady=6);widget.insert(0,value);return widget

    def button(self,parent,label,action):
        self.tk.Button(parent,text=label,command=action,bg='#15364a',fg=INK,activebackground='#24536a',activeforeground=INK,
           relief='flat',font=('DejaVu Sans',12),padx=14,pady=7).pack(side='left',padx=8,pady=16)

    def choose_news(self):
        event=threading.Event();self.news_choice=None;self.requests.put(event)
        listen = getattr(self.box.voice, 'listen_for_news', None) if self.box else None
        if listen is not None:
            try:
                spoken = listen(event)
                if event.is_set():
                    return self.news_choice
                if spoken and not self.stop.is_set():
                    spoken = ' '.join(spoken.lower().split())
                    if spoken in ('cancel', 'return home', 'go home'):
                        return None
                    return '' if spoken == 'hot topics' else spoken
                while not self.stop.is_set() and not event.wait(.1):
                    self.display.tick()
                return self.news_choice
            finally:
                event.set()
        print('NEWS: type keywords here, ENTER for hot topics, or cancel. You can also use the screen.',flush=True)
        while not event.wait(.1):
            if self.stop.is_set():return None
            self.display.tick()
            if self.box and hasattr(self.box.voice,'lines'):
                try:
                    line=self.box.voice.lines.get_nowait()
                    if line is None or line=='q':self.stop.set();event.set();return None
                    self.news_choice=None if line=='cancel' else line
                    event.set()
                except queue.Empty:pass
        return self.news_choice

    def news_dialog(self,event):
        if event.is_set():return
        self.pending_event=event
        window=self.dialog('Your news')
        if window is None:event.set();return
        def finish(value):
            self.news_choice=value;self.dismiss();self.pending_event=None

        def keyboard(initial=''):
            # Keep the keyboard inside the modal so its grab does not block typing.
            for child in window.winfo_children(): child.destroy()
            self.label(window,'Search news')
            query=self.tk.Entry(window,bg='#1b2733',fg=INK,insertbackground=ACCENT,
                                font=('DejaVu Sans',16),relief='flat')
            query.pack(fill='x',padx=16,ipady=5);query.insert(0,initial)
            notice=self.tk.Label(window,text='Enter a topic, then tap Find news.',
                                 bg=BG,fg=MUTED,font=('DejaVu Sans',10))
            notice.pack(pady=4)
            keys=self.tk.Frame(window,bg=BG);keys.pack(fill='both',expand=True,padx=12)
            def press(value):
                query.insert('end',value)
            for row in ('1234567890','qwertyuiop','asdfghjkl','zxcvbnm'):
                line=self.tk.Frame(keys,bg=BG);line.pack(fill='both',expand=True)
                for char in row:
                    self.tk.Button(line,text=char,command=lambda c=char:press(c),
                        bg='#15364a',fg=INK,activebackground='#24536a',
                        activeforeground=INK,relief='flat',font=('DejaVu Sans',14),
                        takefocus=False).pack(side='left',fill='both',expand=True,padx=2,pady=2)
            def search():
                value=query.get().strip()
                if value:finish(value)
                else:notice.config(text='Enter a keyword first.')
            controls=self.tk.Frame(window,bg=BG);controls.pack(fill='x',padx=10)
            for label,action in [('Space',lambda:press(' ')),
                                 ('Delete',lambda:query.delete(max(0,len(query.get())-1),'end')),
                                 ('Find news',search),('Cancel',lambda:finish(None))]:
                self.tk.Button(controls,text=label,command=action,bg='#15364a',fg=INK,
                    font=('DejaVu Sans',12),relief='flat',pady=9).pack(
                    side='left',fill='x',expand=True,padx=3,pady=8)
            query.bind('<Return>',lambda e:(search(),'break')[1])
            query.focus_set()

        self.label(window,'YOUR NEWS  ·  UP TO THREE STORIES')
        if getattr(self, 'box', None) and hasattr(self.box.voice, 'listen_for_news'):
            self.label(window,'Say “Hot Topics,” your keywords, or “Cancel” within 12 seconds.')
        else:
            self.label(window,'Choose U.S. trends or search for a topic.')
        query=self.entry(window,'Keywords — for example: spaceflight or Tampa transit')
        self.label(window,'Search opens the touch keyboard. Results include publisher names and links.')
        actions=self.tk.Frame(window,bg=BG);actions.pack(padx=16)
        self.button(actions,'Hot topics',lambda:finish(''))
        self.button(actions,'Search',lambda:keyboard(query.get()))
        self.button(actions,'Cancel',lambda:finish(None))
        query.bind('<Return>',lambda e:(finish(query.get().strip()) if query.get().strip() else keyboard(),'break')[1])
        query.focus_set()

    def settings(self,kind):
        from tkinter import messagebox
        if self.state_name!='idle':
            messagebox.showinfo('Return home first','Return to the home screen before editing your schedule.',parent=self.root);return
        window=self.dialog('Add event' if kind=='calendar' else 'Add reminder')
        if window is None:return
        name=self.entry(window,'Event name' if kind=='calendar' else 'Reminder name')
        day=self.entry(window,'Date — month name, YYYY-MM-DD, today or tomorrow','today') if kind=='calendar' else None
        times=self.entry(window,'Time — e.g. 11:20 PM, 8am or 2320' if day else 'Daily times — e.g. 8am, 8:30 PM')
        notice=self.label(window,'You’ll review the converted date and time before saving.')
        def save():
            try:
                from personal_store import save_entry,preview_entry
                parsed,description=preview_entry(kind,name.get(),day.get() if day else '',times.get(),self.display.zone)
                if not messagebox.askokcancel('Confirm details',description,parent=window):return
                save_entry(kind,parsed)
                if self.box:
                    from config import load_config
                    fresh=load_config()
                    key = 'schedule' if kind == 'calendar' else 'pills'
                    self.box.services.config[key]=fresh[key]
                self.dismiss();messagebox.showinfo('Saved','Your entry is saved and ready to view.',parent=self.root)
            except (ValueError,OSError) as error:notice.config(text=str(error),fg='#ffb9ac')
        actions=self.tk.Frame(window,bg=BG);actions.pack(padx=16)
        self.button(actions,'Review & save',save);self.button(actions,'Cancel',self.dismiss)
        name.focus_set()

    def poll(self):
        if self.stop.is_set():self.close();return
        try:
            while True:self.render(*self.display.messages.get_nowait())
        except queue.Empty:pass
        if self.pending_event and self.pending_event.is_set():
            self.dismiss();self.pending_event=None
        try:self.news_dialog(self.requests.get_nowait())
        except queue.Empty:pass
        target=.28 if self.state_name in ('idle','startup') else 1
        self.fade+=max(-.06,min(.06,target-self.fade));self.draw();self.root.after(50,self.poll)

    def close(self):
        self.stop.set()
        if self.pending_event:self.pending_event.set()
        self.root.destroy()
    def run(self):self.root.mainloop()
