import os
from .base_agent import BaseAgent, RETRY_MODEL

CPP_SYSTEM_PROMPT = """\
You are an expert competitive programmer writing production-quality C++ solutions compatible with GCC 6.3.0.

Your task is to produce the COMPLETE, RUNNABLE solution.cpp by taking the provided C++ driver code and
REPLACING the stub function body with a correct, optimally efficient implementation.

STRICT RULES:
1. Start from the driver code exactly — keep all I/O, main(), and output formatting unchanged
2. Only fill in the stub function(s) with the real algorithm; do NOT restructure main() or change output calls
3. Do NOT use #include <bits/stdc++.h> — it is not available on Apple clang without special setup
4. Use ONLY explicit, standard headers (e.g., <iostream>, <vector>, <algorithm>, <string>, etc.)
5. Must compile cleanly with: g++ -O2 -std=c++14 -o output/solution output/solution.cpp
6. No debug output, no test harnesses, no file I/O — stdin/stdout only
7. Handle ALL edge cases described in the problem constraints
8. OUTPUT FORMAT: Print results as plain space-separated values. NEVER print brackets, commas-in-brackets,
   or language-native collection formatting. A list [1,2,3] must be printed as "1 2 3".
   Booleans must be "true"/"false" (lowercase). Strings without quotes.
9. GCC 6.3.0 COMPATIBILITY — do NOT use any of the following C++17 features:
   - std::optional, std::variant, std::any
   - if constexpr, structured bindings (auto [a, b] = ...)
   - std::string_view, std::filesystem
   - fold expressions, inline variables
   - __has_include or any C++17-only standard library headers
   Stick to C++14 and below only.

COMPLEXITY REQUIREMENTS (CRITICAL):
- If the problem states an Expected Time Complexity, your solution MUST match it exactly.
- If the problem states an Expected Space Complexity, your solution MUST match it exactly.
- Do NOT submit a brute-force or naive solution if a better complexity is achievable or required.
- A solution that produces correct output but exceeds the time/space complexity is WRONG.
- Always reason about the constraints (e.g. n <= 10^5 means O(n log n) or better; n <= 10^3 allows O(n^2)).

IMPORTANT:
- Wrap your entire solution in a ```cpp ... ``` fenced code block
- Do NOT include any explanation outside the code block
"""

JAVA_SYSTEM_PROMPT = """\
You are an expert competitive programmer writing production-quality Java solutions.

Your task is to produce the COMPLETE, RUNNABLE Main.java by taking the provided Java driver code and
REPLACING the stub method body with a correct, optimally efficient implementation.

STRICT RULES:
1. Start from the driver code exactly — keep all I/O, main(), and output formatting unchanged
2. Only fill in the stub method(s) with the real algorithm; do NOT restructure main() or change output calls
3. The public class MUST be named `Main`
4. Must compile cleanly with: javac Main.java
5. No debug output, no test harnesses, no file I/O — stdin/stdout only
6. Handle ALL edge cases described in the problem constraints
7. OUTPUT FORMAT (CRITICAL): Print results as plain space-separated values on a single line.
   NEVER use Arrays.toString(), List.toString(), Collection.toString(), or any method that produces
   bracketed output like "[1, 2, 3]". You MUST loop through the collection and print each element
   separated by spaces using System.out.print().
   Example for an int array result:
     StringBuilder sb = new StringBuilder();
     for (int i = 0; i < result.length; i++) {
         if (i > 0) sb.append(" ");
         sb.append(result[i]);
     }
     System.out.println(sb.toString());
   Example for a List<Integer> result:
     StringBuilder sb = new StringBuilder();
     for (int i = 0; i < result.size(); i++) {
         if (i > 0) sb.append(" ");
         sb.append(result.get(i));
     }
     System.out.println(sb.toString());
   Booleans: print lowercase "true"/"false".
   Strings: print without quotes.

COMPLEXITY REQUIREMENTS (CRITICAL):
- If the problem states an Expected Time Complexity, your solution MUST match it exactly.
- If the problem states an Expected Space Complexity, your solution MUST match it exactly.
- Do NOT submit a brute-force or naive solution if a better complexity is achievable or required.
- A solution that produces correct output but exceeds the time/space complexity is WRONG.

IMPORTANT:
- Wrap your entire solution in a ```java ... ``` fenced code block
- Do NOT include any explanation outside the code block
"""

