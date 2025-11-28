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
import keyboard

class CustomTestTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Custom Test Tool")
        self.root.geometry("400x600")
        
        # No mutex needed
        self.mutex = None
        
        # Handle window closing to properly exit tray
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)
        
        # Handle minimize button - hide to tray instead
        self.root.bind('<Unmap>', self.on_minimize)
        self.minimizing_to_tray = False  # 트레이로 최소화 중인지 구분하기 위한 플래그

        self.window_list = []
        self.selected_hwnd = None
        self.tray_icon = None
        
        # Hotkey Target Window
        self.hotkey_target_hwnd = None
        
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

        # Buttons Frame (Refresh and Restore)
        buttons_frame = ttk.Frame(control_frame)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        # Inner frame for centering
        center_frame = ttk.Frame(buttons_frame)
        center_frame.pack(anchor=tk.CENTER)
        
        ttk.Button(center_frame, text="새로고침", command=self.refresh_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(center_frame, text="단축키 대상 지정", command=self.set_hotkey_target_from_selection).pack(side=tk.LEFT, padx=5)
        ttk.Button(center_frame, text="단축키 재시작", command=self.manual_reset_hotkeys).pack(side=tk.LEFT, padx=5)
        ttk.Button(center_frame, text="작업표시줄 숨김 일괄 해제", command=self.restore_all_windows).pack(side=tk.LEFT, padx=5)

        # Hotkey Target Info
        self.target_label_var = tk.StringVar(value="단축키 대상: 없음 (목록 선택 후 버튼 클릭)")
        ttk.Label(control_frame, textvariable=self.target_label_var, foreground="blue", font=("Malgun Gothic", 9)).pack(pady=2)

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
        
        # Developer Info
        ttk.Label(control_frame, text="developed by 부트띠", font=("Arial", 8), foreground="gray").pack(pady=(10, 0))
        
        # Set Window Icon (Taskbar & Titlebar)
        try:
            # 1. Set AppUserModelID to ensure Windows treats this as a standalone app
            import ctypes
            myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            
            # 2. Use .ico for Windows Taskbar
            self.root.iconbitmap("app_icon.ico")
            
            # 3. Use .png for Titlebar (optional, but good for internal windows)
            icon_image = tk.PhotoImage(file="app_icon.png")
            self.root.iconphoto(True, icon_image)
        except Exception as e:
            print(f"Failed to load window icon: {e}")

        # Setup hotkeys (may fail in admin mode or due to conflicts)
        try:
            self.setup_hotkeys()
            # Start Hotkey Watchdog
            self.running = True
            self.start_hotkey_watchdog()
            print("Hotkeys registered successfully")
        except Exception as e:
            print(f"Warning: Hotkeys failed to register: {e}")
            print("GUI will work, but hotkeys won't be available")
            self.running = False
        
        self.refresh_list()

    def start_hotkey_watchdog(self):
        """Start a background thread to re-register hotkeys periodically"""
        def watchdog_loop():
            while self.running:
                time.sleep(10) # Check every 10 seconds for faster recovery
                if self.running:
                    self.reset_hotkeys()
                    
        threading.Thread(target=watchdog_loop, daemon=True).start()

    def manual_reset_hotkeys(self):
        """Manually reset hotkeys via button click"""
        self.reset_hotkeys()
        messagebox.showinfo("완료", "단축키 연결을 재시작했습니다.\n다시 사용해보세요.")

    def reset_hotkeys(self):
        """Safely reset all hotkeys"""
        try:
            keyboard.unhook_all()
            self.setup_hotkeys()
            # print("Hotkeys refreshed by watchdog") # Debug
        except Exception as e:
            print(f"Hotkey reset failed: {e}")

    def setup_hotkeys(self):
        """Setup global hotkeys for window control"""
        try:
            # Register Target: Shift+0 OR Alt+0
            keyboard.add_hotkey('shift+0', self.on_hotkey_register)
            keyboard.add_hotkey('alt+0', self.on_hotkey_register)
            
            # Hide Target: Ctrl+1 OR Alt+1
            keyboard.add_hotkey('ctrl+1', self.on_hotkey_hide)
            keyboard.add_hotkey('alt+1', self.on_hotkey_hide)
            
            # Show Target: Ctrl+2 OR Alt+2
            keyboard.add_hotkey('ctrl+2', self.on_hotkey_show)
            keyboard.add_hotkey('alt+2', self.on_hotkey_show)
            
            # Force Hide Target: Ctrl+3 OR Alt+3
            keyboard.add_hotkey('ctrl+3', self.on_hotkey_hide)
            keyboard.add_hotkey('alt+3', self.on_hotkey_hide)
        except Exception as e:
            print(f"Failed to setup hotkeys: {e}")

    def on_hotkey_register(self):
        """Register the currently active window as target"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            self.hotkey_target_hwnd = hwnd
            print(f"Target Registered: [{hwnd}] {title}")
            
            # Update UI label if possible (thread safety check might be needed but usually ok for simple var set)
            try:
                self.target_label_var.set(f"단축키 대상: {title}")
            except:
                pass
        except Exception as e:
            print(f"Error registering target: {e}")
            
    # ... (hide/show methods remain same) ...

    def set_hotkey_target_from_selection(self):
        """Set the hotkey target to the currently selected window in the list"""
        if not self.selected_hwnd:
            messagebox.showwarning("경고", "먼저 목록에서 창을 선택해주세요.")
            return
            
        self.hotkey_target_hwnd = self.selected_hwnd
        
        # Get title for display
        title = ""
        for t, h in self.window_list:
            if h == self.hotkey_target_hwnd:
                title = t
                break
                
        self.target_label_var.set(f"단축키 대상: {title}")
        messagebox.showinfo("설정 완료", f"단축키 대상이 설정되었습니다.\n[{title}]\n\n[사용법]\n숨김: Ctrl+1 또는 Alt+1\n보임: Ctrl+2 또는 Alt+2")

    def on_hotkey_hide(self):
        """Hide the registered target window"""
        if self.hotkey_target_hwnd:
            # Validate window handle
            if not win32gui.IsWindow(self.hotkey_target_hwnd):
                print("Target window invalid.")
                try:
                    self.target_label_var.set("단축키 대상: 없음 (창 사라짐)")
                except:
                    pass
                self.hotkey_target_hwnd = None
                return

            try:
                win32gui.ShowWindow(self.hotkey_target_hwnd, win32con.SW_HIDE)
                self.hidden_windows.add(self.hotkey_target_hwnd) # Track it so we can restore on exit
            except Exception as e:
                print(f"Error hiding target: {e}")

    def on_hotkey_show(self):
        """Show the registered target window"""
        if self.hotkey_target_hwnd:
            # Validate window handle
            if not win32gui.IsWindow(self.hotkey_target_hwnd):
                print("Target window invalid.")
                try:
                    self.target_label_var.set("단축키 대상: 없음 (창 사라짐)")
                except:
                    pass
                self.hotkey_target_hwnd = None
                return

            try:
                win32gui.ShowWindow(self.hotkey_target_hwnd, win32con.SW_SHOW)
                if self.hotkey_target_hwnd in self.hidden_windows:
                    self.hidden_windows.remove(self.hotkey_target_hwnd)
            except Exception as e:
                print(f"Error showing target: {e}")

    def create_icon(self):
        # Load the custom app icon for the tray
        try:
            image = Image.open("app_icon.png")
            return image
        except:
            # Fallback to simple dynamic icon if file missing
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
        self.running = False
        
        # Restore all hidden windows before exit
        if self.hidden_windows:
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
                except:
                    pass  # Ignore errors during exit
            self.hidden_windows.clear()
            
            # Give Windows time to process
            self.root.update()
            time.sleep(0.2)
        
        if self.tray_icon:
            self.tray_icon.stop()
            
        try:
            keyboard.unhook_all()
        except:
            pass
            
        self.root.destroy()

    def quit_app(self, icon, item):
        self.root.after(0, self.perform_exit)

    def restore_all_windows(self):
        """Restore all hidden windows to taskbar"""
        if not self.hidden_windows:
            messagebox.showinfo("알림", "숨겨진 창이 없습니다.")
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
            messagebox.showwarning("해제 완료", 
                                  f"총 {count}개 중 {restored}개 해제 완료\n{len(errors)}개 실패")
        else:
            messagebox.showinfo("해제 완료", f"{restored}개 창 모두 작업표시줄 표시로 변경됨")

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
        msg_text = ("종료 시 작업표시줄에서 숨긴 창들이\n"
                   "자동으로 복구됩니다.")
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
        
        # 취소 / 종료 (종료 버튼 강조)
        # Center the buttons
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Button(bottom_frame, text="취소", command=cancel_exit).grid(row=0, column=0, padx=5, sticky='ew')
        
        # Use tk.Button for colored exit button
        exit_btn = tk.Button(bottom_frame, text="종료", command=confirm_exit,
                            bg="#dc3545", fg="white", font=("Malgun Gothic", 9, "bold"),
                            relief=tk.RAISED, bd=2, cursor="hand2")
        exit_btn.grid(row=0, column=1, padx=5, sticky='ew')
        
        # Bind Enter key to exit
        dialog.bind('<Return>', lambda e: confirm_exit())
        exit_btn.focus_set()

    def get_window_opacity(self, hwnd):
        """Get current window opacity (0-255)"""
        try:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if style & win32con.WS_EX_LAYERED:
                # Window has layered style, get actual alpha value
                try:
                    # GetLayeredWindowAttributes returns (crKey, alpha, flags)
                    _, alpha, flags = win32gui.GetLayeredWindowAttributes(hwnd)
                    # LWA_ALPHA = 0x2, check if alpha flag is set
                    if flags & 0x2:
                        return alpha
                except:
                    pass
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
        # Re-register hotkeys to prevent timeout issues
        self.reset_hotkeys()

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
            
            # Read actual opacity from the window (not from saved settings)
            actual_opacity = self.get_window_opacity(self.selected_hwnd)
            self.level_var.set(actual_opacity)
            
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
            
            # Disable checkbox if tool itself is selected
            if is_self:
                self.taskbar_checkbox.config(state='disabled')
            else:
                self.taskbar_checkbox.config(state='normal')

    def set_hotkey_target_from_selection(self):
        """Set the hotkey target to the currently selected window in the list"""
        if not self.selected_hwnd:
            messagebox.showwarning("경고", "먼저 목록에서 창을 선택해주세요.")
            return
            
        self.hotkey_target_hwnd = self.selected_hwnd
        
        # Get title for display
        title = ""
        for t, h in self.window_list:
            if h == self.hotkey_target_hwnd:
                title = t
                break
                
        self.target_label_var.set(f"단축키 대상: {title}")
        messagebox.showinfo("설정 완료", f"단축키 대상이 설정되었습니다.\n[{title}]\n\n[사용법]\n숨김: Ctrl+1 또는 Alt+1\n보임: Ctrl+2 또는 Alt+2")

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
    root = tk.Tk()
    app = CustomTestTool(root)
    root.mainloop()
