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
    def __init__(self, root, mutex=None):
        self.root = root
        self.root.title("Custom Test Tool")
        self.root.geometry("400x450")
        
        # Store mutex for proper cleanup
        self.mutex = mutex
        
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
        
        # Track hidden windows manually
        self.hidden_windows = set()

        # Frame for controls
        control_frame = ttk.Frame(root, padding="10")
        control_frame.pack(fill=tk.BOTH, expand=True)

        # Filter Frame
        filter_frame = ttk.Frame(control_frame)
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_frame, text="명칭 검색:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar(value="Chrome")
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var)
        self.filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.filter_entry.bind('<Return>', lambda e: self.refresh_list())

        # Refresh Button
        ttk.Button(control_frame, text="새로고침", command=self.refresh_list).pack(pady=5)

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
        self.tree.heading('#0', text='창 이름')
        self.tree.heading('transparency', text='투명도')
        self.tree.heading('taskbar', text='작업표시줄')
        
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
        
        ttk.Label(level_frame, text="투명도:").pack(side=tk.LEFT)
        self.scale = ttk.Scale(level_frame, from_=0, to=255, variable=self.level_var, orient=tk.HORIZONTAL, command=self.update_level)
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Taskbar Visibility Checkbox
        self.taskbar_var = tk.BooleanVar(value=True)
        self.taskbar_checkbox = ttk.Checkbutton(control_frame, text="작업표시줄 표시", variable=self.taskbar_var, command=self.toggle_taskbar)
        self.taskbar_checkbox.pack(pady=5)
        
        # Restore All Windows Button
        restore_btn = ttk.Button(control_frame, text="모든 창 복구", command=self.restore_all_windows)
        restore_btn.pack(pady=5)

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
        try:
            self.minimizing_to_tray = True  # 플래그 설정
            self.root.withdraw()  # Hide the window
            
            # 트레이 아이콘이 이미 실행 중이면 다시 만들지 않음
            if self.tray_icon and self.tray_icon._running:
                self.minimizing_to_tray = False
                # Try to activate selected window even if tray icon exists
                self.activate_selected_window()
                return
                
            image = self.create_icon()
            menu = (pystray.MenuItem('복원', self.restore_from_tray, default=True),
                    pystray.MenuItem('종료', self.quit_app))
            self.tray_icon = pystray.Icon("name", image, "Custom Test Tool", menu)
            
            # Run tray icon in a separate thread to not block tkinter
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            self.minimizing_to_tray = False  # 플래그 해제
            
            # Try to activate selected window to prevent Z-order drop
            self.activate_selected_window()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to minimize to tray:\n{e}")
            self.root.deiconify()  # Restore window if failed
            self.minimizing_to_tray = False

    def activate_selected_window(self):
        """선택된 창을 활성화 (작업표시줄 숨김 창이 최소화되는 것 방지)"""
        if self.selected_hwnd:
            try:
                # 툴 자신이면 패스
                if self.selected_hwnd == self.root.winfo_id():
                    return
                    
                if win32gui.IsWindow(self.selected_hwnd):
                    # 약간의 딜레이 후 활성화 시도
                    def try_activate():
                        try:
                            # 만약 최소화되어 있다면 복구
                            if win32gui.IsIconic(self.selected_hwnd):
                                win32gui.ShowWindow(self.selected_hwnd, win32con.SW_RESTORE)
                            
                            # 보이게 설정
                            win32gui.ShowWindow(self.selected_hwnd, win32con.SW_SHOW)
                            
                            # 맨 앞으로 가져오기
                            win32gui.SetForegroundWindow(self.selected_hwnd)
                        except Exception as e:
                            print(f"Activation error: {e}")
                    
                    # Run in a separate thread
                    threading.Timer(0.1, try_activate).start()
            except Exception as e:
                print(f"Error activating window: {e}")

    def restore_from_tray(self, icon, item):
        self.tray_icon.stop()
        self.root.after(0, self.root.deiconify) # Restore window on main thread

    def perform_exit(self):
        """Actual exit logic to be run on main thread"""
        if self.tray_icon:
            self.tray_icon.stop()
            
        # Release mutex before exiting
        if self.mutex:
            win32api.CloseHandle(self.mutex)
            
        self.root.destroy()

    def quit_app(self, icon, item):
        # Schedule exit on main thread
        self.root.after(0, self.perform_exit)

    # ... (on_closing and other methods remain the same) ...

    def restore_all_windows(self):
        """Restore all hidden windows to taskbar"""
        if not self.hidden_windows:
            messagebox.showinfo("복구", "숨겨진 창이 없습니다.")
            return
        
        count = len(self.hidden_windows)
        restored = 0
        errors = []
        
        for hwnd in list(self.hidden_windows):
            try:
                # Remove TOOLWINDOW, Add APPWINDOW
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                new_style = (style & ~win32con.WS_EX_TOOLWINDOW) | win32con.WS_EX_APPWINDOW
                
                # Apply style
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                
                # Force update frame
                win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 
                                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | 
                                    win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED)
                restored += 1
            except Exception as e:
                errors.append(f"창 ID {hwnd}: {str(e)}")
        
        self.hidden_windows.clear()
        
        # Refresh display
        self.refresh_list()
        
        # Show result
        if errors:
            messagebox.showwarning("복구 완료", 
                                  f"총 {count}개 중 {restored}개 복구 완료\n{len(errors)}개 실패")
        else:
            messagebox.showinfo("복구 완료", f"{restored}개 창 모두 복구 완료")

    def toggle_taskbar(self):
        # Debug: Check if function is called
        if not self.selected_hwnd:
            messagebox.showwarning("경고", "먼저 창을 선택해주세요.")
            self.taskbar_var.set(True)  # Reset checkbox
            return
            
        if self.selected_hwnd:
            try:
                hwnd = self.selected_hwnd
                
                # Check if this is the tool's own window
                is_self = False
                for title, h in self.window_list:
                    if h == hwnd and title == "Custom Test Tool":
                        is_self = True
                        break
                
                # If hiding tool itself from taskbar, minimize to tray instead
                if is_self and not self.taskbar_var.get():
                    self.root.after(100, self.minimize_to_tray)
                    return

                # Style-based Method (Reliable)
                # Save current window placement
                placement = win32gui.GetWindowPlacement(hwnd)
                
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                
                if self.taskbar_var.get():
                    # Show in taskbar: Remove TOOLWINDOW, Add APPWINDOW
                    new_style = (style & ~win32con.WS_EX_TOOLWINDOW) | win32con.WS_EX_APPWINDOW
                    if hwnd in self.hidden_windows:
                        self.hidden_windows.remove(hwnd)
                else:
                    # Hide from taskbar: Add TOOLWINDOW, Remove APPWINDOW
                    new_style = (style | win32con.WS_EX_TOOLWINDOW) & ~win32con.WS_EX_APPWINDOW
                    self.hidden_windows.add(hwnd)
                
                # Need to hide/show to apply style change for taskbar
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
                
                # Restore window placement
                win32gui.SetWindowPlacement(hwnd, placement)
                
                # Bring tool window back to front
                self.root.lift()
                self.root.focus_force()
                
                # Update tree display
                self.update_selected_tree_item()
            except Exception as e:
                print(f"Error toggling taskbar: {e}")

    def on_closing(self):
        """X 버튼 클릭 시 종료 경고 및 확인"""
        # Create custom dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("종료")
        dialog.geometry("350x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        self.root.update_idletasks()
        dialog.update_idletasks()
        
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        
        dialog_width = 350
        dialog_height = 150
        x = root_x + (root_width - dialog_width) // 2
        y = root_y + (root_height - dialog_height) // 2
        
        dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')
        
        # Message
        msg_text = ("주의: 작업표시줄에서 숨긴 창들은\n"
                   "프로그램 종료 후에도 계속 숨김 상태로 유지됩니다.\n"
                   "종료 전에 수동으로 복구하세요.")
        lbl = ttk.Label(dialog, text=msg_text, font=("Malgun Gothic", 9), justify="center")
        lbl.pack(pady=(15, 10))
        
        # Buttons frame
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10, fill='x', padx=20)
        
        def confirm_exit():
            dialog.destroy()
            # Run exit logic after a brief delay to allow dialog to close cleanly
            self.root.after(100, self.perform_exit)
        
        def cancel_exit():
            dialog.destroy()
            
        def minimize_choice():
            dialog.destroy()
            self.minimize_to_tray()
        
        # 트레이로 숨기기 버튼 (위쪽)
        ttk.Button(btn_frame, text="트레이로 숨기기 (종료 X)", command=minimize_choice).pack(fill='x', pady=(0, 10))
        
        # 하단 버튼 프레임 (취소/확인)
        bottom_frame = ttk.Frame(btn_frame)
        bottom_frame.pack(fill='x')
        
        # 취소 / 확인 (확인 강조)
        # Center the buttons
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Button(bottom_frame, text="취소", command=cancel_exit).grid(row=0, column=0, padx=5, sticky='ew')
        
        confirm_btn = ttk.Button(bottom_frame, text="확인", command=confirm_exit)
        confirm_btn.grid(row=0, column=1, padx=5, sticky='ew')
        
        # Bind Enter key to confirm
        dialog.bind('<Return>', lambda e: confirm_exit())
        confirm_btn.focus_set()

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
        if hwnd in self.hidden_windows:
            return "숨김"
        
        # Fallback to style check (for windows hidden by other means or previous sessions if applicable)
        try:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            is_toolwindow = bool(style & win32con.WS_EX_TOOLWINDOW)
            return "숨김" if is_toolwindow else "표시"
        except:
            return "표시"

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
            
            # Check if selected window is the tool itself
            window_title = self.window_list[index][0]
            is_self = (window_title == "Custom Test Tool")
            
            # Load saved opacity for this window (default to 255 if not set)
            saved_opacity = self.window_opacity_settings.get(self.selected_hwnd, 255)
            self.level_var.set(saved_opacity)
            
            # Update taskbar checkbox based on current state
            try:
                if self.selected_hwnd in self.hidden_windows:
                    self.taskbar_var.set(False)
                else:
                    style = win32gui.GetWindowLong(self.selected_hwnd, win32con.GWL_EXSTYLE)
                    # If TOOLWINDOW is set, it's hidden from taskbar (so Show = False)
                    is_toolwindow = bool(style & win32con.WS_EX_TOOLWINDOW)
                    self.taskbar_var.set(not is_toolwindow)
            except:
                self.taskbar_var.set(True)
            
            # Disable taskbar checkbox if tool itself is selected
            if is_self:
                self.taskbar_checkbox.config(state='disabled')
            else:
                self.taskbar_checkbox.config(state='normal')


    def toggle_taskbar(self):
        # Check if window is selected
        if not self.selected_hwnd:
            messagebox.showwarning("경고", "먼저 창을 선택해주세요.")
            self.taskbar_var.set(True)  # Reset checkbox
            return
        
        try:
            hwnd = self.selected_hwnd
            
            # Check if this is the tool's own window
            is_self = False
            for title, h in self.window_list:
                if h == hwnd and title == "Custom Test Tool":
                    is_self = True
                    break
            
            # If hiding tool itself from taskbar, minimize to tray instead
            if is_self and not self.taskbar_var.get():
                self.root.after(100, self.minimize_to_tray)
                return

            # Style-based Method
            # Save current window placement
            placement = win32gui.GetWindowPlacement(hwnd)
            
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            if self.taskbar_var.get():
                # Show in taskbar: Remove TOOLWINDOW, Add APPWINDOW
                new_style = (style & ~win32con.WS_EX_TOOLWINDOW) | win32con.WS_EX_APPWINDOW
                if hwnd in self.hidden_windows:
                    self.hidden_windows.remove(hwnd)
            else:
                # Hide from taskbar: Add TOOLWINDOW, Remove APPWINDOW
                new_style = (style | win32con.WS_EX_TOOLWINDOW) & ~win32con.WS_EX_APPWINDOW
                self.hidden_windows.add(hwnd)
            
            # Need to hide/show to apply style change for taskbar
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
            
            # Restore window placement
            win32gui.SetWindowPlacement(hwnd, placement)
            
            # Bring tool window back to front
            self.root.lift()
            self.root.focus_force()
            
            # Update tree display
            self.update_selected_tree_item()
        except Exception as e:
            messagebox.showerror("오류", f"작업표시줄 토글 실패:\n{e}")
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
        root.withdraw()
        
        # Ask user what to do
        result = messagebox.askyesno(
            "이미 실행 중", 
            "프로그램이 이미 실행 중입니다!\n\n기존 프로그램을 강제 종료하고 실행하시겠습니까?",
            icon='warning'
        )
        
        if result:  # User chose Yes - force run
            # Kill existing CustomTestTool processes
            import subprocess
            try:
                # Kill all python processes running main.py or CustomTestTool.exe
                subprocess.run(['taskkill', '/F', '/IM', 'CustomTestTool.exe'], 
                             capture_output=True, timeout=5)
                subprocess.run(['taskkill', '/F', '/FI', 'WINDOWTITLE eq Custom Test Tool'], 
                             capture_output=True, timeout=5)
            except:
                pass
            
            # Wait a moment for cleanup
            import time
            time.sleep(0.5)
            
            # Release the old mutex and create new one
            win32api.CloseHandle(mutex)
            time.sleep(0.2)
            mutex = win32event.CreateMutex(None, False, mutex_name)
            
            # Continue to run
            root.destroy()
        else:  # User chose No - cancel
            root.destroy()
            import sys
            sys.exit(0)
    
    root = tk.Tk()
    app = CustomTestTool(root, mutex)
    root.mainloop()
