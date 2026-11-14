import ctypes
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

user32 = ctypes.windll.user32
WM_KEYDOWN, WM_KEYUP = 0x100, 0x101
VK_TAB = 0x09
EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
MAX_INTERVAL = 10800.0  # 3 hours between key presses; NO run-time limit


def list_windows():
    result = []
    def visit(hwnd, unused):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n < 1:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        name = buf.value.strip()
        if name and 'Hominhtuan95' not in name:
            result.append((f'{name[:23]} [HWND:{int(hwnd)}]', int(hwnd)))
        return True
    user32.EnumWindows(EnumProc(visit), 0)
    return result


def send_key(hwnd, vk):
    if not user32.IsWindow(hwnd):
        return False
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 0xC0000001)
    return True


class Slot:
    def __init__(self, parent, index, app):
        self.app, self.index = app, index
        self.hwnd = None
        self.running = False
        self.stop_event = threading.Event()
        self.selection = tk.StringVar()
        self.status = tk.StringVar(value='Đã dừng')
        self.enabled = {}
        self.interval = {}
        self.frame = ttk.LabelFrame(parent, text=f'CỬA SỔ {index}', padding=4)
        self.frame.grid(row=(index - 1)//2, column=(index - 1)%2,
                        padx=3, pady=3, sticky='nsew')
        self.frame.columnconfigure(0, weight=1)
        self.combo = ttk.Combobox(self.frame, textvariable=self.selection,
                                  state='readonly', width=23)
        self.combo.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(0, 3))
        self.button = tk.Button(self.frame, text='▶ BẬT AUTO', command=self.toggle,
                                bg='#18834a', fg='white', relief='flat', height=1)
        self.button.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(0, 3))
        # Three columns, three rows: Tab and skills 1-8
        for j, (name, vk) in enumerate([('Tab', VK_TAB)] + [(str(i), 0x30+i) for i in range(1, 9)]):
            var = tk.BooleanVar(value=(name == 'Tab'))
            delay = tk.StringVar(value='3' if name == 'Tab' else '2')
            self.enabled[vk], self.interval[vk] = var, delay
            cell = ttk.Frame(self.frame)
            cell.grid(row=2+j//3, column=j%3, sticky='w', padx=1, pady=1)
            ttk.Checkbutton(cell, text=name, variable=var).pack(side='left')
            ttk.Entry(cell, textvariable=delay, width=4).pack(side='left')
            ttk.Label(cell, text='s').pack(side='left')
        ttk.Label(self.frame, textvariable=self.status, foreground='#25618a').grid(
            row=5, column=0, columnspan=3, sticky='w')

    def refresh(self, entries):
        if not self.running:
            labels = [label for label, _ in entries]
            self.combo['values'] = labels
            if self.selection.get() not in labels:
                self.selection.set('')

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        hwnd = dict(self.app.entries).get(self.selection.get())
        if hwnd is None or not user32.IsWindow(hwnd):
            messagebox.showwarning('Chưa chọn game', f'Chọn cửa sổ game cho ô {self.index}.')
            return
        if any(s.running and s.hwnd == hwnd for s in self.app.slots if s is not self):
            messagebox.showwarning('Trùng cửa sổ', 'Game này đang được điều khiển ở ô khác.')
            return
        schedule = {}
        for vk, enabled in self.enabled.items():
            if enabled.get():
                try:
                    interval = float(self.interval[vk].get().replace(',', '.'))
                    if not 0.1 <= interval <= MAX_INTERVAL:
                        raise ValueError
                except ValueError:
                    messagebox.showerror('Sai thời gian', 'Nhập từ 0,1 đến 10.800 giây (s).')
                    return
                schedule[vk] = interval
        if not schedule:
            messagebox.showwarning('Chưa chọn phím', 'Chọn Tab hoặc ít nhất một Skill.')
            return
        self.hwnd, self.running = hwnd, True
        self.stop_event = threading.Event()
        self.combo.config(state='disabled')
        self.button.config(text='■ TẮT AUTO', bg='#c63838')
        self.status.set('Đang chạy · không giới hạn')
        threading.Thread(target=self.worker, args=(hwnd, schedule, self.stop_event), daemon=True).start()

    def worker(self, hwnd, schedule, event):
        next_at = {vk: time.monotonic() for vk in schedule}
        while not event.is_set() and user32.IsWindow(hwnd):
            now = time.monotonic()
            for vk, interval in schedule.items():
                if event.is_set():
                    break
                if now >= next_at[vk]:
                    if not send_key(hwnd, vk):
                        event.set()
                        break
                    next_at[vk] = now + interval
            event.wait(0.04)
        try:
            self.app.root.after(0, lambda: self.finish(event))
        except RuntimeError:
            pass

    def finish(self, event):
        if self.stop_event is event:
            self.stop()

    def stop(self):
        self.stop_event.set()
        self.running = False
        self.hwnd = None
        self.combo.config(state='readonly')
        self.button.config(text='▶ BẬT AUTO', bg='#18834a')
        self.status.set('Đã dừng')


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Hominhtuan95 - Auto 8 cửa sổ')
        # 16 x 20 cm approximated at 96 DPI; OS scaling may change physical size.
        self.root.geometry('605x756')
        self.root.minsize(560, 540)
        self.root.configure(bg='white')
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('TFrame', background='white')
        style.configure('TLabelframe', background='white')
        style.configure('TLabelframe.Label', background='white', font=('Segoe UI', 9, 'bold'))
        style.configure('TCheckbutton', background='white', font=('Segoe UI', 8))
        style.configure('TLabel', background='white', font=('Segoe UI', 8))
        tk.Label(self.root, text='HOMINHTUAN95 | AUTO 8 CỬA SỔ', bg='white',
                 fg='#173b5b', font=('Segoe UI', 13, 'bold')).pack(pady=(5, 0))
        tk.Label(self.root, text='Skill 1–8 • Tab • Chu kỳ: giây (s) • Chạy không giới hạn',
                 bg='white', fg='#555', font=('Segoe UI', 9)).pack()
        ttk.Button(self.root, text='↻ Làm mới danh sách cửa sổ', command=self.refresh).pack(pady=3)
        container = ttk.Frame(self.root)
        container.pack(fill='both', expand=True, padx=4)
        canvas = tk.Canvas(container, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        board = ttk.Frame(canvas)
        board.columnconfigure(0, weight=1)
        board.columnconfigure(1, weight=1)
        window_id = canvas.create_window((0, 0), window=board, anchor='nw')
        board.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window_id, width=e.width))
        self.entries = []
        self.slots = [Slot(board, i, self) for i in range(1, 9)]
        tk.Label(self.root, text='Zalo: TuanHo | 0398438721', bg='white',
                 fg='#173b5b', font=('Segoe UI', 9, 'bold')).pack(pady=4)
        self.refresh()
        self.root.protocol('WM_DELETE_WINDOW', self.close)

    def refresh(self):
        self.entries = list_windows()
        for slot in self.slots:
            slot.refresh(self.entries)

    def close(self):
        for slot in self.slots:
            slot.stop_event.set()
        self.root.destroy()


if __name__ == '__main__':
    App().root.mainloop()
