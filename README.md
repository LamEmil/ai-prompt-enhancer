# AI Text Prompt Enhancer

A user-friendly desktop application designed to help you craft better prompts for AI models. It analyzes example prompts you provide, understands their style and structure, and generates new prompts based on your topic/goal, mimicking the examples. Built with Python and PySide6, featuring a modern interface.

This tool aims to streamline the process of generating consistent and effective prompts, especially when working with various local Large Language Models (LLMs) via APIs like Ollama or LM Studio (not tested with chatgpt but in theory should work as has the same structure as LMStudio).

## ✨ Features

* **🚀 Smart Prompt Generation:** Provide example prompts and a topic/goal, and the app generates a new prompt matching the style and structure of your examples.
* **🔌 Flexible API Support:** Connects to different local AI API types:
    * **Ollama:** Native support for `/api/generate`.
    * **OpenAI-Compatible:** Support for LM Studio, Jan, and other servers using the `/v1/chat/completions` endpoint format.
* **⚙️ Advanced System Prompt Control:**
    * **Editable Instructions:** Modify the core instructions given to the AI about *how* to generate the new prompt.
    * **Save/Load Presets:** Create, save, and load multiple different system prompt instruction sets for various tasks or styles.
    * **Set Active Prompt:** Easily switch between your saved system prompt presets to control the generation process.
* **📝 Integrated Prompt Editor:**
    * View and edit the text file where your generated prompts are saved.
    * Open existing prompt collections or set a new target file.
    * Save edits made directly within the editor.
    * Close the file reference, resetting the save target.
* **💾 Convenient Output Saving:**
    * Save generated prompts with a single click.
    * Prompts are *appended* to your chosen text file, making it easy to create lists.
    * Perfect for batch processing in tools like **ComfyUI** (using file inputs) without manual copy-pasting.
* **🎨 Modern UI:**
    * Clean, dark interface inspired by modern applications (like Discord's layout).
    * Uses PySide6 (Qt for Python) and the qt-material theme.
    * Sidebar navigation for easy access to different sections.
* **🔧 Easy Configuration:**
    * Configure API type, endpoint URL, and optional API key via the in-app Settings page or by editing `config.json`.

## ✅ Requirements

1.  **Python:** Version 3.8 or higher recommended.
2.  **Python Libraries:** Listed in `requirements.txt`. Install easily via `pip`.
    * `PySide6`: For the user interface.
    * `qt-material`: For the UI theme.
    * `requests`: For making API calls.
    * `qtawesome` (Optional, included with qt-material usually): For icons.
3.  **Running AI Backend API:** You need a separate server running that provides either:
    * An Ollama-compatible API (e.g., [Ollama](https://ollama.com/) running locally).
    * An OpenAI-compatible API (e.g., [LM Studio](https://lmstudio.ai/), [Jan](https://jan.ai/), etc. running locally).
    * The application *does not include* the AI model itself; it only connects to an existing API server.

## 🚀 Installation

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/YourUsername/ai-prompt-enhancer.git](https://github.com/YourUsername/ai-prompt-enhancer.git)
    cd ai-prompt-enhancer
    ```
    *(Replace `YourUsername/ai-prompt-enhancer.git` with your actual repository URL)*

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    # Windows
    python -m venv venv
    venv\Scripts\activate

    # macOS / Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

The application uses a `config.json` file in the main directory to store settings. You can edit this file directly or use the in-app "Configuration" page.

```json
{
  "api_endpoint": "http://localhost:11434",
  "active_system_prompt": "default.txt",
  "api_type": "Ollama",
  "api_key": ""
}