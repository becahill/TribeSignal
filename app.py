"""Offline William & Mary campus explorer. Run: python app.py"""
from __future__ import annotations

import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent
GREEN = '#123F34'
GOLD = '#C5A45B'
PAPER = '#F5F3EC'
INK = '#203D35'
MUTED = '#68786F'
CATEGORIES = ['All locations', 'Academic', 'Services & dining',
              'Athletics & recreation', 'Arts & events', 'Student housing']
COLORS = dict(zip(CATEGORIES[1:], ['#CA624C', '#249BA4', '#62873C', '#195444', '#B08944']))


class CampusMap(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('William & Mary | Campus Explorer')
        self.geometry('1360x900')
        self.minsize(1050, 740)
        self.configure(fg_color=PAPER)
        self.source = Image.open(ROOT / 'assets/campus_map.png').convert('RGB')
        self.locations = json.loads((ROOT / 'assets/locations.json').read_text(encoding='utf-8'))
        self.visible = self.locations[:]
        self.selected = None
        self.scale = 1.0
        self.min_scale = 0.1
        self.ox = self.oy = 0.0
        self.started = False
        self.draw_job = None
        self.search_job = None
        self.drag_start = None
        self.dragged = False
        self.buttons = {}
        self.query = tk.StringVar()
        self.category = tk.StringVar(value=CATEGORIES[0])
        self.show_markers = tk.BooleanVar(value=False)
        self.build_ui()
        self.query.trace_add('write', self.queue_filter)
        self.filter_locations()
        self.bind('<Control-f>', lambda e: self.search.focus_set())
        self.bind('<Escape>', lambda e: self.reset_filters())
        self.protocol('WM_DELETE_WINDOW', self.close)

    def build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, height=86, corner_radius=0, fg_color=GREEN)
        header.grid(row=0, column=0, columnspan=2, sticky='ew')
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text='W&M', font=('Georgia', 30, 'bold'), text_color=GOLD).grid(row=0, column=0, padx=(26, 22), pady=22)
        ctk.CTkLabel(header, text='CAMPUS EXPLORER', font=('Arial', 19, 'bold'), text_color='white').grid(row=0, column=1, sticky='w')
        ctk.CTkLabel(header, text='WILLIAMSBURG, VIRGINIA  /  2026–2027', font=('Arial', 11), text_color='#D9E3DC').grid(row=0, column=2, padx=26)
        sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color='#FFFFFF')
        sidebar.grid(row=1, column=0, sticky='nsew')
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(5, weight=1)
        ctk.CTkLabel(sidebar, text='Find your place.', font=('Georgia', 26), text_color=INK, anchor='w').grid(row=0, column=0, sticky='ew', padx=22, pady=(24, 4))
        ctk.CTkLabel(sidebar, text='Explore 170 campus locations', text_color=MUTED, anchor='w').grid(row=1, column=0, sticky='ew', padx=22, pady=(0, 16))
        self.search = ctk.CTkEntry(sidebar, textvariable=self.query, placeholder_text='Search name, number or grid…', height=42, fg_color=PAPER, border_color='#DCE2DB', text_color=INK)
        self.search.grid(row=2, column=0, sticky='ew', padx=20, pady=(0, 10))
        ctk.CTkOptionMenu(sidebar, values=CATEGORIES, variable=self.category, command=lambda _: self.filter_locations(), fg_color=GREEN, button_color=GREEN, button_hover_color='#28624E', height=36).grid(row=3, column=0, sticky='ew', padx=20)
        self.count_label = ctk.CTkLabel(sidebar, text='', text_color=MUTED, anchor='w', font=('Arial', 11))
        self.count_label.grid(row=4, column=0, sticky='ew', padx=22, pady=(12, 4))
        self.results = ctk.CTkScrollableFrame(sidebar, fg_color='transparent', corner_radius=0)
        self.results.grid(row=5, column=0, sticky='nsew', padx=12)
        self.results.grid_columnconfigure(0, weight=1)
        detail = ctk.CTkFrame(sidebar, fg_color=PAPER, corner_radius=12)
        detail.grid(row=6, column=0, sticky='ew', padx=16, pady=16)
        self.detail_tag = ctk.CTkLabel(detail, text='EXPLORE THE CAMPUS', font=('Arial', 10, 'bold'), text_color=MUTED, anchor='w')
        self.detail_tag.pack(fill='x', padx=16, pady=(14, 4))
        self.detail_name = ctk.CTkLabel(detail, text='Start with a location', font=('Georgia', 21), text_color=INK, anchor='w', justify='left', wraplength=250)
        self.detail_name.pack(fill='x', padx=16)
        self.detail_meta = ctk.CTkLabel(detail, text='Select a result or click a building\nnumber on the map.', text_color=MUTED, anchor='w', justify='left', wraplength=248)
        self.detail_meta.pack(fill='x', padx=16, pady=(6, 12))
        self.focus_button = ctk.CTkButton(detail, text='Center on location', fg_color=GREEN, hover_color='#28624E', command=self.focus_selected, state='disabled')
        self.focus_button.pack(fill='x', padx=16, pady=(0, 14))
        body = ctk.CTkFrame(self, fg_color='transparent')
        body.grid(row=1, column=1, sticky='nsew', padx=18, pady=(16, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(body, fg_color='transparent')
        toolbar.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(toolbar, text='Campus map', font=('Georgia', 24), text_color=INK).grid(row=0, column=0, sticky='w')
        ctk.CTkSwitch(toolbar, text='Location dots', variable=self.show_markers, command=self.schedule_draw, progress_color=GREEN, text_color=INK, width=130).grid(row=0, column=1, padx=10)
        for col, label, command, width in [(2, '−', lambda: self.zoom(1/1.3), 36), (3, '+', lambda: self.zoom(1.3), 36), (4, 'Fit map', self.fit_map, 76)]:
            ctk.CTkButton(toolbar, text=label, width=width, height=34, fg_color=GREEN, hover_color='#28624E', command=command).grid(row=0, column=col, padx=3)
        self.canvas = tk.Canvas(body, bg='#E8E9DF', highlightthickness=0, cursor='hand2')
        self.canvas.grid(row=1, column=0, sticky='nsew')
        self.canvas.bind('<Configure>', self.resize)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Motion>', self.hover)
        self.canvas.bind('<Leave>', lambda _: self.status.configure(text=self.help_text()))
        self.canvas.bind('<MouseWheel>', self.wheel)
        self.canvas.bind('<Button-4>', lambda e: self.zoom(1.16, e.x, e.y))
        self.canvas.bind('<Button-5>', lambda e: self.zoom(1/1.16, e.x, e.y))
        self.status = ctk.CTkLabel(body, text=self.help_text(), text_color=MUTED, anchor='w', font=('Arial', 11))
        self.status.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        ctk.CTkLabel(body, text='Source: supplied William & Mary campus map • Inset locations retain their printed positions', text_color=MUTED, anchor='w', font=('Arial', 10)).grid(row=3, column=0, sticky='ew')

    @staticmethod
    def help_text():
        return 'Scroll to zoom  ·  Drag to pan  ·  Click a building number  ·  Ctrl+F to search'

    def queue_filter(self, *_):
        if self.search_job:
            self.after_cancel(self.search_job)
        self.search_job = self.after(160, self.filter_locations)

    def filter_locations(self):
        self.search_job = None
        query = self.query.get().strip().casefold()
        category = self.category.get()
        self.visible = [p for p in self.locations if (category == CATEGORIES[0] or p['category'] == category) and all(word in f"{p['name']} {p['id']} {p['grid']}".casefold() for word in query.split())]
        for child in self.results.winfo_children():
            child.destroy()
        self.buttons.clear()
        self.count_label.configure(text=f'{len(self.visible)} LOCATIONS' + ('  ·  FILTERED' if query or category != CATEGORIES[0] else ''))
        if not self.visible:
            ctk.CTkLabel(self.results, text='No locations found.\nTry a name, map number, or grid.', text_color=MUTED, justify='left').grid(row=0, column=0, pady=20)
        for i, p in enumerate(self.visible):
            # Wrap long names so the full directory remains readable.
            import textwrap
            label = '\n'.join(textwrap.wrap(p['name'], width=28))
            button = ctk.CTkButton(self.results, text=f"{label}\n#{p['id']}  ·  {p['grid']}", anchor='w', font=('Arial', 13), height=58 if '\n' not in label else 76, corner_radius=7, fg_color='#E4EBE3' if self.selected == p else 'transparent', text_color=INK, hover_color='#EDF1E9', command=lambda place=p: self.select(place))
            button.grid(row=i, column=0, sticky='ew', pady=2, padx=2)
            self.buttons[p['id']] = button
        self.results._parent_canvas.yview_moveto(0)
        self.schedule_draw()

    def reset_filters(self):
        self.category.set(CATEGORIES[0])
        self.query.set('')
        self.filter_locations()

    def select(self, place):
        old = self.selected
        self.selected = place
        if old and old['id'] in self.buttons:
            self.buttons[old['id']].configure(fg_color='transparent')
        if place['id'] in self.buttons:
            self.buttons[place['id']].configure(fg_color='#E4EBE3')
        self.detail_tag.configure(text=place['category'].upper(), text_color=COLORS[place['category']])
        self.detail_name.configure(text=place['name'].rstrip('*'))
        note = '\nUnder construction on source map.' if '*' in place['name'] else ''
        inset = '\nShown in a separate map inset.' if place['grid'].startswith('Ins') else ''
        self.detail_meta.configure(text=f"Map #{place['id']}   ·   Grid {place['grid']}{inset}{note}")
        self.focus_button.configure(state='normal')
        self.focus_selected()

    def focus_selected(self):
        if not self.selected:
            return
        self.scale = max(self.scale, self.min_scale * 2.7)
        self.ox = self.canvas.winfo_width()/2 - self.selected['x']*self.scale
        self.oy = self.canvas.winfo_height()/2 - self.selected['y']*self.scale
        self.schedule_draw()

    def resize(self, event):
        self.min_scale = min((event.width-20)/self.source.width, (event.height-20)/self.source.height)
        self.min_scale = max(.02, self.min_scale)
        if not self.started:
            self.started = True
            self.fit_map()
        else:
            self.scale = max(self.min_scale, self.scale)
            self.schedule_draw()

    def fit_map(self):
        self.scale = self.min_scale
        self.ox = (self.canvas.winfo_width() - self.source.width*self.scale)/2
        self.oy = (self.canvas.winfo_height() - self.source.height*self.scale)/2
        self.schedule_draw()

    def zoom(self, factor, x=None, y=None):
        x = self.canvas.winfo_width()/2 if x is None else x
        y = self.canvas.winfo_height()/2 if y is None else y
        new = min(max(self.scale*factor, self.min_scale), max(3.0, self.min_scale*8))
        ratio = new/self.scale
        self.ox = x-(x-self.ox)*ratio
        self.oy = y-(y-self.oy)*ratio
        self.scale = new
        self.schedule_draw()

    def wheel(self, event):
        if event.delta:
            self.zoom(1.16 if event.delta > 0 else 1/1.16, event.x, event.y)
        return 'break'

    def press(self, event):
        self.canvas.focus_set()
        self.drag_start = (event.x, event.y, self.ox, self.oy)
        self.dragged = False

    def drag(self, event):
        if self.drag_start:
            x, y, ox, oy = self.drag_start
            if math.hypot(event.x-x, event.y-y) > 4:
                self.dragged = True
            if self.dragged:
                self.ox, self.oy = ox+event.x-x, oy+event.y-y
                self.schedule_draw()

    def nearest(self, x, y):
        if not self.visible:
            return None
        place = min(self.visible, key=lambda p: math.hypot(p['x']*self.scale+self.ox-x, p['y']*self.scale+self.oy-y))
        distance = math.hypot(place['x']*self.scale+self.ox-x, place['y']*self.scale+self.oy-y)
        return place if distance < max(10, min(24, 16*self.scale)) else None

    def release(self, event):
        if not self.dragged:
            place = self.nearest(event.x, event.y)
            if place:
                self.select(place)
        self.drag_start = None

    def hover(self, event):
        place = self.nearest(event.x, event.y)
        self.status.configure(text=f"{place['name']}  ·  #{place['id']}  ·  {place['grid']}" if place else self.help_text())

    def schedule_draw(self):
        if not self.draw_job:
            self.draw_job = self.after(16, self.draw)

    def draw(self):
        self.draw_job = None
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width < 2 or height < 2:
            return
        # Render only the viewport: memory stays bounded at maximum zoom.
        viewport = self.source.transform((width, height), Image.Transform.AFFINE,
            (1/self.scale, 0, -self.ox/self.scale, 0, 1/self.scale, -self.oy/self.scale),
            resample=Image.Resampling.BILINEAR, fillcolor='#E8E9DF')
        self.photo = ImageTk.PhotoImage(viewport)
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, image=self.photo, anchor='nw')
        filtered = len(self.visible) != len(self.locations)
        if self.show_markers.get() or filtered:
            for p in self.visible:
                x, y = p['x']*self.scale+self.ox, p['y']*self.scale+self.oy
                if -10 < x < width+10 and -10 < y < height+10:
                    self.canvas.create_oval(x-5, y-5, x+5, y+5, fill=COLORS[p['category']], outline='white', width=1.5)
        if self.selected:
            p = self.selected
            x, y = p['x']*self.scale+self.ox, p['y']*self.scale+self.oy
            self.canvas.create_oval(x-16, y-16, x+16, y+16, outline='white', width=7)
            self.canvas.create_oval(x-16, y-16, x+16, y+16, outline=GREEN, width=3)
            text = self.canvas.create_text(x, y-32, text=p['name'].rstrip('*'), font=('Arial', 12, 'bold'), fill='white', width=240, anchor='s')
            bounds = self.canvas.bbox(text)
            if bounds:
                a,b,c,d = bounds
                box = self.canvas.create_rectangle(a-10,b-7,c+10,d+7,fill=GREEN,outline=GREEN)
                self.canvas.tag_raise(text, box)
        self.canvas.create_rectangle(width-78, height-31, width-8, height-8, fill=GREEN, outline=GREEN)
        self.canvas.create_text(width-43, height-20, text=f'{self.scale/self.min_scale:.1f}×', fill='white', font=('Arial', 11, 'bold'))

    def close(self):
        for job in (self.draw_job, self.search_job):
            if job:
                self.after_cancel(job)
        self.source.close()
        self.destroy()


if __name__ == '__main__':
    ctk.set_appearance_mode('light')
    ctk.set_default_color_theme('green')
    try:
        app = CampusMap()
    except (OSError, ValueError) as exc:
        messagebox.showerror('Campus Explorer', f'Could not load map assets. Keep the assets folder beside app.py.\n\n{exc}')
        raise SystemExit(1) from exc
    app.mainloop()
