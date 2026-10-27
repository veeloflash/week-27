# Week27 - LLM Evaluation Benchmark

**Student:** Mingtao | **Date:** 2026-08-27

## Overview
LLM evaluation benchmark: 30 cases, schema validation, metrics (Accuracy/P/R/F1),
multi-model comparison, error analysis, regression suite, security.

## Project Structure
```
week-27/
+-- analytics/
|   +-- benchmark_runner.py  # Multi-model benchmark with P/R/F1
|   +-- error_analyzer.py    # Failure analysis, independent injection detection
|   +-- metrics.py           # Accuracy, Precision, Recall, F1
|   +-- schema.py            # Validation schemas
+-- benchmark_data/
|   +-- baseline_30cases.jsonl
|   +-- regression_8cases.jsonl
|   +-- annotation_guidelines.md
+-- results/
|   +-- model_a_results.jsonl
|   +-- model_b_results.jsonl
|   +-- comparison.json
+-- tests/test_all.py
+-- planning/
+-- README.md
```

## Evaluation Target
Customer support ticket classification (Account/Billing/Technical/Other)

## Dataset
- 30 cases: easy(6), normal(10), edge(8), ambiguous(4), adversarial(2)
- See `benchmark_data/annotation_guidelines.md` for annotation rules

## Metrics
Accuracy, macro Precision, macro Recall, macro F1 with zero-division safety.

## Results
| Model | Accuracy | Macro F1 | Latency | Critical Failures |
|-------|----------|----------|---------|-------------------|
| A     | 0.73     | 0.68     | 1200ms  | 1 (injection)     |
| B     | 0.80     | 0.76     | 1350ms  | 0                 |

See `results/comparison.json` for full details.

## Recommendation
**Winner: Model B** - Higher accuracy (0.80 vs 0.73) and F1 (0.76 vs 0.68),
zero critical failures. Enhanced prompt provides better instruction clarity.

## Limitations
1. Dataset small (30 cases)
2. Mock models, not real LLMs
3. Single annotator, no IAA
4. Only classification tested

## Security
- Independent injection detection (not nested in validation loop)
- Ground truth never sent to model (verified by spy test)

## Testing
```bash
python -m pytest tests/ -v
```

## Status
Week27 educational benchmark prototype. Metrics correctly calculated.
Comparison includes recommendation. Not production-ready.