"""AWS Lambda handler for the DSA Question Agent."""
import json
import logging
import os
import shutil
import tempfile
import urllib.request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DEFAULT_TIME_LIMIT = 2.0


def _post_json(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        logger.info("Callback status: %s", r.status)


def _collect_test_cases(output_dir):
    cases = []
    for i in range(1, 11):
        inp = os.path.join(output_dir, "inputs", f"test_{i}.txt")
        out = os.path.join(output_dir, "outputs", f"test_{i}_output.txt")
        if not os.path.exists(inp):
            continue
        cases.append({
            "input": open(inp).read(),
            "output": open(out).read() if os.path.exists(out) else "",
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
