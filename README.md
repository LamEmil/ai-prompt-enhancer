# AI Text Prompt Enhancer

A desktop application designed to work with ollama. Built with Python and PySide6 to enhance text prompts, for ai image, video and audio generators, using locally running AI models via an API (like Ollama). It analyzes example prompts and user input to generate new prompts in a similar style.

## Features

* Connects to a local AI API (default: http://localhost:11434).
* Loads example prompts from a text file.
* Generates new prompts based on examples and user topic/goal.
* Manages system prompts:
    * Edit system prompt instructions.
    * Save/load multiple system prompt presets.
    * Set an active system prompt for generation.
* Saves generated prompts to a file.
* Modern dark UI.

## Requirements

* Python 3.x
* PySide6 (`pip install PySide6`)
* qt-material (`pip install qt-material`)
* Requests (`pip install requests`)
* A running AI API endpoint compatible with the requests (e.g., Ollama running locally).

## How to Run

1.  Ensure all requirements are installed (`pip install -r requirements.txt` - see below).
2.  Make sure your AI API (e.g., Ollama) is running.
3.  If your API is not at `http://localhost:11434`, edit `config.json`.
4.  Run the application: `python run_app.pyw`

## Project Structure

* `run_app.pyw`: Main script to launch the application.
* `main_window.py`: Contains the PySide6 UI logic and main application class.
* `api_client.py`: Handles communication with the AI API.
* `config_manager.py`: Manages `config.json`.
* `prompt_manager.py`: Manages system prompt presets in `system_prompts/`.
* `utils.py`: Utility functions.
* `config.json`: Configuration file (API endpoint, active prompt).
* `system_prompts/`: Folder containing system prompt presets (includes `default.txt`).
* `saved_prompts/`: Default folder for saved generated prompts (created automatically, ignored by Git).
* `requirements.txt`: Lists Python dependencies.
