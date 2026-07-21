import sys
import os
import json
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_config import (
    API_BASE, TEST_OUTPUT_DIR, DEFAULT_TIMEOUT,
    get_test_run_id, ensure_output_dir, save_to_file,
    log_step, save_result, save_input, save_metadata,
    save_intermediate, validate_required_params, calculate_metrics,
    print_test_summary, Timer,
)

import requests


def run_nl_extraction_test(
    ontology_id: str,
    test_text: str,
    test_run_id: str = None,
    auto_search: bool = False,
    method: str = "auto",
) -> Dict[str, Any]:
    test_run_id = test_run_id or get_test_run_id()
    run_dir = ensure_output_dir(test_run_id)
    timer = Timer().start()

    print(f"[NL提取测试] 开始执行，测试ID: {test_run_id}")
    print(f"[NL提取测试] 本体ID: {ontology_id}")
    print(f"[NL提取测试] 测试文本长度: {len(test_text)}")

    validation_error = validate_required_params(
        {"ontology_id": ontology_id, "test_text": test_text},
        ["ontology_id", "test_text"]
    )
    if validation_error:
        error_result = {
            "status": "error",
            "step": "validation",
            "error_message": validation_error,
            "test_run_id": test_run_id,
        }
        save_result(test_run_id, "natural_language", error_result)
        print(f"[NL提取测试] 参数验证失败: {validation_error}")
        return error_result

    input_data = {
        "ontology_id": ontology_id,
        "text": test_text,
        "auto_search": auto_search,
        "method": method,
        "source_type": "text",
    }
    save_input(test_run_id, "natural_language", input_data)
    log_step(test_run_id, "输入数据已保存", {"ontology_id": ontology_id, "text_length": len(test_text)})
    save_metadata(test_run_id, {"test_type": "natural_language", "ontology_id": ontology_id})

    try:
        print(f"[NL提取测试] 步骤1: 调用自然语言提取API")
        step_timer = Timer().start()
        response = requests.post(
            f"{API_BASE}/api/extraction/extract/natural-language",
            json=input_data,
            timeout=DEFAULT_TIMEOUT,
        )
        response_time = step_timer.stop()
        log_step(test_run_id, "提取API调用完成", {"response_time": response_time, "status_code": response.status_code})

        if response.status_code != 200:
            error_result = {
                "status": "error",
                "step": "extract",
                "http_status": response.status_code,
                "error_message": response.text[:500],
                "response_time": response_time,
                "test_run_id": test_run_id,
                "total_time": timer.stop(),
            }
            log_step(test_run_id, "提取API调用失败", error_result)
            save_result(test_run_id, "natural_language", error_result)
            print(f"[NL提取测试] 提取失败: HTTP {response.status_code}")
            print(f"[NL提取测试] 错误信息: {response.text[:200]}")
            return error_result

        extract_result = response.json()
        save_intermediate(test_run_id, "extract_result", extract_result)
        log_step(test_run_id, "提取API调用成功", {
            "status": extract_result.get("status"),
            "session_id": extract_result.get("session_id"),
            "response_time": response_time,
        })
        print(f"[NL提取测试] 提取成功，Session ID: {extract_result.get('session_id', 'N/A')}")

        session_id = extract_result.get("session_id", "")
        if not session_id:
            error_result = {
                "status": "error",
                "step": "session_id_missing",
                "message": "提取结果中缺少session_id",
                "extract_result": extract_result,
                "test_run_id": test_run_id,
                "total_time": timer.stop(),
            }
            log_step(test_run_id, "session_id缺失", error_result)
            save_result(test_run_id, "natural_language", error_result)
            print(f"[NL提取测试] 错误: 提取结果中缺少session_id")
            return error_result

        print(f"[NL提取测试] 步骤2: 查询提取会话详情")
        step_timer = Timer().start()
        session_response = requests.get(
            f"{API_BASE}/api/extraction/sessions/{session_id}",
            timeout=30,
        )
        session_query_time = step_timer.stop()

        if session_response.status_code == 200:
            session_data = session_response.json()
            save_intermediate(test_run_id, "session_details", session_data)
            log_step(test_run_id, "会话查询成功", {
                "status": session_data.get("status"),
                "ontology_id": session_data.get("ontology_id"),
                "response_time": session_query_time,
            })
            print(f"[NL提取测试] 会话查询成功")
        else:
            log_step(test_run_id, "会话查询失败", {
                "http_status": session_response.status_code,
                "error": session_response.text[:200],
                "response_time": session_query_time,
            })
            print(f"[NL提取测试] 会话查询失败: HTTP {session_response.status_code}")

        print(f"[NL提取测试] 步骤3: 调用确认导入API")
        step_timer = Timer().start()
        confirm_data = {
            "ontology_id": ontology_id,
            "merge_strategy": "skip",
            "selected": {
                "object_types": [],
                "link_types": [],
                "action_types": [],
                "rule_types": [],
                "process_types": [],
                "function_types": [],
                "indicator_types": [],
            },
            "data": extract_result.get("result", {}),
        }
        confirm_response = requests.post(
            f"{API_BASE}/api/extraction/sessions/{session_id}/confirm",
            json=confirm_data,
            timeout=60,
        )
        confirm_time = step_timer.stop()
        total_time = timer.stop()

        if confirm_response.status_code == 200:
            confirm_result = confirm_response.json()
            save_intermediate(test_run_id, "confirm_result", confirm_result)

            metrics = calculate_metrics(extract_result)
            final_result = {
                "status": "success",
                "test_run_id": test_run_id,
                "session_id": session_id,
                "extract_result": extract_result,
                "confirm_result": confirm_result,
                "total_time": total_time,
                "response_times": {
                    "extract": response_time,
                    "session_query": session_query_time,
                    "confirm": confirm_time,
                },
                "metrics": metrics,
            }
            log_step(test_run_id, "确认导入成功", confirm_result)
            save_result(test_run_id, "natural_language", final_result)
            print(f"[NL提取测试] 确认导入成功")
            print(f"[NL提取测试] 提取指标: {final_result['metrics']}")
            print(f"[NL提取测试] 总耗时: {total_time:.2f}秒")
            print_test_summary(final_result, "自然语言提取")
            return final_result
        else:
            error_result = {
                "status": "error",
                "step": "confirm",
                "http_status": confirm_response.status_code,
                "error_message": confirm_response.text[:500],
                "session_id": session_id,
                "extract_result": extract_result,
                "total_time": total_time,
                "test_run_id": test_run_id,
            }
            log_step(test_run_id, "确认导入失败", error_result)
            save_result(test_run_id, "natural_language", error_result)
            print(f"[NL提取测试] 确认导入失败: HTTP {confirm_response.status_code}")
            print(f"[NL提取测试] 错误信息: {confirm_response.text[:200]}")
            print_test_summary(error_result, "自然语言提取")
            return error_result

    except requests.exceptions.RequestException as e:
        error_result = {
            "status": "error",
            "step": "network",
            "error_message": str(e),
            "test_run_id": test_run_id,
            "total_time": timer.stop(),
        }
        log_step(test_run_id, "网络错误", error_result)
        save_result(test_run_id, "natural_language", error_result)
        print(f"[NL提取测试] 网络错误: {e}")
        print_test_summary(error_result, "自然语言提取")
        return error_result

    except Exception as e:
        error_result = {
            "status": "error",
            "step": "unexpected",
            "error_message": str(e),
            "test_run_id": test_run_id,
            "total_time": timer.stop(),
        }
        log_step(test_run_id, "未知错误", error_result)
        save_result(test_run_id, "natural_language", error_result)
        print(f"[NL提取测试] 未知错误: {e}")
        print_test_summary(error_result, "自然语言提取")
        return error_result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="自然语言本体提取测试脚本")
    parser.add_argument("--ontology-id", required=True, help="目标本体ID")
    parser.add_argument("--text", help="测试文本内容")
    parser.add_argument("--text-file", help="包含测试文本的文件路径")
    parser.add_argument("--auto-search", action="store_true", default=False, help="是否启用联网检索")
    parser.add_argument("--method", choices=["auto", "graph_rag", "light_rag"], default="auto", help="提取方法")
    parser.add_argument("--output-dir", help="测试输出目录")

    args = parser.parse_args()

    if args.text_file:
        with open(args.text_file, 'r', encoding='utf-8') as f:
            test_text = f.read().strip()
    elif args.text:
        test_text = args.text
    else:
        test_text = "我们的系统管理客户和订单。每个客户可以下多个订单，每个订单包含多个商品。商品有名称、价格和库存。客户有姓名、电话和地址。"

    if args.output_dir:
        os.environ["TEST_OUTPUT_DIR"] = args.output_dir

    run_nl_extraction_test(
        ontology_id=args.ontology_id,
        test_text=test_text,
        auto_search=args.auto_search,
        method=args.method,
    )