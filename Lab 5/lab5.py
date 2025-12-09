import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import serial
import serial.tools.list_ports
import time
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import csv
import os
from datetime import datetime

class GSRMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Sensor Monitor - Real Time")
        self.root.geometry("1400x900")
        self.root.configure(bg="#fafafa")

        self.recording = False
        self.record_start_time = None
        self.csv_file = None
        self.csv_writer = None
        self.recorded_data = []

        self.PORT = None
        self.BAUDRATE = 115200
        self.CHANNEL = 'A0'
        self.ser = None

        self.x_data = deque(maxlen=1000)
        self.y_data = deque(maxlen=1000)
        self.counter = 0
        self.running = True

        self.visible_points = 500
        self.scroll_position = 0

        self.setup_styles()
        self.setup_ui()
        self.refresh_ports()
        self.start_serial_reading()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background="#fafafa", font=('Helvetica', 11))
        style.configure('TButton', font=('Helvetica', 11), padding=6)
        style.configure('TCombobox', font=('Helvetica', 11))
        style.configure('Header.TLabel', font=('Helvetica', 14, 'bold'), background="#e0e0e0")
        style.configure('Info.TLabel', font=('Helvetica', 11, 'italic'), background="#fafafa", foreground="#555555")

    def setup_ui(self):
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Левая панель настроек
        left_panel = ttk.Frame(self.root, padding=15, style='TFrame')
        left_panel.grid(row=0, column=0, sticky='ns')

        ttk.Label(left_panel, text="⚙️ Connection Settings", style='Header.TLabel', anchor='center').pack(fill=tk.X, pady=(0,10))
        self.setup_control_panel(left_panel)
        ttk.Separator(left_panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        ttk.Label(left_panel, text="💾 Data Recording", style='Header.TLabel', anchor='center').pack(fill=tk.X, pady=(0,10))
        self.setup_recording_panel(left_panel)

        # Правая панель с графиком и информацией
        right_panel = ttk.Frame(self.root, padding=10)
        right_panel.grid(row=0, column=1, sticky='nsew')
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        self.setup_info_panel(right_panel)
        self.setup_plot_with_scroll(right_panel)

        # Кнопка выхода внизу справа
        exit_btn = ttk.Button(right_panel, text="🚪 Exit", command=self.stop)
        exit_btn.grid(row=2, column=0, sticky='e', pady=10)

    def setup_control_panel(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X)

        ttk.Label(frame, text="Port:").pack(anchor='w', pady=3)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=20, state="readonly")
        self.port_combo.pack(fill=tk.X, pady=3)

        refresh_btn = ttk.Button(frame, text="🔄 Refresh Ports", command=self.refresh_ports)
        refresh_btn.pack(fill=tk.X, pady=5)

        ttk.Label(frame, text="Baudrate:").pack(anchor='w', pady=3)
        self.baudrate_var = tk.StringVar(value="115200")
        baudrates = ["9600", "19200", "38400", "57600", "115200"]
        self.baudrate_combo = ttk.Combobox(frame, textvariable=self.baudrate_var, values=baudrates,
                                           width=20, state="readonly")
        self.baudrate_combo.pack(fill=tk.X, pady=3)

        ttk.Label(frame, text="Channel:").pack(anchor='w', pady=3)
        self.channel_var = tk.StringVar(value="A0")
        channels = ["A0", "A1", "A2", "A3", "A4", "A5"]
        self.channel_combo = ttk.Combobox(frame, textvariable=self.channel_var, values=channels,
                                          width=20, state="readonly")
        self.channel_combo.pack(fill=tk.X, pady=3)

        self.connect_btn = ttk.Button(frame, text="🔌 Connect", command=self.toggle_connection)
        self.connect_btn.pack(fill=tk.X, pady=15)

    def setup_info_panel(self, parent):
        info_frame = ttk.Frame(parent, padding=(5, 5))
        info_frame.grid(row=0, column=0, sticky='ew')
        info_frame.columnconfigure(0, weight=1)
        info_frame.config(style='TFrame')

        self.status_var = tk.StringVar(value="🔌 Disconnected")
        status_label = ttk.Label(info_frame, textvariable=self.status_var, foreground="red")
        status_label.grid(row=0, column=0, sticky='w', padx=5)

        self.counter_var = tk.StringVar(value="📊 Data points: 0")
        counter_label = ttk.Label(info_frame, textvariable=self.counter_var)
        counter_label.grid(row=0, column=1, sticky='w', padx=10)

        self.value_var = tk.StringVar(value="🎯 Current value: --")
        value_label = ttk.Label(info_frame, textvariable=self.value_var)
        value_label.grid(row=0, column=2, sticky='w', padx=10)

        self.record_status_var = tk.StringVar(value="🔴 Recording: OFF")
        record_status_label = ttk.Label(info_frame, textvariable=self.record_status_var, foreground="red")
        record_status_label.grid(row=0, column=3, sticky='e', padx=5)

    def setup_plot_with_scroll(self, parent):
        plot_frame = ttk.LabelFrame(parent, text="📈 Real-time Data with Scroll", padding=10)
        plot_frame.grid(row=1, column=0, sticky='nsew', pady=10)
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)

        graph_scroll_frame = ttk.Frame(plot_frame)
        graph_scroll_frame.grid(row=0, column=0, sticky='nsew')
        graph_scroll_frame.columnconfigure(0, weight=1)

        self.fig, self.ax = plt.subplots(figsize=(12, 5))
        self.ax.set_facecolor('#fefefe')
        self.fig.patch.set_facecolor('#f9f9f9')

        self.ax.set_ylim(0, 300)
        self.ax.set_xlim(0, self.visible_points)
        self.ax.set_title(f'Sensor Data - Channel {self.channel_var.get()} (Scroll to navigate)', fontsize=14, pad=20)
        self.ax.set_xlabel('Time (samples)', fontsize=12)
        self.ax.set_ylabel('Sensor Value', fontsize=12)
        self.ax.grid(True, alpha=0.3, linestyle='--')

        self.line, = self.ax.plot([], [], 'teal', linewidth=2, alpha=0.8)

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_scroll_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')

        scroll_frame = ttk.Frame(graph_scroll_frame)
        scroll_frame.grid(row=0, column=1, sticky='ns', padx=5)

        ttk.Label(scroll_frame, text="Scroll:", font=("Helvetica", 10)).pack(pady=(0, 8))

        self.scroll_var = tk.IntVar(value=0)
        self.scrollbar = ttk.Scale(scroll_frame,
                                   from_=0,
                                   to=100,
                                   orient=tk.VERTICAL,
                                   variable=self.scroll_var,
                                   command=self.on_scroll,
                                   length=300)
        self.scrollbar.pack()

        scroll_buttons_frame = ttk.Frame(scroll_frame)
        scroll_buttons_frame.pack(pady=10)

        ttk.Button(scroll_buttons_frame, text="⬆️", width=4,
                   command=self.scroll_up).pack(pady=2)
        ttk.Button(scroll_buttons_frame, text="⬇️", width=4,
                   command=self.scroll_down).pack(pady=2)
        ttk.Button(scroll_buttons_frame, text="🎯", width=4,
                   command=self.scroll_to_latest).pack(pady=2)

        self.scroll_info_var = tk.StringVar(value="Viewing: latest data")
        scroll_info_label = ttk.Label(scroll_frame, textvariable=self.scroll_info_var,
                                      font=("Helvetica", 9), foreground="#666666")
        scroll_info_label.pack(pady=5)

    def setup_recording_panel(self, parent):
        record_frame = ttk.Frame(parent)
        record_frame.pack(fill=tk.X, pady=5)

        ttk.Label(record_frame,
                  text="1. Connect → 2. Set save path → 3. Start recording",
                  font=("Helvetica", 9), foreground="#444").pack(anchor='w', pady=5)

        path_row = ttk.Frame(record_frame)
        path_row.pack(fill=tk.X, pady=5)

        ttk.Label(path_row, text="Save to:", width=7).pack(side=tk.LEFT)
        self.path_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "sensor_data.csv"))
        path_entry = ttk.Entry(path_row, textvariable=self.path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5,5))

        ttk.Button(path_row, text="📁 Browse", command=self.browse_save_path).pack(side=tk.RIGHT)

        button_row = ttk.Frame(record_frame)
        button_row.pack(fill=tk.X, pady=10)

        self.start_record_btn = ttk.Button(button_row, text="⏺️ START Recording",
                                           command=self.start_recording,
                                           state="disabled")
        self.start_record_btn.pack(side=tk.LEFT, padx=5)

        self.stop_record_btn = ttk.Button(button_row, text="⏹️ STOP Recording",
                                          command=self.stop_recording,
                                          state="disabled")
        self.stop_record_btn.pack(side=tk.LEFT, padx=5)

        self.record_info_var = tk.StringVar(value="No active recording")
        record_info_label = ttk.Label(record_frame, textvariable=self.record_info_var,
                                      font=("Helvetica", 9), foreground="#0066cc")
        record_info_label.pack(anchor='w')

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.port_combo['values'] = port_list
        if port_list and not self.port_var.get():
            self.port_var.set(port_list[0])

    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        if not self.port_var.get():
            messagebox.showerror("Error", "Please select a port")
            return
        try:
            self.PORT = self.port_var.get()
            self.BAUDRATE = int(self.baudrate_var.get())
            self.CHANNEL = self.channel_var.get()
            self.ser = serial.Serial(self.PORT, self.BAUDRATE, timeout=1)
            time.sleep(2)
            self.ser.reset_input_buffer()
            self.status_var.set("✅ Connected to " + self.PORT)
            self.connect_btn.config(text="🔌 Disconnect")
            self.start_record_btn.config(state="normal")
            self.record_info_var.set("Ready to record! Click 'START Recording'")
            self.ax.set_title(f'Sensor Data - Channel {self.CHANNEL} (Scroll to navigate)', fontsize=14, pad=20)
            self.canvas.draw()
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {e}")
            self.status_var.set("❌ Connection failed")

    def disconnect_serial(self):
        if self.recording:
            self.stop_recording()
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.status_var.set("🔌 Disconnected")
        self.connect_btn.config(text="🔌 Connect")
        self.start_record_btn.config(state="disabled")
        self.stop_record_btn.config(state="disabled")
        self.record_info_var.set("Connect to device to enable recording")

    def start_serial_reading(self):
        def read_from_serial():
            while self.running:
                if self.ser and self.ser.is_open and self.ser.in_waiting >= 3:
                    try:
                        byte1 = self.ser.read(1)
                        byte2 = self.ser.read(1)
                        expected_bytes = self.CHANNEL.encode('utf-8')
                        if byte1 == expected_bytes[0:1] and byte2 == expected_bytes[1:2]:
                            value_byte = self.ser.read(1)
                            sensor_value = ord(value_byte)
                            timestamp = time.time()
                            self.x_data.append(self.counter)
                            self.y_data.append(sensor_value)
                            self.counter += 1
                            if self.scroll_position >= len(self.x_data) - self.visible_points - 10:
                                self.scroll_to_latest()
                            if self.recording:
                                elapsed = time.time() - self.record_start_time
                                self.recorded_data.append({'timestamp': timestamp, 'value': sensor_value, 'counter': self.counter})
                                if self.csv_writer:
                                    self.csv_writer.writerow([timestamp, sensor_value, self.counter, self.CHANNEL])
                                    self.record_info_var.set(f"Recording... {len(self.recorded_data)} points | Elapsed: {elapsed:.1f}s")
                            self.root.after(0, self.update_display, sensor_value)
                    except Exception as e:
                        self.root.after(0, lambda: self.status_var.set(f"Read error: {e}"))
                time.sleep(0.001)

        self.serial_thread = threading.Thread(target=read_from_serial, daemon=True)
        self.serial_thread.start()

    def update_display(self, value):
        if self.x_data and self.y_data:
            self.update_plot_view()
            self.counter_var.set(f"📊 Data points: {self.counter}")
            self.value_var.set(f"🎯 Current value: {value}")

    def browse_save_path(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save recording as...",
            initialfile=f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if filename:
            self.path_var.set(filename)
            if self.ser and self.ser.is_open:
                self.record_info_var.set(f"Will save to: {os.path.basename(filename)}")

    def start_recording(self):
        if not self.ser or not self.ser.is_open:
            messagebox.showerror("Error", "Not connected to any device")
            return
        if not self.path_var.get():
            messagebox.showerror("Error", "Please select a save path first")
            return
        try:
            self.csv_file = open(self.path_var.get(), 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(['timestamp', 'value', 'counter', 'channel'])
            self.recording = True
            self.record_start_time = time.time()
            self.recorded_data = []
            self.record_status_var.set("🟢 Recording: ON")
            self.start_record_btn.config(state="disabled")
            self.stop_record_btn.config(state="normal")
            self.record_info_var.set(f"Recording started! Saving to: {os.path.basename(self.path_var.get())}")
            messagebox.showinfo("Recording Started", f"Data recording started!\nFile: {self.path_var.get()}\nData will be saved in real-time.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recording: {e}")

    def stop_recording(self):
        if self.recording:
            self.recording = False
            if self.csv_file:
                self.csv_file.close()
                self.csv_file = None
                self.csv_writer = None
            duration = time.time() - self.record_start_time
            data_points = len(self.recorded_data)
            self.record_status_var.set("🔴 Recording: OFF")
            self.start_record_btn.config(state="normal")
            self.stop_record_btn.config(state="disabled")
            self.record_info_var.set(f"Recording saved! {data_points} points | Duration: {duration:.1f}s | File: {os.path.basename(self.path_var.get())}")
            messagebox.showinfo("Recording Stopped", f"Recording completed!\n\n📊 Data points: {data_points}\n⏱️ Duration: {duration:.1f} seconds\n📁 File: {self.path_var.get()}\n📈 Average rate: {data_points / duration:.1f} points/second")

    def clear_plot(self):
        self.x_data.clear()
        self.y_data.clear()
        self.counter = 0
        self.scroll_position = 0
        self.scroll_var.set(0)
        self.line.set_data([], [])
        self.ax.set_xlim(0, self.visible_points)
        self.canvas.draw()
        self.counter_var.set("📊 Data points: 0")
        self.value_var.set("🎯 Current value: --")
        self.scroll_info_var.set("Viewing: latest data")

    def stop(self):
        if self.recording:
            self.stop_recording()
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.quit()
        self.root.destroy()

    def on_scroll(self, value):
        if len(self.x_data) > self.visible_points:
            max_scroll = len(self.x_data) - self.visible_points
            self.scroll_position = int(float(value) / 100 * max_scroll)
            self.update_plot_view()

    def scroll_up(self):
        if self.scroll_position > 0:
            self.scroll_position -= 10
            if self.scroll_position < 0:
                self.scroll_position = 0
            self.update_scrollbar_position()
            self.update_plot_view()

    def scroll_down(self):
        max_scroll = max(0, len(self.x_data) - self.visible_points)
        if self.scroll_position < max_scroll:
            self.scroll_position += 10
            if self.scroll_position > max_scroll:
                self.scroll_position = max_scroll
            self.update_scrollbar_position()
            self.update_plot_view()

    def scroll_to_latest(self):
        self.scroll_position = max(0, len(self.x_data) - self.visible_points)
        self.update_scrollbar_position()
        self.update_plot_view()

    def update_scrollbar_position(self):
        max_scroll = max(1, len(self.x_data) - self.visible_points)
        if max_scroll > 0:
            scroll_percentage = (self.scroll_position / max_scroll) * 100
            self.scroll_var.set(scroll_percentage)

    def update_plot_view(self):
        if len(self.x_data) > 0:
            start_idx = self.scroll_position
            end_idx = start_idx + self.visible_points

            if len(self.x_data) >= end_idx:
                x_view = list(self.x_data)[start_idx:end_idx]
                y_view = list(self.y_data)[start_idx:end_idx]
            else:
                x_view = list(self.x_data)
                y_view = list(self.y_data)

            self.line.set_data(x_view, y_view)
            self.ax.set_xlim(start_idx, end_idx)

            total_points = len(self.x_data)
            if total_points > self.visible_points:
                view_info = f"Viewing: {start_idx}-{min(end_idx, total_points)} of {total_points}"
                if end_idx >= total_points:
                    view_info += " (LATEST)"
            else:
                view_info = "Viewing: all data"

            self.scroll_info_var.set(view_info)
            self.canvas.draw_idle()


def main():
    root = tk.Tk()
    app = GSRMonitor(root)
    root.protocol("WM_DELETE_WINDOW", app.stop)
    root.mainloop()

if __name__ == "__main__":
    main()
