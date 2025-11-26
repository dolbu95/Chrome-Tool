import tkinter as tk
from tkinter import ttk, messagebox
import win32gui
import win32con
import win32api
import win32event
import pystray
from PIL import Image, ImageDraw
import threading
import time

class CustomTestTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Custom Test Tool")
        self.root.geometry("400x450")
        
        # Handle window closing to properly exit tray
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)
        
        # Handle minimize button - hide to tray instead
        self.root.bind('<Unmap>', self.on_minimize)
        self.minimizing_to_tray = False  # 트레이로 최소화 중인지 구분하기 위한 플래그

        self.window_list = []
        self.selected_hwnd = None
        self.tray_icon = None
        
        # Store opacity settings for each window (hwnd -> opacity value 0-255)
        self.window_opacity_settings = {}

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

        # Treeview for windows with status
        tree_frame = ttk.Frame(control_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure Treeview with columns
        self.tree = ttk.Treeview(tree_frame, columns=('transparency', 'taskbar'), show='tree headings', height=10, yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.tree.yview)
        
        # Column headers
        self.tree.heading('#0', text='Window Name')
        self.tree.heading('transparency', text='Opacity')
        self.tree.heading('taskbar', text='Taskbar')
        
        # Column widths
        self.tree.column('#0', width=200, minwidth=150)
        self.tree.column('transparency', width=80, minwidth=60, anchor='center')
        self.tree.column('taskbar', width=80, minwidth=60, anchor='center')
        
        self.tree.bind('<<TreeviewSelect>>', self.on_select)

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

    def on_minimize(self, event):
        """창 최소화 버튼 클릭 시 트레이로 숨기기"""
        # withdraw() 호출 시에도 Unmap 이벤트가 발생하므로 플래그로 구분
        if event.widget == self.root and not self.minimizing_to_tray:
            # 사용자가 최소화 버튼을 누른 경우
            if self.root.state() == 'iconic':
                # 이미 최소화된 상태라면 트레이로 숨기기
                self.root.after(10, self.minimize_to_tray)

    def minimize_to_tray(self):
        self.minimizing_to_tray = True  # 플래그 설정
        self.root.withdraw()  # Hide the window
        
        # 트레이 아이콘이 이미 실행 중이면 다시 만들지 않음
        if self.tray_icon and self.tray_icon._running:
            self.minimizing_to_tray = False
            return
            
        image = self.create_icon()
        menu = (pystray.MenuItem('Restore', self.restore_from_tray, default=True),
                pystray.MenuItem('Quit', self.quit_app))
        self.tray_icon = pystray.Icon("name", image, "Custom Test Tool", menu)
        
        # Run tray icon in a separate thread to not block tkinter
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self.minimizing_to_tray = False  # 플래그 해제

    def restore_from_tray(self, icon, item):
        self.tray_icon.stop()
        self.root.after(0, self.root.deiconify) # Restore window on main thread

    def quit_app(self, icon, item):
        self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def on_closing(self):
        """X 버튼 클릭 시 트레이로 숨김 (종료하지 않음)"""
        self.minimize_to_tray()

    def get_window_opacity(self, hwnd):
        """Get current window opacity (0-255)"""
        try:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if style & win32con.WS_EX_LAYERED:
                # Window has layered style, try to get alpha value
                # Note: There's no direct API to get the alpha, so we return 255 as default
                return 255
            return 255
        except:
            return 255

    def get_taskbar_status(self, hwnd):
        """Check if window is shown in taskbar"""
        try:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            is_toolwindow = bool(style & win32con.WS_EX_TOOLWINDOW)
            return "Hidden" if is_toolwindow else "Shown"
        except:
            return "Shown"

    def update_selected_tree_item(self):
        """Update the tree item for the currently selected window"""
        if not self.selected_hwnd:
            return
            
        # Find the index of the selected window
        for i, (title, hwnd) in enumerate(self.window_list):
            if hwnd == self.selected_hwnd:
                # Get the tree item at this index
                items = self.tree.get_children()
                if i < len(items):
                    item = items[i]
                    
                    # Get current status
                    opacity_percent = int((self.level_var.get() / 255) * 100)
                    taskbar_status = self.get_taskbar_status(hwnd)
                    
                    # Update the tree item
                    self.tree.item(item, values=(f'{opacity_percent}%', taskbar_status))
                break

    def refresh_list(self):
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.window_list = []
        filter_text = self.filter_var.get().lower()
        
        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    if filter_text in title.lower():
                        self.window_list.append((title, hwnd))
                        
                        # Get status
                        opacity = self.get_window_opacity(hwnd)
                        opacity_percent = int((opacity / 255) * 100)
                        taskbar_status = self.get_taskbar_status(hwnd)
                        
                        # Insert into tree
                        self.tree.insert('', 'end', text=title, values=(f'{opacity_percent}%', taskbar_status))
        
        win32gui.EnumWindows(enum_handler, None)

    def on_select(self, event):
        selection = self.tree.selection()
        if selection:
            # Get the index of the selected item
            item = selection[0]
            index = self.tree.index(item)
            self.selected_hwnd = self.window_list[index][1]
            
            # Load saved opacity for this window (default to 255 if not set)
            saved_opacity = self.window_opacity_settings.get(self.selected_hwnd, 255)
            self.level_var.set(saved_opacity)
            
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
                
                # Save current window placement (includes position, size, and state)
                placement = win32gui.GetWindowPlacement(hwnd)
                
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
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
                
                # Restore window placement (position, size, and state)
                win32gui.SetWindowPlacement(hwnd, placement)
                
                # Update tree display
                self.update_selected_tree_item()
            except Exception as e:
                print(f"Error toggling taskbar: {e}")

    def update_level(self, val):
        if self.selected_hwnd:
            try:
                level = int(float(val))
                hwnd = self.selected_hwnd
                
                # Save this opacity setting for this window
                self.window_opacity_settings[hwnd] = level
                
                # Get current window style
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                
                # Add WS_EX_LAYERED if not present
                if not (style & win32con.WS_EX_LAYERED):
                    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_LAYERED)
                
                # Set transparency (LWA_ALPHA = 0x2)
                win32gui.SetLayeredWindowAttributes(hwnd, 0, level, win32con.LWA_ALPHA)
                
                # Update tree display
                self.update_selected_tree_item()
            except Exception as e:
                print(f"Error updating level: {e}")

if __name__ == "__main__":
    # Single instance check using mutex
    mutex_name = "Global\\CustomTestToolMutex"
    mutex = win32event.CreateMutex(None, False, mutex_name)
    last_error = win32api.GetLastError()
    
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        # Another instance is already running
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        messagebox.showwarning("Already Running", "Tool is already running!")
        root.destroy()
        import sys
        sys.exit(0)
    
    root = tk.Tk()
    app = CustomTestTool(root)
    root.mainloop()
    
    # Release mutex on exit
    win32api.CloseHandle(mutex)
