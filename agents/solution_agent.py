import os
from .base_agent import BaseAgent

SYSTEM_PROMPT = """\
You are an expert competitive programmer writing production-quality C++ solutions compatible with GCC 6.3.0.

Your task is to write a CORRECT and EFFICIENT C++ solution for a given DSA problem.

STRICT RULES:
1. Do NOT use #include <bits/stdc++.h> — it is not available on Apple clang without special setup
2. Use ONLY explicit, standard headers (e.g., <iostream>, <vector>, <algorithm>, <string>, etc.)
3. Read ALL input from std::cin; write ALL output to std::cout
4. Must compile cleanly with: g++ -O2 -std=c++14 -o output/solution output/solution.cpp
5. No debug output, no test harnesses, no file I/O — stdin/stdout only
6. Handle ALL edge cases described in the problem constraints
7. Use efficient algorithms appropriate for the given constraints
8. GCC 6.3.0 COMPATIBILITY — do NOT use any of the following C++17 features:
   - std::optional, std::variant, std::any
   - if constexpr, structured bindings (auto [a, b] = ...)
   - std::string_view, std::filesystem
   - fold expressions, inline variables
   - __has_include or any C++17-only standard library headers
   Stick to C++14 and below only.

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
            test_num, status, exit_code, input
        """
        print(f"[SolutionAgent] Retrying with {len(failures)} failing test case(s) as context...")

        cases_text = ""
        for f in failures:
            cases_text += (
                f"\n--- test_{f['test_num']} ({f['status']}) ---\n"
                f"Input:\n{f['input'].strip()}\n"
            )

        user_prompt = (
            f"The following C++ solution has bugs. It fails on these test cases:\n"
            f"{cases_text}\n"
            f"Common causes:\n"
            f"- Out-of-bounds array access when input values are outside expected constraints\n"
            f"- Missing input validation before using values as indices\n"
            f"- Integer overflow on large inputs\n"
            f"- Infinite loop / wrong algorithm for edge cases\n\n"
            f"Carefully analyze each failing input, identify the root cause, and rewrite a "
            f"CORRECT solution for this problem:\n\n{problem_text}"
        )
        response = self.call_model(SYSTEM_PROMPT, user_prompt)
        code = self.extract_code_block(response, "cpp")
        out_path = os.path.join(self.output_dir, "solution.cpp")
        with open(out_path, "w") as f:
            f.write(code + "\n")
        print(f"[SolutionAgent] Retried solution written to {out_path}")
        return out_path
