#!/usr/bin/env python3
"""
Themed Mod Installer for GTA Stars & Stripes / Project Eagle
- Dark naval UI, red accents, off-white text
- Header logo support
"""

import os
import sys
import threading
import tempfile
import time
import subprocess
import requests
import customtkinter as ctk
from tkinter import filedialog, messagebox
import winreg
import ctypes
import re

# Try importing PIL, handle gracefully if not available
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: PIL not available. Logo display will be disabled.")

# ——— THEME COLORS —————————————————————————————————————————
BG_COLOR      = "#0d1b2a"   # Deep navy
PANEL_COLOR   = "#1b263b"   # Lighter navy
ACCENT        = "#e63946"   # Bright red
ACCENT_HOVER  = "#cf2e3c"   # Slightly darker red
TEXT_COLOR    = "#f1faee"   # Off-white
STAR_COLOR    = "#415a77"   # Subtle star pattern

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ——— CONFIGURATION —————————————————————————————————————————
MOD_ARCHIVE_URL      = "https://github.com/Madhav2609/project-eagle-releases/releases/download/1.1/V2-Snapshot1.1-GTAPE.7z"
ARCHIVE_NAME         = "V2-Snapshot1.1-GTAPE.7z"
EXPECTED_EXECUTABLE  = "gta_sa.exe"

BLACKLISTED_FILES = [
    "modloader.asi",          # Popular mod loader
    "d3d9.dll",   
    "$fastman92limitAdjuster.asi"  ,   # Fastman92 limit adjuster

]

# ——— UTILS ——————————————————————————————————————————————————

def styled_btn(master, **kw):
    return ctk.CTkButton(
        master,
        fg_color=ACCENT,
        hover_color=ACCENT_HOVER,
        text_color=TEXT_COLOR,
        corner_radius=8,  # Increased from 4 for smoother look
        height=32,
        **kw
    )

def styled_frame(*args, **kw):
    return ctk.CTkFrame(*args, fg_color=PANEL_COLOR, corner_radius=8, **kw)  # Increased from 4

def page_title(text):
    return {"font":("Segoe UI", 24, "bold"), "text_color":TEXT_COLOR, "text":text}

def page_label(text,size=13):
    return {"font":("Segoe UI", size), "text_color":TEXT_COLOR, "text":text}

def get_bundled_path(filename):
    """Return full path to a data file bundled by PyInstaller (using sys._MEIPASS)."""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        return os.path.join(sys._MEIPASS, filename)
    else:
        # Running in normal Python environment
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)



def extract_with_7zr(archive_path, dest_dir, progress_callback=None):
    """Extract archive using bundled 7zr.exe, with improved error handling"""
    cmd = [
        get_bundled_path('7zr.exe'),
        'x', archive_path,
        f'-o{dest_dir}',
        '-y',       # assume Yes on all prompts
        '-bso0',    # no ordinary output
        '-bsp1',    # send progress (%) to stdout
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # Capture stderr too
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        for line in proc.stdout:
            if pct := re.search(r'(\d+)%', line):
                p = int(pct.group(1)) / 100.0
                if progress_callback:
                    progress_callback(p, line.strip())

        proc.wait()
        if proc.returncode != 0:
            # Get error output if available
            error_output = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"7zr failed (code {proc.returncode}): {error_output}")

    except Exception as e:
        raise RuntimeError(f"Extraction failed: {str(e)}")

# ——— APPLICATION ——————————————————————————————————————————————

