import os
import json
import glob
from datetime import datetime
from typing import Dict, Any, List


def collect_test_results(base_dir: str = "./test-output") -> Dict[str, List[Dict]]:
    all_results = {}
    if not os.path.exists(base_dir):
        return all_results

    for test_dir in os.listdir(base_dir):
        test_path = os.path.join(base_dir, test_dir)
        if not os.path.isdir(test_path):
            continue

        for result_file in glob.glob(os.path.join(test_path, "result_*.json")):
            method = os.path.basename(result_file).replace("result_", "").replace(".json", "")
            if method not in all_results:
                all_results[method] = []

            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    result["test_run_id"] = test_dir
                    all_results[method].append(result)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[警告] 无法读取结果文件 {result_file}: {e}")

    return all_results


def calculate_statistics(results: List[Dict]) -> Dict[str, Any]:
    if not results:
        return {
            "total_runs": 0,
            "success_count": 0,
            "error_count": 0,
            "partial_count": 0,
            "avg_time": 0.0,
            "min_time": 0.0,
            "max_time": 0.0,
            "metrics_summary": {},
        }

    success_count = sum(1 for r in results if r.get("status") == "success")
    error_count = sum(1 for r in results if r.get("status") == "error")
    partial_count = sum(1 for r in results if r.get("status") == "partial")

    times = [r.get("total_time", 0) for r in results if r.get("total_time")]
    avg_time = sum(times) / len(times) if times else 0.0
    min_time = min(times) if times else 0.0
    max_time = max(times) if times else 0.0

    metrics_summary = {}
    type_categories = [
        "object_types", "link_types", "action_types",
        "rule_types", "process_types", "function_types", "indicator_types",
    ]
    for category in type_categories:
        values = []
        for r in results:
            metrics = r.get("metrics", {})
            if isinstance(metrics, dict) and category in metrics:
                values.append(metrics[category])
        if values:
            metrics_summary[category] = {
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "total": sum(values),
            }

    return {
        "total_runs": len(results),
        "success_count": success_count,
        "error_count": error_count,
        "partial_count": partial_count,
        "success_rate": success_count / len(results) * 100,
        "avg_time": avg_time,
        "min_time": min_time,
        "max_time": max_time,
        "metrics_summary": metrics_summary,
    }


def generate_report(results_by_method: Dict[str, List[Dict]]) -> Dict[str, Any]:
    report = {
        "report_generated_at": datetime.now().isoformat(),
        "total_methods": len(results_by_method),
        "methods": {},
        "summary": {},
        "issues": [],
    }

    overall_success = 0
    overall_total = 0

    for method, results in results_by_method.items():
        stats = calculate_statistics(results)
        report["methods"][method] = {
            "statistics": stats,
            "sample_results": results[:3],
        }
        overall_success += stats["success_count"]
        overall_total += stats["total_runs"]

        for result in results:
            if result.get("status") == "error":
                report["issues"].append({
                    "method": method,
                    "test_run_id": result.get("test_run_id"),
                    "step": result.get("step"),
                    "error_message": result.get("error_message"),
                    "http_status": result.get("http_status"),
                })

    report["summary"] = {
        "total_runs": overall_total,
        "total_success": overall_success,
        "overall_success_rate": (overall_success / overall_total * 100) if overall_total > 0 else 0,
    }

    return report


def format_report(report: Dict[str, Any]) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("本体提取测试综合报告")
    lines.append("=" * 80)
    lines.append(f"报告生成时间: {report['report_generated_at']}")
    lines.append(f"测试方法数量: {report['total_methods']}")
    lines.append("")

    lines.append("-" * 80)
    lines.append("总体统计")
    lines.append("-" * 80)
    summary = report["summary"]
    lines.append(f"总测试次数: {summary['total_runs']}")
    lines.append(f"成功次数: {summary['total_success']}")
    lines.append(f"总体成功率: {summary['overall_success_rate']:.1f}%")
    lines.append("")

    lines.append("-" * 80)
    lines.append("各方法详细统计")
    lines.append("-" * 80)

    method_names = {
        "natural_language": "自然语言提取",
        "database": "数据库提取",
        "document": "文档提取",
        "manual": "手动设计",
        "knowledge_base": "知识库提取",
    }

    for method, data in report["methods"].items():
        stats = data["statistics"]
        method_name = method_names.get(method, method)
        lines.append("")
        lines.append(f"【{method_name}】")
        lines.append("-" * 60)
        lines.append(f"测试次数: {stats['total_runs']}")
        lines.append(f"成功: {stats['success_count']}")
        lines.append(f"失败: {stats['error_count']}")
        lines.append(f"部分成功: {stats['partial_count']}")
        lines.append(f"成功率: {stats['success_rate']:.1f}%")
        lines.append(f"平均耗时: {stats['avg_time']:.2f}秒")
        lines.append(f"最短耗时: {stats['min_time']:.2f}秒")
        lines.append(f"最长耗时: {stats['max_time']:.2f}秒")

        if stats["metrics_summary"]:
            lines.append("类型提取统计:")
            for category, metrics in stats["metrics_summary"].items():
                lines.append(f"  - {category}: 平均{metrics['avg']:.1f} | 最小{metrics['min']} | 最大{metrics['max']}")

    if report["issues"]:
        lines.append("")
        lines.append("-" * 80)
        lines.append("问题汇总")
        lines.append("-" * 80)
        for idx, issue in enumerate(report["issues"], 1):
            lines.append(f"{idx}. [{issue['method']}] 步骤: {issue['step']}")
            lines.append(f"   测试ID: {issue['test_run_id']}")
            lines.append(f"   错误: {issue['error_message']}")
            if issue.get("http_status"):
                lines.append(f"   HTTP状态: {issue['http_status']}")
            lines.append("")

    lines.append("=" * 80)
    lines.append("测试结论与建议")
    lines.append("=" * 80)

    success_rate = summary["overall_success_rate"]
    if success_rate >= 90:
        lines.append("✓ 测试通过: 所有本体提取方法运行正常")
    elif success_rate >= 70:
        lines.append("⚠ 部分通过: 大部分方法运行正常，但存在一些问题需要修复")
    else:
        lines.append("✗ 需要改进: 多个方法存在问题，建议优先修复")

    if report["issues"]:
        lines.append("")
        lines.append("建议修复的问题:")
        for issue in report["issues"][:5]:
            lines.append(f"- [{issue['method']}] {issue['step']}: {issue['error_message']}")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="本体提取测试报告生成器")
    parser.add_argument("--input-dir", default="./test-output", help="测试输出目录")
    parser.add_argument("--output-file", help="报告输出文件路径")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="报告格式")

    args = parser.parse_args()

    results_by_method = collect_test_results(args.input_dir)

    if not results_by_method:
        print("未找到测试结果，请先运行测试脚本")
        return

    report = generate_report(results_by_method)

    if args.format == "json":
        report_json = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(report_json)
            print(f"JSON报告已保存到: {args.output_file}")
        else:
            print(report_json)
    else:
        formatted_report = format_report(report)
        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(formatted_report)
            print(f"测试报告已保存到: {args.output_file}")
        else:
            print(formatted_report)


if __name__ == "__main__":
    main()