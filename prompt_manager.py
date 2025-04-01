# prompt_manager.py
import os
import tkinter.messagebox as messagebox

PROMPT_DIR = "system_prompts"
DEFAULT_PROMPT_NAME = "default.txt"

# Ensure the system_prompts directory exists
if not os.path.exists(PROMPT_DIR):
    try:
        os.makedirs(PROMPT_DIR)
        print(f"Created directory: {PROMPT_DIR}")
        # Create a default file if the directory was just created and default doesn't exist
        default_path = os.path.join(PROMPT_DIR, DEFAULT_PROMPT_NAME)
        if not os.path.exists(default_path):
             # Define the default content here or ensure it's created elsewhere
             default_content = """
You are provided with a collection of example text prompts.
Your task is to analyze these examples and determine their structure, wording patterns, and overall style.

Based on this analysis, generate a **new** text prompt that follows the same format and style as the provided examples.

Your response must:
- Match the format and style of the example prompts.
- Use common words, phrases, and patterns found in the examples.
- Be clear, coherent, and consistent with the example prompts.
- NOT introduce any new or unrelated styles.
- **ONLY return the generated text prompt. Do not include explanations, reasoning, or additional text.**

Example Text Prompts:
{example_text}

User Input:
{user_prompt}
"""
             try:
                 with open(default_path, 'w', encoding='utf-8') as f:
                     f.write(default_content.strip())
                 print(f"Created default prompt file: {default_path}")
             except IOError as e:
                 print(f"Error creating default prompt file '{default_path}': {e}")

    except OSError as e:
        print(f"Error creating directory '{PROMPT_DIR}': {e}")
        # Handle the error appropriately, maybe exit or show a message

def get_prompt_presets():
    """Returns a list of available prompt preset filenames."""
    if not os.path.exists(PROMPT_DIR):
        return []
    try:
        # List .txt files, ensure default is first if it exists
        files = [f for f in os.listdir(PROMPT_DIR) if f.endswith(".txt")]
        if DEFAULT_PROMPT_NAME in files:
            files.remove(DEFAULT_PROMPT_NAME)
            files.insert(0, DEFAULT_PROMPT_NAME)
        return files
    except OSError as e:
        print(f"Error listing prompts in '{PROMPT_DIR}': {e}")
        return []

def load_prompt_text(filename):
    """Loads the text content of a specific prompt file."""
    if not filename:
        return ""
    filepath = os.path.join(PROMPT_DIR, filename)
    if not os.path.exists(filepath):
        messagebox.showerror("Error", f"Prompt file not found: {filename}")
        return ""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except IOError as e:
        messagebox.showerror("Error", f"Error reading prompt file '{filename}': {e}")
        return ""

def save_prompt_text(filename, text):
    """Saves text content to a specific prompt file."""
    if not filename.endswith(".txt"):
        filename += ".txt"
    filepath = os.path.join(PROMPT_DIR, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        return True # Indicate success
    except IOError as e:
        messagebox.showerror("Error", f"Error saving prompt file '{filename}': {e}")
        return False # Indicate failure

def delete_prompt_preset(filename):
    """Deletes a specific prompt preset file."""
    if not filename or filename == DEFAULT_PROMPT_NAME:
        messagebox.showwarning("Delete Prevented", f"Cannot delete the default prompt or an empty selection.")
        return False
    filepath = os.path.join(PROMPT_DIR, filename)
    if os.path.exists(filepath):
        try:
            confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{filename}'?")
            if confirm:
                os.remove(filepath)
                return True
        except OSError as e:
            messagebox.showerror("Error", f"Error deleting prompt file '{filename}': {e}")
    else:
         messagebox.showerror("Error", f"Prompt file not found for deletion: {filename}")
    return False

if __name__ == '__main__':
     # Example usage
     print("Available presets:", get_prompt_presets())
     # print("Content of default.txt:", load_prompt_text("default.txt"))
