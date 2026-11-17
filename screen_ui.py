"""Local touchscreen client. Only the existing motor loop can apply mode changes."""
import json
import os
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import messagebox
from urllib.request import Request, urlopen

from network_status import NetworkStatus


def display_connected(root=Path('/sys/class/drm')):
    for status in root.glob('card*-*/status'):
        try:
            if status.read_text().strip() == 'connected':
                return True
        except OSError:
            continue
    return False


class Screen:
    def __init__(self, root):
        self.root = root
        self.base = os.environ.get('ROBOT_SCREEN_URL', 'http://127.0.0.1:8080').rstrip('/')
        self.frames = queue.Queue(maxsize=1)
        self.actions = queue.Queue(maxsize=4)
        self.closed = threading.Event()
        self.state = {}
        self.network_status = NetworkStatus()
        self.dump = 0
        self.extra_layout = None
        self.video_size = (640, 480)
        self.follow_size = (640, 480)
        self.follow_pressed = None
        root.title('YardBot')
        root.configure(bg='#111820')
        root.attributes('-fullscreen', True)
        root.bind('<Escape>', lambda event: root.attributes('-fullscreen', False))
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.title = tk.Label(root, text='YardBot · Connecting…', bg='#111820', fg='#76baff', font=('Sans', 20))
        self.title.pack(fill='x', pady=6)
        self.network_indicator = tk.Label(root, text='Network: Checking…', bg='#111820',
                                          fg='#b0bfce', font=('Sans', 14, 'bold'))
        self.network_indicator.pack(fill='x', pady=(0, 4))
        self.bar = tk.Frame(root, bg='#111820', height=56)
        self.bar.pack(side='bottom', fill='x', pady=(0, 8))
        self.bar.pack_propagate(False)
        self.buttons = {}
        for action, label in [('stop', 'STOP'), ('manual', 'Manual'), ('single', 'Single stick'), ('follow', 'Follow me')]:
            button = tk.Button(self.bar, text=label, command=lambda a=action: self.select(a),
                               font=('Sans', 15), bg='#b91f2b' if action == 'stop' else '#283d55',
                               fg='white', height=2)
            button.pack(side='left', fill='both', expand=True, padx=4)
            self.buttons[action] = button
        self.extra = tk.Frame(root, bg='#111820')
        self.system_buttons = {}
        for action, label in [('hotspot', 'Hotspot on/off'), ('wifi', 'Wi-Fi on/off'), ('shutdown', 'Shutdown')]:
            self.system_buttons[action] = tk.Button(
                self.extra, text=label, font=('Sans', 16), height=2,
                command=lambda a=action: self.select(a))
        self.shutdown = self.system_buttons['shutdown']
        self.dump_buttons = []
        for label, direction in [('Dump ↑\nHold to raise', -1), ('Dump ↓\nHold to lower', 1)]:
            button = tk.Button(self.extra, text=label, font=('Sans', 16), width=16, height=3,
                               bg='#283d55', fg='white', activebackground='#76baff')
            button.bind('<ButtonPress-1>', lambda event, d=direction: self.set_dump(d))
            button.bind('<ButtonRelease-1>', lambda event: self.set_dump(0))
            button.bind('<Leave>', lambda event: self.set_dump(0))
            self.dump_buttons.append(button)
        root.bind('<FocusOut>', lambda event: self.set_dump(0))
        self.video = tk.Label(root, text='Select a mode below', bg='#090f17', fg='white', font=('Sans', 18))
        self.video.pack(fill='both', expand=True, padx=6, pady=6)
        self.video.bind('<Configure>', lambda event: setattr(self, 'video_size', (max(1, event.width), max(1, event.height))))
        self.note = tk.Label(root, text='Hold Dump to move · Drive sticks require the controller', bg='#111820', fg='#b0bfce', wraplength=750)
        self.note.pack(side='bottom', fill='x', pady=4, before=self.video)
        threading.Thread(target=self.worker, daemon=True).start()
        self.follow_view = False
        self.follow_canvas = tk.Canvas(root, bg='#090f17', highlightthickness=0)
        self.follow_canvas.bind('<Configure>', self.resize_follow)
        self.follow_canvas.bind('<ButtonPress-1>', self.follow_press)
        self.follow_canvas.bind('<ButtonRelease-1>', self.follow_release)
        self.follow_canvas.bind('<Leave>', lambda event: setattr(self, 'follow_pressed', None))
        self.follow_image = self.follow_canvas.create_image(0, 0, anchor='center')
        self.render()

    def resize_follow(self, event):
        self.follow_size = (max(1, event.width), max(1, event.height))
        self.draw_follow_overlay()

    def draw_follow_overlay(self):
        canvas = self.follow_canvas
        width, height = self.follow_size
        canvas.coords(self.follow_image, width / 2, height / 2)
        canvas.delete('overlay')
        # Stipple leaves camera pixels visible through the gray control backgrounds.
        canvas.create_rectangle(0, 0, width, 34, fill='#333333', stipple='gray50',
                                outline='', tags='overlay')
        canvas.create_text(10, 17, anchor='w', text='YardBot · Follow me', fill='white',
                           font=('Sans', 13, 'bold'), tags='overlay')
        canvas.create_text(width - 10, 17, anchor='e', text=self.network_indicator.cget('text'),
                           fill=self.network_indicator.cget('fg'), font=('Sans', 12), tags='overlay')
        for index, (action, label) in enumerate([('stop', 'STOP'), ('manual', 'Manual'),
                                                ('single', 'Single stick'), ('follow', 'Follow me')]):
            tag = 'follow_' + action
            left, right = index * width / 4 + 4, (index + 1) * width / 4 - 4
            enabled = str(self.buttons[action].cget('state')) != 'disabled'
            canvas.create_rectangle(left, height - 64, right, height - 8, fill='#555555',
                                    stipple='gray50', outline='#aaaaaa', tags=('overlay', tag))
            canvas.create_text((left + right) / 2, height - 36, text=label,
                               fill='white' if enabled else '#888888', font=('Sans', 15, 'bold'),
                               tags=('overlay', tag))

    def follow_action_at(self, event):
        width, height = self.follow_size
        if not (height - 64 <= event.y <= height - 8 and 0 <= event.x < width):
            return None
        index = min(3, int(event.x * 4 / width))
        left, right = index * width / 4 + 4, (index + 1) * width / 4 - 4
        return ('stop', 'manual', 'single', 'follow')[index] if left <= event.x <= right else None

    def follow_press(self, event):
        self.follow_pressed = self.follow_action_at(event)

    def follow_release(self, event):
        action = self.follow_action_at(event)
        pressed, self.follow_pressed = self.follow_pressed, None
        if action is not None and action == pressed:
            self.buttons[action].invoke()

    def set_follow_view(self, enabled):
        if enabled == self.follow_view:
            return
        self.follow_view = enabled
        self.follow_pressed = None
        if enabled:
            self.follow_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self.root.tk.call('raise', self.follow_canvas._w)
        else:
            self.follow_canvas.place_forget()
            self.video_size = (max(1, self.video.winfo_width()), max(1, self.video.winfo_height()))

    def set_dump(self, direction):
        self.dump = direction if self.state.get('live') and self.state.get('mode') in ('manual', 'single') else 0

    def select(self, action):
        self.dump = 0
        if action == 'shutdown' and not messagebox.askyesno('Shutdown', 'Shut down the robot?', parent=self.root):
            return
        if action in ('hotspot', 'wifi') and not messagebox.askyesno(
                'Network controls',
                'Toggle ' + ('the hotspot' if action == 'hotspot' else 'Wi-Fi') + '? Remote connections may disconnect.',
                parent=self.root):
            return
        if action == 'follow' and not messagebox.askyesno('Follow me', 'Start following the detected person? The robot can move.', parent=self.root):
            return
        try:
            # Stop takes priority over queued selections.
            if action == 'stop':
                while not self.actions.empty():
                    self.actions.get_nowait()
            self.actions.put_nowait(action)
        except queue.Full:
            pass

    def fetch(self, path, data=None, token=''):
        headers = {'Origin': self.base, 'X-Robot-Control': token, 'Content-Type': 'application/json'}
        request = Request(self.base + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
        with urlopen(request, timeout=1.5) as response:
            return response.read()

    def worker(self):
        import cv2
        import numpy as np
        token = ''
        while not self.closed.is_set():
            state, ppm, error = {}, None, ''
            try:
                if not token:
                    page = self.fetch('/').decode()
                    token = re.search(r"window.robotControlToken='([^']+)'", page).group(1)
                if not self.actions.empty():
                    action = self.actions.get_nowait()
                    self.fetch('/api/action', {'action': action, 'confirmed': action in ('follow', 'shutdown', 'hotspot', 'wifi')}, token)
                state = json.loads(self.fetch('/api/status'))
                if state.get('live') and state.get('mode') in ('manual', 'single'):
                    self.fetch('/api/action', {'action': {1: 'dump_up', -1: 'dump_down', 0: 'dump_stop'}[self.dump]}, token)
                if state.get('live') and state.get('mode') == 'follow':
                    try:
                        jpeg = self.fetch('/camera.jpg')
                        image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if image is not None:
                            width, height = self.follow_size
                            scale = min(width / image.shape[1], height / image.shape[0])
                            image = cv2.resize(image, (max(1, round(image.shape[1] * scale)),
                                                       max(1, round(image.shape[0] * scale))))
                            # Tk supports PPM directly; no extra Pillow/Tk dependency.
                            ppm = cv2.imencode('.ppm', image)[1].tobytes()
                    except Exception:
                        error = 'Camera starting or unavailable'
            except Exception as exc:
                error = 'Connection/request failed: ' + str(exc)
                token = ''  # Refresh the CSRF token after a server restart.
            try:
                self.frames.get_nowait()
            except queue.Empty:
                pass
            self.frames.put((state, ppm, error))
            self.closed.wait(.2)

    def render(self):
        network_labels = {
            'hotspot': ('HOTSPOT ACTIVE', '#efc17b'),
            'off': ('WI-FI OFF', '#ff8e94'),
            'wifi': ('Wi-Fi connected', '#76baff'),
            'disconnected': ('Wi-Fi on · Not connected', '#efc17b'),
        }
        label, color = network_labels.get(self.network_status.snapshot(), ('Network status unavailable', '#b0bfce'))
        self.network_indicator.config(text=label, fg=color)
        try:
            state, ppm, error = self.frames.get_nowait()
            self.state = state
            live = state.get('live', False)
            mode = state.get('mode', 'stop')
            # Keep widgets mapped between polls so a press survives until release.
            layout = ('shutdown' if mode == 'stop' else 'dump'
                      if mode in ('manual', 'single') else None) if live else None
            if layout != self.extra_layout:
                for button in self.system_buttons.values():
                    button.pack_forget()
                for button in self.dump_buttons:
                    button.pack_forget()
                self.extra.pack_forget()
                if layout is not None:
                    self.extra.pack(side='bottom', fill='x', before=self.note)
                    if layout == 'shutdown':
                        for button in self.system_buttons.values():
                            button.pack(side='left', expand=True, fill='x', padx=4, pady=4)
                    else:
                        for button in self.dump_buttons:
                            button.pack(side='left', expand=True, padx=4, pady=4)
                self.extra_layout = layout
            system_ready = live and state.get('teleop_ready') and not state.get('system_action', {}).get('busy')
            for button in self.system_buttons.values():
                button.config(state='normal' if system_ready else 'disabled')
            if not live or mode not in ('manual', 'single'):
                self.dump = 0
            self.title.config(text='YardBot · ' + (state.get('mode', 'stop').replace('_', ' ').title() if live else 'Offline'))
            for action, button in self.buttons.items():
                ready = live and (action == 'stop' or state.get('teleop_ready'))
                if action == 'single':
                    ready = ready and state.get('connected')
                button.config(state='normal' if ready else 'disabled')
            self.set_follow_view(live and mode == 'follow')
            if ppm and live:
                self.photo = tk.PhotoImage(data=ppm, format='PPM')
                if self.follow_view:
                    self.follow_canvas.itemconfig(self.follow_image, image=self.photo)
                else:
                    self.video.config(image=self.photo, text='')
            else:
                self.video.config(image='', text=error or ('Waiting for camera…' if state.get('mode') == 'follow' else 'Select a mode below'))
                self.follow_canvas.itemconfig(self.follow_image, image='')
                self.photo = None
            if self.follow_view:
                self.draw_follow_overlay()
                if not ppm:
                    self.follow_canvas.create_text(self.follow_size[0] / 2, self.follow_size[1] / 2,
                                                   text=error or 'Waiting for camera…', fill='white',
                                                   font=('Sans', 18), tags='overlay')
            self.note.config(text=error or state.get('system_action', {}).get('message', '') or state.get('message', '') or 'Hold Dump to move · Drive sticks require the controller')
        except queue.Empty:
            pass
        self.root.after(100, self.render)

    def close(self):
        self.dump = 0
        self.closed.set()
        self.network_status.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    root.withdraw()
    screen = None

    def monitor():
        nonlocal screen
        if display_connected():
            if screen is None:
                screen = Screen(root)
            root.deiconify()
        else:
            root.withdraw()
        root.after(2000, monitor)

    monitor()
    root.mainloop()


if __name__ == '__main__':
    main()
