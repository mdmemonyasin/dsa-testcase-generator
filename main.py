#!/usr/bin/env python3
"""
DSA Agent Helper — CLI entry point and pipeline orchestrator.

Usage:
    python3 main.py --problem problem.txt
    cat problem.txt | python3 main.py
"""

import argparse
import os
import shutil
import sys

from dotenv import load_dotenv

from agents.test_generator_agent import TestGeneratorAgent
from agents.solution_agent import SolutionAgent
from agents.executor_agent import ExecutorAgent, TestGeneratorError
from agents.driver_code_agent import DriverCodeAgent


def validate_environment() -> None:
    """Check that GEMINI_API_KEY is set and g++ is available."""
    if not os.environ.get("GEMINI_API_KEY"):
        print("[ERROR] GEMINI_API_KEY is not set.")
        print("  Add it to your .env file: GEMINI_API_KEY=<your-key>")
        sys.exit(1)

    if shutil.which("g++") is None:
        print("[ERROR] 'g++' not found on PATH.")
        print("  Install Xcode Command Line Tools: xcode-select --install")
        sys.exit(1)

    print("[main] Environment validated: GEMINI_API_KEY set, g++ found.")


def read_problem(args: argparse.Namespace) -> str:
    """Read problem text from --problem file or stdin."""
    if args.problem:
        if not os.path.exists(args.problem):
            print(f"[ERROR] Problem file not found: {args.problem}")
            sys.exit(1)
        with open(args.problem, "r") as f:
            text = f.read().strip()
        print(f"[main] Problem loaded from: {args.problem}")
    else:
        print("[main] Reading problem from stdin (Ctrl+D to finish)...")
        text = sys.stdin.read().strip()

    if not text:
        print("[ERROR] Problem text is empty.")
        sys.exit(1)
    return text


def run_pipeline(problem_text: str, output_dir: str = "output") -> tuple:
    """
    Run the full DSA agent pipeline.

    Returns:
        (passed, failures, driver_paths) where:
          - passed: int — number of tests that passed
          - failures: list of failing test dicts
          - driver_paths: dict mapping language -> file path
    """
    MAX_SOLUTION_RETRIES = 2
    MAX_TESTGEN_RETRIES = 2

    # Create output directory structure
    for d in [
        os.path.join(output_dir, "inputs"),
        os.path.join(output_dir, "outputs"),
    ]:
        os.makedirs(d, exist_ok=True)
    print("[main] Output directories ready.")

    executor = ExecutorAgent(output_dir=output_dir)

    # Step 1: Generate test cases
    print("\n--- Step 1: Generate Test Cases ---")
    test_gen_agent = TestGeneratorAgent(output_dir=output_dir)
    test_gen_agent.run(problem_text)

    # Step 2: Run test generator script (with retry on failure)
    print("\n--- Step 2: Execute Test Generator ---")
    for attempt in range(MAX_TESTGEN_RETRIES + 1):
        try:
            executor.run_test_generator()
            break
        except TestGeneratorError as e:
            if attempt >= MAX_TESTGEN_RETRIES:
                print(f"[main] Test generator failed after {MAX_TESTGEN_RETRIES} retries. Aborting.")
                raise
            print(f"\n--- Test Generator Retry {attempt + 1}/{MAX_TESTGEN_RETRIES} ---")
            with open(os.path.join(output_dir, "test_generator.py"), "r") as f:
                current_script = f.read()
            test_gen_agent.retry(problem_text, e.stderr, current_script)

    # Step 3: Generate C++ solution
    print("\n--- Step 3: Generate C++ Solution ---")
    solution_agent = SolutionAgent(output_dir=output_dir)
    solution_agent.run(problem_text)

    # Step 4: Compile solution
    print("\n--- Step 4: Compile Solution ---")
    executor.compile_solution()

    # Step 5: Run solution against all tests (with retry loop)
    print("\n--- Step 5: Run Solution Against Tests ---")
    total = ExecutorAgent.NUM_TESTS
    passed, failures = executor.run_solution_against_tests()

    for attempt in range(1, MAX_SOLUTION_RETRIES + 1):
        if not failures:
            break
        failing_nums = [f["test_num"] for f in failures]
        print(f"\n--- Retry {attempt}/{MAX_SOLUTION_RETRIES}: Fixing failures on tests {failing_nums} ---")
        solution_agent.retry(problem_text, failures)
        executor.compile_solution()
        passed, failures = executor.run_solution_against_tests()

    # Step 6: Generate driver code templates
    print("\n--- Step 6: Generate Driver Code Templates ---")
    driver_agent = DriverCodeAgent(output_dir=output_dir)
    driver_paths = driver_agent.run(problem_text)

    return passed, failures, driver_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DSA Agent Helper — auto-generate tests and solution for a competitive programming problem."
    )
    parser.add_argument(
        "--problem",
        metavar="FILE",
        help="Path to a text file containing the problem statement (default: read from stdin).",
    )
    args = parser.parse_args()

    load_dotenv()

    print("=" * 60)
    print("  DSA Agent Helper")
    print("=" * 60)

    validate_environment()
    problem_text = read_problem(args)

    passed, failures, driver_paths = run_pipeline(problem_text, output_dir="output")

    total = ExecutorAgent.NUM_TESTS

    # Final summary
    print("\n" + "=" * 60)
    print(f"  RESULT: {passed}/{total} tests passed")
    if failures:
        print(f"  Still failing: {[f['test_num'] for f in failures]}")
    if driver_paths:
        print(f"  Driver code: {list(driver_paths.values())}")
    print("=" * 60)

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
