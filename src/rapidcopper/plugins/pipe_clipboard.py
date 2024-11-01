"""Copy to clipboard"""

import pyperclip


def run(content: str) -> None:
    pyperclip.copy(content)
