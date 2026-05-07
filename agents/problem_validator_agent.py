import json
import re
from typing import List

from .base_agent import BaseAgent

SYSTEM_PROMPT = """\
You are a strict reviewer of competitive-programming problem statements.

Your sole job is to decide whether the provided problem statement contains every section
needed for an automated agent to (a) generate test inputs and (b) generate a correct solution.
You do NOT solve the problem and do NOT write code.

REQUIRED SECTIONS (each must be present, complete, and unambiguous):
1. CONSTRAINTS — concrete numeric bounds for every input variable
   (e.g. "1 ≤ N ≤ 100", "1 ≤ a[i] ≤ 10^9"). Vague phrases like "small N",
   "fits in memory", or missing upper bounds are NOT acceptable.
2. INPUT FORMAT — exact stdin layout: which line contains what, separators, ordering.
3. OUTPUT FORMAT — exact stdout layout: what to print and in what form.
4. AT LEAST ONE WORKED EXAMPLE — a complete sample input AND its corresponding sample output.
   The example must be consistent with both the stated input format and the constraints.
   An explanation is preferred but not required.
5. UNAMBIGUOUS RULE / OPERATION — the core operation the solver is asked to perform must
   be defined precisely. Words like "match", "valid", "best", "process" must have an exact
   mathematical/algorithmic definition. If two competent solvers could read the rule two
   different ways and produce different outputs on the same input, the rule is ambiguous.

EXAMPLE-LEVEL CHECKS (these are the most common source of "wrong data" — be especially strict):
A. EXAMPLE OUTPUT MUST BE LOGICALLY DERIVABLE.
   For every worked example, mentally apply the problem's rules to the stated Input and derive
   what the Output SHOULD be. Compare against the stated Output. If they disagree, this is a
   defect — say which example, what the stated output is, and what it should be.
   Watch especially for outputs like "No match / No solution / -1" that are inconsistent with
   inputs that clearly produce a non-empty answer.
B. OUTPUT vs EXPLANATION MUST AGREE.
   If an example has both a stated Output and an Explanation, they must agree word-for-word
   on count, contents, and order. A mismatch (the Explanation lists 4 items but the Output
   lists 3, or different elements) is a defect — call it out specifically.
C. EXAMPLES MUST AGREE WITH EACH OTHER.
   The same rule, applied uniformly, must produce all the stated example outputs. If you can
   only justify Example 1 with rule interpretation X but Example 2 requires interpretation Y,
   the rule is ambiguous or one example is wrong.
D. EXAMPLE INPUT MUST SATISFY THE CONSTRAINTS.
   No example input may violate any stated bound (size, value range, format).

GENERAL CONSISTENCY CHECKS:
- The input format and the example must agree (no contradictions about how many lines, etc.).
- The output format and the example output must agree.
- If multiple test cases per run are implied, that must be stated explicitly with a T variable.
- The problem must not contradict itself (e.g. "you do not handle I/O" alongside an explicit
  "Custom Input/Output Format" section is a contradiction worth flagging).

OUTPUT (your response):
Return a single JSON object inside a ```json ... ``` fenced code block, with this exact schema:
{
  "valid": true | false,
  "issues": ["one specific defect per string", "..."],
  "summary": "one or two sentences describing the overall verdict"
}

Rules:
- If valid, "issues" must be an empty array.
- If invalid, list every defect separately and concretely.
- For an example-output defect, cite the example number, the stated output, and the output
  the rules would actually produce — e.g. "Example 1: stated output is 'No match found',
  but with pattern 'H' the words 'Hi' and 'Hello' both have abbreviation 'H' and must match."
- For an internal contradiction inside an example, name the two locations in conflict — e.g.
  "Example 2: Output lists 3 words but Explanation lists 4 (CoolCode appears in the
  Explanation but not the Output)."
- Do NOT include any prose outside the fenced JSON block.
"""


class ValidationResult:
    def __init__(self, valid: bool, issues: List[str], summary: str, raw: str = ""):
        self.valid = valid
        self.issues = issues
        self.summary = summary
        self.raw = raw

    def __bool__(self) -> bool:
        return self.valid


class ProblemValidatorAgent(BaseAgent):
    """
    Runs BEFORE any other agent. Verifies the problem statement is well-formed:
    constraints present and concrete, input/output format defined, at least one
    consistent worked example. Aborts the pipeline on failure so we don't waste
    budget generating tests/solutions for an under-specified problem.
    """

    def run(self, problem_text: str) -> ValidationResult:
        print("[ProblemValidatorAgent] Validating problem statement...")
        user_prompt = f"Validate the following problem statement:\n\n{problem_text}"
        response = self.call_model(SYSTEM_PROMPT, user_prompt, max_output_tokens=2048)
        return self._parse(response)

    def _parse(self, response: str) -> ValidationResult:
        match = re.search(r"```json\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
        payload = match.group(1).strip() if match else response.strip()

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            return ValidationResult(
                valid=False,
                issues=[f"Validator returned malformed JSON: {e}"],
                summary="Could not parse validator output.",
                raw=response,
            )

        valid = bool(data.get("valid", False))
        issues = data.get("issues") or []
        if not isinstance(issues, list):
            issues = [str(issues)]
        issues = [str(x) for x in issues]
        summary = str(data.get("summary", "")).strip()

        return ValidationResult(valid=valid, issues=issues, summary=summary, raw=response)
