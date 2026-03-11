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

    # Language configs: (compile_fn_name, run_command_builder, outputs_subdir)
    LANG_CONFIG = {
        "cpp": {
            "label": "C++",
            "outputs_dir": "outputs",
        },
        "java": {
            "label": "Java",
            "outputs_dir": "java_outputs",
        },
        "python": {
            "label": "Python",
            "outputs_dir": "python_outputs",
        },
    }

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir

    # ── Test Generator ──────────────────────────────────────────────────

    def run_test_generator(self) -> None:
        """
        Run output/test_generator.py using the current Python interpreter.
        Raises TestGeneratorError (with .stderr attribute) on failure.
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

    # ── Compilation ─────────────────────────────────────────────────────

    def compile_cpp(self) -> None:
        """Compile output/solution.cpp with g++ -O2 -std=c++14."""
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
                f"[ExecutorAgent] C++ compilation failed (exit {result.returncode}).\n"
                f"stderr:\n{result.stderr}"
            )
        print("[ExecutorAgent] C++ compilation successful.")

    # Keep old name as alias for backward compat
    compile_solution = compile_cpp

    def compile_java(self) -> None:
        """Compile output/Main.java with javac."""
        print("[ExecutorAgent] Compiling Main.java...")
        try:
            result = subprocess.run(
                ["javac", "-d", self.output_dir,
                 os.path.join(self.output_dir, "Main.java")],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "[ExecutorAgent] Java compilation failed: 'javac' not found on PATH. "
                "Install a JDK to enable the Java pipeline."
            )
        if result.returncode != 0:
            raise RuntimeError(
                f"[ExecutorAgent] Java compilation failed (exit {result.returncode}).\n"
                f"stderr:\n{result.stderr}"
            )
        print("[ExecutorAgent] Java compilation successful.")

    # ── Run command builders ────────────────────────────────────────────

    def _get_run_command(self, lang: str) -> list:
        if lang == "cpp":
            return [os.path.join(self.output_dir, "solution")]
        elif lang == "java":
            return ["java", "-cp", self.output_dir, "Main"]
        elif lang == "python":
            return [sys.executable, os.path.join(self.output_dir, "solution.py")]
        raise ValueError(f"Unknown language: {lang}")

    # ── Compile + Run (unified entry point) ─────────────────────────────

    def compile_and_run(self, lang: str, expected_outputs_dir: str = None) -> tuple:
        """
        Compile (if needed) and run solution against all tests for the given language.
        If expected_outputs_dir is provided, compare outputs against ground truth.
        Returns (passed, failures).
        Raises RuntimeError on compile failure.
        """
        if lang == "cpp":
            self.compile_cpp()
        elif lang == "java":
            self.compile_java()
        # Python needs no compilation

        return self._run_against_tests(lang, expected_outputs_dir=expected_outputs_dir)

    # ── Generic test runner ─────────────────────────────────────────────

    def _run_against_tests(self, lang: str, expected_outputs_dir: str = None) -> tuple:
        """
        Run the solution for `lang` against each of the NUM_TESTS input files.
        If expected_outputs_dir is provided, compare outputs against those files (ground truth).

        Returns:
            (passed, failures) where failures is a list of dicts:
            {"test_num": int, "status": str, "exit_code": int|None, "input": str, "output": str}
        """
        cfg = self.LANG_CONFIG[lang]
        command = self._get_run_command(lang)
        outputs_dir = os.path.join(self.output_dir, cfg["outputs_dir"])
        inputs_dir = os.path.join(self.output_dir, "inputs")
        os.makedirs(outputs_dir, exist_ok=True)

        print(f"[ExecutorAgent] Running {cfg['label']} solution against all test cases...")
        if expected_outputs_dir:
            print(f"[ExecutorAgent] Comparing against expected outputs from: {expected_outputs_dir}")
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
                    try:
                        result = subprocess.run(
                            command,
                            stdin=infile,
                            capture_output=True,
                            text=True,
                            timeout=self.TIMEOUT_SECONDS,
                        )
                    except FileNotFoundError:
                        raise RuntimeError(
                            f"Runtime not found: {command[0]}. "
                            f"Is the required runtime installed and on PATH?"
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
                        "output": output_content,
                    })
                else:
                    output_content = result.stdout

                    # Compare against expected output if available
                    if expected_outputs_dir:
                        expected_path = os.path.join(expected_outputs_dir, f"test_{i}_output.txt")
                        if os.path.exists(expected_path):
                            with open(expected_path, "r") as ef:
                                expected = ef.read().strip()
                            actual = output_content.strip()
                            if actual != expected:
                                status = "WRONG ANSWER"
                                failures.append({
                                    "test_num": i,
                                    "status": "WRONG_ANSWER",
                                    "exit_code": 0,
                                    "input": input_content,
                                    "output": output_content,
                                    "expected": expected,
                                })
                            else:
                                status = "OK"
                                passed += 1
                        else:
                            status = "OK"
                            passed += 1
                    else:
                        status = "OK"
                        passed += 1

                with open(output_path, "w") as outfile:
                    outfile.write(output_content)

                print(f"  test_{i}: {status} ({elapsed:.3f}s)")
                if result.returncode != 0 and result.stderr:
                    err_lines = result.stderr.strip().splitlines()[:3]
                    for line in err_lines:
                        print(f"           {line}")
                if status == "WRONG ANSWER" and expected_outputs_dir:
                    print(f"           Expected: {expected[:80]}")
                    print(f"           Got:      {actual[:80]}")

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
                    "output": "",
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
                    "output": "",
                })

        return passed, failures

    # ── Legacy methods (backward compat) ────────────────────────────────

    def run_solution_against_tests(self) -> tuple:
        """Run C++ binary against tests (legacy wrapper)."""
        return self._run_against_tests("cpp")
