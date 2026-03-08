import os
from .base_agent import BaseAgent, RETRY_MODEL

SYSTEM_PROMPT = """\
You are an expert competitive programmer writing production-quality C++ solutions compatible with GCC 6.3.0.

Your task is to write a CORRECT and OPTIMALLY EFFICIENT C++ solution for a given DSA problem.

STRICT RULES:
1. Do NOT use #include <bits/stdc++.h> — it is not available on Apple clang without special setup
2. Use ONLY explicit, standard headers (e.g., <iostream>, <vector>, <algorithm>, <string>, etc.)
3. Read ALL input from std::cin; write ALL output to std::cout
4. Must compile cleanly with: g++ -O2 -std=c++14 -o output/solution output/solution.cpp
5. No debug output, no test harnesses, no file I/O — stdin/stdout only
6. Handle ALL edge cases described in the problem constraints
7. GCC 6.3.0 COMPATIBILITY — do NOT use any of the following C++17 features:
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


class SolutionAgent(BaseAgent):
    def __init__(self, output_dir: str = "output"):
        super().__init__()
        self.output_dir = output_dir

    def run(self, problem_text: str) -> str:
        """Generate solution.cpp from problem text and write it to output/."""
        print("[SolutionAgent] Generating C++ solution...")
        user_prompt = f"Write the C++ solution for this problem:\n\n{problem_text}"
        response = self.call_model(SYSTEM_PROMPT, user_prompt)
        code = self.extract_code_block(response, "cpp")
        out_path = os.path.join(self.output_dir, "solution.cpp")
        with open(out_path, "w") as f:
            f.write(code + "\n")
        print(f"[SolutionAgent] Written to {out_path}")
        return out_path

    def retry(self, problem_text: str, failures: list) -> str:
        """
        Re-generate solution.cpp with failing test cases as additional context.

        failures: list of dicts from ExecutorAgent with keys:
            test_num, status, exit_code, input, output
        """
        print(f"[SolutionAgent] Retrying with {len(failures)} failing test case(s) as context...")

        # Read current buggy solution for context
        solution_path = os.path.join(self.output_dir, "solution.cpp")
        try:
            with open(solution_path, "r") as f:
                current_solution = f.read()
        except OSError:
            current_solution = "(could not read current solution)"

        cases_text = ""
        for fail in failures:
            actual_output = fail.get("output", "").strip()
            cases_text += (
                f"\n--- test_{fail['test_num']} ({fail['status']}) ---\n"
                f"Input:\n{fail['input'].strip()}\n"
                f"Actual output:\n{actual_output if actual_output else '(none)'}\n"
            )

        has_tle = any(f.get("status") == "TLE" for f in failures)
        tle_note = (
            "\nNOTE: One or more test cases hit the time limit (TLE). "
            "Your current solution is too slow — you MUST use a more efficient algorithm. "
            "Match the Expected Time Complexity stated in the problem. "
            "Do NOT resubmit a brute-force or O(n^2)/O(n^3) approach.\n"
            if has_tle else ""
        )

        user_prompt = (
            f"The following C++ solution fails on some test cases. "
            f"Analyze the buggy solution and the failing test cases, identify the root cause, "
            f"and rewrite a CORRECT and OPTIMALLY EFFICIENT solution.\n"
            f"{tle_note}\n"
            f"Buggy solution:\n```cpp\n{current_solution}\n```\n\n"
            f"Failing test cases:\n{cases_text}\n"
            f"Problem statement:\n\n{problem_text}"
        )
        print(f"[SolutionAgent] Using stronger model for retry: {RETRY_MODEL}")
        response = self.call_model(SYSTEM_PROMPT, user_prompt, model=RETRY_MODEL, max_output_tokens=32768)
        code = self.extract_code_block(response, "cpp")
        out_path = os.path.join(self.output_dir, "solution.cpp")
        with open(out_path, "w") as f:
            f.write(code + "\n")
        print(f"[SolutionAgent] Retried solution written to {out_path}")
        return out_path
