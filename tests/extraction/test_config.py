import os
import json
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
TEST_OUTPUT_DIR = os.environ.get("TEST_OUTPUT_DIR", "./test-output")
DEFAULT_TIMEOUT = 120


class Timer:
    def __init__(self):
        self.start_time = None
        self.elapsed = 0.0

    def start(self):
        self.start_time = time.time()
        return self

    def stop(self) -> float:
        if self.start_time is not None:
            self.elapsed = time.time() - self.start_time
        return self.elapsed

    def elapsed_ms(self) -> float:
        return self.elapsed * 1000


def get_test_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{uuid.uuid4().hex[:8]}"


def ensure_output_dir(test_run_id: str) -> str:
    run_dir = os.path.join(TEST_OUTPUT_DIR, test_run_id)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def save_to_file(data: dict, file_path: str):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_from_file(file_path: str) -> dict:
    if not os.path.exists(file_path):
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def log_step(test_run_id: str, step: str, data: dict):
    run_dir = ensure_output_dir(test_run_id)
    log_path = os.path.join(run_dir, f"steps.json")
    if os.path.exists(log_path):
        logs = load_from_file(log_path)
    else:
        logs = []
    logs.append({
        "timestamp": datetime.now().isoformat(),
        "step": step,
        "data": data,
    })
    save_to_file(logs, log_path)


def save_result(test_run_id: str, method: str, result: dict):
    run_dir = ensure_output_dir(test_run_id)
    result_path = os.path.join(run_dir, f"result_{method}.json")
    save_to_file(result, result_path)


def save_input(test_run_id: str, method: str, input_data: dict):
    run_dir = ensure_output_dir(test_run_id)
    input_path = os.path.join(run_dir, f"input_{method}.json")
    save_to_file(input_data, input_path)


def save_metadata(test_run_id: str, metadata: dict):
    run_dir = ensure_output_dir(test_run_id)
    metadata_path = os.path.join(run_dir, "metadata.json")
    save_to_file(metadata, metadata_path)


def get_test_metadata(test_run_id: str) -> dict:
    run_dir = ensure_output_dir(test_run_id)
    metadata_path = os.path.join(run_dir, "metadata.json")
    return load_from_file(metadata_path)


def save_intermediate(test_run_id: str, step_name: str, data: dict):
    run_dir = ensure_output_dir(test_run_id)
    step_path = os.path.join(run_dir, f"intermediate_{step_name}.json")
    save_to_file(data, step_path)


def validate_required_params(params: Dict[str, Any], required: list) -> Optional[str]:
    missing = [p for p in required if p not in params or params[p] is None]
    if missing:
        return f"缺少必需参数: {', '.join(missing)}"
    return None


def calculate_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    metrics = {}
    result_data = result.get("result", result)

    type_categories = [
        "object_types", "link_types", "action_types",
        "rule_types", "process_types", "function_types", "indicator_types",
        "entities", "relations",
    ]

    for category in type_categories:
        items = result_data.get(category, [])
        metrics[category] = len(items)

    metrics["total_types"] = sum(
        len(result_data.get(cat, []))
        for cat in ["object_types", "link_types", "action_types",
                    "rule_types", "process_types", "function_types", "indicator_types"]
    )

    if result.get("session_id"):
        metrics["session_id_present"] = True
    else:
        metrics["session_id_present"] = False

    return metrics


def print_test_summary(result: Dict[str, Any], method_name: str):
    print("\n" + "="*60)
    print(f"{method_name} 测试结果总结")
    print("="*60)
    print(f"测试ID: {result.get('test_run_id')}")
    print(f"状态: {result.get('status')}")
    if result.get("session_id"):
        print(f"Session ID: {result.get('session_id')}")
    if result.get("metrics"):
        print(f"提取指标: {result['metrics']}")
    if result.get("total_time"):
        print(f"总耗时: {result['total_time']:.2f}秒")
    if result.get("error_message"):
        print(f"错误信息: {result['error_message']}")


def generate_test_report(test_run_id: str) -> Dict[str, Any]:
    run_dir = os.path.join(TEST_OUTPUT_DIR, test_run_id)
    report = {
        "test_run_id": test_run_id,
        "generated_at": datetime.now().isoformat(),
        "results": {},
        "steps": [],
        "metadata": {},
    }

    if os.path.exists(run_dir):
        for filename in os.listdir(run_dir):
            filepath = os.path.join(run_dir, filename)
            if filename.startswith("result_") and filename.endswith(".json"):
                method = filename.replace("result_", "").replace(".json", "")
                report["results"][method] = load_from_file(filepath)
            elif filename == "steps.json":
                report["steps"] = load_from_file(filepath)
            elif filename == "metadata.json":
                report["metadata"] = load_from_file(filepath)

    return report