import tkinter as tk
from tkinter import ttk
import win32gui
import win32con
import win32api

class CustomTestTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Custom Test Tool")
        self.root.geometry("400x300")

        self.window_list = []
        self.selected_hwnd = None

        # Frame for controls
        control_frame = ttk.Frame(root, padding="10")
        control_frame.pack(fill=tk.BOTH, expand=True)

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
        
        # Developer Info
        ttk.Label(control_frame, text="developed by 부트띠", font=("Arial", 8), foreground="gray").pack(pady=(20, 0))
        
        self.refresh_list()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        self.window_list = []
        
        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    print(f"Found window: {title}") # Debug print
                if "Chrome" in title: # Relaxed filter
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
