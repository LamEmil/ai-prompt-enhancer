# utils.py
import re

def process_response(text):
    """Cleans AI response by removing unnecessary tags or formatting."""
    # Remove <think>...</think> blocks (case-insensitive and multiline)
    cleaned_text = re.sub(r"<\s*think\s*>.*?<\s*/\s*think\s*>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Add any other cleaning rules here if needed
    return cleaned_text.strip()

if __name__ == '__main__':
    test_text = "Some text <think>This is thinking</think> More text.\n< THINK >\nAnother thought\n</ THINK > Final words."
    print("Original:", test_text)
    print("Cleaned:", process_response(test_text))
