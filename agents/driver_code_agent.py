import os
import re
from .base_agent import BaseAgent

SYSTEM_PROMPT = """\
You are an expert competitive programmer. Given a DSA problem, you will generate \
DRIVER CODE in four languages: Java, C++, C, and Python.

Driver code rules:
1. Handle ALL input reading and output printing exactly as the problem specifies
2. Set up all required data structures (arrays, graphs, lists, etc.) from the input
3. Provide an EMPTY stub function/method for the core algorithm — the user fills this in
4. The stub must have the correct signature and return a dummy/empty value
5. Call the stub, then print the result in the exact output format the problem requires
6. No algorithmic logic in the driver — only I/O and wiring

Language-specific rules:
- Java  : public class MUST be named `Main`; use Scanner for input; stub inside a `Solution` inner class
- C++   : use iostream, vector, etc. (no bits/stdc++.h); stub as a free function or class method
- C     : use stdio.h; stub as a regular function; dynamic arrays via malloc if needed
- Python: use sys.stdin for input; stub as a standalone function

Boolean output rule (CRITICAL):
- When the problem output is a boolean (true/false), ALL four languages MUST print the lowercase string
  "true" or "false" — never 0/1 and never Python's capitalised True/False.
- C++   : cout << (result ? "true" : "false") << endl;
- C     : printf("%s\n", result ? "true" : "false");
- Java  : System.out.println(result);   // Java already prints "true"/"false"
- Python: print("true" if result else "false")

Output format — respond with exactly four fenced code blocks in this order:
1. ```java   ... ```
2. ```cpp    ... ```
3. ```c      ... ```
4. ```python ... ```

Do NOT include any explanation or text outside the four code blocks.
"""


def _extract_language_block(response: str, language: str) -> str:
    """
    Extract the first fenced block for the given language tag.
    For 'c' specifically, avoids matching 'cpp' or 'csharp' etc.
    """
    if language == "c":
        # Match ```c followed by a non-word character (newline/space), not ```cpp
        pattern = r"```c(?!\w)\s*(.*?)```"
    else:
        pattern = rf"```{re.escape(language)}\s*(.*?)```"

    match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    raise ValueError(
        f"No `{language}` code block found in driver code response.\n"
        f"Response preview: {response[:600]}"
    )


class DriverCodeAgent(BaseAgent):
    LANGUAGES = [
        ("java",   "Main.java"),
        ("cpp",    "driver.cpp"),
        ("c",      "driver.c"),
        ("python", "driver.py"),
    ]

    def __init__(self, output_dir: str = "output"):
        super().__init__()
        self.output_dir = os.path.join(output_dir, "driver")

    def run(self, problem_text: str) -> dict:
        """
        Generate driver code in Java, C++, C, and Python.
        Returns dict mapping language tag -> file path.
        """
        print("[DriverCodeAgent] Generating driver code for all 4 languages...")
        os.makedirs(self.output_dir, exist_ok=True)

        user_prompt = (
            f"Generate driver code in Java, C++, C, and Python for this problem:\n\n"
            f"{problem_text}"
        )
        response = self.call_model(SYSTEM_PROMPT, user_prompt)

        paths = {}
        for lang, filename in self.LANGUAGES:
            try:
                code = _extract_language_block(response, lang)
            except ValueError as e:
                print(f"  [DriverCodeAgent] WARNING: {e}")
                continue

            file_path = os.path.join(self.output_dir, filename)
            with open(file_path, "w") as f:
                f.write(code + "\n")
            paths[lang] = file_path
            print(f"  Written: {file_path}")

        return paths
