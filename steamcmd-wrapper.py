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
import shutil
import unicodedata
import threading
import queue

# --- Logging Setup ---
# Using logging provides more flexibility than print (e.g., levels, output to file)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global Settings ---
# app_settings: Dictionary holding application settings, loaded from/saved to file.
#               Using a global dict is simple for this single-window app structure,
#               but consider refactoring into a class if managing more complex state later.
app_settings = {}
# SETTINGS_FILE: Name of the JSON file used for persisting settings.
SETTINGS_FILE = "settings.json"

# --- Utility Functions ---

def sanitize_filename(name):
    """
    Sanitizes a string to create a valid directory name for common OSes.

    - Removes/replaces characters invalid in Windows/Linux/macOS filenames/paths.
    - Normalizes Unicode to ASCII, ignoring characters that cannot be represented.
    - Removes leading/trailing whitespace and dots.
    - Handles Windows reserved names (CON, PRN, etc.).
    - Limits maximum length to prevent issues with path limits.

    Args:
        name (str): The original string (e.g., mod name).

    Returns:
        str: The sanitized string. Returns "Unnamed Mod" if the name is empty
             or becomes empty after sanitization.
    """
    if not name:
        return "Unnamed Mod"

    try:
        # Normalize unicode characters to their closest ASCII equivalent
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    except Exception:
        # Fallback if normalization fails (should be rare)
        name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()

    # Replace invalid path characters with underscore
    # Invalid chars: \ / : * ? " < > | plus control characters
    name = re.sub(r'[\\/:*?"<>|\t\n\r\f\v]+', '_', name)
    name = "".join(c for c in name if unicodedata.category(c)[0] != "C") # Remove control chars

    # Remove leading/trailing whitespace and dots, crucial for Windows validity
    name = name.strip('. ')

    # Prevent names reserved on Windows (case-insensitive check)
    reserved_names = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
                      "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2",
                      "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if name.upper() in reserved_names:
        name = name + "_mod" # Append suffix if reserved

    # Limit length to avoid potential path length issues
    max_len = 100 # Arbitrary limit, adjust if needed
    if len(name) > max_len:
        name = name[:max_len].strip('. ') # Re-strip in case limit cuts mid-space/dot

    # Final check if name became empty after sanitization
    if not name:
        return "Unnamed Mod"

    return name

# --- Settings Management ---

def get_default_settings():
    """Returns a dictionary containing the default application settings."""
    # These serve as fallback values if the settings file is missing or invalid.
    return {
        "steamcmd_path": "", # Empty string triggers auto-detect logic
        "default_download_dir": "", # Empty string uses system default logic (e.g., ~/Downloads)
        "app_id": "294100", # Default to RimWorld App ID as a common example
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36" # Standard UA
    }

def load_settings():
    """
    Loads settings from the JSON file (SETTINGS_FILE).
    If the file doesn't exist, is empty, or contains invalid JSON,
    it falls back to default settings and logs the issue.
    Updates the global `app_settings` dictionary.
    """
    global app_settings
    defaults = get_default_settings()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                # Load JSON data, ensuring it's not empty
                content = f.read()
                if not content:
                    logging.warning(f"Settings file '{SETTINGS_FILE}' is empty. Using defaults.")
                    app_settings = defaults.copy()
                    return
                loaded = json.loads(content)
                # Merge loaded settings with defaults to ensure all expected keys exist
                app_settings = defaults.copy()
                app_settings.update(loaded) # Overwrite defaults with loaded values
                logging.info(f"Settings loaded from {SETTINGS_FILE}")
        except (json.JSONDecodeError, IOError, TypeError) as e:
            # Handle potential errors during file reading or JSON parsing
            logging.error(f"Error loading settings file '{SETTINGS_FILE}': {e}. Using default settings.")
            messagebox.showwarning("Settings Error", f"Could not load settings from {SETTINGS_FILE}:\n{e}\nUsing default values.")
            app_settings = defaults.copy()
    else:
        # Settings file doesn't exist, use defaults
        logging.info(f"{SETTINGS_FILE} not found, using default settings.")
        app_settings = defaults.copy()
        # Consider saving defaults here to create the file on first run:
        # save_settings(app_settings)

def save_settings(settings_dict):
    """
    Saves the provided settings dictionary to SETTINGS_FILE as formatted JSON.

    Args:
        settings_dict (dict): The dictionary containing settings to save.
    """
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            # Use indent for readability, ensure_ascii=False for non-ASCII chars
            json.dump(settings_dict, f, indent=4, ensure_ascii=False)
        logging.info(f"Settings saved to {SETTINGS_FILE}")
    except IOError as e:
        # Handle potential file writing errors
        logging.error(f"Error saving settings to '{SETTINGS_FILE}': {e}")
        messagebox.showerror("Settings Error", f"Could not save settings to {SETTINGS_FILE}:\n{e}")


# --- Settings Window ---