PYTHON_SYSTEM_PROMPT = """\
You are an expert competitive programmer writing production-quality Python solutions.

Your task is to produce the COMPLETE, RUNNABLE solution.py by taking the provided Python driver code and
REPLACING the stub function body with a correct, optimally efficient implementation.

STRICT RULES:
1. Start from the driver code exactly — keep all I/O, main(), and output formatting unchanged
2. Only fill in the stub function(s) with the real algorithm; do NOT restructure I/O or change print calls
3. Must run cleanly with: python3 solution.py
4. No debug output, no test harnesses, no file I/O — stdin/stdout only
5. Handle ALL edge cases described in the problem constraints
6. Use ONLY standard library modules (no numpy, no external packages)
7. OUTPUT FORMAT (CRITICAL): Print results as plain space-separated values.
   NEVER use print(list) or print(result) when result is a list — this produces "[1, 2, 3]" which is WRONG.
   Use print(*result) for flat lists to get "1 2 3".
   For 2D lists, loop and print(*row) for each row.
   Booleans: print "true" or "false" (lowercase), NOT Python's True/False.
   Strings: print without quotes.

COMPLEXITY REQUIREMENTS (CRITICAL):
- If the problem states an Expected Time Complexity, your solution MUST match it exactly.
- If the problem states an Expected Space Complexity, your solution MUST match it exactly.
- Do NOT submit a brute-force or naive solution if a better complexity is achievable or required.
- A solution that produces correct output but exceeds the time/space complexity is WRONG.

IMPORTANT:
- Wrap your entire solution in a ```python ... ``` fenced code block
- Do NOT include any explanation outside the code block
"""

LANG_CONFIG = {
    "cpp": {
        "system_prompt": CPP_SYSTEM_PROMPT,
        "driver_file": "driver/driver.cpp",
        "output_file": "solution.cpp",
        "code_tag": "cpp",
        "label": "C++",
    },
    "java": {
        "system_prompt": JAVA_SYSTEM_PROMPT,
        "driver_file": "driver/Main.java",
        "output_file": "Main.java",
        "code_tag": "java",
        "label": "Java",
    },
    "python": {
        "system_prompt": PYTHON_SYSTEM_PROMPT,
        "driver_file": "driver/driver.py",
        "output_file": "solution.py",
        "code_tag": "python",
        "label": "Python",
    },
}


