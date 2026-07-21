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


def run_database_extraction_test(
    ontology_id: str,
    db_type: str,
    host: str = None,
    port: int = None,
    database: str = None,
    username: str = None,
    password: str = None,
    table_filter: list = None,
    use_llm_enrichment: bool = False,
    test_run_id: str = None,
) -> Dict[str, Any]:
    test_run_id = test_run_id or get_test_run_id()
    run_dir = ensure_output_dir(test_run_id)
    timer = Timer().start()

    print(f"[数据库提取测试] 开始执行，测试ID: {test_run_id}")
    print(f"[数据库提取测试] 本体ID: {ontology_id}")
    print(f"[数据库提取测试] 数据库类型: {db_type}")

    validation_error = validate_required_params(
        {"ontology_id": ontology_id, "db_type": db_type, "database": database},
        ["ontology_id", "db_type", "database"]
    )
    if validation_error:
        error_result = {
            "status": "error",
            "step": "validation",
            "error_message": validation_error,
            "test_run_id": test_run_id,
        }
        save_result(test_run_id, "database", error_result)
        print(f"[数据库提取测试] 参数验证失败: {validation_error}")
        return error_result

    input_data = {
        "ontology_id": ontology_id,
        "db_type": db_type,
        "host": host,
        "port": port,
        "database": database,
        "username": username,
        "password": password,
        "table_filter": table_filter,
        "use_llm_enrichment": use_llm_enrichment,
    }
    save_input(test_run_id, "database", input_data)
    log_step(test_run_id, "输入数据已保存", {"ontology_id": ontology_id, "db_type": db_type})
    save_metadata(test_run_id, {"test_type": "database", "ontology_id": ontology_id, "db_type": db_type})

    try:
        print(f"[数据库提取测试] 步骤1: 测试数据库连接")
        step_timer = Timer().start()
        test_payload = {
            "db_type": db_type,
            "database": database,
        }
        if db_type != "sqlite":
            test_payload.update({
                "host": host,
                "port": port,
                "username": username,
                "password": password,
            })

        test_response = requests.post(
            f"{API_BASE}/api/extraction/test-connection",
            json=test_payload,
            timeout=30,
        )
        connection_time = step_timer.stop()
        log_step(test_run_id, "连接测试完成", {"response_time": connection_time, "status_code": test_response.status_code})

        if test_response.status_code != 200:
            error_result = {
                "status": "error",
                "step": "test_connection",
                "http_status": test_response.status_code,
                "error_message": test_response.text[:500],
                "test_run_id": test_run_id,
                "total_time": timer.stop(),
            }
            log_step(test_run_id, "连接测试失败", error_result)
            save_result(test_run_id, "database", error_result)
            print(f"[数据库提取测试] 连接测试失败: HTTP {test_response.status_code}")
            return error_result

        test_result = test_response.json()
        available_tables = test_result.get("tables", [])
        save_intermediate(test_run_id, "connection_test_result", test_result)
        log_step(test_run_id, "连接测试成功", {
            "tables_found": len(available_tables),
            "tables": available_tables[:10],
            "response_time": connection_time,
        })
        print(f"[数据库提取测试] 连接成功，发现 {len(available_tables)} 个表")

        if not available_tables:
            error_result = {
                "status": "error",
                "step": "no_tables",
                "message": "数据库中没有可用的表",
                "test_run_id": test_run_id,
                "total_time": timer.stop(),
            }
            log_step(test_run_id, "无可用表", error_result)
            save_result(test_run_id, "database", error_result)
            print(f"[数据库提取测试] 错误: 数据库中没有可用的表")
            return error_result

        extract_tables = table_filter or available_tables[:3]
        print(f"[数据库提取测试] 步骤2: 开始提取，选择表: {extract_tables}")

        step_timer = Timer().start()
        extract_payload = {
            "ontology_id": ontology_id,
            "db_type": db_type,
            "database": database,
            "table_filter": extract_tables,
            "use_llm_enrichment": use_llm_enrichment,
        }
        if db_type != "sqlite":
            extract_payload.update({
                "host": host,
                "port": port,
                "username": username,
                "password": password,
            })

        extract_response = requests.post(
            f"{API_BASE}/api/extraction/extract/database",
            json=extract_payload,
            timeout=DEFAULT_TIMEOUT,
        )
        extract_time = step_timer.stop()

        if extract_response.status_code != 200:
            error_result = {
                "status": "error",
                "step": "extract",
                "http_status": extract_response.status_code,
                "error_message": extract_response.text[:500],
                "test_run_id": test_run_id,
                "total_time": timer.stop(),
            }
            log_step(test_run_id, "提取失败", error_result)
            save_result(test_run_id, "database", error_result)
            print(f"[数据库提取测试] 提取失败: HTTP {extract_response.status_code}")
            return error_result

        extract_result = extract_response.json()
        save_intermediate(test_run_id, "extract_result", extract_result)
        log_step(test_run_id, "提取成功", {
            "status": extract_result.get("status"),
            "session_id": extract_result.get("session_id"),
            "response_time": extract_time,
        })
        print(f"[数据库提取测试] 提取成功，Session ID: {extract_result.get('session_id', 'N/A')}")

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
            save_result(test_run_id, "database", error_result)
            print(f"[数据库提取测试] 错误: 提取结果中缺少session_id")
            return error_result

        print(f"[数据库提取测试] 步骤3: 调用确认导入API")
        step_timer = Timer().start()
        confirm_data = {
            "ontology_id": ontology_id,
            "merge_strategy": "skip",
            "selected": {
                "object_types": [],
                "link_types": [],
                "action_types": [],
                "rule_types": [],
            },
            "data": {
                "object_types": extract_result.get("object_types", []),
                "link_types": extract_result.get("link_types", []),
                "action_types": extract_result.get("action_types", []),
                "rule_types": extract_result.get("rule_types", []),
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
            metrics["tables_extracted"] = len(extract_tables)

            final_result = {
                "status": "success",
                "test_run_id": test_run_id,
                "session_id": session_id,
                "extract_result": extract_result,
                "confirm_result": confirm_result,
                "total_time": total_time,
                "response_times": {
                    "connection": connection_time,
                    "extract": extract_time,
                    "confirm": confirm_time,
                },
                "metrics": metrics,
            }
            log_step(test_run_id, "确认导入成功", confirm_result)
            save_result(test_run_id, "database", final_result)
            print(f"[数据库提取测试] 确认导入成功")
            print(f"[数据库提取测试] 提取指标: {final_result['metrics']}")
            print(f"[数据库提取测试] 总耗时: {total_time:.2f}秒")
            print_test_summary(final_result, "数据库提取")
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
            save_result(test_run_id, "database", error_result)
            print(f"[数据库提取测试] 确认导入失败: HTTP {confirm_response.status_code}")
            print_test_summary(error_result, "数据库提取")
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
        save_result(test_run_id, "database", error_result)
        print(f"[数据库提取测试] 网络错误: {e}")
        print_test_summary(error_result, "数据库提取")
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
        save_result(test_run_id, "database", error_result)
        print(f"[数据库提取测试] 未知错误: {e}")
        print_test_summary(error_result, "数据库提取")
        return error_result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="数据库本体提取测试脚本")
    parser.add_argument("--ontology-id", required=True, help="目标本体ID")
    parser.add_argument("--db-type", required=True, choices=["mysql", "postgresql", "sqlite"], help="数据库类型")
    parser.add_argument("--host", help="数据库主机地址")
    parser.add_argument("--port", type=int, help="数据库端口")
    parser.add_argument("--database", required=True, help="数据库名称或SQLite文件路径")
    parser.add_argument("--username", help="数据库用户名")
    parser.add_argument("--password", help="数据库密码")
    parser.add_argument("--tables", nargs="+", help="要提取的表名列表")
    parser.add_argument("--llm-enrichment", action="store_true", default=False, help="是否启用LLM增强")
    parser.add_argument("--output-dir", help="测试输出目录")

    args = parser.parse_args()

    if args.output_dir:
        os.environ["TEST_OUTPUT_DIR"] = args.output_dir

    run_database_extraction_test(
        ontology_id=args.ontology_id,
        db_type=args.db_type,
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.username,
        password=args.password,
        table_filter=args.tables,
        use_llm_enrichment=args.llm_enrichment,
    )