def open_settings_window(parent):
    """
    Creates and displays the modal Toplevel window for editing application settings.
    Loads current settings into the fields and saves them back on confirmation.
    """
    settings_win = Toplevel(parent)
    settings_win.title("Settings")
    settings_win.transient(parent) # Keep on top of parent
    settings_win.grab_set()      # Make modal (block interaction with parent)
    settings_win.resizable(False, False) # Fixed size is fine for settings

    # Tkinter variables linked to the Entry widgets for easy get/set
    steamcmd_path_var = StringVar(value=app_settings.get("steamcmd_path", ""))
    download_dir_var = StringVar(value=app_settings.get("default_download_dir", ""))
    app_id_var = StringVar(value=app_settings.get("app_id", ""))
    user_agent_var = StringVar(value=app_settings.get("user_agent", ""))

    # Main content frame with padding
    frame = ttk.Frame(settings_win, padding="15") # Generous padding
    frame.pack(fill="both", expand=True)
    # Configure the grid column containing the entry fields to expand horizontally
    frame.columnconfigure(1, weight=1)

    # --- SteamCMD Path ---
    ttk.Label(frame, text="SteamCMD Path:").grid(row=0, column=0, sticky="w", pady=(0, 2))
    steamcmd_entry = ttk.Entry(frame, textvariable=steamcmd_path_var, width=55)
    steamcmd_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=(0, 2))
    def browse_steamcmd():
        # Define file types based on OS for the dialog
        if sys.platform == "win32": filetypes, initial_file = [("Executable", "*.exe"), ("All files", "*.*")], "steamcmd.exe"
        else: filetypes, initial_file = [("Shell Script", "*.sh"), ("All files", "*.*")], "steamcmd.sh"
        filepath = filedialog.askopenfilename(title="Select SteamCMD Executable", filetypes=filetypes, initialfile=initial_file, parent=settings_win)
        if filepath: steamcmd_path_var.set(filepath) # Update variable if user selected a file
    ttk.Button(frame, text="Browse...", command=browse_steamcmd).grid(row=0, column=2, padx=(5, 0), pady=(0, 2))
    # Hint label using a secondary style for less emphasis
    ttk.Label(frame, text="(Leave blank for auto-detect)", style="secondary.TLabel").grid(row=1, column=1, columnspan=2, sticky="w", padx=5, pady=(0, 10))

    # --- Default Download Directory ---
    ttk.Label(frame, text="Default Download Dir:").grid(row=2, column=0, sticky="w", pady=(0, 2))
    download_dir_entry = ttk.Entry(frame, textvariable=download_dir_var, width=55)
    download_dir_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=(0, 2))
    def browse_download_dir():
        dirpath = filedialog.askdirectory(title="Select Default Download Directory", parent=settings_win)
        if dirpath: download_dir_var.set(dirpath) # Update variable if user selected a directory
    ttk.Button(frame, text="Browse...", command=browse_download_dir).grid(row=2, column=2, padx=(5, 0), pady=(0, 2))
    ttk.Label(frame, text="(Optional, sets starting point for download dialog)", style="secondary.TLabel").grid(row=3, column=1, columnspan=2, sticky="w", padx=5, pady=(0, 10))

    # --- Game App ID ---
    ttk.Label(frame, text="Game App ID:").grid(row=4, column=0, sticky="w", pady=(0, 2))
    app_id_entry = ttk.Entry(frame, textvariable=app_id_var, width=15)
    app_id_entry.grid(row=4, column=1, sticky="w", padx=5, pady=(0, 10)) # Align left

    # --- User Agent ---
    ttk.Label(frame, text="User Agent:").grid(row=5, column=0, sticky="w", pady=(0, 2))
    user_agent_entry = ttk.Entry(frame, textvariable=user_agent_var, width=55)
    user_agent_entry.grid(row=5, column=1, columnspan=2, sticky="ew", padx=5, pady=(0, 15)) # Span browse column

    # --- Separator and Action Buttons ---
    ttk.Separator(frame, orient='horizontal').grid(row=6, column=0, columnspan=3, sticky='ew', pady=(0, 10))

    # Frame to hold buttons, aligned to the right using grid sticky option
    button_frame = ttk.Frame(frame)
    button_frame.grid(row=7, column=0, columnspan=3, sticky="e") # Align frame itself to the east

    def on_save():
        """Validates input, updates global settings, saves, and closes."""
        global app_settings
        # Simple validation for App ID
        app_id_val = app_id_var.get().strip()
        if app_id_val and not app_id_val.isdigit():
            messagebox.showerror("Invalid Input", "App ID must be a number.", parent=settings_win)
            return # Keep window open

        # Prepare updated settings dictionary
        new_settings = {
            "steamcmd_path": steamcmd_path_var.get().strip(),
            "default_download_dir": download_dir_var.get().strip(),
            # Use default if field is empty, otherwise use validated value
            "app_id": app_id_val if app_id_val else get_default_settings()["app_id"],
            # Use default if field is empty, otherwise use entered value
            "user_agent": user_agent_var.get().strip() or get_default_settings()["user_agent"]
        }
        # Update the global dictionary and save to file
        app_settings.update(new_settings)
        save_settings(app_settings)
        settings_win.destroy() # Close window on successful save

    # Place buttons within the button_frame using pack (simpler for just two buttons)
    ttk.Button(button_frame, text="Save", command=on_save, style="Accent.TButton").pack(side="right", padx=(5, 0))
    ttk.Button(button_frame, text="Cancel", command=settings_win.destroy).pack(side="right")

    # --- Final Setup ---
    # Attempt to configure the secondary label style (might fail depending on theme)
    try:
        style = ttk.Style()
        style.configure("secondary.TLabel", foreground="grey") # Use grey for less emphasis
    except tk.TclError:
        logging.warning("Could not configure secondary label style (theme might not support it).")

    # Calculate position to center the settings window over the parent window
    settings_win.update_idletasks() # Ensure window dimensions are calculated
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()
    win_w = settings_win.winfo_width()
    win_h = settings_win.winfo_height()
    # Calculate top-left corner coordinates for centering
    x = parent_x + (parent_w // 2) - (win_w // 2)
    y = parent_y + (parent_h // 2) - (win_h // 2)
    settings_win.geometry(f'+{x}+{y}') # Set window position

    settings_win.wait_window() # Wait for the settings window to be closed before returning


# --- Core Functions ---

def scrape_mod_details(source, source_type):
    """
    Scrapes mod IDs and names from a Steam Workshop URL or HTML source.

    Prioritizes finding mods within specific container divs (e.g., 'workshopItem').
    Falls back to a broader link search if the primary strategy fails.
    Uses the User-Agent configured in settings. Handles duplicate mod IDs
    by preferring entries where a proper name was found.

    Args:
        source (str): The URL or raw HTML content.
        source_type (str): 'url' or 'html'.

    Returns:
        list: A list of dictionaries [{'id': mod_id, 'name': mod_name}],
              sorted numerically by mod ID. Returns empty list on error.
              Returns None if a fatal error occurred preventing normal return.
    """
    # Using a dictionary keyed by mod_id ensures uniqueness and allows
    # easily replacing placeholder names if a real name is found later.
    mod_details_dict = {}
    try:
        user_agent = app_settings.get("user_agent", get_default_settings()["user_agent"])
        headers = {'User-Agent': user_agent}

        if source_type == 'url':
            logging.info(f"Fetching URL: {source}")
            # Added timeout to prevent indefinite hanging on network issues
            response = requests.get(source, headers=headers, timeout=15)
            response.raise_for_status() # Check for HTTP errors (4xx/5xx)
            html_content = response.text
        elif source_type == 'html':
            html_content = source
        else:
            # This should ideally not be reached if input validation is done, but belt-and-suspenders.
            raise ValueError("Invalid source_type provided to scrape_mod_details.")

        soup = BeautifulSoup(html_content, 'html.parser')

        # --- Primary Scraping Strategy ---
        # Look for divs likely containing individual mod details. Common class names observed.
        # Regex allows matching slight variations if Steam changes class names (e.g., workshopItemLarge).
        mod_containers = soup.find_all('div', class_=re.compile(r'(workshopItem|collectionItem)\b'))
        if not mod_containers:
            # Fallback if primary classes are not found (less reliable)
            mod_containers = soup.find_all('div', class_='item')
        logging.info(f"Found {len(mod_containers)} potential mod containers using primary strategy.")

        placeholder_prefix = "Name not found" # Constant for placeholder name start

        for container in mod_containers:
            # Find the workshop item link within this container
            # Regex looks for the standard filedetails URL pattern.
            link_element = container.find('a', href=re.compile(r'/sharedfiles/filedetails/\?id='))
            if not link_element: continue # Skip if no link found

            href = link_element.get('href')
            match = re.search(r'id=(\d+)', href) # Extract the numeric mod ID
            if not match: continue # Skip if ID couldn't be parsed

            mod_id = match.group(1)

            # Find the mod title div within the container
            # Regex looks for common title class names, case-insensitive.
            name_element = container.find('div', class_=re.compile(r'(workshopItemTitle|item_title|title)\b', re.IGNORECASE))
            mod_name = ""
            if name_element:
                mod_name = name_element.get_text(strip=True) # Get text, remove surrounding whitespace
            else:
                # Fallback: If title div not found, try using the link's text content
                mod_name_fallback = link_element.get_text(strip=True)
                if mod_name_fallback: mod_name = mod_name_fallback

            # Assign placeholder if no name was found by any method
            if not mod_name: mod_name = f"{placeholder_prefix} ({mod_id})"

            # --- Store/Update Mod Details ---
            existing_name = mod_details_dict.get(mod_id)
            # Add if new, OR update if the existing entry was just a placeholder and the new one isn't.
            # This prioritizes keeping a real name once found.
            if not existing_name or (existing_name.startswith(placeholder_prefix) and not mod_name.startswith(placeholder_prefix)):
                mod_details_dict[mod_id] = mod_name

        # --- Fallback Scraping Strategy ---
        # Use this only if the primary strategy yielded absolutely nothing.
        # This is less reliable as it finds *all* matching links on the page,
        # potentially including related items or duplicates.
        if not mod_details_dict and not mod_containers:
             logging.warning("Primary scraping strategy failed. Trying broader link search fallback.")
             # Find all links matching the filedetails pattern anywhere on the page
             links = soup.find_all('a', href=re.compile(r'https://steamcommunity\.com/sharedfiles/filedetails/\?id='))
             for link in links:
                 href = link.get('href')
                 match = re.search(r'id=(\d+)', href)
                 if match:
                     mod_id = match.group(1)
                     # Attempt to find the *next* title div after the link (less reliable)
                     name_element = link.find_next('div', class_='workshopItemTitle')
                     mod_name = name_element.text.strip() if name_element else f"{placeholder_prefix} ({mod_id})"

                     # Heuristic check to try and skip the collection's own link in the results
                     # Checks if the link is inside a div commonly used for the main collection info.
                     if source_type == 'url' and f"id={mod_id}" in source and link.find_parent('div', class_='collectioninfo'):
                          logging.info(f"Skipping potential collection link in fallback: {mod_id}")
                          continue # Skip this link

                     # Apply same dictionary update logic as primary strategy
                     existing_name = mod_details_dict.get(mod_id)
                     if not existing_name or (existing_name.startswith(placeholder_prefix) and not mod_name.startswith(placeholder_prefix)):
                         mod_details_dict[mod_id] = mod_name

        # Convert the final dictionary to a list of dicts, sorted numerically by ID
        mod_details = [{'id': k, 'name': v} for k, v in sorted(mod_details_dict.items(), key=lambda item: int(item[0]))]
        logging.info(f"Scraped {len(mod_details)} unique mods.")
        return mod_details

    # --- Error Handling ---
    except requests.exceptions.RequestException as e:
        # Handle network-related errors (DNS, connection, timeout, etc.)
        logging.error(f"Network error fetching URL: {e}")
        messagebox.showerror("Network Error", f"Error fetching URL:\n{e}")
        return [] # Return empty list on network error
    except ValueError as e:
         # Handle specific value errors (e.g., invalid source_type)
         logging.error(f"Value error during scraping setup: {e}")
         messagebox.showerror("Error", f"Configuration error: {e}")
         return []
    except Exception as e:
        # Catch any other unexpected errors during scraping/parsing
        logging.exception("An unexpected error occurred during scraping.") # Log full traceback
        messagebox.showerror("Scraping Error", f"An unexpected error occurred during scraping:\n{e}")
        return [] # Return empty list for other errors


def download_mods_with_steamcmd(selected_mods, install_path, progress_queue):
    """
    Manages the SteamCMD download process and subsequent file operations.

    1. Determines the SteamCMD executable path (from settings or auto-detect).
    2. Creates a temporary download directory inside the user's chosen install path.
    3. Runs SteamCMD using subprocess.Popen to download all selected mods into the temp dir.
    4. Waits for SteamCMD to complete.
    5. If SteamCMD was successful, iterates through downloaded mods:
        - Sanitizes the mod name.
        - Moves the mod folder from the temp structure to the final install path,
          renaming it to the sanitized name.
        - Handles potential filename collisions by appending the mod ID.
    6. Cleans up the temporary download directory.
    7. Sends progress and status updates to the main GUI thread via the progress_queue.

    Args:
        selected_mods (list): List of tuples [(mod_id, mod_name), ...].
        install_path (str): The target base directory chosen by the user.
        progress_queue (queue.Queue): Queue for sending progress/status dicts.
    """
    # Send initial status update to the progress window
    progress_queue.put({'status': 'Initializing download...', 'overall_value': 0})

    if not selected_mods:
        logging.warning("download_mods_with_steamcmd called with no selected mods.")
        progress_queue.put({'error': 'No mods selected for download.', 'finished': True})
        return

    # Extract just the IDs needed for the SteamCMD command line
    mod_ids = [mod_id for mod_id, _ in selected_mods]

    # --- Get Settings and Validate ---
    steamcmd_path_setting = app_settings.get("steamcmd_path", "")
    app_id = app_settings.get("app_id", get_default_settings()["app_id"])
    if not app_id or not app_id.isdigit():
        errmsg = f"Invalid or missing App ID in settings: '{app_id}'. Cannot download."
        logging.error(errmsg)
        progress_queue.put({'error': errmsg, 'finished': True}) # Send error via queue
        return

    # --- Determine SteamCMD Executable ---
    # (Logic remains the same: check settings, then auto-detect based on OS, finally assume in PATH)
    steamcmd_executable = ""
    if steamcmd_path_setting and os.path.exists(steamcmd_path_setting) and os.path.isfile(steamcmd_path_setting):
        steamcmd_executable = steamcmd_path_setting
        logging.info(f"Using SteamCMD path from settings: {steamcmd_executable}")
    else:
        if steamcmd_path_setting: logging.warning(f"SteamCMD path invalid: '{steamcmd_path_setting}'. Auto-detecting.")
        logging.info("Attempting to auto-detect SteamCMD path...")
        base_cmd = "steamcmd"; exe_suffix = ".exe" if sys.platform == "win32" else ".sh" if sys.platform == "darwin" else ""
        script_name = base_cmd + exe_suffix; possible_paths = []
        # Define common installation paths based on OS
        if sys.platform == "win32": possible_paths = [ os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam", script_name), os.path.join(os.environ.get("ProgramFiles", ""), "Steam", script_name) ]
        elif sys.platform == "darwin": possible_paths = ["~/steamcmd/steamcmd.sh", "/usr/local/bin/steamcmd", "/Applications/SteamCMD/steamcmd.sh"]
        elif sys.platform.startswith("linux"): possible_paths = ["~/.steam/steamcmd/steamcmd.sh", "~/steamcmd/steamcmd.sh", "/usr/games/steamcmd", "/usr/bin/steamcmd"]
        # Find first existing path from the list
        found_path = next((os.path.expanduser(p) for p in possible_paths if os.path.exists(os.path.expanduser(p))), None)
        if found_path:
            steamcmd_executable = found_path
            logging.info(f"Auto-detected SteamCMD at: {steamcmd_executable}")
        else:
            # Fallback: Assume the command name is in the system's PATH environment variable
            steamcmd_executable = base_cmd
            logging.info(f"SteamCMD not found in common locations, assuming '{steamcmd_executable}' is in system PATH.")


    # --- Prepare Temporary Download Path ---
    # We create a temporary subdir to contain the 'steamapps' structure SteamCMD creates.
    # This prevents cluttering the user's chosen directory directly.
    install_path_abs = os.path.expanduser(install_path)
    # Using a name starting with '_' often signifies temporary/internal use.
    temp_download_base = os.path.join(install_path_abs, "_steamcmd_temp_download")
    steamcmd_install_dir = temp_download_base # This is the path passed to SteamCMD's +force_install_dir

    try:
        # Ensure the base directory and the temp subdir exist
        os.makedirs(steamcmd_install_dir, exist_ok=True)
        logging.info(f"Ensured temporary download base exists: {steamcmd_install_dir}")
    except OSError as e:
        error_message = f"Error creating temporary directory '{steamcmd_install_dir}': {e}"
        logging.error(error_message)
        progress_queue.put({'error': error_message, 'finished': True})
        return

    # --- Build and Execute SteamCMD Command ---
    steamcmd_command = [
        steamcmd_executable,
        "+login", "anonymous", # Use anonymous login for workshop downloads
        "+force_install_dir", steamcmd_install_dir, # Tell SteamCMD where to put 'steamapps'
    ]
    # Add download command for each selected mod ID
    for mod_id in mod_ids:
        steamcmd_command.extend(["+workshop_download_item", app_id, str(mod_id)])
    steamcmd_command.extend(["+quit"]) # Ensure SteamCMD exits after commands

    logging.info(f"Executing SteamCMD: {' '.join(steamcmd_command)}")
    progress_queue.put({'status': 'Running SteamCMD (this may take a while)...'}) # Update status

    process_success = False # Flag to track if SteamCMD ran without critical errors
    full_stdout = ""
    stderr_output = ""
    try:
        # Use Popen for non-blocking execution (though we wait with communicate).
        # Capture stdout/stderr for logging and basic result checking.
        process = subprocess.Popen(steamcmd_command,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   text=True, # Decode output as text
                                   encoding='utf-8', # Specify encoding
                                   errors='replace') # Handle potential decoding errors

        # communicate() waits for process termination and reads all output.
        # Good for processes that finish relatively quickly and don't produce massive output.
        # For extremely long downloads or huge output, line-by-line reading (as in previous version)
        # might be better, but requires more complex handling of process state.
        full_stdout, stderr_output = process.communicate()

        logging.info("--- SteamCMD Output Start ---")
        logging.info(full_stdout.strip()) # Log captured stdout
        logging.info("--- SteamCMD Output End ---")
        if stderr_output:
            logging.warning(f"SteamCMD stderr output:\n{stderr_output.strip()}") # Log stderr if any

        # --- Check SteamCMD Result ---
        if process.returncode != 0:
            # SteamCMD exited with an error code
            error_message = f"SteamCMD process failed (Code: {process.returncode})."
            # Provide more specific feedback based on common error messages/codes
            if "No such file or directory" in stderr_output or "command not found" in stderr_output or process.returncode == 127:
                 error_message += f"\n\n'{steamcmd_executable}' was not found or is not executable. Check Settings or PATH."
            elif "available CPlatform instance" in full_stdout or "connect to Steam" in stderr_output:
                 error_message += f"\n\nSteamCMD failed to connect or initialize. Check network or SteamCMD install."
            else:
                 # Generic error message
                 error_message += f"\n\nCheck console logs for details.\nStderr: {stderr_output.strip()}"
            logging.error(f"SteamCMD execution failed. {error_message}")
            progress_queue.put({'error': error_message, 'finished': True})
            # Do not proceed to post-processing if SteamCMD failed
            return
        else:
             # SteamCMD exited with code 0, assume success for now
             process_success = True

    except FileNotFoundError:
        # This specifically catches if the steamcmd_executable itself couldn't be found by Popen
        error_message = f"Error: Command '{steamcmd_executable}' not found. Check Settings or system PATH."
        logging.error(error_message)
        progress_queue.put({'error': error_message, 'finished': True})
        return
    except Exception as e:
        # Catch other potential errors during Popen or communicate
        logging.exception("Unexpected error during SteamCMD execution.")
        progress_queue.put({'error': f"Unexpected error running SteamCMD:\n{e}", 'finished': True})
        return

    # --- Post-Download Processing: Move and Rename ---
    if not process_success:
        # This block should technically not be reached due to returns above, but safety first.
        logging.error("Skipping post-download: SteamCMD did not complete successfully.")
        return

    logging.info("SteamCMD finished. Starting post-download move and rename...")
    # Reset overall progress for the move/rename stage
    progress_queue.put({'status': 'Processing downloaded mods...', 'overall_value': 0})

    mods_moved_count = 0
    mods_failed_count = 0
    total_mods_to_process = len(selected_mods)

    for i, (mod_id, mod_name) in enumerate(selected_mods):
        # Update progress display before processing each mod
        progress_queue.put({
            'status': f'Processing {i+1}/{total_mods_to_process}', # e.g., "Processing 5/10"
            'current_mod': f'{mod_name} ({mod_id})', # Show which mod is being handled
            'overall_value': i # Update overall bar (0 to total_mods-1)
        })

        # Construct the expected path where SteamCMD placed the mod content
        source_mod_path = os.path.join(steamcmd_install_dir, 'steamapps', 'workshop', 'content', app_id, mod_id)

        # Sanitize the mod name to create a valid target folder name
        target_folder_name_base = sanitize_filename(mod_name)
        # Construct the initial target path directly under the user's chosen install directory
        target_mod_path = os.path.join(install_path_abs, target_folder_name_base)

        # --- Handle Potential Name Collisions ---
        # If a directory with the sanitized name already exists, append the mod ID
        # to ensure uniqueness. Check again in case even that exists (highly unlikely).
        collision_counter = 1
        target_folder_name = target_folder_name_base
        while os.path.exists(target_mod_path):
            logging.warning(f"Target path '{target_mod_path}' already exists. Handling collision.")
            # First attempt: append mod ID
            target_folder_name = f"{target_folder_name_base}_{mod_id}"
            target_mod_path = os.path.join(install_path_abs, target_folder_name)
            # If ID-appended name also exists, append a counter
            if os.path.exists(target_mod_path):
                 target_folder_name = f"{target_folder_name_base}_{mod_id}_{collision_counter}"
                 target_mod_path = os.path.join(install_path_abs, target_folder_name)
                 collision_counter += 1

            # Safety break to prevent infinite loop in extremely unlikely scenarios
            if collision_counter > 10:
                 logging.error(f"Could not find unique target name for mod ID {mod_id} near '{target_folder_name_base}'. Skipping move.")
                 mods_failed_count += 1
                 break # Break collision handling loop for this mod

        if os.path.exists(target_mod_path): continue # Skip this mod if collision handling failed

        # --- Move the Mod Directory ---
        if os.path.isdir(source_mod_path):
            try:
                logging.info(f"Moving '{source_mod_path}' to '{target_mod_path}'")
                # shutil.move works for renaming/moving directories
                shutil.move(source_mod_path, target_mod_path)
                mods_moved_count += 1
            except (shutil.Error, OSError, IOError) as e:
                # Catch errors during the move operation (permissions, disk full, etc.)
                logging.error(f"Error moving mod ID {mod_id} from '{source_mod_path}' to '{target_mod_path}': {e}")
                mods_failed_count += 1
        else:
            # This case occurs if SteamCMD exited successfully but failed to download this specific item.
            logging.warning(f"Source directory for mod ID {mod_id} not found at '{source_mod_path}'. Download might have failed silently. Skipping move.")
            mods_failed_count += 1 # Count as failed if source doesn't exist

    logging.info(f"Finished moving mods. Moved: {mods_moved_count}, Failed/Skipped: {mods_failed_count}")

    # --- Cleanup Temporary Directory ---
    # Attempt to remove the entire temporary directory structure used by SteamCMD.
    try:
        logging.info(f"Removing temporary download directory: {temp_download_base}")
        shutil.rmtree(temp_download_base) # Recursively remove the temp base dir
        logging.info("Removed temporary directory.")
    except (OSError, IOError) as e:
        # Log warning if cleanup fails (e.g., permissions, files in use)
        # Manual cleanup might be needed by the user in this case.
        logging.warning(f"Could not remove temporary download directory '{temp_download_base}': {e}.")

    # --- Send Final Update to GUI ---
    final_status = f"Finished. Moved: {mods_moved_count}, Failed/Skipped: {mods_failed_count}."
    progress_queue.put({
        'status': final_status,
        'overall_value': total_mods_to_process, # Ensure overall bar reaches 100%
        'finished': True, # Signal completion
        'final_message': final_status, # Message for the final popup
        'show_warning': mods_failed_count > 0 # Flag to show warning if issues occurred
    })


# --- Progress Window ---

# Global references to the progress window and its components
# Necessary because updates happen via callbacks scheduled from the main thread
progress_window = None
progress_bar_overall = None
progress_bar_current = None
progress_label_status = None
progress_label_current_mod = None
progress_overall_var = None
progress_status_var = None
progress_current_mod_var = None

def create_progress_window(parent, total_mods):
    """Creates the non-modal progress Toplevel window."""
    global progress_window, progress_bar_overall, progress_bar_current
    global progress_label_status, progress_label_current_mod
    global progress_overall_var, progress_status_var, progress_current_mod_var

    # Destroy previous instance if it exists (e.g., user starts new download)
    if progress_window and progress_window.winfo_exists():
        progress_window.destroy()

    progress_window = Toplevel(parent)
    progress_window.title("Download Progress")
    progress_window.geometry("450x180")
    progress_window.resizable(False, False)
    # Not modal - allows interaction with main window (though buttons are disabled)

    # Intercept the window close ('X') button click
    # Prevents closing while the background task is running.
    progress_window.protocol("WM_DELETE_WINDOW",
        lambda: messagebox.showwarning("In Progress", "Download is in progress. Please wait.", parent=progress_window))

    frame = ttk.Frame(progress_window, padding="15")
    frame.pack(fill="both", expand=True)

    # --- Widgets for Progress Display ---
    # Status Label (e.g., "Running SteamCMD...", "Processing mods...")
    progress_status_var = StringVar(value="Initializing...")
    ttk.Label(frame, text="Status:").pack(anchor="w")
    progress_label_status = ttk.Label(frame, textvariable=progress_status_var, anchor="w", wraplength=400)
    progress_label_status.pack(fill="x", pady=(0, 10))

    # Current Item Label (e.g., "Mod Name (12345)")
    progress_current_mod_var = StringVar(value="N/A")
    ttk.Label(frame, text="Current Item:").pack(anchor="w")
    progress_label_current_mod = ttk.Label(frame, textvariable=progress_current_mod_var, anchor="w", wraplength=400)
    progress_label_current_mod.pack(fill="x", pady=(0, 5))

    # Current Item Progress Bar (Indeterminate - pulses)
    # Used because we can't get granular % progress from SteamCMD easily.
    progress_bar_current = ttk.Progressbar(frame, mode='indeterminate', length=400)
    progress_bar_current.pack(fill="x", pady=(0, 15))
    progress_bar_current.start(10) # Start pulsing animation (interval in ms)

    # Overall Progress Bar (Determinate - fills up)
    progress_overall_var = tk.DoubleVar() # Use DoubleVar for smoother updates if needed
    ttk.Label(frame, text="Overall Progress:").pack(anchor="w")
    # Maximum value is the total number of mods to process
    progress_bar_overall = ttk.Progressbar(frame, mode='determinate', length=400, variable=progress_overall_var, maximum=total_mods)
    progress_bar_overall.pack(fill="x")

    # Center the progress window over the main window
    progress_window.update_idletasks()
    parent_x, parent_y = parent.winfo_rootx(), parent.winfo_rooty(); parent_w, parent_h = parent.winfo_width(), parent.winfo_height()
    win_w, win_h = progress_window.winfo_width(), progress_window.winfo_height(); x = parent_x + (parent_w // 2) - (win_w // 2); y = parent_y + (parent_h // 2) - (win_h // 2)
    progress_window.geometry(f'+{x}+{y}')

def update_progress_display(update_data):
    """
    Updates the widgets in the progress window based on data received from the queue.
    This function MUST run in the main GUI thread.
    """
    global progress_window, progress_bar_overall, progress_bar_current
    global progress_label_status, progress_label_current_mod
    global progress_overall_var, progress_status_var, progress_current_mod_var

    # Check if the progress window still exists before trying to update it
    if not progress_window or not progress_window.winfo_exists():
        logging.warning("Progress window closed or invalid, cannot update display.")
        return

    # Update labels and progress bars based on keys present in the update dictionary
    if 'status' in update_data:
        progress_status_var.set(update_data['status'])
    if 'current_mod' in update_data:
        progress_current_mod_var.set(update_data['current_mod'])
    if 'overall_value' in update_data:
        progress_overall_var.set(update_data['overall_value'])

    # Handle the 'finished' signal
    if update_data.get('finished', False):
        progress_bar_current.stop() # Stop the indeterminate pulsing
        progress_bar_current['mode'] = 'determinate' # Change mode to fill
        progress_bar_current['value'] = progress_bar_current['maximum'] # Fill the bar

        # Re-enable the 'X' button to allow normal closing now
        progress_window.protocol("WM_DELETE_WINDOW", progress_window.destroy)

        # Display the final status message (error, warning, or success)
        final_message = update_data.get('final_message', "Operation finished.")
        if update_data.get('error'):
             messagebox.showerror("Error", update_data['error'], parent=progress_window)
        elif update_data.get('show_warning'):
             messagebox.showwarning("Finished with Issues", final_message + "\nCheck logs for details.", parent=progress_window)
        else:
             messagebox.showinfo("Finished", final_message, parent=progress_window)

        # Consider automatically closing the progress window after a short delay or immediately
        # progress_window.after(2000, progress_window.destroy)


def check_download_progress(progress_queue):
    """
    Periodically checks the progress queue for updates from the download thread.
    Schedules itself to run again using `root.after` until a 'finished' signal is received.
    This function runs in the main GUI thread.
    """
    global progress_window, root # Need root to schedule next check

    try:
        # Process all messages currently in the queue to avoid lag
        while True:
            update_data = progress_queue.get_nowait() # Non-blocking get
            update_progress_display(update_data) # Update GUI elements

            # If the 'finished' flag is set in the update, stop the check loop
            if update_data.get('finished', False):
                set_ui_state(tk.NORMAL) # Re-enable the main UI
                logging.info("Download thread finished. Stopping progress check.")
                return # Exit the function, stopping the loop
    except queue.Empty:
        # Queue is empty, no updates right now. This is normal.
        pass
    except Exception as e:
        # Catch errors during the update process itself
        logging.exception("Error processing progress queue update.")
        # Optionally display an error to the user or try to recover

    # Reschedule the check if the progress window is still open
    # This creates the loop that periodically checks the queue.
    if progress_window and progress_window.winfo_exists():
        # Schedule this function to run again after 100ms
        root.after(100, lambda: check_download_progress(progress_queue))
    else:
        # Window was closed manually (though we try to prevent this) or unexpectedly
        logging.warning("Progress window closed unexpectedly. Stopping progress check.")
        # Ensure UI is re-enabled if the thread might still be running (though it shouldn't be)
        set_ui_state(tk.NORMAL)


# --- Main GUI Creation ---

def create_mod_selection_gui():
    """Creates and runs the main application window and its components."""
    global root # Make main window accessible globally for scheduling checks
    root = tk.Tk()
    root.title("Steam Mod Downloader")
    root.geometry("750x600") # Initial size
    root.minsize(650, 450) # Minimum allowed size

    # --- Style Configuration ---
    style = ttk.Style()
    try:
        # 'clam' is a good cross-platform theme available in ttk
        style.theme_use('clam')
    except tk.TclError:
        logging.warning("Failed to set 'clam' theme, using default.")
    # Define an optional 'Accent' style for primary action buttons
    try:
        style.configure("Accent.TButton", font=('Segoe UI', 9, 'bold')) # Example: bold font
    except tk.TclError:
        logging.warning("Could not configure Accent.TButton style.")

    # --- Top Bar Frame ---
    # Holds input selection, input fields, load button, settings button
    top_bar = ttk.Frame(root, padding=(10, 10, 10, 5))
    top_bar.pack(fill="x", side="top") # Pack at the top, fill horizontally

    # --- Input Frame (within Top Bar) ---
    # Using grid layout for better control over alignment within this frame
    input_frame = ttk.Frame(top_bar)
    input_frame.pack(side="left", fill="x", expand=True, padx=(0, 10)) # Expand to fill space left of Settings button
    # Configure grid columns for input_frame
    input_frame.columnconfigure(1, weight=1) # Allow column 1 (entry/text) to expand

    source_type_var = tk.StringVar(value='url') # Variable for radio buttons

    # --- Widgets within Input Frame (using grid) ---
    # Radio buttons frame (optional, but helps group them)
    radio_frame = ttk.Frame(input_frame)
    radio_frame.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 5)) # Span 2 rows, stick N+S
    ttk.Radiobutton(radio_frame, text="URL", variable=source_type_var, value='url', command=lambda: toggle_source_input()).pack(anchor="w")
    ttk.Radiobutton(radio_frame, text="HTML", variable=source_type_var, value='html', command=lambda: toggle_source_input()).pack(anchor="w")

    # Label (changes text based on radio selection)
    source_label = ttk.Label(input_frame, text="Workshop URL:")
    source_label.grid(row=0, column=1, sticky="sw", padx=(0, 5), pady=(0,1)) # Align bottom-west

    # URL Entry widget (shown/hidden by toggle_source_input)
    source_entry = ttk.Entry(input_frame, width=50)
    source_entry.grid(row=1, column=1, sticky="ew", padx=(0, 5)) # Expand East-West

    # Frame for HTML Text widget + Scrollbar (shown/hidden by toggle_source_input)
    html_scroll_frame = ttk.Frame(input_frame)
    html_scroll_frame.grid(row=1, column=1, sticky="nsew", padx=(0, 5)) # Fill cell
    html_text = Text(html_scroll_frame, height=4, width=40, wrap="word", relief="solid", borderwidth=1, font=('Consolas', 9))
    html_scrollbar = ttk.Scrollbar(html_scroll_frame, orient="vertical", command=html_text.yview)
    html_text['yscrollcommand'] = html_scrollbar.set
    html_scrollbar.pack(side="right", fill="y")
    html_text.pack(side="left", fill="both", expand=True)

    # Load Mods button
    load_button = ttk.Button(input_frame, text="Load Mods", command=lambda: load_mods())
    load_button.grid(row=1, column=2, sticky="ew", padx=(5, 0)) # Align next to input field

    # --- Settings Button (in top_bar, aligned right) ---
    settings_button = ttk.Button(top_bar, text="Settings", command=lambda: open_settings_window(root))
    settings_button.pack(side="right", anchor="ne") # Anchor North-East

    # Function to switch between URL entry and HTML text area visibility
    def toggle_source_input():
        if source_type_var.get() == 'url':
            source_label.config(text="Workshop URL:")
            # Manage grid children directly for show/hide
            source_entry.grid() # Show URL entry
            html_scroll_frame.grid_remove() # Hide HTML frame
            source_entry.focus_set()
        else:
            source_label.config(text="Paste HTML:")
            source_entry.grid_remove() # Hide URL entry
            html_scroll_frame.grid() # Show HTML frame
            html_text.focus_set()
    toggle_source_input() # Call initially to set the default view


    # --- Mod Selection Area ---
    # LabelFrame provides a border and title for the section
    mod_outer_frame = ttk.LabelFrame(root, text="Available Mods", padding=10)
    mod_outer_frame.pack(fill="both", expand=True, padx=10, pady=(5, 5))

    # Frame for Select/Deselect buttons and Info Label at the top of the mod list
    select_buttons_frame = ttk.Frame(mod_outer_frame)
    select_buttons_frame.pack(fill="x", pady=(0, 10)) # Space below this frame

    def select_all_mods(select_state):
        """Sets the state of all mod checkboxes."""
        if not mod_vars: return # Do nothing if list is empty
        for var, _, _ in mod_vars: var.set(select_state)
        update_mod_info() # Update count display

    ttk.Button(select_buttons_frame, text="Select All", command=lambda: select_all_mods(True)).pack(side="left", padx=(0, 5))
    ttk.Button(select_buttons_frame, text="Deselect All", command=lambda: select_all_mods(False)).pack(side="left")
    # Info label to show mod counts, expands to fill remaining space
    global info_label
    info_label = ttk.Label(select_buttons_frame, text="Load mods to see details.", anchor="w")
    info_label.pack(side="left", padx=20, fill="x", expand=True)

    # Frame containing the scrollable Canvas for the checkbutton list
    mod_list_frame = ttk.Frame(mod_outer_frame)
    mod_list_frame.pack(fill="both", expand=True)

    global canvas, container, scrollbar # References needed for updates
    # Use style lookup for background consistency
    canvas_bg = style.lookup('TFrame', 'background')
    canvas = tk.Canvas(mod_list_frame, borderwidth=0, background=canvas_bg, highlightthickness=0)
    scrollbar = ttk.Scrollbar(mod_list_frame, orient="vertical", command=canvas.yview)
    # This inner 'container' frame actually holds the checkbuttons
    container = ttk.Frame(canvas)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)
    # Place the container frame onto the canvas
    canvas_window = canvas.create_window((0, 0), window=container, anchor="nw", tags="container")

    # --- Scrolling Configuration ---
    # Update the canvas scrollregion when the container frame's size changes
    def on_frame_configure(event): canvas.configure(scrollregion=canvas.bbox("all"))
    # Update the container frame's width to match the canvas width when canvas resizes
    def on_canvas_configure(event): canvas.itemconfig(canvas_window, width=event.width)
    container.bind("<Configure>", on_frame_configure) # Bind to container size changes
    canvas.bind("<Configure>", on_canvas_configure) # Bind to canvas size changes

    # Mouse wheel scrolling logic (platform-specific delta calculation)
    def on_mouse_wheel(event):
        if sys.platform == "win32": delta = int(-1*(event.delta/120))
        elif sys.platform == "darwin": delta = int(-1*event.delta)
        else: delta = -1 if event.num == 4 else 1 if event.num == 5 else 0 # Linux buttons 4/5
        canvas.yview_scroll(delta, "units")

    # Bind mouse wheel events only when the cursor is over the canvas
    # This prevents interference if other scrollable elements are added later.
    def _bind_scroll(event):
        # Use bind_all for broader compatibility, especially on Linux
        canvas.bind_all("<MouseWheel>", on_mouse_wheel)
        canvas.bind_all("<Button-4>", lambda e: on_mouse_wheel(e))
        canvas.bind_all("<Button-5>", lambda e: on_mouse_wheel(e))
    def _unbind_scroll(event):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")
    canvas.bind('<Enter>', _bind_scroll) # Bind when mouse enters canvas
    canvas.bind('<Leave>', _unbind_scroll) # Unbind when mouse leaves


    # --- Mod List Data and Population ---
    # Global list holding (BooleanVar, mod_id, mod_name) tuples
    global mod_vars
    mod_vars = []

    def populate_mod_list(mod_details):
        """Clears and repopulates the scrollable list with mod checkbuttons."""
        global mod_vars, container
        # Clear previous checkbuttons from the container
        for widget in container.winfo_children():
            widget.destroy()
        mod_vars = [] # Reset data list

        if not mod_details:
            # Display a message if the list is empty
            ttk.Label(container, text="No mods found or error occurred.").pack(pady=10, padx=5)
            update_mod_info() # Ensure count is updated (to 0)
            return

        # Create and pack a checkbutton for each mod detail found
        for mod in mod_details:
            # Basic validation of mod data structure
            if 'id' not in mod or 'name' not in mod:
                logging.warning(f"Skipping mod with incomplete data: {mod}")
                continue
            var = BooleanVar(value=True) # Checkbox variable, default to selected
            mod_vars.append((var, mod['id'], mod['name'])) # Store var, id, and name
            # Create the checkbutton inside the scrollable container
            cb = ttk.Checkbutton(container, text=f"{mod['name']} ({mod['id']})", variable=var, command=update_mod_info)
            # Pack vertically, anchor west, fill horizontally, add minimal padding
            cb.pack(anchor="w", fill="x", padx=5, pady=1)

        update_mod_info() # Update the count label
        canvas.yview_moveto(0) # Scroll list to the top
        # Crucial: Update layout calculations before setting scroll region
        root.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all")) # Set scrollable area

    def update_mod_info():
        """Updates the info label text with total and selected mod counts."""
        # Check if the label widget still exists before trying to configure it
        if info_label and info_label.winfo_exists():
            total_mods = len(mod_vars)
            enabled_mods = sum(var.get() for var, _, _ in mod_vars) # Count checked boxes
            info_label.config(text=f"Total Mods: {total_mods}  |  Selected: {enabled_mods}")

    # --- Download Button Frame ---
    # Placed at the bottom of the window
    download_button_frame = ttk.Frame(root, padding=(10, 5, 10, 10))
    download_button_frame.pack(fill="x", side="bottom") # Pack at bottom, fill horizontally
    # The main action button
    download_button = ttk.Button(download_button_frame, text="Download Selected Mods", command=lambda: start_download(), style="Accent.TButton")
    download_button.pack() # Center the button by default


    # --- Action Functions (Callbacks) ---
    def start_download():
        """
        Initiates the download process:
        1. Gathers selected mod data.
        2. Asks user for installation directory.
        3. Creates and shows the progress window.
        4. Disables main UI elements.
        5. Starts the download logic in a separate thread.
        6. Starts the progress queue checking loop in the main thread.
        """
        if not mod_vars:
            messagebox.showinfo("Info", "No mods loaded to download.", parent=root)
            return
        # Get list of (id, name) tuples ONLY for selected mods
        selected_mods_data = [(mod_id, mod_name) for var, mod_id, mod_name in mod_vars if var.get()]
        if not selected_mods_data:
            messagebox.showinfo("Info", "No mods selected for download.", parent=root)
            return

        # --- Ask for Installation Directory ---
        initial_dir_setting = app_settings.get("default_download_dir", "")
        # Use configured default if it's a valid directory, otherwise fallback
        if initial_dir_setting and os.path.isdir(initial_dir_setting):
            initial_dir = initial_dir_setting
        else:
            # Sensible fallback: User's Downloads folder, or home directory if Downloads doesn't exist
            initial_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.isdir(initial_dir): initial_dir = os.path.expanduser("~")

        install_path = filedialog.askdirectory(
            title="Select Mod Installation Base Directory",
            initialdir=initial_dir,
            parent=root # Ensure dialog is parented to main window
        )
        # If user cancels the directory selection dialog
        if not install_path:
            logging.info("Mod download cancelled by user (directory selection).")
            return

        # --- Start Background Download ---
        # 1. Show Progress Window
        create_progress_window(root, len(selected_mods_data))

        # 2. Create Queue for communication between threads
        progress_queue = queue.Queue()

        # 3. Disable Main UI elements
        set_ui_state(tk.DISABLED)
        root.update_idletasks() # Ensure UI updates visually

        # 4. Create and start the background thread
        #    `daemon=True` allows the main program to exit even if this thread is stuck.
        download_thread = threading.Thread(
            target=download_mods_with_steamcmd, # Function to run in thread
            args=(selected_mods_data, install_path, progress_queue), # Arguments for the function
            daemon=True
        )
        download_thread.start()

        # 5. Start the loop checking the queue for updates (runs in main thread)
        root.after(100, lambda: check_download_progress(progress_queue))


    def load_mods():
        """
        Handles scraping mods based on user input from URL or HTML text area.
        Updates the mod list display. Disables UI during operation.
        """
        source_type = source_type_var.get()
        source = ""
        # --- Input Validation ---
        if source_type == 'url':
            source = source_entry.get().strip()
            # Basic check for http/https prefix and a dot
            if not (source.startswith(("http://", "https://")) and "." in source):
                messagebox.showerror("Invalid Input", "Please enter a valid web URL (e.g., https://steamcommunity.com/...).", parent=root)
                return
        elif source_type == 'html':
            source = html_text.get("1.0", tk.END).strip()
            # Basic check if non-empty and looks like start of HTML
            if not source or not source.lower().startswith(("<html", "<!doctype")):
                 messagebox.showerror("Invalid Input", "Please paste valid HTML source code.", parent=root)
                 return
        else:
            # Should not happen with radio buttons
            messagebox.showerror("Error", "Invalid source type selected.", parent=root)
            return

        # --- Execute Scraping ---
        info_label.config(text="Loading mods...") # Update status label
        set_ui_state(tk.DISABLED) # Disable UI
        root.update_idletasks() # Refresh GUI

        try:
            # FUTURE: Consider running scrape_mod_details in a thread too if it's slow
            #         or blocks the GUI for too long on complex pages or slow networks.
            mod_details = scrape_mod_details(source, source_type)
            populate_mod_list(mod_details) # Update the GUI list with results
        except Exception as e:
             # Catch unexpected errors during the scraping call itself
             logging.exception("Unexpected error initiating scraping function.")
             messagebox.showerror("Error", f"Failed to load mods:\n{e}", parent=root)
             populate_mod_list([]) # Clear list on error
        finally:
             # Ensure UI is always re-enabled, regardless of success or failure
             update_mod_info() # Update counts (might be 0)
             set_ui_state(tk.NORMAL) # Re-enable UI

    def set_ui_state(state):
        """
        Helper function to enable or disable key interactive UI elements.
        Prevents user interaction during background operations.

        Args:
            state (str): tk.NORMAL or tk.DISABLED.
        """
        # List of widgets to toggle state for
        widgets_to_toggle = [
            load_button, settings_button, download_button,
            source_entry, html_text
        ]
        # Include radio buttons in the list
        for child in radio_frame.winfo_children(): # Use radio_frame reference
             if isinstance(child, ttk.Radiobutton):
                 widgets_to_toggle.append(child)

        # Iterate and set state, handling potential errors
        for widget in widgets_to_toggle:
            try:
                 # Check if widget still exists (might be destroyed)
                 if widget.winfo_exists():
                     # Text widget uses 'config', ttk widgets use 'configure'
                     if isinstance(widget, Text):
                         widget.config(state=state)
                     elif hasattr(widget, 'configure'):
                         widget.configure(state=state)
            except tk.TclError as e:
                 # Log warning if state couldn't be set (e.g., widget destroyed unexpectedly)
                 logging.warning(f"Could not set state '{state}' for widget: {widget}. Error: {e}")


    # --- Start GUI Event Loop ---
    root.mainloop()


def main():
    """Main entry point: Loads settings and runs the GUI."""
    load_settings() # Load settings before creating any GUI elements
    create_mod_selection_gui()


if __name__ == "__main__":
    # Basic logging config (consider adding file logging for release)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()