class Installer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Project Eagle Installer")
        self.geometry("720x680")
        self.resizable(False, False)
        self.configure(fg_color=BG_COLOR)

        # Set window icon
        if getattr(sys, 'frozen', False):
            # Running in PyInstaller bundle
            basedir = sys._MEIPASS
        else:
            # Running in normal Python environment
            basedir = os.path.dirname(os.path.abspath(__file__))
        
        icon_path = os.path.join(basedir, "favicon.png")
        if os.path.exists(icon_path):
            # Convert PNG to ICO format for Windows
            if HAS_PIL:
                try:
                    ico_path = os.path.join(tempfile.gettempdir(), "favicon.ico")
                    img = Image.open(icon_path)
                    # Save as ICO
                    img.save(ico_path, format='ICO', sizes=[(32, 32)])
                    self.iconbitmap(ico_path)
                    self.wm_iconbitmap(ico_path)  # Set taskbar icon
                except Exception as e:
                    print(f"Failed to set icon: {e}")
            else:
                print("PIL not available for icon conversion")
        else:
            print(f"Icon file not found at: {icon_path}")

        # Load logo
        self.LOGO = None
        if HAS_PIL:
            try:
                # Get the base path for resources
                if getattr(sys, 'frozen', False):
                    # Running in PyInstaller bundle
                    basedir = sys._MEIPASS
                else:
                    # Running in normal Python environment
                    basedir = os.path.dirname(os.path.abspath(__file__))
                
                logo_path = os.path.join(basedir, "favicon.png")
                if os.path.isfile(logo_path):
                    pil_image = Image.open(logo_path)
                    self.LOGO = ctk.CTkImage(light_image=pil_image, size=(160, 160))
                    self.log(f"Loaded logo from: {logo_path}")
                else:
                    print(f"Logo file not found at: {logo_path}")
            except Exception as e:
                print(f"Failed to load logo: {e}")

        # State tracking
        self.game_path = ""
        self.deps_ok = False
        self.install_ok = False
        self.install_success = False  # Add this to track final installation status

        # HEADER
        header = ctk.CTkFrame(self, fg_color=PANEL_COLOR, corner_radius=0, height=20)
        header.pack(fill="x", side="top")
        ctk.CTkLabel(
            header,
            text="PROJECT EAGLE INSTALLER",
            font=("Arial", 22, "bold"),
            text_color=TEXT_COLOR
        ).pack(side="left", padx=20)

        # CONTENT PANEL
        self.content = ctk.CTkFrame(self, fg_color=PANEL_COLOR, corner_radius=8)
        self.content.pack(fill="both", expand=True, padx=20, pady=(20,20))

        # PAGES
        self.pages = {}
        for PageClass in (WelcomePage, SelectPage, DependencyPage, InstallPage, FinishPage):
            page = PageClass(self.content, self)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.pages[PageClass.__name__[:-4]] = page

        self.show_tab("Welcome")

    def show_tab(self, name):
        # Just raise the page
        self.pages[name].tkraise()

# ——— PAGES ——————————————————————————————————————————————————

class BasePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=PANEL_COLOR)
        self.ctrl = controller
        # Header with logo (if available)
        if controller.LOGO:
            ctk.CTkLabel(self, image=controller.LOGO, text="").pack(pady=(20,10))
        else:
            ctk.CTkLabel(self, **page_title("Project Eagle - A GTA Total conversion Mod")).pack(pady=20)

class WelcomePage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        ctk.CTkLabel(self, **page_label(
            "Welcome to the GTA: Project Eagle Installer Wizard\n\n"
            "Thank you for downloading GTA: Stars & Stripes — Project Eagle edition!\n\n"
            "Make sure you have a 100% clean copy of GTA: San Andreas before continuing.\n"
            "If not, you might experience problems during installation.\n\n"
            "This wizard will guide you through:\n"
            "  • Selecting your game folder\n"
            "  • Verifying critical dependencies\n"
            "  • Downloading & extracting the mod\n"
            "  • Finishing up & launching the game\n\n"
            "Installer created by madhav2609\n"
            ,
            size=14
        ), justify="left").pack(padx=40)
        styled_btn(self, text="Start ▶", command=lambda: controller.show_tab("Select")).pack(pady=30)

class SelectPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        ctk.CTkLabel(self, **page_title("1) Select GTA:SA folder")).pack(pady=(20,5))
        ctk.CTkLabel(self, **page_label(f"Setup will install Project Eagle mod to the following GTA:SA Installation")).pack()

        frm = styled_frame(self)
        frm.pack(fill="x", padx=40, pady=10)
        self.path_var = ctk.StringVar()
        ctk.CTkEntry(frm, textvariable=self.path_var, state="readonly", fg_color=BG_COLOR, text_color=TEXT_COLOR).pack(side="left", fill="x", expand=True, padx=(0,5))
        styled_btn(frm, text="Browse…", width=100, command=self.browse).pack(side="right")

        styled_btn(self, text="Verify Folder", command=self.verify).pack(pady=10)
        nav = styled_frame(self)
        nav.pack(fill="x", pady=20, padx=40)
        styled_btn(nav, text="◀ Back", width=100, command=lambda: controller.show_tab("Welcome")).pack(side="left")
        self.next_btn = styled_btn(nav, text="Next ▶", width=100, state="disabled", command=lambda: controller.show_tab("Dependency"))
        self.next_btn.pack(side="right")

    def browse(self):
        p = filedialog.askdirectory(title="Select Game Folder")
        if p: self.path_var.set(p)

    def verify(self):
        p = self.path_var.get()
        exe_path = os.path.join(p, EXPECTED_EXECUTABLE)
        
        if not os.path.isfile(exe_path):
            messagebox.showerror("Error", f"{EXPECTED_EXECUTABLE} not found in:\n{p}")
            return

        # Check for modified installation
        found_mods = []
        for item in BLACKLISTED_FILES:
            full_path = os.path.join(p, item)
            if item.endswith('/'):
                if os.path.isdir(full_path.rstrip('/')):
                    found_mods.append(item.rstrip('/'))
            elif os.path.isfile(full_path):
                found_mods.append(item)

        if found_mods:
            messagebox.showerror(
                "Modified Installation Detected",
                "This appears to be a modified GTA:SA installation.\n\n"
                f"Found the following mod files/folders:\n• " + 
                "\n• ".join(found_mods) + 
                "\n\nPlease select a clean, unmodified game installation."
            )
            return

        # If we get here, it's a clean installation
        messagebox.showinfo("Verified", f"Found clean {EXPECTED_EXECUTABLE} installation")
        self.ctrl.game_path = p
        
        # Check dependencies
        missing = []
        for dep, fn in self.ctrl.pages["Dependency"].DEPENDENCIES.items():
            try:
                if not fn():
                    missing.append(dep)
            except Exception:
                missing.append(dep)
                
        if not missing:
            # If no missing dependencies, skip dependency page entirely
            self.ctrl.deps_ok = True
            self.ctrl.show_tab("Install")
        else:
            # If there are missing dependencies, enable next button to go to dependency page
            self.next_btn.configure(state="normal")

class DependencyPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        
        # Setup basic UI
        ctk.CTkLabel(self, **page_title("Required Dependencies")).pack(pady=(20,5))
        self.content_frame = styled_frame(self)
        self.content_frame.pack(fill="both", expand=True, padx=40, pady=10)
        
        # Define dependency checking functions
        def check_directx_jun2010():
            windir = os.environ.get("WINDIR", r"C:\Windows")
            for sub in ("System32","SysWOW64"):
                if os.path.isfile(os.path.join(windir, sub, "d3dx9_43.dll")):
                    return True
            return False

        def check_dotnet48():
            MIN_RELEASE = 461814
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full",
                    0,
                    winreg.KEY_READ|winreg.KEY_WOW64_32KEY
                )
                release, _ = winreg.QueryValueEx(key, "Release")
                return release >= MIN_RELEASE
            except FileNotFoundError:
                return False

        def check_vc_redist_x86():
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x86",
                    0,
                    winreg.KEY_READ|winreg.KEY_WOW64_32KEY
                )
                installed, _ = winreg.QueryValueEx(key, "Installed")
                return installed == 1
            except FileNotFoundError:
                return False

        # Move dependency dictionaries into class scope
        self.DEPENDENCIES = {
            "DirectX Jun2010":         check_directx_jun2010,
            ".NET Framework ≥4.8":     check_dotnet48,
            "VC++ 2015‑2022 (x86)":    check_vc_redist_x86,
        }

        self.DEPENDENCY_FILES = {
            "DirectX Jun2010": {
                "url": "https://github.com/Madhav2609/project-eagle-releases/releases/download/1.0/directx_Jun2010_redist.exe",
                "installer": "directx_Jun2010_redist.exe",
                "silent_args": ""  # Empty to run with default UI
            },
            ".NET Framework ≥4.8": {
                "url": "https://go.microsoft.com/fwlink/?LinkId=2085155",
                "installer": "ndp48-web.exe",
                "silent_args": ""  # Empty to run with default UI
            },
            "VC++ 2015‑2022 (x86)": {
                "url": "https://aka.ms/vs/17/release/vc_redist.x86.exe",
                "installer": "vc_redist.x86.exe",
                "silent_args": ""  # Empty to run with default UI
            }
        }
        
        # Only check dependencies when page is shown
        self.bind("<Visibility>", lambda e: self.check_deps())
        
    def check_deps(self):
        # Clear any existing widgets
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
        # Check dependencies
        missing = []
        for dep, fn in self.DEPENDENCIES.items():
            try:
                if not fn():
                    missing.append(dep)
            except Exception:
                missing.append(dep)
                
        if not missing:
            self.ctrl.deps_ok = True
            # Don't automatically go to install page, just enable the Next button
            self.next_btn.configure(state="normal")
            return
            
        # Setup UI for missing dependencies
        ctk.CTkLabel(self.content_frame, **page_label("The following dependencies are missing:")).pack(pady=(10,5), anchor="w")
        
        self.dep_labels = {}
        for dep in missing:
            lbl = ctk.CTkLabel(self.content_frame, **page_label(f"• {dep}"))
            lbl.pack(fill="x", pady=2, anchor="w")
            self.dep_labels[dep] = lbl

        # Add buttons frame
        btn_frame = styled_frame(self.content_frame)
        btn_frame.pack(pady=20)
        
        # Add install button
        self.install_btn = styled_btn(
            btn_frame, 
            text="Download & Install Missing Dependencies",
            command=lambda: threading.Thread(target=lambda: self._install_deps(missing), daemon=True).start()
        )
        self.install_btn.pack(side="left", padx=5)
        
        # Add skip button
        self.skip_btn = styled_btn(
            btn_frame,
            text="Skip Dependencies",
            command=self._skip_dependencies
        )
        self.skip_btn.pack(side="left", padx=5)

        self.progress = ctk.CTkProgressBar(self.content_frame, width=560)
        self.progress.pack(pady=(20,5))
        self.progress.set(0)
        
        self.status_lbl = ctk.CTkLabel(self.content_frame, **page_label(""))
        self.status_lbl.pack(pady=(0,10))

        self.logbox = ctk.CTkTextbox(
            self.content_frame, 
            width=560, 
            height=150,
            fg_color=PANEL_COLOR,
            text_color=TEXT_COLOR,
            state="disabled"
        )
        self.logbox.pack(pady=10)

        # Add navigation
        nav = styled_frame(self.content_frame)
        nav.pack(fill="x", pady=20)
        styled_btn(nav, text="◀ Back", width=100, command=lambda: self.ctrl.show_tab("Select")).pack(side="left")
        self.next_btn = styled_btn(nav, text="Next ▶", width=100, state="disabled", command=lambda: self.ctrl.show_tab("Install"))
        self.next_btn.pack(side="right")

    def _skip_dependencies(self):
        self.log("Dependencies installation skipped by user")
        self.ctrl.deps_ok = True  # Mark dependencies as OK even though they're skipped
        messagebox.showwarning("Dependencies Skipped", 
            "You have chosen to skip installing dependencies.\n"
            "The mod may not work correctly if required dependencies are missing.")
        self.ctrl.show_tab("Install")  # Navigate to Install page after showing warning

    def log(self, msg):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", msg + "\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _install_deps(self, missing):
        try:
            total_missing = len(missing)
            for i, dep in enumerate(missing):
                progress_base = (i/total_missing)

                try:
                    self.status_lbl.configure(text=f"Downloading: {dep}")
                    self.log(f"Downloading {dep}...")

                    dep_info = self.DEPENDENCY_FILES[dep]
                    temp_dir = tempfile.gettempdir()
                    installer_path = os.path.join(temp_dir, dep_info["installer"])

                    # Download with requests and proper streaming for better speed
                    with requests.get(dep_info["url"], stream=True) as r:
                        r.raise_for_status()
                        total = int(r.headers.get("Content-Length", 0))
                        dl = 0
                        with open(installer_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):  # 8KB chunks
                                if not chunk:
                                    continue
                                f.write(chunk)
                                dl += len(chunk)
                                if total:
                                    self.progress.set(progress_base + (dl/total * 0.5 / total_missing))

                    self.status_lbl.configure(text=f"Running installer: {dep}")
                    self.log(f"Starting installer for {dep}...")
                    
                    # Run the installer
                    result = ctypes.windll.shell32.ShellExecuteW(
                        None,
                        "runas",
                        installer_path,
                        dep_info["silent_args"],
                        None,
                        1  # Show the window
                    )
                    
                    if result <= 32:
                        error_codes = {
                            0: "Out of memory",
                            2: "File not found",
                            3: "Path not found", 
                            5: "Access denied",
                            8: "Insufficient memory",
                            11: "Bad format",
                            26: "Sharing violation",
                            27: "Incomplete association",
                            28: "DDE busy",
                            29: "DDE fail", 
                            30: "DDE timeout",
                            31: "DDE error",
                            32: "DDE in use"
                        }
                        error_msg = error_codes.get(result, f"Unknown error (code: {result})")
                        raise Exception(f"Failed to run installer: {error_msg}")

                    self.log(f"Started installer for {dep}")
                    
                except Exception as e:
                    self.log(f"Error with {dep}: {str(e)}")
                    messagebox.showerror("Installation Error",
                        f"Problem with {dep}.\nError: {str(e)}\nYou may need to install it manually.")
                    return

            self.log("All installers have been launched!")
            self.ctrl.deps_ok = True
            messagebox.showinfo("Dependencies", 
                "The dependency installers have been launched.\n"
                "Please complete each installer as they appear.\n"
                "Click OK to continue once all installers are finished.")
            self.after(1000, lambda: self.ctrl.show_tab("Install"))

        finally:
            self.progress.set(1.0)
            self.status_lbl.configure(text="Done")

class InstallPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        ctk.CTkLabel(self, **page_title("3) Download & Install")).pack(pady=(20,10))

        # Download size
        ctk.CTkLabel(self, **page_label("Download Size: 1.7GB")).pack(anchor="w", padx=60)

        # Single Progress Bar
        ctk.CTkLabel(self, **page_label("Progress:")).pack(anchor="w", padx=60)
        self.progress_bar = ctk.CTkProgressBar(
            self, 
            width=560, 
            fg_color=PANEL_COLOR, 
            progress_color=ACCENT,
            corner_radius=8  # Added corner radius for progress bar
        )
        self.progress_bar.pack(pady=(0,5))
        self.progress_pct = ctk.CTkLabel(self, **page_label("0.0%"))
        self.progress_pct.pack()
        self.status_lbl = ctk.CTkLabel(self, **page_label("Waiting to start..."))
        self.status_lbl.pack(pady=(0,10))

        # Log
        self.logbox = ctk.CTkTextbox(
            self, 
            width=560, 
            height=150, 
            fg_color=PANEL_COLOR, 
            text_color=TEXT_COLOR,
            scrollbar_button_color=ACCENT,
            corner_radius=8,  # Added corner radius for logbox
            state="disabled"
        )
        self.logbox.pack(pady=10)

        # Controls
        ctl = styled_frame(self)
        ctl.pack(pady=5)
        self.start_btn = styled_btn(ctl, text="Start ▶", command=self.start)
        self.start_btn.pack(side="left", padx=5)
        self.next_btn = styled_btn(ctl, text="Next ▶", state="disabled", command=lambda: controller.show_tab("Finish"))
        self.next_btn.pack(side="left", padx=5)

        # State tracking
        self.progress = 0.0
        self.phase = "waiting"  # waiting, downloading, preparing, installing
        self.speed = 0.0
        self.current_file = ""
        self.current_filename = ""  # Add this line to track current file
        self.prep_start_time = 0
        self.after(100, self.refresh_ui)

    def log(self, msg):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", msg+"\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def start(self):  # Remove the 'msg' parameter
        self.start_btn.configure(state="disabled")
        threading.Thread(target=self._worker, daemon=True).start()


    def _worker(self):
        try:
            if not hasattr(self.ctrl, 'deps_ok') or not self.ctrl.deps_ok:
                messagebox.showerror("Error", "Please complete dependency checks first")
                return
                
            if not self.ctrl.game_path:
                messagebox.showerror("Error", "Please select game folder first")
                return

            # Only import what's not already imported at the top
            from tempfile import TemporaryDirectory

            # Create temp file path but don't try to access it yet
            temp = os.path.join(tempfile.gettempdir(), ARCHIVE_NAME)

            # Download Phase (50% of total progress) 
            self.phase = "downloading"
            self.log("Starting download...")
            
            try:
                with requests.get(MOD_ARCHIVE_URL, stream=True) as r:
                    r.raise_for_status()
                    total = int(r.headers.get("Content-Length",0))
                    dl = 0
                    t0 = time.time()
                    with open(temp, "wb") as f:
                        for chunk in r.iter_content(64*1024):
                            if not chunk: continue
                            f.write(chunk)
                            dl += len(chunk)
                            self.progress = (dl/total if total else 0) * 0.5
                            elapsed = time.time() - t0
                            self.speed = dl/elapsed if elapsed > 0 else 0
                            self.current_file = f"Downloading {ARCHIVE_NAME}"

                self.log("Download complete")

                # Only proceed with installation if download was successful
                if os.path.exists(temp):
                    self.phase = "installing"
                    self.log("Extracting mod files into game folder…")

                    def on_progress(p, status):
                        overall = 0.5 + p * 0.5  # Map 0-1 to 50%-100%
                        self.progress = overall
                        self.current_file = status
                        self.progress_bar.set(overall)
                        self.progress_pct.configure(text=f"{overall*100:.1f}%")
                        self.status_lbl.configure(text=status)
                        self.update_idletasks()

                    extract_with_7zr(temp, self.ctrl.game_path, on_progress)
                    self.log("Extraction complete!")
                    
                    # Add these lines after extraction is done:
                    self.phase = "complete"
                    self.progress = 1.0  # Set progress to 100%
                    self.ctrl.install_ok = True
                    self.ctrl.install_success = True
                    self.next_btn.configure(state="normal")  # Enable the Next button
                else:
                    raise Exception("Download failed - temporary file not created")

            except requests.RequestException as e:
                raise Exception(f"Download failed: {str(e)}")
            
        except Exception as e:
            self.log(f"Error: {e}")
            messagebox.showerror("Installation Error", str(e))
            self.phase = "error"
            self.ctrl.install_ok = False
            self.ctrl.install_success = False
        finally:
            # Only attempt cleanup if the temp file exists
            if os.path.exists(temp):
                try:
                    os.remove(temp)
                except Exception as e:
                    self.log(f"Warning: Could not remove temporary file: {e}")
            self.after(0, lambda: self.start_btn.configure(state="normal"))

    def refresh_ui(self):
        # Update progress bar
        self.progress_bar.set(self.progress)
        self.progress_pct.configure(text=f"{self.progress*100:.1f}%")
        
        # Update status text based on phase
        if self.phase == "downloading":
            self.status_lbl.configure(text=f"{self.current_file} - {self._hr_size(self.speed)}/s")
        elif self.phase == "installing":
            self.status_lbl.configure(text=self.current_file)
            if hasattr(self, 'current_filename') and self.current_filename:
                self.logbox.configure(state="normal")
                self.logbox.see("end")
                self.logbox.configure(state="disabled")
        elif self.phase == "complete":
            self.status_lbl.configure(text="Installation Complete!")
        elif self.phase == "error":
            self.status_lbl.configure(text="Installation Failed")
        
        if self.phase != "complete" and self.phase != "error":
            self.after(100, self.refresh_ui)

    def _hr_size(self, bps):
        for unit in ["B","KB","MB","GB","TB"]:
            if bps < 1024:
                return f"{bps:.1f} {unit}"
            bps /= 1024
        return f"{bps:.1f} PB"

class FinishPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        ctk.CTkLabel(self, **page_title("4) Done!")).pack(pady=(30,10))
        
        # Thank you message
        self.msg = ctk.CTkLabel(self, **page_label(
            "Installation finished\n\n"
            "Thank you for downloading Project Eagle Mod, hope you will enjoy playing it\n\n"
            "Click Finish to exit the wizard"
        ))
        self.msg.pack(pady=20)

        # Exit button
        btns = styled_frame(self)
        btns.pack(pady=20)
        styled_btn(btns, text="Finish", command=controller.destroy).pack(padx=5)

# ——— RUN ——————————————————————————————————————————————————

if __name__ == "__main__":
    app = Installer()
    app.mainloop()

