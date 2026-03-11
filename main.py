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


LANGUAGES = ["cpp", "java", "python"]
LANG_LABELS = {"cpp": "C++", "java": "Java", "python": "Python"}


def validate_environment() -> dict:
    """
    Check that GEMINI_API_KEY is set and required compilers/runtimes are available.
    Returns a dict of language -> bool indicating availability.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[ERROR] ANTHROPIC_API_KEY is not set.")
        print("  Add it to your .env file: ANTHROPIC_API_KEY=<your-key>")
        sys.exit(1)

    available = {}

    # C++ — required
    if shutil.which("g++") is None:
        print("[WARNING] 'g++' not found on PATH — C++ pipeline will be skipped.")
        available["cpp"] = False
    else:
        available["cpp"] = True

    # Java — optional
    if shutil.which("javac") is None or shutil.which("java") is None:
        print("[WARNING] 'javac'/'java' not found on PATH — Java pipeline will be skipped.")
        available["java"] = False
    else:
        available["java"] = True

    # Python — always available (we're running in Python)
    available["python"] = True

    active = [LANG_LABELS[l] for l in LANGUAGES if available.get(l)]
    print(f"[main] Environment validated. Active languages: {', '.join(active)}")
    return available


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


# Languages that only generate code (no compile/run)
GENERATE_ONLY_LANGS = set()


def _run_language_pipeline(
    lang: str,
    problem_text: str,
    solution_agent: SolutionAgent,
    executor: ExecutorAgent,
    max_retries: int,
    expected_outputs_dir: str = None,
) -> tuple:
    """
    Generate solution, compile, run, and retry for a single language.
    If expected_outputs_dir is provided, compare outputs against ground truth (C++).
    Returns (passed, failures).
    """
    label = LANG_LABELS[lang]

    print(f"\n{'=' * 50}")
    print(f"  {label} Pipeline")
    print(f"{'=' * 50}")

    # Generate solution from driver stub
    print(f"\n--- Generate {label} Solution ---")
    solution_agent.run(problem_text, lang=lang)

    # Compile + run
    print(f"\n--- Compile & Run {label} ---")
    try:
        passed, failures = executor.compile_and_run(lang, expected_outputs_dir=expected_outputs_dir)
    except RuntimeError as e:
        print(f"[main] {label} compilation failed — will retry with error context.")
        passed = 0
        failures = [{
            "test_num": 0,
            "status": "COMPILE_ERROR",
            "exit_code": None,
            "input": "",
            "output": str(e),
        }]

    # Retry loop
    for attempt in range(1, max_retries + 1):
        if not failures:
            break
        failing_nums = [f["test_num"] for f in failures]
        print(f"\n--- {label} Retry {attempt}/{max_retries}: Fixing failures on tests {failing_nums} ---")
        solution_agent.retry(problem_text, failures, lang=lang)
        try:
            passed, failures = executor.compile_and_run(lang, expected_outputs_dir=expected_outputs_dir)
        except RuntimeError as e:
            print(f"[main] {label} compilation failed on retry {attempt}.")
            passed = 0
            failures = [{
                "test_num": 0,
                "status": "COMPILE_ERROR",
                "exit_code": None,
                "input": "",
                "output": str(e),
            }]

    return passed, failures


def run_pipeline(problem_text: str, output_dir: str = "output", lang_available: dict = None) -> dict:
    """
    Run the full DSA agent pipeline for all available languages.

    Returns:
        dict mapping language -> {"passed": int, "failures": list}
    """
    MAX_SOLUTION_RETRIES = 2
    MAX_TESTGEN_RETRIES = 2

    if lang_available is None:
        lang_available = {l: True for l in LANGUAGES}

    # Create output directory structure
    for d in [
        os.path.join(output_dir, "inputs"),
        os.path.join(output_dir, "outputs"),
        os.path.join(output_dir, "java_outputs"),
        os.path.join(output_dir, "python_outputs"),
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

    # Step 3: Generate driver code templates (all 4 languages)
    print("\n--- Step 3: Generate Driver Code Templates ---")
    driver_agent = DriverCodeAgent(output_dir=output_dir)
    driver_paths = driver_agent.run(problem_text)

    # Step 4: Run solution pipeline for each available language
    # C++ runs first as ground truth; Java/Python compare against C++ outputs
    solution_agent = SolutionAgent(output_dir=output_dir)
    results = {}
    cpp_outputs_dir = os.path.join(output_dir, "outputs")

    # Run C++ first (ground truth)
    if lang_available.get("cpp", False):
        passed, failures = _run_language_pipeline(
            lang="cpp",
            problem_text=problem_text,
            solution_agent=solution_agent,
            executor=executor,
            max_retries=MAX_SOLUTION_RETRIES,
        )
        results["cpp"] = {"passed": passed, "failures": failures}
    else:
        print(f"\n[main] Skipping C++ (not available).")
        cpp_outputs_dir = None  # No ground truth available

    # Run Java and Python, comparing against C++ outputs
    for lang in ["java", "python"]:
        if not lang_available.get(lang, False):
            print(f"\n[main] Skipping {LANG_LABELS[lang]} (not available).")
            continue

        passed, failures = _run_language_pipeline(
            lang=lang,
            problem_text=problem_text,
            solution_agent=solution_agent,
            executor=executor,
            max_retries=MAX_SOLUTION_RETRIES,
            expected_outputs_dir=cpp_outputs_dir,
        )
        results[lang] = {"passed": passed, "failures": failures}

    return results


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

    lang_available = validate_environment()
    problem_text = read_problem(args)

    results = run_pipeline(problem_text, output_dir="output", lang_available=lang_available)

    total = ExecutorAgent.NUM_TESTS

    # Final summary
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    any_failure = False
    for lang in LANGUAGES:
        if lang not in results:
            continue
        r = results[lang]
        label = LANG_LABELS[lang]
        status = "PASS" if not r["failures"] else "FAIL"
        print(f"  {label:8s}: {r['passed']}/{total} tests passed  [{status}]")
        if r["failures"]:
            failing = [f["test_num"] for f in r["failures"]]
            print(f"           Still failing: {failing}")
            any_failure = True
    print("=" * 60)

    if any_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
