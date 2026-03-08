"""AWS Lambda handler for the DSA Question Agent."""
import json
import logging
import os
import shutil
import tempfile
import urllib.request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DEFAULT_TIME_LIMIT = 1.0


def _post_json(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        logger.info("Callback status: %s", r.status)


_INVALID_OUTPUT_MARKERS = ("TLE", "EXCEPTION:", "ERROR")

def _collect_test_cases(output_dir):
    cases = []
    for i in range(1, 11):
        inp = os.path.join(output_dir, "inputs", f"test_{i}.txt")
        out = os.path.join(output_dir, "outputs", f"test_{i}_output.txt")
        if not os.path.exists(inp):
            continue
        output_content = open(out).read() if os.path.exists(out) else ""
        stripped = output_content.strip()
        if any(stripped.startswith(marker) for marker in _INVALID_OUTPUT_MARKERS):
            logger.warning("Skipping test_%d: output contains error marker (%s)", i, stripped[:20])
            continue
        cases.append({
            "input": open(inp).read(),
            "output": output_content,
            "timeLimit": DEFAULT_TIME_LIMIT
        })
    return cases


def _collect_driver_codes(output_dir):
    driver = os.path.join(output_dir, "driver")
    files = {
        "java":   "Main.java",
        "cpp":    "driver.cpp",
        "c":      "driver.c",
        "python": "driver.py"
    }
    return {
        lang: open(os.path.join(driver, f)).read()
        if os.path.exists(os.path.join(driver, f)) else None
        for lang, f in files.items()
    }


def push(question_id: str, callback_url: str = None, tenant_id: str = "", output_dir: str = "output"):
    """
    Push the current driver codes and test cases for the given questionId.

    Args:
        question_id:  The question ID to tag the payload with.
        callback_url: URL to POST the payload to. Falls back to CALLBACK_URL env var.
        tenant_id:    Optional tenant ID. Falls back to TENANT_ID env var.
        output_dir:   Path to the output directory (default: 'output').
    """
    url = callback_url or os.environ.get("CALLBACK_URL", "")
    if not url:
        raise ValueError("callback_url must be provided or CALLBACK_URL env var must be set")

    tenant = tenant_id or os.environ.get("TENANT_ID", "")

    test_cases = _collect_test_cases(output_dir)
    driver_codes = _collect_driver_codes(output_dir)

    if not test_cases:
        raise RuntimeError(f"No test cases found in {output_dir}/inputs/")

    payload = {
        "questionId": question_id,
        "tenantId": tenant,
        "testCases": test_cases,
        "driverCodes": driver_codes,
    }
    _post_json(url, payload)
    print(f"[push] Pushed {len(test_cases)} test case(s) for questionId={question_id}")
    return payload


def handler(event, context):
    question_id = event.get("questionId", "unknown")
    question_text = event.get("questionText", "")
    callback_url = event.get("callbackUrl", "")
    tenant_id = event.get("tenantId", "")

    if not question_text or not callback_url:
        return {"statusCode": 400, "body": "Missing questionText or callbackUrl"}

    output_dir = tempfile.mkdtemp(prefix=f"dsa_{question_id}_")
    try:
        from main import run_pipeline
        run_pipeline(problem_text=question_text, output_dir=output_dir)

        test_cases = _collect_test_cases(output_dir)
        driver_codes = _collect_driver_codes(output_dir)

        if not test_cases:
            raise RuntimeError("Pipeline completed but no test cases were generated")

        _post_json(callback_url, {
            "questionId": question_id,
            "tenantId": tenant_id,
            "testCases": test_cases,
            "driverCodes": driver_codes
        })
        return {
            "statusCode": 200,
            "body": json.dumps({"questionId": question_id, "count": len(test_cases)})
        }

    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        try:
            _post_json(callback_url, {
                "questionId": question_id,
                "tenantId": tenant_id,
                "error": str(exc),
                "testCases": [],
                "driverCodes": {}
            })
        except Exception as cb_err:
            logger.error("Callback also failed: %s", cb_err)
        return {"statusCode": 500, "body": str(exc)}
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)
