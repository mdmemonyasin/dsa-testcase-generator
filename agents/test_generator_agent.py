import os
from .base_agent import BaseAgent

SYSTEM_PROMPT = """\
You are an expert competitive programming test case designer.

Your task is to write a STANDALONE Python script that generates exactly 10 test input files \
for a given DSA/competitive-programming problem.

STRICT RULES for the script you write:
1. Import ONLY standard library modules: random, os, math, sys
2. Create files: output/inputs/test_1.txt through output/inputs/test_10.txt
3. Each file must contain RAW input only — no labels, no annotations, no comments
4. The format must exactly match what the problem expects on stdin
5. The 10 test cases must collectively cover:
   - test_1.txt : Minimum possible input (smallest constraint, e.g. N=1)
   - test_2.txt : Maximum possible input (largest N/values — stress test)
   - test_3.txt : All-zeros or empty-ish case
   - test_4.txt : All same values
   - test_5.txt : Already sorted sequence (ascending)
   - test_6.txt : Reverse sorted sequence (descending)
   - test_7.txt : Single element / minimal structure
   - test_8.txt : Negative numbers (if constraints allow, else another edge case)
   - test_9.txt : Random average-case input #1
   - test_10.txt: Off-by-one boundary condition

IMPORTANT:
- Wrap your entire script in a ```python ... ``` fenced code block
- The script must run without errors with: python3 output/test_generator.py
- Do NOT include any explanation outside the code block
"""


class TestGeneratorAgent(BaseAgent):
    def run(self, problem_text: str) -> str:
        """Generate test_generator.py from problem text and write it to output/."""
        print("[TestGeneratorAgent] Generating test case generator script...")
        user_prompt = f"Write the test generator script for this problem:\n\n{problem_text}"
        response = self.call_model(SYSTEM_PROMPT, user_prompt)
        code = self.extract_code_block(response, "python")
        out_path = os.path.join("output", "test_generator.py")
        with open(out_path, "w") as f:
            f.write(code + "\n")
        print(f"[TestGeneratorAgent] Written to {out_path}")
        return out_path

    def retry(self, problem_text: str, error_output: str, current_script: str) -> str:
        """
        Re-generate test_generator.py after a runtime failure.

        error_output: the stderr/exception from the failed run
        current_script: the script that caused the error
        """
        print("[TestGeneratorAgent] Retrying after script error...")
        user_prompt = (
            f"The test generator script you wrote has a bug. It failed with this error:\n\n"
            f"```\n{error_output.strip()}\n```\n\n"
            f"Here is the buggy script:\n\n"
            f"```python\n{current_script.strip()}\n```\n\n"
            f"Fix ALL bugs and rewrite the complete working script for this problem:\n\n"
            f"{problem_text}"
        )
        response = self.call_model(SYSTEM_PROMPT, user_prompt)
        code = self.extract_code_block(response, "python")
        out_path = os.path.join("output", "test_generator.py")
        with open(out_path, "w") as f:
            f.write(code + "\n")
        print(f"[TestGeneratorAgent] Retried script written to {out_path}")
        return out_path