class SolutionAgent(BaseAgent):
    def __init__(self, output_dir: str = "output"):
        super().__init__()
        self.output_dir = output_dir

    def _load_driver(self, lang: str) -> str:
        cfg = LANG_CONFIG[lang]
        driver_path = os.path.join(self.output_dir, cfg["driver_file"])
        try:
            with open(driver_path, "r") as f:
                return f.read()
        except OSError:
            return ""

    def _load_cpp_solution(self) -> str:
        """Load the C++ solution as reference for other languages."""
        cpp_path = os.path.join(self.output_dir, "solution.cpp")
        try:
            with open(cpp_path, "r") as f:
                return f.read()
        except OSError:
            return ""

    def run(self, problem_text: str, lang: str = "cpp") -> str:
        """Generate solution by filling in the driver stub for the given language."""
        cfg = LANG_CONFIG[lang]
        print(f"[SolutionAgent] Generating {cfg['label']} solution...")
        driver_code = self._load_driver(lang)
        driver_section = (
            f"{cfg['label']} driver code (keep all I/O and main() unchanged — only implement the stub):\n"
            f"```{cfg['code_tag']}\n{driver_code}\n```\n\n"
            if driver_code else ""
        )

        # For Java/Python: include the working C++ solution as reference
        # so the LLM matches the exact same algorithm and output behavior
        cpp_ref_section = ""
        if lang != "cpp":
            cpp_solution = self._load_cpp_solution()
            if cpp_solution:
                cpp_ref_section = (
                    f"REFERENCE: Below is the working C++ solution that passes all test cases. "
                    f"Your {cfg['label']} solution MUST implement the EXACT SAME algorithm and "
                    f"produce IDENTICAL output for every input. Translate the logic faithfully — "
                    f"do not change sorting order, tiebreaker rules, or any algorithmic behavior.\n\n"
                    f"```cpp\n{cpp_solution}\n```\n\n"
                )

        user_prompt = (
            f"{driver_section}"
            f"{cpp_ref_section}"
            f"Problem statement:\n\n{problem_text}"
        )
        response = self.call_model(cfg["system_prompt"], user_prompt)
        code = self.extract_code_block(response, cfg["code_tag"])
        out_path = os.path.join(self.output_dir, cfg["output_file"])
        with open(out_path, "w") as f:
            f.write(code + "\n")
        print(f"[SolutionAgent] Written to {out_path}")
        return out_path

    def retry(self, problem_text: str, failures: list, lang: str = "cpp") -> str:
        """
        Re-generate solution with failing test cases as additional context.

        failures: list of dicts from ExecutorAgent with keys:
            test_num, status, exit_code, input, output
        """
        cfg = LANG_CONFIG[lang]
        print(f"[SolutionAgent] Retrying {cfg['label']} with {len(failures)} failing test case(s)...")

        solution_path = os.path.join(self.output_dir, cfg["output_file"])
        try:
            with open(solution_path, "r") as f:
                current_solution = f.read()
        except OSError:
            current_solution = "(could not read current solution)"

        cases_text = ""
        for fail in failures:
            actual_output = fail.get("output", "").strip()
            if fail.get("status") == "COMPILE_ERROR":
                cases_text += (
                    f"\n--- COMPILATION ERROR ---\n"
                    f"Compiler output:\n{actual_output if actual_output else '(none)'}\n"
                )
            else:
                expected_output = fail.get("expected", "").strip()
                expected_section = (
                    f"Expected output:\n{expected_output}\n"
                    if expected_output else ""
                )
                cases_text += (
                    f"\n--- test_{fail['test_num']} ({fail['status']}) ---\n"
                    f"Input:\n{fail['input'].strip()}\n"
                    f"{expected_section}"
                    f"Actual output:\n{actual_output if actual_output else '(none)'}\n"
                )

        has_tle = any(f.get("status") == "TLE" for f in failures)
        has_compile_error = any(f.get("status") == "COMPILE_ERROR" for f in failures)
        has_wrong_answer = any(f.get("status") == "WRONG_ANSWER" for f in failures)
        tle_note = (
            "\nNOTE: One or more test cases hit the time limit (TLE). "
            "Your current solution is too slow — you MUST use a more efficient algorithm. "
            "Match the Expected Time Complexity stated in the problem. "
            "Do NOT resubmit a brute-force or O(n^2)/O(n^3) approach.\n"
            if has_tle else ""
        )
        compile_note = (
            "\nNOTE: The solution FAILED TO COMPILE. Fix all compilation errors before anything else.\n"
            if has_compile_error else ""
        )
        wa_note = (
            "\nNOTE: One or more test cases produced WRONG ANSWER. Your output does not match the expected output. "
            "The root cause could be in the SOLUTION (wrong algorithm/sorting/tiebreaker) OR in the DRIVER CODE "
            "(wrong I/O parsing or output formatting). Analyze BOTH carefully.\n"
            "- Compare expected vs actual output to determine if it's a logic issue or a formatting issue.\n"
            "- If the driver code has a bug (e.g., wrong output format, wrong parsing), fix the driver code part too.\n"
            "- Your output must be EXACTLY identical to the expected output (same values, same order, same format).\n"
            if has_wrong_answer else ""
        )

        driver_code = self._load_driver(lang)
        driver_section = (
            f"Original {cfg['label']} driver code (you MAY fix bugs in it if the I/O is wrong):\n"
            f"```{cfg['code_tag']}\n{driver_code}\n```\n\n"
            if driver_code else ""
        )

        # For Java/Python retries: include the working C++ solution as reference
        cpp_ref_section = ""
        if lang != "cpp":
            cpp_solution = self._load_cpp_solution()
            if cpp_solution:
                cpp_ref_section = (
                    f"REFERENCE: The working C++ solution (passes all tests). Your {cfg['label']} "
                    f"solution must produce IDENTICAL output. Translate the algorithm faithfully:\n"
                    f"```cpp\n{cpp_solution}\n```\n\n"
                )

        user_prompt = (
            f"The following {cfg['label']} solution fails on some test cases. "
            f"Analyze the buggy solution, the driver code, and the failing test cases. "
            f"Identify whether the root cause is in the solution logic OR the driver code I/O, "
            f"and rewrite the COMPLETE file with all fixes.\n"
            f"{tle_note}"
            f"{compile_note}"
            f"{wa_note}\n"
            f"{cpp_ref_section}"
            f"{driver_section}"
            f"Buggy solution:\n```{cfg['code_tag']}\n{current_solution}\n```\n\n"
            f"Failing test cases:\n{cases_text}\n"
            f"Problem statement:\n\n{problem_text}"
        )
        print(f"[SolutionAgent] Using stronger model for retry: {RETRY_MODEL}")
        response = self.call_model(cfg["system_prompt"], user_prompt, model=RETRY_MODEL, max_output_tokens=32768)
        code = self.extract_code_block(response, cfg["code_tag"])
        out_path = os.path.join(self.output_dir, cfg["output_file"])
        with open(out_path, "w") as f:
            f.write(code + "\n")
        print(f"[SolutionAgent] Retried {cfg['label']} solution written to {out_path}")
        return out_path
