import tkinter as tk
from tkinter import ttk
import win32gui
import win32con
import win32api
import pystray
from PIL import Image, ImageDraw
import threading

class CustomTestTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Custom Test Tool")
        self.root.geometry("400x450")
        
        # Handle window closing to properly exit tray
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)

        self.window_list = []
        self.selected_hwnd = None
        self.tray_icon = None

        # Frame for controls
        control_frame = ttk.Frame(root, padding="10")
        control_frame.pack(fill=tk.BOTH, expand=True)

        # Filter Frame
        filter_frame = ttk.Frame(control_frame)
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar(value="Chrome")
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var)
        self.filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.filter_entry.bind('<Return>', lambda e: self.refresh_list())

        # Refresh Button
        ttk.Button(control_frame, text="Refresh List", command=self.refresh_list).pack(pady=5)

        # Listbox for windows
        self.listbox = tk.Listbox(control_frame, height=10)
        self.listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)

        # Test Level Slider (Opacity)
        # Range 0-255, where 255 is fully opaque
        self.level_var = tk.IntVar(value=255)
        
        level_frame = ttk.Frame(control_frame)
        level_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(level_frame, text="Test Level:").pack(side=tk.LEFT)
        self.scale = ttk.Scale(level_frame, from_=0, to=255, variable=self.level_var, orient=tk.HORIZONTAL, command=self.update_level)
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Taskbar Visibility Checkbox
        self.taskbar_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="Show in Taskbar", variable=self.taskbar_var, command=self.toggle_taskbar).pack(pady=5)

        # Minimize to Tray Button
        ttk.Button(control_frame, text="Minimize to Tray", command=self.minimize_to_tray).pack(pady=5)

        # Developer Info
        ttk.Label(control_frame, text="developed by 부트띠", font=("Arial", 8), foreground="gray").pack(pady=(10, 0))
        
        self.refresh_list()

    def create_icon(self):
        # Create a simple icon dynamically
        width = 64
        height = 64
        color1 = "black"
        color2 = "white"
        image = Image.new('RGB', (width, height), color1)
        dc = ImageDraw.Draw(image)
        dc.rectangle((width // 2, 0, width, height // 2), fill=color2)
        dc.rectangle((0, height // 2, width // 2, height), fill=color2)
        return image

    def minimize_to_tray(self):
        self.root.withdraw()  # Hide the window
        image = self.create_icon()
        menu = (pystray.MenuItem('Restore', self.restore_from_tray, default=True),
                pystray.MenuItem('Quit', self.quit_app))
        self.tray_icon = pystray.Icon("name", image, "Custom Test Tool", menu)
        
        # Run tray icon in a separate thread to not block tkinter
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def restore_from_tray(self, icon, item):
        self.tray_icon.stop()
        self.root.after(0, self.root.deiconify) # Restore window on main thread

    def quit_app(self, icon, item):
        self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def on_closing(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        self.window_list = []
        filter_text = self.filter_var.get().lower()
        
        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    # print(f"Found window: {title}") # Debug print
                    if filter_text in title.lower():
                        self.window_list.append((title, hwnd))
                        self.listbox.insert(tk.END, title)
        
        win32gui.EnumWindows(enum_handler, None)

    def on_select(self, event):
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            self.selected_hwnd = self.window_list[index][1]
            # Reset slider to opaque when selecting new window, or try to get current alpha if possible
            # For simplicity, we'll just set it to current slider value or max
            self.update_level(self.level_var.get())
            
            # Update taskbar checkbox based on current state
            try:
                style = win32gui.GetWindowLong(self.selected_hwnd, win32con.GWL_EXSTYLE)
                # If TOOLWINDOW is set, it's hidden from taskbar (so Show = False)
                is_toolwindow = bool(style & win32con.WS_EX_TOOLWINDOW)
                self.taskbar_var.set(not is_toolwindow)
            except:
                self.taskbar_var.set(True)

    def toggle_taskbar(self):
        if self.selected_hwnd:
            try:
                hwnd = self.selected_hwnd
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                
                if self.taskbar_var.get():
                    # Show in taskbar: Remove TOOLWINDOW, Add APPWINDOW
                    new_style = (style & ~win32con.WS_EX_TOOLWINDOW) | win32con.WS_EX_APPWINDOW
                else:
                    # Hide from taskbar: Add TOOLWINDOW, Remove APPWINDOW
                    new_style = (style | win32con.WS_EX_TOOLWINDOW) & ~win32con.WS_EX_APPWINDOW
                
                # Need to hide/show to apply style change for taskbar
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            except Exception as e:
                print(f"Error toggling taskbar: {e}")

    def update_level(self, val):
        if self.selected_hwnd:
            try:
                level = int(float(val))
                hwnd = self.selected_hwnd
                
                # Get current window style
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                
                # Add WS_EX_LAYERED if not present
                if not (style & win32con.WS_EX_LAYERED):
                    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_LAYERED)
                
                # Set transparency (LWA_ALPHA = 0x2)
                win32gui.SetLayeredWindowAttributes(hwnd, 0, level, win32con.LWA_ALPHA)
            except Exception as e:
                print(f"Error updating level: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CustomTestTool(root)
    root.mainloop()
