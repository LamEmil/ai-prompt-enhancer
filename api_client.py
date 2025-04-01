# api_client.py
import requests
import json # Make sure json is imported

# Keep using messagebox for direct user feedback on API errors? Or handle in main_window?
# Let's keep it here for now, but could be refactored later.
from PySide6 import QtWidgets # Use PySide6's messagebox if running within app context

def show_api_error(title, message):
    """Helper to show error message."""
    print(f"!! API Client Error: {title} - {message}")
    # This assumes the client might be run standalone or needs immediate feedback.
    # Ideally, errors should propagate back to the main UI to be displayed there.
    # For now, a simple print and potentially a basic Qt messagebox if possible.
    try:
        # This might fail if called from non-GUI thread directly without proper setup
        msgBox = QtWidgets.QMessageBox()
        msgBox.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        msgBox.setWindowTitle(title)
        msgBox.setText(str(message))
        msgBox.exec()
    except Exception: # Catch errors if GUI not available
        pass


def fetch_installed_models(api_endpoint, api_type="Ollama", api_key=None):
    """Fetches available AI models from the specified API endpoint and type."""
    models = []
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    print(f"--- API: Fetching models (Type: {api_type}, Endpoint: {api_endpoint}) ---")

    if not api_endpoint:
        show_api_error("API Error", "API endpoint is not configured.")
        return []

    try:
        if api_type == "Ollama":
            url = f"{api_endpoint}/api/tags"
            print(f"   Ollama Request: GET {url}")
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            models_data = response.json()
            ollama_models = models_data.get("models", [])
            models = sorted([model["name"] for model in ollama_models if "name" in model])
            print(f"   Ollama Response: Found {len(models)} models.")

        elif api_type == "OpenAI":
            url = f"{api_endpoint}/v1/models"
             # LM Studio might use different endpoints, ensure URL is correct
            if not url.endswith('/v1/models'):
                 # Basic correction attempt if endpoint is just the base URL
                 base_url = api_endpoint.strip('/')
                 url = f"{base_url}/v1/models"

            print(f"   OpenAI Request: GET {url}")
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            models_data = response.json()
            openai_models = models_data.get("data", [])
            # Extract model IDs - filter out embeddings/other types if necessary later
            models = sorted([model["id"] for model in openai_models if "id" in model])
            print(f"   OpenAI Response: Found {len(models)} models.")

        else:
            show_api_error("API Error", f"Unsupported API type: {api_type}")
            return []

        return models

    except requests.exceptions.Timeout:
         error_msg = f"Request timed out connecting to {url}."
         show_api_error("API Connection Error", error_msg)
         print(f"   Error: {error_msg}")
         return []
    except requests.exceptions.RequestException as e:
        error_msg = f"Could not connect or fetch models from {url}.\nError: {e}\n\nCheck API server and endpoint/type configuration."
        show_api_error("API Connection Error", error_msg)
        print(f"   Error: {e}")
        return []
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON response received from {url}.\nError: {e}"
        show_api_error("API Response Error", error_msg)
        print(f"   Error: {e}")
        return []
    except Exception as e:
         # Catch unexpected errors
         error_msg = f"An unexpected error occurred while fetching models: {e}"
         show_api_error("API Error", error_msg)
         print(f"   Error: {e}")
         return []


