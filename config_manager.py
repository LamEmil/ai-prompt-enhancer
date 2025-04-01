# config_manager.py
import json
import os

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "api_endpoint": "http://localhost:11434",
    "active_system_prompt": "default.txt",
    "api_type": "Ollama",
    "api_key": "" 
}

def load_config():
    """Loads configuration from config.json, creating it if it doesn't exist."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Config file '{CONFIG_FILE}' not found, creating with defaults.")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy() # Return a copy
    try:
        with open(CONFIG_FILE, 'r') as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError as json_err:
                 print(f"Error decoding JSON from '{CONFIG_FILE}': {json_err}. Backing up and using defaults.")
                 # Optional: backup bad config file
                 try:
                     import shutil
                     import time
                     timestamp = time.strftime("%Y%m%d%H%M%S")
                     backup_file = f"{CONFIG_FILE}.{timestamp}.bak"
                     shutil.copy2(CONFIG_FILE, backup_file)
                     print(f"Backed up corrupted config to '{backup_file}'")
                 except Exception as backup_err:
                      print(f"Could not back up corrupted config: {backup_err}")
                 save_config(DEFAULT_CONFIG) # Create a fresh default one
                 return DEFAULT_CONFIG.copy()

            # Ensure essential keys exist, merge with defaults if necessary
            needs_save = False
            final_config = DEFAULT_CONFIG.copy() # Start with defaults
            final_config.update(config) # Overwrite with loaded values

            # Check if all default keys are present after update, add if missing
            for key, value in DEFAULT_CONFIG.items():
                 if key not in final_config:
                      print(f"Config file missing key '{key}', adding default value.")
                      final_config[key] = value
                      needs_save = True # Mark that we need to save the updated config

            if needs_save:
                 print("Saving updated configuration file with missing keys added.")
                 save_config(final_config)

            return final_config

    except IOError as e:
        print(f"Error loading config file '{CONFIG_FILE}': {e}. Using default config.")
        # Optionally, try to save defaults here again
        return DEFAULT_CONFIG.copy() # Return a copy

def save_config(config_data):
    """Saves the configuration data to config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"Configuration saved to {CONFIG_FILE}")
    except IOError as e:
        print(f"Error saving config file '{CONFIG_FILE}': {e}")

if __name__ == '__main__':
    # Example usage when run directly
    config = load_config()
    print("Loaded config:", config)
    # config["api_endpoint"] = "http://new-endpoint:12345" # Example modification
    # save_config(config)
    # print("Saved config:", load_config())
