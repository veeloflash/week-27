"""Week27 Benchmark Runner v1.1"""
import json, csv, os
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any
from pathlib import Path
from analytics.schema import (BenchmarkCase, ModelOutputRecord, EvaluationResult,
    FailureCategory, SeverityLevel, validate_support_ticket, validate_invoice)
from analytics.metrics import (calculate_all_metrics, calculate_macro_metrics,
    calculate_schema_validity_rate, calculate_field_accuracy, calculate_exact_match)

class BenchmarkRunner:
    def __init__(self, benchmark_path: str, output_dir: str = "./benchmark_results"):
        self.benchmark_path = Path(benchmark_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cases: List[BenchmarkCase] = []
        self.results: Dict[str, List[ModelOutputRecord]] = {}
        self.metadata = {"benchmark_version": "1.1", "created_at": datetime.now().isoformat()}

    def load_jsonl(self) -> List[BenchmarkCase]:
        cases = []
        with open(self.benchmark_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                try:
                    case = json.loads(line)
                    for field in ["id", "task_type", "input_prompt", "expected_output"]:
                        if field not in case: raise ValueError(f"Missing: {field}")
                    cases.append(case)
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping malformed JSON: {e}")
        self.cases = cases
        return cases

    def run_model(self, model_name: str, model_fn: Callable, model_version: str = "1.0", resume: bool = True):
        records = []
        results_file = self.output_dir / f"{model_name}_results.jsonl"
        existing_case_ids = set()
        if resume and results_file.exists():
            with open(results_file, "r") as f:
                for line in f:
                    r = json.loads(line.strip())
                    existing_case_ids.add(r["case_id"])
                    records.append(r)
        for case in self.cases:
            if case["id"] in existing_case_ids: continue
            start_time = datetime.now()
            try:
                result = model_fn(case["input_prompt"])
                end_time = datetime.now()
                raw_output = result.get("raw_output", "")
                parsed_output = result.get("parsed_output")
                schema_valid = False
                validation_errors = []
                semantic_valid = False
                if case["task_type"] == "extraction" and parsed_output:
                    if case.get("schema_type") == "support_ticket":
                        schema_valid, validation_errors = validate_support_ticket(parsed_output)
                        if schema_valid:
                            expected = case["expected_output"]
                            semantic_valid = all(parsed_output.get(k) == v for k, v in expected.items())
                    elif case.get("schema_type") == "invoice":
                        schema_valid, validation_errors = validate_invoice(parsed_output)
                        if schema_valid:
                            expected = case["expected_output"]
                            semantic_valid = all(parsed_output.get(k) == v for k, v in expected.items())
                elif case["task_type"] == "classification":
                    # FIX Issue 1: Actually compare predicted vs expected label
                    if parsed_output and isinstance(parsed_output, dict):
                        predicted_label = parsed_output.get("label", "")
                        expected_label = case["expected_output"].get("label", "")
                        semantic_valid = (predicted_label == expected_label)
                record = {
                    "case_id": case["id"], "model_name": model_name, "model_version": model_version,
                    "raw_output": raw_output, "parsed_output": parsed_output,
                    "schema_valid": schema_valid, "semantic_valid": semantic_valid,
                    "validation_errors": validation_errors,
                    "latency_ms": (end_time - start_time).total_seconds() * 1000,
                    "timestamp": end_time.isoformat()
                }
                records.append(record)
                with open(results_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
            except Exception as e:
                error_record = {
                    "case_id": case["id"], "model_name": model_name, "model_version": model_version,
                    "raw_output": f"ERROR: {str(e)}", "parsed_output": None,
                    "schema_valid": False, "semantic_valid": False, "validation_errors": [str(e)],
                    "latency_ms": None, "timestamp": datetime.now().isoformat()
                }
                records.append(error_record)
                with open(results_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(error_record) + "\n")
        self.results[model_name] = records
        return records

    def evaluate_model(self, model_name: str) -> EvaluationResult:
        """FIX Issue 2: Calculate real P/R/F1 for classification."""
        if model_name not in self.results:
            raise ValueError(f"No results for: {model_name}")
        records = self.results[model_name]
        total = len(records)
        if total == 0:
            return {"model_name": model_name, "total_cases": 0, "schema_pass_rate": 0.0,
                "semantic_pass_rate": 0.0, "accuracy": None, "precision": None,
                "recall": None, "f1_score": None, "avg_latency_ms": None,
                "failure_breakdown": {}, "slice_results": {}}
        schema_valid_count = sum(1 for r in records if r["schema_valid"])
        schema_pass_rate = schema_valid_count / total
        semantic_valid_count = sum(1 for r in records if r["semantic_valid"])
        semantic_pass_rate = semantic_valid_count / total
        latencies = [r["latency_ms"] for r in records if r["latency_ms"] is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else None
        # FIX Issue 2: Real P/R/F1
        predictions = []
        ground_truth = []
        classes = set()
        for record in records:
            case = next((c for c in self.cases if c["id"] == record["case_id"]), None)
            if case and case["task_type"] == "classification":
                pred = record["parsed_output"].get("label", "") if record["parsed_output"] else ""
                expected = case["expected_output"].get("label", "")
                predictions.append(pred)
                ground_truth.append(expected)
                classes.add(expected)
                classes.add(pred)
        accuracy = precision = recall = f1_score = None
        if predictions and ground_truth:
            correct = sum(1 for p, g in zip(predictions, ground_truth) if p == g)
            accuracy = correct / len(predictions)
            if classes:
                macro = calculate_macro_metrics(predictions, ground_truth, list(classes))
                precision = macro["macro_precision"]
                recall = macro["macro_recall"]
                f1_score = macro["macro_f1"]
        failure_breakdown = {}
        for record in records:
            if not record["schema_valid"] and record["validation_errors"]:
                for error in record["validation_errors"]:
                    if "Missing" in error: cat = "missing_field"
                    elif "must be" in error: cat = "wrong_type"
                    elif "one of" in error: cat = "invalid_enum"
                    else: cat = "schema_violation"
                    failure_breakdown[cat] = failure_breakdown.get(cat, 0) + 1
        case_map = {c["id"]: c for c in self.cases}
        slice_results = {}
        slices = set(case_map[r["case_id"]]["slice_category"] for r in records if r["case_id"] in case_map)
        for sc in slices:
            sr = [r for r in records if case_map.get(r["case_id"], {}).get("slice_category") == sc]
            if sr:
                slice_results[sc] = {"count": len(sr), "semantic_pass_rate": sum(1 for r in sr if r["semantic_valid"]) / len(sr)}
        return {"model_name": model_name, "total_cases": total, "schema_pass_rate": schema_pass_rate,
            "semantic_pass_rate": semantic_pass_rate, "accuracy": accuracy, "precision": precision,
            "recall": recall, "f1_score": f1_score, "avg_latency_ms": avg_latency,
            "failure_breakdown": failure_breakdown, "slice_results": slice_results}

    def compare_models(self, model_names: List[str]) -> Dict[str, Any]:
        """FIX Issue 5: Real comparison with recommendation."""
        comparison = {"models": [], "comparison_date": datetime.now().isoformat(),
            "benchmark_path": str(self.benchmark_path), "recommendation": None, "reasoning": None, "limitations": []}
        model_results = {}
        for name in model_names:
            if name in self.results:
                result = self.evaluate_model(name)
                comparison["models"].append(result)
                model_results[name] = result
        if len(model_results) >= 2:
            best_model = None
            best_score = -1
            for name, result in model_results.items():
                score = 0
                if result.get("f1_score") is not None: score += result["f1_score"] * 0.6
                if result.get("accuracy") is not None: score += result["accuracy"] * 0.4
                if score > best_score:
                    best_score = score
                    best_model = name
            if best_model:
                comparison["recommendation"] = best_model
                comparison["reasoning"] = f"{best_model} achieved highest combined F1 and accuracy"
                for name, result in model_results.items():
                    if result.get("f1_score") is not None and result["f1_score"] < 0.7:
                        comparison["limitations"].append(f"{name}: Low F1 ({result['f1_score']:.2f})")
        return comparison

    def export_report(self, output_path: Optional[str] = None) -> str:
        if output_path is None:
            output_path = self.output_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            output_path = Path(output_path)
        report = {"metadata": self.metadata, "summary": {}, "model_results": {}, "comparison": None}
        for model_name in self.results.keys():
            result = self.evaluate_model(model_name)
            report["model_results"][model_name] = result
            report["summary"][model_name] = {"total_cases": result["total_cases"],
                "accuracy": result.get("accuracy"), "precision": result.get("precision"),
                "recall": result.get("recall"), "f1_score": result.get("f1_score")}
        if len(self.results) >= 2:
            report["comparison"] = self.compare_models(list(self.results.keys()))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        return str(output_path)