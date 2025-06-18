import json
import re
import os
from typing import Dict, List, Union, Any

from openai import OpenAI
# from tenacity import retry, wait_random_exponential, stop_after_attempt
from dotenv import load_dotenv

load_dotenv()

os.environ['OPENAI_API_KEY'] = os.getenv("OPENAI_API_KEY")
# os.environ['OPENAI_API_KEY'] = os.getenv("api_hub")
# os.environ['OPENAI_BASE_URL'] = "https://api.openai-hub.com/v1"
client = OpenAI()


def message_template(role: str, content: Any) -> Dict[str, str]:
    """Create a message template dictionary.

    Args:
        role: Message role ('system', 'user', or 'assistant')
        content: Message content

    Returns:
        Dictionary containing role and content
    """
    return {'role': role, 'content': str(content)}


def print_color(text, color='default'):
    color_codes = {
        'default': '\033[39m',
        'black': '\033[30m',
        'red': '\033[31m',
        'green': '\033[32m',
        'yellow': '\033[33m',
        'blue': '\033[34m',
        'magenta': '\033[35m',
        'cyan': '\033[36m',
        'light_gray': '\033[37m',
        'dark_gray': '\033[90m',
        'light_red': '\033[91m',
        'light_green': '\033[92m',
        'light_yellow': '\033[93m',
        'light_blue': '\033[94m',
        'light_magenta': '\033[95m',
        'light_cyan': '\033[96m',
        'white': '\033[97m',
    }

    reset_code = '\033[0m'
    color_code = color_codes.get(color.lower(), color_codes['default'])
    print(f"{color_code}{text}{reset_code}")

def chat_single(messages: List[Dict[str, str]],
                mode: str = "",
                model: str = 'gpt-4.1',
                temperature: float = 0.3,
                verbose: bool = False):
    """Send a single chat request to OpenAI API.

    Args:
        messages: List of messages
        mode: Response mode ('stream', 'json', 'json_few_shot', or empty string for normal mode)
        model: Model to use
        temperature: Temperature parameter controlling response randomness
        verbose: Whether to print detailed information

    Returns:
        Different types of responses based on mode
    """
    if mode == "stream":
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
            max_tokens=2560
        )
        return response
    elif mode == "json":
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=temperature,
            messages=messages
        )
        if verbose:
            print_color(response.choices[0].message.content,'blue')
            print(response.choices[0].message.content)
        return json.loads(response.choices[0].message.content)
    elif mode == 'json_few_shot':
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=2560
        )
        result = response.choices[0].message.content
        if verbose:
            print(result)
        return extract_json_and_similar_words(result)
    else:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        if verbose:
            print(response.choices[0].message.content)
        return response.choices[0].message.content


def format_list_string(input_str: str) -> str:
    """Format a string containing a list into valid JSON.

    Args:
        input_str: String containing a list

    Returns:
        Formatted JSON string
    """
    match = re.search(r'\{\s*"[^"]+"\s*:\s*\[(.*?)\]\s*\}', input_str)
    if not match:
        return "Invalid input format"

    list_content = match.group(1)
    elements = [e.strip() for e in list_content.split(',')]

    formatted_elements = []
    for elem in elements:
        if not re.match(r'^([\'"])(.*)\1$', elem):
            elem = f'"{elem}"'
        formatted_elements.append(elem)

    return f'{{ "similar_words":[{", ".join(formatted_elements)}]}}'


def extract_json_and_similar_words(text: str) -> Dict[str, Any]:
    """Extract JSON data from text.

    Args:
        text: Text containing JSON data

    Returns:
        Extracted JSON data dictionary
    """
    try:
        json_match = re.search(r'```json\s*({.*?})\s*```', text, re.DOTALL)

        if not json_match:
            raise ValueError("No JSON data found in the text.")

        json_str = json_match.group(1)
        if 'similar_words' in text:
            data = json.loads(format_list_string(json_str))
        else:
            data = json.loads(json_str)

        return data
    except Exception as e:
        print(f"Error extracting JSON: {e}")
        return {"error": str(e)}


def run_examples():
    """Run examples for all modes, demonstrating different API call methods."""

    # Base message template for all examples
    base_messages = [
        message_template('system',
                         'hi'),
    ]

    print("\n===== 1. Standard Mode Example =====")
    standard_messages = base_messages.copy()
    standard_messages.append(
        message_template('user', 'Who are you?'))

    standard_response = chat_single(standard_messages)
    print(f"Response:\n{standard_response}\n")

    print("\n===== 2. Stream Response Mode Example =====")
    stream_messages = base_messages.copy()
    stream_messages.append(
        message_template('user', 'Explain the concept of asynchronous programming in Python.'))

    stream_response = chat_single(stream_messages, mode="stream")

    collected_response = ""
    print("Stream response:")
    for chunk in stream_response:
        if chunk.choices[0].delta.content is not None:
            content_chunk = chunk.choices[0].delta.content
            collected_response += content_chunk
            print(content_chunk, end="", flush=True)

    print("\n\nComplete collected response:")
    print(collected_response)

    print("\n===== 3. JSON Response Mode Example =====")
    json_messages = base_messages.copy()
    json_messages.append(message_template('user',
                                          'Provide names and brief descriptions of three main Python data structures in JSON format.'))

    json_response = chat_single(json_messages, mode="json")
    print(f"JSON response:\n{json_response}\n")
    print(f"Parsed JSON:\n{json.loads(json_response)}\n")

    print(
        "\n===== 4. JSON Few-Shot Example =====")  # Can retain reasoning part to reduce performance degradation caused by structured output text
    few_shot_messages = base_messages.copy()
    few_shot_messages.append(message_template('user',
                                              '''Please provide words similar to "programming".

                                              Please reply in the following JSON format:
                                              ```json
                                              {
                                                "similar_words": ["coding", "development", ...]
                                              }
                                              ```
                                              '''))

    few_shot_response = chat_single(few_shot_messages, mode="json_few_shot",
                                    verbose=True)
    print(f"Processed response:\n{few_shot_response}\n")


if __name__ == "__main__":
    run_examples()