def generate_text(api_endpoint, api_type, selected_model,
                  system_prompt_content, user_input, example_text,
                  api_key=None):
    """
    Generates text using the specified API type, model, and prompts.

    Args:
        api_endpoint (str): The base URL of the API.
        api_type (str): "Ollama" or "OpenAI".
        selected_model (str): The name/ID of the model to use.
        system_prompt_content (str): The content of the system prompt/instructions.
        user_input (str): The user's specific topic or goal description.
        example_text (str): The provided example prompts text.
        api_key (str, optional): API key, if required. Defaults to None.

    Returns:
        dict: A dictionary containing either {"response": "generated_text"} on success
              or {"error": "error_message"} on failure.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    print(f"--- API: Generating text (Type: {api_type}, Model: {selected_model}, Endpoint: {api_endpoint}) ---")

    if not api_endpoint:
        return {"error": "API endpoint is not configured."}
    if not selected_model:
        return {"error": "No AI model selected."}

    try:
        if api_type == "Ollama":
            url = f"{api_endpoint}/api/generate"
            # Construct the single prompt string expected by Ollama's /api/generate
            # This combines the system instructions, examples, and user input description
            # (We keep the original formatting structure from default.txt here)
            prompt_template = system_prompt_content # Assumes system_prompt has placeholders
            try:
                 final_prompt = prompt_template.format(
                     example_text=example_text,
                     user_prompt=user_input
                 )
            except KeyError as e:
                 return {"error": f"System prompt for Ollama is missing placeholder: {e}"}
            except Exception as e:
                 return {"error": f"Error formatting Ollama prompt: {e}"}


            payload = {
                "model": selected_model,
                "prompt": final_prompt,
                "stream": False
                # Add other Ollama params like temperature if needed
            }
            print(f"   Ollama Request: POST {url}")
            # print(f"   Ollama Payload: {json.dumps(payload, indent=2)}") # Careful logging prompts
            response = requests.post(url, headers=headers, json=payload, timeout=300)
            response.raise_for_status()
            response_data = response.json()
            generated_text = response_data.get("response", "")
            print(f"   Ollama Response: Success (Length: {len(generated_text)})")
            return {"response": generated_text}

        elif api_type == "OpenAI":
            url = f"{api_endpoint}/v1/chat/completions"
            # LM Studio might use different endpoints, ensure URL is correct
            if not url.endswith('/v1/chat/completions'):
                 base_url = api_endpoint.strip('/')
                 url = f"{base_url}/v1/chat/completions"

            # Construct the messages list for OpenAI format
            messages = []
            # 1. System message: The instructions on *how* to behave (generate a prompt)
            if system_prompt_content:
                 # We need to remove the placeholders from the system prompt content here,
                 # as the actual examples/user input go into the user message.
                 cleaned_system_prompt = system_prompt_content.split("Example Text Prompts:")[0].strip()
                 cleaned_system_prompt = cleaned_system_prompt.split("User Input:")[0].strip() # Remove user input too just in case
                 if cleaned_system_prompt:
                      messages.append({"role": "system", "content": cleaned_system_prompt})
                 else:
                      print("   Warning: System prompt content seemed empty after cleaning placeholders.")
                      # Add a generic system message if needed? Or rely on user message only.
                      # messages.append({"role": "system", "content": "You are a helpful assistant."})


            # 2. User message: The actual task input (examples + goal)
            # Combine examples and user goal into one user message for clarity
            user_message_content = f"Analyze the following examples and generate a new prompt based on them, focusing on the user's goal.\n\n**Example Text Prompts:**\n{example_text}\n\n**User Input/Goal:**\n{user_input}"
            messages.append({"role": "user", "content": user_message_content})

            payload = {
                "model": selected_model,
                "messages": messages,
                "temperature": 0.7, # Example value, make configurable later?
                # "max_tokens": -1, # -1 might mean unlimited in LM Studio, check docs
                "stream": False
                # Add optional "response_format" here if needed later
            }
            print(f"   OpenAI Request: POST {url}")
            # print(f"   OpenAI Payload: {json.dumps(payload, indent=2)}") # Careful logging prompts
            response = requests.post(url, headers=headers, json=payload, timeout=300)
            response.raise_for_status()
            response_data = response.json()

            # Extract response from choices list
            if "choices" in response_data and len(response_data["choices"]) > 0:
                message = response_data["choices"][0].get("message", {})
                generated_text = message.get("content", "")
                print(f"   OpenAI Response: Success (Length: {len(generated_text)})")
                return {"response": generated_text.strip()}
            else:
                print("   OpenAI Response Error: 'choices' array missing or empty.")
                print(f"   Full Response Data: {response_data}")
                return {"error": "API response did not contain expected 'choices' data."}

        else:
            return {"error": f"Unsupported API type for generation: {api_type}"}

    except requests.exceptions.Timeout:
        error_msg = f"Request timed out trying to generate text via {url}."
        print(f"   Error: {error_msg}")
        return {"error": error_msg}
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP error occurred: {e.response.status_code} {e.response.reason}"
        try:
             # Try to get more detail from response body
             error_detail = e.response.json() # Or e.response.text
             error_msg += f"\nDetails: {json.dumps(error_detail, indent=2)}"
        except Exception:
             error_msg += f"\nResponse Body: {e.response.text}"
        print(f"   Error: {error_msg}")
        return {"error": error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed connecting to {url}.\nError: {e}"
        print(f"   Error: {e}")
        return {"error": error_msg}
    except json.JSONDecodeError as e:
         error_msg = f"Invalid JSON response received from {url}.\nError: {e}"
         print(f"   Error: {e}")
         return {"error": error_msg}
    except Exception as e:
        # Catch unexpected errors during processing
        import traceback
        print(f"   Error: An unexpected error occurred during text generation: {e}")
        traceback.print_exc()
        return {"error": f"An unexpected error occurred: {e}"}
