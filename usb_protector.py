import os
import sys
import ctypes
import string
import subprocess
import threading
import shutil
import time
import queue
import tkinter as tk
from tkinter import ttk, messagebox

# --- Admin Privilege Check ---
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# --- Detect USB Drives ---
def get_usb_drives():
    drives = []
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drive_path = f"{letter}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(drive_path) == 2:
                    drives.append(f"{letter}:")
            bitmask >>= 1
    except Exception:
        pass
    return drives

# --- GUI Application Class ---
class USBProtectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("USB Anti-Shortcut Protector v3.1 (XDR-SAM)")
        self.root.geometry("550x580")
        self.root.resizable(False, False)
        self.root.configure(bg="#f8f9fa")
        
        self.log_queue = queue.Queue()
        self.desktop_path = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        
        self.setup_ui()
        self.process_queue()

    def setup_ui(self):
        # Header
        tk.Label(self.root, text="USB Anti-Shortcut Protector", font=("Segoe UI", 18, "bold"), bg="#f8f9fa", fg="#212529").pack(pady=(15, 5))
        tk.Label(self.root, text="Safe Format, Virus Lock & Auto Backup", font=("Segoe UI", 10), bg="#f8f9fa", fg="#6c757d").pack(pady=(0, 15))

        # Drive Selection
        frame = tk.Frame(self.root, bg="#f8f9fa")
        frame.pack(pady=5)

        tk.Label(frame, text="Select USB Drive:", font=("Segoe UI", 10, "bold"), bg="#f8f9fa").grid(row=0, column=0, padx=5)
        self.drive_combo = ttk.Combobox(frame, state="readonly", width=10, font=("Segoe UI", 10))
        self.drive_combo.grid(row=0, column=1, padx=5)

        ttk.Button(frame, text="Refresh", command=self.refresh_drives).grid(row=0, column=2, padx=5)
        self.refresh_drives()

        # Options
        self.backup_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.root, text="Auto Backup & Restore Files (Desktop)", variable=self.backup_var, font=("Segoe UI", 10, "bold"), bg="#f8f9fa", fg="#0056b3").pack(pady=10)

        # Progress Bar
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=10)

        # Action Button
        self.protect_btn = tk.Button(self.root, text="🛡️ Format & Protect USB", font=("Segoe UI", 12, "bold"), bg="#dc3545", fg="white", activebackground="#c82333", activeforeground="white", relief=tk.FLAT, padx=10, pady=5, command=self.start_process)
        self.protect_btn.pack(pady=5)

        # Log Console with Scrollbar & Wrap
        tk.Label(self.root, text="Live Process Logs:", font=("Segoe UI", 9, "bold"), bg="#f8f9fa", anchor="w").pack(fill="x", padx=40, pady=(10, 2))
        
        log_frame = tk.Frame(self.root, bg="#f8f9fa")
        log_frame.pack(pady=5, padx=40, fill="both", expand=True)

        self.log_text = tk.Text(log_frame, height=8, font=("Consolas", 9), bg="#1e1e1e", fg="#00ff00", state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill="both", expand=True)

        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

        # Footer
        tk.Label(self.root, text="Made by XDR-SAM", font=("Courier New", 10, "bold"), bg="#f8f9fa", fg="#adb5bd").pack(side=tk.BOTTOM, pady=10)

    def log(self, message):
        self.log_queue.put(message)

    def process_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
                self.root.update_idletasks()
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def refresh_drives(self):
        drives = get_usb_drives()
        self.drive_combo['values'] = drives
        if drives:
            self.drive_combo.current(0)
            self.log("Drives refreshed successfully.")
        else:
            self.drive_combo.set('')
            self.log("No USB drives detected.")

    def run_command(self, cmd_string, success_msg, error_msg, is_robocopy=False):
        self.log(f"Executing: {cmd_string}")
        # shell=True fixes the WinError 2 issue
        result = subprocess.run(cmd_string, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        if is_robocopy:
            # Robocopy exit codes > 7 mean error
            if result.returncode >= 8:
                self.log(f"ERROR: {result.stderr.strip() or result.stdout.strip()}")
                raise Exception(error_msg)
        else:
            if result.returncode != 0:
                self.log(f"ERROR: {result.stderr.strip() or result.stdout.strip()}")
                raise Exception(error_msg)
                
        self.log(f"SUCCESS: {success_msg}")
        return result

    def protect_drive_thread(self, drive_letter, auto_backup):
        backup_dir = os.path.join(self.desktop_path, f"USB_Backup_{drive_letter[0]}")
        folder_path = f"{drive_letter}\\My_Files"
        
        try:
            self.progress['value'] = 0
            self.log(f"\n--- Starting process for {drive_letter} ---")

            # Step 1: Backup
            if auto_backup:
                self.log("Step 1: Backing up files safely...")
                backup_cmd = f'robocopy "{drive_letter}\\" "{backup_dir}" /E /XD "System Volume Information" /XF *.lnk *.vbs *.bat'
                self.run_command(backup_cmd, "Backup completed.", "Backup failed! Format aborted.", is_robocopy=True)
            
            self.progress['value'] = 25
            
            # Step 2: Format
            self.log("Step 2: Quick Formatting to NTFS...")
            format_cmd = f'format {drive_letter} /FS:NTFS /Q /Y'
            self.run_command(format_cmd, "Drive formatted to NTFS.", "Failed to format drive.")
            
            self.log("Waiting for Windows to register the new file system...")
            time.sleep(3)
            self.progress['value'] = 50

            # Step 3: Create Folder
            self.log("Step 3: Creating 'My_Files' folder...")
            os.makedirs(folder_path, exist_ok=True)
            self.log("Folder 'My_Files' created.")
            self.progress['value'] = 65

            # Step 4: Lock Root
            self.log("Step 4: Locking Root Directory safely...")
            deny_cmd = f'icacls "{drive_letter}\\" /deny "Everyone:(WD,AD)"'
            self.run_command(deny_cmd, "Root locked securely.", "Failed to lock root.")
            self.progress['value'] = 75

            # Step 5: Grant Full Access to My_Files
            self.log("Step 5: Unlocking 'My_Files' for Full Access...")
            grant_cmd = f'icacls "{folder_path}" /grant "Everyone:(F)" /T'
            self.run_command(grant_cmd, "'My_Files' is now fully accessible.", "Failed to set folder permissions.")
            self.progress['value'] = 85

            # Step 6: Restore Files
            if auto_backup and os.path.exists(backup_dir):
                self.log("Step 6: Restoring files to 'My_Files'...")
                restore_cmd = f'robocopy "{backup_dir}" "{folder_path}" /E'
                self.run_command(restore_cmd, "Files restored successfully.", "Failed to restore files.", is_robocopy=True)
                
                self.log("Cleaning up Desktop backup...")
                shutil.rmtree(backup_dir, ignore_errors=True)
            
            self.progress['value'] = 100
            self.log("\n--- COMPLETE: Pendrive is now 100% Protected! ---")
            messagebox.showinfo("Success", f"{drive_letter} is successfully formatted, protected, and ready to use!\n\nUse the 'My_Files' folder for all your work.")

        except Exception as e:
            self.log(f"\nPROCESS ABORTED: {str(e)}")
            messagebox.showerror("Error", str(e))
        finally:
            self.protect_btn.config(state=tk.NORMAL)

    def start_process(self):
        selected_drive = self.drive_combo.get()
        auto_backup = self.backup_var.get()
        
        if not selected_drive:
            messagebox.showwarning("Warning", "Please select a USB Drive first!")
            return
            
        confirm = messagebox.askyesno("Confirm Action", f"Are you sure you want to protect {selected_drive}?")
        if confirm:
            self.protect_btn.config(state=tk.DISABLED)
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state=tk.DISABLED)
            
            t = threading.Thread(target=self.protect_drive_thread, args=(selected_drive, auto_backup))
            t.daemon = True
            t.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = USBProtectorApp(root)
    root.mainloop()