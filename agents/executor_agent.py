import os
import sys
import subprocess
import time


class TestGeneratorError(RuntimeError):
    """Raised when test_generator.py fails; carries the raw stderr for retry prompts."""
    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message)
        self.stderr = stderr


class ExecutorAgent:
    TIMEOUT_SECONDS = 10
    NUM_TESTS = 10

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir

    def run_test_generator(self) -> None:
        """
        Run output/test_generator.py using the current Python interpreter.
        Raises TestGeneratorError (with .stderr attribute) on failure so callers
        can extract the error text for LLM retry prompts.
        """
        print("[ExecutorAgent] Running test generator script...")
        result = subprocess.run(
            [sys.executable, os.path.join(self.output_dir, "test_generator.py")],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise TestGeneratorError(
                f"[ExecutorAgent] test_generator.py failed (exit {result.returncode}).\n"
                f"stderr:\n{result.stderr}",
                stderr=result.stderr,
            )
        if result.stdout:
            print(result.stdout, end="")

        # Validate that exactly NUM_TESTS input files were created
        inputs_dir = os.path.join(self.output_dir, "inputs")
        created = [
            f for f in os.listdir(inputs_dir)
            if f.startswith("test_") and f.endswith(".txt")
        ]
        if len(created) != self.NUM_TESTS:
            raise TestGeneratorError(
                f"[ExecutorAgent] Expected {self.NUM_TESTS} input files, "
                f"found {len(created)}: {sorted(created)}",
                stderr=f"Wrong file count: expected {self.NUM_TESTS}, got {len(created)}",
            )
        print(f"[ExecutorAgent] {self.NUM_TESTS} test input files created.")

    def compile_solution(self) -> None:
        """Compile output/solution.cpp with g++ -O2 -std=c++14 (GCC 6.3.0 compatible)."""
        print("[ExecutorAgent] Compiling solution.cpp...")
        result = subprocess.run(
            [
                "g++", "-O2", "-std=c++14",
                "-o", os.path.join(self.output_dir, "solution"),
                os.path.join(self.output_dir, "solution.cpp"),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"[ExecutorAgent] Compilation failed (exit {result.returncode}).\n"
                f"stderr:\n{result.stderr}"
            )
        print("[ExecutorAgent] Compilation successful.")

    def run_solution_against_tests(self) -> tuple:
        """
        Run the compiled binary against each of the NUM_TESTS input files.

        Returns:
            (passed, failures) where failures is a list of dicts:
            {"test_num": int, "status": str, "exit_code": int|None, "input": str}
        """
        print("[ExecutorAgent] Running solution against all test cases...")
        inputs_dir = os.path.join(self.output_dir, "inputs")
        outputs_dir = os.path.join(self.output_dir, "outputs")
        binary = os.path.join(self.output_dir, "solution")
        passed = 0
        failures = []

        for i in range(1, self.NUM_TESTS + 1):
            input_path = os.path.join(inputs_dir, f"test_{i}.txt")
            output_path = os.path.join(outputs_dir, f"test_{i}_output.txt")

            if not os.path.exists(input_path):
                print(f"  test_{i}: SKIP (input file not found)")
                continue

            with open(input_path, "r") as f:
                input_content = f.read()

            start = time.perf_counter()
            try:
                with open(input_path, "r") as infile:
                    result = subprocess.run(
                        [binary],
                        stdin=infile,
                        capture_output=True,
                        text=True,
                        timeout=self.TIMEOUT_SECONDS,
                    )
                elapsed = time.perf_counter() - start

                if result.returncode != 0:
                    status = f"ERROR (exit {result.returncode})"
                    output_content = result.stdout + result.stderr
                    failures.append({
                        "test_num": i,
                        "status": status,
                        "exit_code": result.returncode,
                        "input": input_content,
                    })
                else:
                    status = "OK"
                    passed += 1
                    output_content = result.stdout

                with open(output_path, "w") as outfile:
                    outfile.write(output_content)

                print(f"  test_{i}: {status} ({elapsed:.3f}s) → {output_path}")

            except subprocess.TimeoutExpired:
                elapsed = time.perf_counter() - start
                print(f"  test_{i}: TLE ({elapsed:.1f}s limit={self.TIMEOUT_SECONDS}s)")
                with open(output_path, "w") as outfile:
                    outfile.write("TLE\n")
                failures.append({
                    "test_num": i,
                    "status": "TLE",
                    "exit_code": None,
                    "input": input_content,
                })

            except Exception as e:
                elapsed = time.perf_counter() - start
                print(f"  test_{i}: EXCEPTION ({elapsed:.3f}s) — {e}")
                with open(output_path, "w") as outfile:
                    outfile.write(f"EXCEPTION: {e}\n")
                failures.append({
                    "test_num": i,
                    "status": f"EXCEPTION: {e}",
                    "exit_code": None,
                    "input": input_content,
                })

        return passed, failures
