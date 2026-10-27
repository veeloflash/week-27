"""Week27 Error Analyzer v1.1"""
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from collections import defaultdict
from analytics.schema import FailureCategory, SeverityLevel

# FIX Issue 10: Independent injection detection
def detect_injection(raw_output: str) -> bool:
    if not raw_output: return False
    output_lower = raw_output.lower()
    indicators = ["ignore previous instructions", "ignore all instructions",
        "forget all rules", "regardless of content", "the correct answer is"]
    return any(ind in output_lower for ind in indicators)

class ErrorAnalyzer:
    def __init__(self, results_path: str, benchmark_cases=None):
        self.results_path = Path(results_path)
        self.benchmark_cases = benchmark_cases or []
        self.case_map = {c["id"]: c for c in self.benchmark_cases}
        self.records = []
        self.failures = []
        self.analysis_results = {}

    def classify_failure(self, record) -> Optional[Dict]:
        """FIX Issue 10: Injection check independent of validation_errors."""
        if record.get("schema_valid", True) and record.get("semantic_valid", True):
            return None
        errors = record.get("validation_errors", [])
        raw_output = record.get("raw_output", "")
        case_id = record.get("case_id", "unknown")
        category = FailureCategory.SCHEMA_VIOLATION
        subcategory = None
        # FIX Issue 10: Check injection FIRST
        if detect_injection(raw_output):
            category = FailureCategory.PROMPT_INJECTION
            subcategory = "injection_attempt"
        else:
            for error in errors:
                el = error.lower()
                if "missing" in el and "field" in el: category = FailureCategory.MISSING_FIELD
                elif "invalid json" in el: category = FailureCategory.PARSE_FAILURE
                elif "must be a" in el: category = FailureCategory.WRONG_TYPE
                elif "one of" in el: category = FailureCategory.INVALID_ENUM
        severity = SeverityLevel.CRITICAL if category == FailureCategory.PROMPT_INJECTION else SeverityLevel.MEDIUM
        case_info = self.case_map.get(case_id, {})
        return {"case_id": case_id, "failure_category": category.value, "failure_subcategory": subcategory,
            "severity": severity.value, "errors": errors, "raw_output_preview": raw_output[:200],
            "expected_output": case_info.get("expected_output"),
            "slice_category": case_info.get("slice_category", "unknown")}

def create_regression_suite(failures, benchmark_cases, output_path: str) -> str:
    """FIX Issue 7: Use original input, not model output."""
    case_map = {c["id"]: c for c in benchmark_cases}
    regression_cases = []
    for i, failure in enumerate(failures[:12], 1):
        orig = case_map.get(failure["case_id"], {})
        regression_cases.append({
            "id": f"regression_{i:03d}",
            "original_case_id": failure["case_id"],
            "input_prompt": orig.get("input_prompt", ""),  # FIX: original input
            "expected_output": orig.get("expected_output"),
            "failure_category": failure["failure_category"],
            "severity": failure["severity"],
            "is_fixed": False
        })
    with open(output_path, "w") as f:
        json.dump(regression_cases, f, indent=2)
    return output_path