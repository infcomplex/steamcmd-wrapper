import json
import subprocess
import os
import sys
import tkinter as tk
from tkinter import ttk, Scrollbar, Checkbutton, BooleanVar, Button, Label, Entry, Text, filedialog, messagebox, Toplevel, StringVar
from bs4 import BeautifulSoup
import requests
import re
import logging

# --- Logging Setup ---
# More robust than print for messages/errors
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global Settings ---
app_settings = {}
SETTINGS_FILE = "settings.json"

# --- Settings Management ---

def get_default_settings():
    """Returns a dictionary containing the default application settings."""
    return {
        "steamcmd_path": "", # Empty string triggers auto-detect
        "default_download_dir": "", # Empty string uses system default (e.g., ~/Downloads)
        "app_id": "294100", # Default: RimWorld App ID
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

def load_settings():
    """
    Loads settings from SETTINGS_FILE.
    Uses defaults if the file doesn't exist or is invalid.
    Updates the global `app_settings` dictionary.
    """
    global app_settings
    defaults = get_default_settings()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Merge loaded settings with defaults to ensure all keys exist
                app_settings = defaults.copy()
                app_settings.update(loaded)
                logging.info(f"Settings loaded from {SETTINGS_FILE}")
        except (json.JSONDecodeError, IOError, TypeError) as e:
            logging.error(f"Error loading settings file '{SETTINGS_FILE}': {e}. Using default settings.")
            messagebox.showwarning("Settings Error", f"Could not load settings from {SETTINGS_FILE}:\n{e}\nUsing default values.")
            app_settings = defaults.copy()
    else:
        logging.info(f"{SETTINGS_FILE} not found, using default settings.")
        app_settings = defaults.copy()
        # Optionally save defaults on first run to create the file
        # save_settings(app_settings)

def save_settings(settings_dict):
    """Saves the provided settings dictionary to SETTINGS_FILE as JSON."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings_dict, f, indent=4, ensure_ascii=False)
        logging.info(f"Settings saved to {SETTINGS_FILE}")
    except IOError as e:
        logging.error(f"Error saving settings to '{SETTINGS_FILE}': {e}")
        messagebox.showerror("Settings Error", f"Could not save settings to {SETTINGS_FILE}:\n{e}")

# --- Settings Window ---

def open_settings_window(parent):
    """Creates and displays the modal Toplevel settings window."""
    settings_win = Toplevel(parent)
    settings_win.title("Settings")
    settings_win.transient(parent)
    settings_win.grab_set()
    settings_win.resizable(False, False) # Prevent resizing settings window

    # Variables bound to the Entry widgets
    steamcmd_path_var = StringVar(value=app_settings.get("steamcmd_path", ""))
    download_dir_var = StringVar(value=app_settings.get("default_download_dir", ""))
    app_id_var = StringVar(value=app_settings.get("app_id", ""))
    user_agent_var = StringVar(value=app_settings.get("user_agent", ""))

    # Main frame with padding
    frame = ttk.Frame(settings_win, padding="15 15 15 15") # Increased padding
    frame.pack(fill="both", expand=True)

    # Configure grid columns
    frame.columnconfigure(1, weight=1) # Allow entry column to expand

    # --- Widgets ---
    # SteamCMD Path
    ttk.Label(frame, text="SteamCMD Path:").grid(row=0, column=0, sticky="w", pady=(0, 2)) # Adjusted padding
    steamcmd_entry = ttk.Entry(frame, textvariable=steamcmd_path_var, width=55) # Slightly wider
    steamcmd_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=(0, 2))
    def browse_steamcmd():
        if sys.platform == "win32":
            filetypes = [("Executable", "*.exe"), ("All files", "*.*")]
            initial_file = "steamcmd.exe"
        else:
            filetypes = [("Shell Script", "*.sh"), ("All files", "*.*")]
            initial_file = "steamcmd.sh"
        filepath = filedialog.askopenfilename(title="Select SteamCMD Executable", filetypes=filetypes, initialfile=initial_file, parent=settings_win)
        if filepath:
            steamcmd_path_var.set(filepath)
    ttk.Button(frame, text="Browse...", command=browse_steamcmd).grid(row=0, column=2, padx=(5, 0), pady=(0, 2)) # Adjusted padding
    ttk.Label(frame, text="(Leave blank to attempt auto-detect)", style="secondary.TLabel").grid(row=1, column=1, columnspan=2, sticky="w", padx=5, pady=(0, 10)) # Hint text, more padding below

    # Default Download Directory
    ttk.Label(frame, text="Default Download Dir:").grid(row=2, column=0, sticky="w", pady=(0, 2))
    download_dir_entry = ttk.Entry(frame, textvariable=download_dir_var, width=55)
    download_dir_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=(0, 2))
    def browse_download_dir():
        dirpath = filedialog.askdirectory(title="Select Default Download Directory", parent=settings_win)
        if dirpath:
            download_dir_var.set(dirpath)
    ttk.Button(frame, text="Browse...", command=browse_download_dir).grid(row=2, column=2, padx=(5, 0), pady=(0, 2))
    ttk.Label(frame, text="(Optional, defaults to system Downloads)", style="secondary.TLabel").grid(row=3, column=1, columnspan=2, sticky="w", padx=5, pady=(0, 10))

    # App ID
    ttk.Label(frame, text="Game App ID:").grid(row=4, column=0, sticky="w", pady=(0, 2))
    app_id_entry = ttk.Entry(frame, textvariable=app_id_var, width=15)
    app_id_entry.grid(row=4, column=1, sticky="w", padx=5, pady=(0, 10)) # Sticky west, padding below

    # User Agent
    ttk.Label(frame, text="User Agent:").grid(row=5, column=0, sticky="w", pady=(0, 2))
    user_agent_entry = ttk.Entry(frame, textvariable=user_agent_var, width=55)
    user_agent_entry.grid(row=5, column=1, columnspan=2, sticky="ew", padx=5, pady=(0, 15)) # Span columns, more padding below

    # --- Separator and Buttons ---
    ttk.Separator(frame, orient='horizontal').grid(row=6, column=0, columnspan=3, sticky='ew', pady=(0, 10))

    button_frame = ttk.Frame(frame) # Place buttons within the main frame grid
    button_frame.grid(row=7, column=0, columnspan=3, sticky="e") # Align buttons right

    def on_save():
        global app_settings
        app_id_val = app_id_var.get().strip()
        if app_id_val and not app_id_val.isdigit():
            messagebox.showerror("Invalid Input", "App ID must be a number.", parent=settings_win)
            return

        new_settings = {
            "steamcmd_path": steamcmd_path_var.get().strip(),
            "default_download_dir": download_dir_var.get().strip(),
            "app_id": app_id_val if app_id_val else get_default_settings()["app_id"],
            "user_agent": user_agent_var.get().strip() or get_default_settings()["user_agent"]
        }
        app_settings.update(new_settings)
        save_settings(app_settings)
        settings_win.destroy()

    def on_cancel():
        settings_win.destroy()

    ttk.Button(button_frame, text="Save", command=on_save, style="Accent.TButton").pack(side="right", padx=(5, 0)) # Added style hint
    ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side="right")

    # --- Final Touches ---
    # Add secondary style for hint labels if theme supports it
    try:
        style = ttk.Style()
        style.configure("secondary.TLabel", foreground="grey")
    except tk.TclError:
        logging.warning("Could not configure secondary label style (theme might not support it).")

    settings_win.update_idletasks() # Calculate size needed
    # Center window relative to parent
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()
    win_width = settings_win.winfo_width()
    win_height = settings_win.winfo_height()
    x = parent_x + (parent_width // 2) - (win_width // 2)
    y = parent_y + (parent_height // 2) - (win_height // 2)
    settings_win.geometry(f'+{x}+{y}')

    settings_win.wait_window() # Block until closed

# --- Core Functions ---

def scrape_mod_details(source, source_type):
    """
    Scrapes mod IDs and names from a Steam Workshop URL or HTML source.

    Uses the User-Agent configured in settings. Handles duplicates by prioritizing
    entries with actual names found over placeholders.

    Args:
        source (str): The URL or raw HTML content.
        source_type (str): 'url' or 'html'.

    Returns:
        list: A list of dictionaries [{'id': mod_id, 'name': mod_name}],
              sorted numerically by mod ID. Returns empty list on error.
    """
    mod_details_dict = {} # Use dict {mod_id: mod_name} to handle duplicates
    try:
        user_agent = app_settings.get("user_agent", get_default_settings()["user_agent"])
        headers = {'User-Agent': user_agent}

        if source_type == 'url':
            logging.info(f"Fetching URL: {source}")
            response = requests.get(source, headers=headers, timeout=15) # Added timeout
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            html_content = response.text
        elif source_type == 'html':
            html_content = source
        else:
            raise ValueError("Invalid source_type. Must be 'url' or 'html'.")

        soup = BeautifulSoup(html_content, 'html.parser')

        # Primary scraping strategy: Find mod container divs
        mod_containers = soup.find_all('div', class_=re.compile(r'(workshopItem|collectionItem)\b'))
        if not mod_containers:
            # Fallback: Try finding divs with class 'item' (less specific)
            mod_containers = soup.find_all('div', class_='item')
        logging.info(f"Found {len(mod_containers)} potential mod containers using primary strategy.")

        placeholder_prefix = "Name not found"

        for container in mod_containers:
            link_element = container.find('a', href=re.compile(r'/sharedfiles/filedetails/\?id='))
            if not link_element: continue # Skip container if no valid link found

            href = link_element.get('href')
            match = re.search(r'id=(\d+)', href)
            if not match: continue # Skip if no ID found in link

            mod_id = match.group(1)

            # Find mod name within the container
            name_element = container.find('div', class_=re.compile(r'(workshopItemTitle|item_title|title)\b', re.IGNORECASE))
            mod_name = ""
            if name_element:
                mod_name = name_element.get_text(strip=True)
            else:
                # Fallback: Try getting name from link text itself
                mod_name_fallback = link_element.get_text(strip=True)
                if mod_name_fallback: mod_name = mod_name_fallback

            # Assign placeholder if no name was found
            if not mod_name: mod_name = f"{placeholder_prefix} ({mod_id})"

            # Store/update in dictionary, prioritizing non-placeholder names
            existing_name = mod_details_dict.get(mod_id)
            if existing_name:
                # Update only if existing name was a placeholder and the new one is not
                if existing_name.startswith(placeholder_prefix) and not mod_name.startswith(placeholder_prefix):
                    mod_details_dict[mod_id] = mod_name
            else:
                # Add if ID is new
                mod_details_dict[mod_id] = mod_name

        # Fallback scraping strategy (if primary found nothing) - Less reliable
        if not mod_details_dict and not mod_containers:
             logging.warning("Primary scraping strategy failed. Trying broader link search fallback.")
             links = soup.find_all('a', href=re.compile(r'https://steamcommunity\.com/sharedfiles/filedetails/\?id='))
             for link in links:
                 href = link.get('href')
                 match = re.search(r'id=(\d+)', href)
                 if match:
                     mod_id = match.group(1)
                     # Attempt to find the *next* title div (less reliable structure assumption)
                     name_element = link.find_next('div', class_='workshopItemTitle')
                     mod_name = name_element.text.strip() if name_element else f"{placeholder_prefix} ({mod_id})"

                     # Heuristic: Try to skip the collection's own link if it appears in results
                     if source_type == 'url' and f"id={mod_id}" in source:
                          parent_div = link.find_parent('div', class_='collectioninfo') # Check common parent for collection link
                          if parent_div:
                              logging.info(f"Skipping potential collection link in fallback: {mod_id}")
                              continue

                     # Apply same dictionary update logic
                     existing_name = mod_details_dict.get(mod_id)
                     if existing_name:
                         if existing_name.startswith(placeholder_prefix) and not mod_name.startswith(placeholder_prefix):
                             mod_details_dict[mod_id] = mod_name
                     else:
                         mod_details_dict[mod_id] = mod_name

        # Convert final dictionary to sorted list
        mod_details = [{'id': k, 'name': v} for k, v in sorted(mod_details_dict.items(), key=lambda item: int(item[0]))]
        logging.info(f"Scraped {len(mod_details)} unique mods.")
        return mod_details

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error fetching URL: {e}")
        messagebox.showerror("Network Error", f"Error fetching URL:\n{e}")
        return []
    except ValueError as e:
         logging.error(f"Value error during scraping setup: {e}")
         messagebox.showerror("Error", f"Configuration error: {e}")
         return []
    except Exception as e:
        logging.exception("An unexpected error occurred during scraping.") # Log full traceback
        messagebox.showerror("Scraping Error", f"An unexpected error occurred during scraping:\n{e}")
        return []


def download_mods_with_steamcmd(mod_ids, install_path):
    """
    Downloads the specified list of mod IDs using SteamCMD.

    Uses the SteamCMD path and Game App ID configured in settings.
    Attempts to auto-detect SteamCMD path if not configured or invalid.

    Args:
        mod_ids (list): A list of mod ID strings to download.
        install_path (str): The target directory path for downloads.
    """
    if not mod_ids:
        logging.warning("download_mods_with_steamcmd called with no mod IDs.")
        messagebox.showinfo("Info", "No mod IDs provided for download.")
        return

    # --- Get Required Settings ---
    steamcmd_path_setting = app_settings.get("steamcmd_path", "")
    app_id = app_settings.get("app_id", get_default_settings()["app_id"])

    if not app_id or not app_id.isdigit():
        errmsg = f"Invalid or missing App ID configured in settings: '{app_id}'. Please set a valid numeric App ID."
        logging.error(errmsg)
        messagebox.showerror("Configuration Error", errmsg)
        return

    # --- Determine SteamCMD Executable Path ---
    steamcmd_executable = ""
    if steamcmd_path_setting and os.path.exists(steamcmd_path_setting) and os.path.isfile(steamcmd_path_setting):
        steamcmd_executable = steamcmd_path_setting
        logging.info(f"Using SteamCMD path from settings: {steamcmd_executable}")
    else:
        if steamcmd_path_setting: # Path was set but invalid
             logging.warning(f"SteamCMD path from settings is invalid: '{steamcmd_path_setting}'. Attempting auto-detect.")
        # Auto-detect logic
        logging.info("Attempting to auto-detect SteamCMD path...")
        base_cmd = "steamcmd"
        exe_suffix = ".exe" if sys.platform == "win32" else ".sh" if sys.platform == "darwin" else ""
        script_name = base_cmd + exe_suffix

        possible_paths = []
        if sys.platform == "win32":
            # Common Windows locations (add more if needed)
            possible_paths = [ os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam", script_name),
                               os.path.join(os.environ.get("ProgramFiles", ""), "Steam", script_name) ]
        elif sys.platform == "darwin": # macOS
             possible_paths = ["~/steamcmd/steamcmd.sh", "/usr/local/bin/steamcmd", "/Applications/SteamCMD/steamcmd.sh"]
        elif sys.platform.startswith("linux"):
             possible_paths = ["~/.steam/steamcmd/steamcmd.sh", "~/steamcmd/steamcmd.sh", "/usr/games/steamcmd", "/usr/bin/steamcmd"]

        # Check common paths first
        found_path = next((os.path.expanduser(p) for p in possible_paths if os.path.exists(os.path.expanduser(p))), None)

        if found_path:
            steamcmd_executable = found_path
            logging.info(f"Auto-detected SteamCMD at: {steamcmd_executable}")
        else:
            # If not found in common paths, assume it's in system PATH
            steamcmd_executable = base_cmd # Let the OS find it via PATH
            logging.info(f"SteamCMD not found in common locations, assuming '{steamcmd_executable}' is in system PATH.")


    # --- Prepare Install Directory ---
    install_path_abs = os.path.expanduser(install_path)
    try:
        os.makedirs(install_path_abs, exist_ok=True)
        logging.info(f"Ensured install directory exists: {install_path_abs}")
    except OSError as e:
        error_message = f"Error creating install directory '{install_path_abs}': {e}"
        logging.error(error_message)
        messagebox.showerror("Directory Error", error_message)
        return

    # --- Build and Execute SteamCMD Command ---
    steamcmd_command = [
        steamcmd_executable,
        "+force_install_dir", install_path_abs,
        "+login", "anonymous",
    ]
    for mod_id in mod_ids:
        steamcmd_command.extend(["+workshop_download_item", app_id, str(mod_id)])
    steamcmd_command.extend(["+quit"])

    logging.info(f"Executing SteamCMD: {' '.join(steamcmd_command)}")

    try:
        # Use Popen to capture output without blocking indefinitely
        process = subprocess.Popen(steamcmd_command,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   text=True,
                                   encoding='utf-8',
                                   errors='replace')

        logging.info("--- SteamCMD Output Start ---")
        full_stdout = ""
        # Read output line by line to allow GUI updates
        while True:
            try:
                 output = process.stdout.readline()
                 if output == '' and process.poll() is not None:
                     break
                 if output:
                     line = output.strip()
                     logging.info(f"SteamCMD: {line}") # Log each line
                     full_stdout += output
                     # Keep GUI responsive (if main window exists)
                     if 'root' in globals() and root.winfo_exists():
                          root.update_idletasks()
            except Exception as e:
                 logging.error(f"Error reading SteamCMD stdout: {e}")
                 break # Stop reading if stream breaks

        stderr_output = process.stderr.read()
        process.wait() # Wait for process to fully terminate
        logging.info("--- SteamCMD Output End ---")

        if stderr_output:
             logging.warning(f"SteamCMD stderr output:\n{stderr_output.strip()}")

        # --- Process Results ---
        if process.returncode != 0:
            error_message = f"SteamCMD process failed (Return Code: {process.returncode})."
            # Provide more specific feedback based on common errors
            if "No such file or directory" in stderr_output or "command not found" in stderr_output or process.returncode == 127:
                 error_message += f"\n\n'{steamcmd_executable}' was not found or is not executable. Please check the path in Settings or ensure SteamCMD is installed correctly and in your system's PATH."
            elif "available CPlatform instance" in full_stdout or "connect to Steam" in stderr_output:
                 error_message += f"\n\nSteamCMD failed to connect or initialize. This might be a temporary Steam network issue or a problem with the SteamCMD installation/login."
            else:
                 error_message += f"\n\nCheck console logs for details.\nStderr: {stderr_output.strip()}"

            logging.error(f"SteamCMD execution failed. {error_message}")
            messagebox.showerror("SteamCMD Error", error_message)
            return

        # Check stdout for success confirmation (heuristic)
        success_count = full_stdout.count("Success. Downloaded item")
        logging.info(f"SteamCMD reported {success_count} successful downloads.")

        if success_count < len(mod_ids):
             warning_msg = f"SteamCMD finished, but only reported {success_count}/{len(mod_ids)} successful downloads. Check console logs for potential issues."
             logging.warning(warning_msg)
             # Show warning only if stderr was empty (otherwise error was already shown)
             if not stderr_output:
                 messagebox.showwarning("Download Status", warning_msg)
        else:
             logging.info("SteamCMD process finished successfully.")
             messagebox.showinfo("Success", f"SteamCMD process finished.\n{success_count}/{len(mod_ids)} items reported as downloaded successfully.")


    except FileNotFoundError:
        # This catches if the steamcmd_executable itself wasn't found by Popen
        error_message = f"Error: The command '{steamcmd_executable}' was not found. Please configure the correct path in Settings or ensure SteamCMD is installed and in your system's PATH."
        logging.error(error_message)
        messagebox.showerror("File Not Found Error", error_message)
        return
    except Exception as e:
        # Catch other potential Popen errors or issues
        logging.exception("An unexpected error occurred during SteamCMD execution.")
        messagebox.showerror("Execution Error", f"An unexpected error occurred running SteamCMD:\n{e}")
        return


def create_mod_selection_gui():
    """Creates and runs the main application window."""
    global root # Make accessible for GUI updates from other functions
    root = tk.Tk()
    root.title("Steam Mod Downloader")
    root.geometry("750x600") # Slightly wider default size
    root.minsize(650, 450) # Set minimum size

    # --- Style Configuration ---
    style = ttk.Style()
    # Available themes: 'clam', 'alt', 'default', 'classic' (Windows might have 'vista', 'xpnative')
    try:
        style.theme_use('clam') # Clam is generally available and decent
    except tk.TclError:
        logging.warning("Failed to set 'clam' theme, using default.")
    # Define an accent style for primary buttons (optional)
    try:
        style.configure("Accent.TButton", font=('Segoe UI', 9, 'bold')) # Example style
    except tk.TclError:
        logging.warning("Could not configure Accent.TButton style.")


    # --- Top Bar (Input Source and Settings) ---
    top_bar = ttk.Frame(root, padding=(10, 10, 10, 5)) # Padding: left, top, right, bottom
    top_bar.pack(fill="x")

    input_frame = ttk.Frame(top_bar)
    input_frame.pack(side="left", fill="x", expand=True, padx=(0, 10)) # Pad between input and settings

    source_type_var = tk.StringVar(value='url')

    # Function to switch between URL entry and HTML text area
    def toggle_source_input():
        if source_type_var.get() == 'url':
            source_label.config(text="Workshop URL:")
            source_entry.pack(side="left", fill="x", expand=True, padx=(0, 5)) # Pack URL entry
            html_scroll_frame.pack_forget() # Hide HTML input
            source_entry.focus_set()
        else:
            source_label.config(text="Paste HTML:")
            source_entry.pack_forget() # Hide URL input
            html_scroll_frame.pack(side="left", fill="both", expand=True, padx=(0, 5)) # Pack HTML frame
            html_text.focus_set()

    # Radio buttons for source type selection
    ttk.Radiobutton(input_frame, text="URL", variable=source_type_var, value='url', command=toggle_source_input).pack(side="left", padx=(0, 5))
    ttk.Radiobutton(input_frame, text="HTML", variable=source_type_var, value='html', command=toggle_source_input).pack(side="left", padx=(0, 10))

    source_label = ttk.Label(input_frame, text="Workshop URL:") # Text updated by toggle_source_input
    source_label.pack(side="left")

    # URL Entry widget (packed/unpacked by toggle_source_input)
    source_entry = ttk.Entry(input_frame, width=50)

    # Frame containing HTML Text widget and its Scrollbar
    html_scroll_frame = ttk.Frame(input_frame)
    html_text = Text(html_scroll_frame, height=4, width=40, wrap="word", relief="solid", borderwidth=1, font=('Consolas', 9)) # Monospace font for HTML
    html_scrollbar = ttk.Scrollbar(html_scroll_frame, orient="vertical", command=html_text.yview)
    html_text['yscrollcommand'] = html_scrollbar.set
    html_scrollbar.pack(side="right", fill="y")
    html_text.pack(side="left", fill="both", expand=True)

    # Load Mods button (associated with input frame)
    load_button = ttk.Button(input_frame, text="Load Mods", command=lambda: load_mods())
    load_button.pack(side="left", padx=(5, 0))

    # Settings Button (aligned right in the top bar)
    settings_button = ttk.Button(top_bar, text="Settings", command=lambda: open_settings_window(root))
    settings_button.pack(side="right")

    toggle_source_input() # Initialize the correct input view


    # --- Mod Selection Area ---
    mod_outer_frame = ttk.LabelFrame(root, text="Available Mods", padding=10)
    mod_outer_frame.pack(fill="both", expand=True, padx=10, pady=(5, 5)) # Consistent padding

    # Frame for Select/Deselect buttons and Info Label
    select_buttons_frame = ttk.Frame(mod_outer_frame)
    select_buttons_frame.pack(fill="x", pady=(0, 10)) # Padding below buttons

    def select_all_mods(select_state):
        """Sets the state of all mod checkboxes."""
        if not mod_vars: return
        for var, _, _ in mod_vars: var.set(select_state)
        update_mod_info() # Update count after changing selection

    ttk.Button(select_buttons_frame, text="Select All", command=lambda: select_all_mods(True)).pack(side="left", padx=(0, 5))
    ttk.Button(select_buttons_frame, text="Deselect All", command=lambda: select_all_mods(False)).pack(side="left")

    # Label to display mod counts
    global info_label
    info_label = ttk.Label(select_buttons_frame, text="Load mods to see details.", anchor="w")
    info_label.pack(side="left", padx=20, fill="x", expand=True) # Expand to fill space


    # Frame containing the scrollable Canvas for the mod list
    mod_list_frame = ttk.Frame(mod_outer_frame)
    mod_list_frame.pack(fill="both", expand=True)

    global canvas, container, scrollbar # Make accessible for population/scrolling
    canvas_bg = style.lookup('TFrame', 'background') # Match canvas background to frame
    canvas = tk.Canvas(mod_list_frame, borderwidth=0, background=canvas_bg, highlightthickness=0)
    scrollbar = ttk.Scrollbar(mod_list_frame, orient="vertical", command=canvas.yview)
    container = ttk.Frame(canvas) # This frame holds the actual checkboxes

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)
    # Embed the container frame within the canvas
    canvas_window = canvas.create_window((0, 0), window=container, anchor="nw", tags="container")

    # --- Scrolling Configuration ---
    # Update scrollregion when the container frame size changes
    def on_frame_configure(event): canvas.configure(scrollregion=canvas.bbox("all"))
    # Resize the container frame width to match the canvas width
    def on_canvas_configure(event): canvas.itemconfig(canvas_window, width=event.width)
    container.bind("<Configure>", on_frame_configure)
    canvas.bind("<Configure>", on_canvas_configure)

    # Mouse wheel scrolling (platform-aware)
    def on_mouse_wheel(event):
        if sys.platform == "win32": delta = int(-1*(event.delta/120))
        elif sys.platform == "darwin": delta = int(-1*event.delta) # macOS uses delta directly
        else: delta = -1 if event.num == 4 else 1 if event.num == 5 else 0 # Linux button 4/5
        canvas.yview_scroll(delta, "units")

    # Bind scrolling only when mouse is over the canvas to avoid interfering with other widgets
    def _bind_scroll(event):
        canvas.bind_all("<MouseWheel>", on_mouse_wheel)
        canvas.bind_all("<Button-4>", lambda e: on_mouse_wheel(e))
        canvas.bind_all("<Button-5>", lambda e: on_mouse_wheel(e))
    def _unbind_scroll(event):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind('<Enter>', _bind_scroll)
    canvas.bind('<Leave>', _unbind_scroll)


    # List to hold references to checkbox variables and mod details
    global mod_vars
    mod_vars = [] # Stores tuples of (BooleanVar, mod_id, mod_name)

    def populate_mod_list(mod_details):
        """Clears and repopulates the scrollable list with mod checkboxes."""
        global mod_vars, container
        # Clear previous widgets from the container frame
        for widget in container.winfo_children():
            widget.destroy()
        mod_vars = [] # Reset the list

        if not mod_details:
            # Display message if no mods were found/loaded
            ttk.Label(container, text="No mods found or error occurred.").pack(pady=10, padx=5)
            update_mod_info() # Update count (to zero)
            return

        # Create and pack a checkbutton for each mod
        for mod in mod_details:
            if 'id' not in mod or 'name' not in mod:
                logging.warning(f"Skipping mod with incomplete data: {mod}")
                continue
            var = BooleanVar(value=True) # Default to selected
            mod_vars.append((var, mod['id'], mod['name']))
            # Create checkbutton inside the container frame
            cb = ttk.Checkbutton(container, text=f"{mod['name']} ({mod['id']})", variable=var, command=update_mod_info)
            cb.pack(anchor="w", fill="x", padx=5, pady=1) # Fill width, minimal vertical padding

        update_mod_info() # Update count label
        canvas.yview_moveto(0) # Scroll list to top
        # Ensure layout is updated before configuring scroll region
        root.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def update_mod_info():
        """Updates the info label with total and selected mod counts."""
        if info_label and info_label.winfo_exists(): # Check if label exists
            total_mods = len(mod_vars)
            enabled_mods = sum(var.get() for var, _, _ in mod_vars)
            info_label.config(text=f"Total Mods: {total_mods}  |  Selected: {enabled_mods}")

    # --- Action Buttons ---
    # Frame for the main download button at the bottom
    download_button_frame = ttk.Frame(root, padding=(10, 5, 10, 10))
    download_button_frame.pack(fill="x", side="bottom")

    download_button = ttk.Button(download_button_frame, text="Download Selected Mods", command=lambda: start_download(), style="Accent.TButton")
    download_button.pack() # Center the button


    # --- Action Functions ---
    def start_download():
        """Initiates the download process for selected mods."""
        if not mod_vars:
            messagebox.showinfo("Info", "No mods loaded to download.")
            return
        selected_mod_ids = [mod_id for var, mod_id, _ in mod_vars if var.get()]
        if not selected_mod_ids:
            messagebox.showinfo("Info", "No mods selected for download.")
            return

        # Determine initial directory for file dialog
        initial_dir_setting = app_settings.get("default_download_dir", "")
        if initial_dir_setting and os.path.isdir(initial_dir_setting):
            initial_dir = initial_dir_setting
        else:
            # Fallback to user's Downloads or Home directory
            initial_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.isdir(initial_dir): initial_dir = os.path.expanduser("~")

        # Ask user for the final installation path
        install_path = filedialog.askdirectory(title="Select Mod Installation Path", initialdir=initial_dir, parent=root)
        if not install_path:
            logging.info("Mod download cancelled by user (directory selection).")
            # messagebox.showinfo("Cancelled", "Download cancelled.") # Optional: explicit cancel message
            return

        # Disable buttons during download process
        set_ui_state(tk.DISABLED)
        root.update_idletasks()

        try:
            logging.info(f"Starting download of {len(selected_mod_ids)} mods to: {install_path}")
            # Consider running in a thread for large downloads to prevent GUI freezing
            # For now, direct call:
            download_mods_with_steamcmd(selected_mod_ids, install_path)
        except Exception as e:
             # Catch unexpected errors during the download call itself
             logging.exception("Unexpected error initiating download function.")
             messagebox.showerror("Error", f"Failed to start download process:\n{e}")
        finally:
            # Re-enable UI elements after download attempt completes
            set_ui_state(tk.NORMAL)

    def load_mods():
        """Handles scraping mods based on user input."""
        source_type = source_type_var.get()
        source = ""
        if source_type == 'url':
            source = source_entry.get().strip()
            # Basic validation: check for http/https prefix and at least one dot
            if not (source.startswith(("http://", "https://")) and "." in source):
                messagebox.showerror("Invalid Input", "Please enter a valid web URL (e.g., https://steamcommunity.com/...).", parent=root)
                return
        elif source_type == 'html':
            source = html_text.get("1.0", tk.END).strip()
            # Basic validation: check if non-empty and looks like HTML start tag
            if not source or not source.lower().startswith(("<html", "<!doctype")):
                 messagebox.showerror("Invalid Input", "Please paste valid HTML source code.", parent=root)
                 return
        else:
            # Should not happen with radio buttons, but good practice
            messagebox.showerror("Error", "Invalid source type selected.", parent=root)
            return

        info_label.config(text="Loading mods...")
        set_ui_state(tk.DISABLED) # Disable UI during loading
        root.update_idletasks()

        try:
            mod_details = scrape_mod_details(source, source_type)
            populate_mod_list(mod_details) # Update the GUI list
        except Exception as e:
             # Catch unexpected errors during scraping call
             logging.exception("Unexpected error initiating scraping function.")
             messagebox.showerror("Error", f"Failed to load mods:\n{e}", parent=root)
             populate_mod_list([]) # Clear list on error
        finally:
             update_mod_info() # Update counts even on error
             set_ui_state(tk.NORMAL) # Re-enable UI

    def set_ui_state(state):
        """Helper function to enable/disable relevant UI elements."""
        widgets_to_toggle = [load_button, settings_button, download_button, source_entry, html_text]
        # Add radio buttons if needed
        # widgets_to_toggle.extend([rb for rb in input_frame.winfo_children() if isinstance(rb, ttk.Radiobutton)])
        for widget in widgets_to_toggle:
            try:
                 # Check if widget exists and supports 'state' configuration
                 if widget.winfo_exists() and hasattr(widget, 'configure'):
                     widget.configure(state=state)
            except tk.TclError:
                 # Ignore if widget state cannot be set (e.g., Text widget state works differently)
                 if isinstance(widget, Text):
                      widget.config(state=state) # Text widget uses config
                 else:
                      logging.warning(f"Could not set state for widget: {widget}")


    # --- Start GUI ---
    root.mainloop()


def main():
    """Main entry point: Loads settings and runs the GUI."""
    load_settings()
    create_mod_selection_gui()


if __name__ == "__main__":
    # Setup basic logging to console
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()
