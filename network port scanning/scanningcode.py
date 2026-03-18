# Based on your original file :contentReference[oaicite:0]{index=0}

import socket
import threading
import time
import queue
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ---------------------------
# Common Services
# ---------------------------
PORT_SERVICES = {
    21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP', 53: 'DNS',
    80: 'HTTP', 110: 'POP3', 143: 'IMAP', 443: 'HTTPS',
    3306: 'MySQL', 3389: 'RDP', 5900: 'VNC', 8080: 'HTTP-Alt'
}

# ---------------------------
# Scanner Class
# ---------------------------
class ScannerCore:
    def __init__(self, target, start, end, timeout=0.5, threads=300):
        self.target = target
        self.start = start
        self.end = end
        self.timeout = timeout
        self.threads = threads

        self.stop_flag = threading.Event()
        self.total = max(0, end - start + 1)
        self.done = 0
        self.results = []

        self.lock = threading.Lock()
        self.queue = queue.Queue()

    def stop(self):
        self.stop_flag.set()

    def scan_single(self, port):
        if self.stop_flag.is_set():
            return

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            res = sock.connect_ex((self.target, port))

            if res == 0:
                service = PORT_SERVICES.get(port, "Unknown")
                with self.lock:
                    self.results.append((port, service))
                self.queue.put(("open", port, service))

            sock.close()

        except Exception as e:
            self.queue.put(("error", port, str(e)))

        finally:
            with self.lock:
                self.done += 1
            self.queue.put(("progress", self.done, self.total))

    def run(self):
        sem = threading.Semaphore(self.threads)
        workers = []

        for p in range(self.start, self.end + 1):
            if self.stop_flag.is_set():
                break

            sem.acquire()
            t = threading.Thread(target=self.worker, args=(sem, p), daemon=True)
            workers.append(t)
            t.start()

        for t in workers:
            t.join()

        self.queue.put(("done", None, None))

    def worker(self, sem, port):
        try:
            self.scan_single(port)
        finally:
            sem.release()

    def resolve(self):
        return socket.gethostbyname(self.target)


# ---------------------------
# GUI
# ---------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Custom Port Scanner")
        self.geometry("720x520")

        self.core = None
        self.thread = None
        self.start_time = None

        self.build_ui()

    def build_ui(self):
        frame = ttk.LabelFrame(self, text="Settings")
        frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(frame, text="Target:").grid(row=0, column=0)
        self.target = ttk.Entry(frame)
        self.target.grid(row=0, column=1)

        ttk.Label(frame, text="Start Port:").grid(row=0, column=2)
        self.start = ttk.Entry(frame)
        self.start.insert(0, "1")
        self.start.grid(row=0, column=3)

        ttk.Label(frame, text="End Port:").grid(row=0, column=4)
        self.end = ttk.Entry(frame)
        self.end.insert(0, "1024")
        self.end.grid(row=0, column=5)

        # NEW FEATURE: Scan Speed
        ttk.Label(frame, text="Speed:").grid(row=1, column=0)
        self.speed = ttk.Combobox(frame, values=["Fast", "Normal", "Slow"])
        self.speed.set("Normal")
        self.speed.grid(row=1, column=1)

        self.start_btn = ttk.Button(frame, text="Start", command=self.start_scan)
        self.start_btn.grid(row=1, column=4)

        self.stop_btn = ttk.Button(frame, text="Stop", command=self.stop_scan, state="disabled")
        self.stop_btn.grid(row=1, column=5)

        # Output
        self.text = tk.Text(self)
        self.text.pack(fill="both", expand=True, padx=10, pady=10)

        self.progress = ttk.Progressbar(self)
        self.progress.pack(fill="x", padx=10)

    def start_scan(self):
        target = self.target.get()

        try:
            start = int(self.start.get())
            end = int(self.end.get())
        except:
            messagebox.showerror("Error", "Invalid ports")
            return

        # Speed control
        speed = self.speed.get()
        if speed == "Fast":
            timeout, threads = 0.2, 500
        elif speed == "Slow":
            timeout, threads = 1, 100
        else:
            timeout, threads = 0.5, 300

        self.core = ScannerCore(target, start, end, timeout, threads)

        try:
            ip = self.core.resolve()
        except:
            messagebox.showerror("Error", "Invalid target")
            return

        self.text.insert(tk.END, f"Target: {target} ({ip})\n")
        self.text.insert(tk.END, f"Range: {start}-{end}\n")
        self.text.insert(tk.END, f"Started at: {time.ctime()}\n\n")

        self.start_time = time.time()

        self.thread = threading.Thread(target=self.core.run, daemon=True)
        self.thread.start()

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        self.after(50, self.update_ui)

    def stop_scan(self):
        if self.core:
            self.core.stop()

    def update_ui(self):
        try:
            while True:
                msg, a, b = self.core.queue.get_nowait()

                if msg == "open":
                    self.text.insert(tk.END, f"[OPEN] Port {a} ({b})\n")

                elif msg == "progress":
                    self.progress["maximum"] = b
                    self.progress["value"] = a

                elif msg == "done":
                    total_time = time.time() - self.start_time
                    self.text.insert(tk.END, "\nScan Finished\n")
                    self.text.insert(tk.END, f"Time Taken: {total_time:.2f}s\n")
                    self.text.insert(tk.END, f"Open Ports: {len(self.core.results)}\n")

                    self.start_btn.config(state="normal")
                    self.stop_btn.config(state="disabled")

        except queue.Empty:
            pass

        if self.thread and self.thread.is_alive():
            self.after(50, self.update_ui)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()