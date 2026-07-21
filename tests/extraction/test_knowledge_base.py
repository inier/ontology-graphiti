import sys
import os
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_config import (
    API_BASE, TEST_OUTPUT_DIR, DEFAULT_TIMEOUT,
    get_test_run_id, ensure_output_dir, log_step,
    save_result, save_input, save_metadata, save_intermediate,
    validate_required_params, calculate_metrics, print_test_summary, Timer,
)

import requests


def run_knowledge_base_extraction_test(
    ontology_id: str,
    kb_id: str,
    document_ids: list = None,
    test_run_id: str = None,
) -> Dict[str, Any]:
    test_run_id = test_run_id or get_test_run_id()
    run_dir = ensure_output_dir(test_run_id)
    timer = Timer().start()

    print(f"[知识库提取测试] 开始执行，测试ID: {test_run_id}")
    print(f"[知识库提取测试] 本体ID: {ontology_id}")
    print(f"[知识库提取测试] 知识库ID: {kb_id}")

    validation_error = validate_required_params(
        {"ontology_id": ontology_id, "kb_id": kb_id},
        ["ontology_id", "kb_id"]
    )
    if validation_error:
        error_result = {
            "status": "error",
            "step": "validation",
            "error_message": validation_error,
            "test_run_id": test_run_id,
        }
        save_result(test_run_id, "knowledge_base", error_result)
        print(f"[知识库提取测试] 参数验证失败: {validation_error}")
        return error_result

    input_data = {
        "ontology_id": ontology_id,
        "kb_id": kb_id,
        "document_ids": document_ids,
    }
    save_input(test_run_id, "knowledge_base", input_data)
    log_step(test_run_id, "输入数据已保存", {"ontology_id": ontology_id, "kb_id": kb_id})
    save_metadata(test_run_id, {"test_type": "knowledge_base", "ontology_id": ontology_id, "kb_id": kb_id})

    try:
        print(f"[知识库提取测试] 步骤1: 调用知识库提取API")
        step_timer = Timer().start()
        payload = {
            "ontology_id": ontology_id,
            "kb_id": kb_id,
        }
        if document_ids:
            payload["document_ids"] = document_ids

        extract_response = requests.post(
            f"{API_BASE}/api/extraction/extract/knowledge-base",
            json=payload,
            timeout=300,
        )
        response_time = step_timer.stop()
        log_step(test_run_id, "提取完成", {"response_time": response_time, "status_code": extract_response.status_code})

        if extract_response.status_code != 200:
            error_result = {
                "status": "error",
                "step": "extract",
                "http_status": extract_response.status_code,
                "error_message": extract_response.text[:500],
                "response_time": response_time,
                "test_run_id": test_run_id,
                "total_time": timer.stop(),
            }
            log_step(test_run_id, "提取失败", error_result)
            save_result(test_run_id, "knowledge_base", error_result)
            print(f"[知识库提取测试] 提取失败: HTTP {extract_response.status_code}")
            return error_result

        extract_result = extract_response.json()
        save_intermediate(test_run_id, "extract_result", extract_result)
        log_step(test_run_id, "提取成功", {
            "status": extract_result.get("status"),
            "session_id": extract_result.get("session_id"),
            "response_time": response_time,
        })
        print(f"[知识库提取测试] 提取成功，Session ID: {extract_result.get('session_id', 'N/A')}")

        session_id = extract_result.get("session_id", "")
        if not session_id:
            error_result = {
                "status": "error",
                "step": "session_id_missing",
                "message": "提取结果中缺少session_id",
                "test_run_id": test_run_id,
                "total_time": timer.stop(),
            }
            log_step(test_run_id, "session_id缺失", error_result)
            save_result(test_run_id, "knowledge_base", error_result)
            print(f"[知识库提取测试] 错误: 提取结果中缺少session_id")
            return error_result

        print(f"[知识库提取测试] 步骤2: 查询提取会话详情")
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
            print(f"[知识库提取测试] 会话查询成功")
        else:
            log_step(test_run_id, "会话查询失败", {
                "http_status": session_response.status_code,
                "error": session_response.text[:200],
                "response_time": session_query_time,
            })
            print(f"[知识库提取测试] 会话查询失败: HTTP {session_response.status_code}")

        print(f"[知识库提取测试] 步骤3: 调用确认导入API")
        step_timer = Timer().start()
        result_data = extract_result.get("result", extract_result)
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
            "data": {
                "object_types": result_data.get("object_types", []),
                "link_types": result_data.get("link_types", []),
                "action_types": result_data.get("action_types", []),
                "rule_types": result_data.get("rule_types", []),
                "process_types": result_data.get("process_types", []),
                "function_types": result_data.get("function_types", []),
                "indicator_types": result_data.get("indicator_types", []),
            },
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
            metrics["kb_id"] = kb_id

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
            save_result(test_run_id, "knowledge_base", final_result)
            print(f"[知识库提取测试] 确认导入成功")
            print(f"[知识库提取测试] 提取指标: {final_result['metrics']}")
            print(f"[知识库提取测试] 总耗时: {total_time:.2f}秒")
            print_test_summary(final_result, "知识库提取")
            return final_result
        else:
            error_result = {
                "status": "error",
                "step": "confirm",
                "http_status": confirm_response.status_code,
                "error_message": confirm_response.text[:500],
                "session_id": session_id,
                "test_run_id": test_run_id,
                "total_time": total_time,
            }
            log_step(test_run_id, "确认导入失败", error_result)
            save_result(test_run_id, "knowledge_base", error_result)
            print(f"[知识库提取测试] 确认导入失败: HTTP {confirm_response.status_code}")
            print_test_summary(error_result, "知识库提取")
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
        save_result(test_run_id, "knowledge_base", error_result)
        print(f"[知识库提取测试] 网络错误: {e}")
        print_test_summary(error_result, "知识库提取")
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
        save_result(test_run_id, "knowledge_base", error_result)
        print(f"[知识库提取测试] 未知错误: {e}")
        print_test_summary(error_result, "知识库提取")
        return error_result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="知识库本体提取测试脚本")
    parser.add_argument("--ontology-id", required=True, help="目标本体ID")
    parser.add_argument("--kb-id", required=True, help="知识库ID")
    parser.add_argument("--document-ids", nargs="+", help="要提取的文档ID列表")
    parser.add_argument("--output-dir", help="测试输出目录")

    args = parser.parse_args()

    if args.output_dir:
        os.environ["TEST_OUTPUT_DIR"] = args.output_dir

    run_knowledge_base_extraction_test(
        ontology_id=args.ontology_id,
        kb_id=args.kb_id,
        document_ids=args.document_ids,
    )