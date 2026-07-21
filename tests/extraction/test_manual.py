import sys
import os
import json
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_config import (
    API_BASE, TEST_OUTPUT_DIR, DEFAULT_TIMEOUT,
    get_test_run_id, ensure_output_dir, log_step,
    save_result, save_input, save_metadata, save_intermediate,
    validate_required_params, print_test_summary, Timer,
)

import requests


def run_manual_design_test(
    ontology_id: str,
    test_data: Dict[str, Any] = None,
    test_run_id: str = None,
) -> Dict[str, Any]:
    test_run_id = test_run_id or get_test_run_id()
    run_dir = ensure_output_dir(test_run_id)
    timer = Timer().start()

    print(f"[手动设计测试] 开始执行，测试ID: {test_run_id}")
    print(f"[手动设计测试] 本体ID: {ontology_id}")

    validation_error = validate_required_params(
        {"ontology_id": ontology_id},
        ["ontology_id"]
    )
    if validation_error:
        error_result = {
            "status": "error",
            "step": "validation",
            "error_message": validation_error,
            "test_run_id": test_run_id,
        }
        save_result(test_run_id, "manual", error_result)
        print(f"[手动设计测试] 参数验证失败: {validation_error}")
        return error_result

    if test_data is None:
        test_data = {
            "object_types": [
                {
                    "name": "customer",
                    "display_name": "客户",
                    "description": "系统中的客户实体",
                    "classification_level": "TS",
                    "properties": [
                        {"name": "name", "data_type": "string", "required": True},
                        {"name": "phone", "data_type": "string", "required": False},
                        {"name": "email", "data_type": "string", "required": False},
                    ],
                    "relations": [],
                },
                {
                    "name": "order",
                    "display_name": "订单",
                    "description": "客户提交的订单",
                    "classification_level": "TS",
                    "properties": [
                        {"name": "order_no", "data_type": "string", "required": True},
                        {"name": "total_amount", "data_type": "float", "required": True},
                        {"name": "status", "data_type": "string", "required": True},
                    ],
                    "relations": [],
                },
            ],
            "link_types": [
                {
                    "name": "places_order",
                    "display_name": "下订单",
                    "description": "客户下单关系",
                    "source_type": "customer",
                    "target_type": "order",
                    "cardinality": "1:N",
                    "link_type": "association",
                },
            ],
            "action_types": [
                {
                    "name": "create_order",
                    "display_name": "创建订单",
                    "description": "创建新订单的操作",
                },
            ],
        }

    save_input(test_run_id, "manual", {"ontology_id": ontology_id, "test_data": test_data})
    log_step(test_run_id, "输入数据已保存", {"ontology_id": ontology_id, "object_types_count": len(test_data.get("object_types", []))})
    save_metadata(test_run_id, {"test_type": "manual", "ontology_id": ontology_id})

    all_results = []
    created_ids = []

    try:
        print(f"[手动设计测试] 步骤1: 创建对象类型")
        object_types = test_data.get("object_types", [])
        for obj_type in object_types:
            obj_start = Timer().start()
            response = requests.post(
                f"{API_BASE}/api/ontologies/{ontology_id}/object-types",
                json=obj_type,
                timeout=30,
            )
            obj_time = obj_start.stop()

            if response.status_code == 200:
                result = response.json()
                type_id = result.get("type_id") or result.get("id")
                created_ids.append({"category": "object_types", "id": type_id})
                log_step(test_run_id, f"创建对象类型成功: {obj_type['name']}", {
                    "status": "success",
                    "type_id": type_id,
                    "response_time": obj_time,
                })
                all_results.append({
                    "category": "object_types",
                    "name": obj_type["name"],
                    "status": "success",
                    "type_id": type_id,
                    "response_time": obj_time,
                })
                print(f"[手动设计测试] 创建对象类型成功: {obj_type['name']}")
            else:
                log_step(test_run_id, f"创建对象类型失败: {obj_type['name']}", {
                    "status": "error",
                    "http_status": response.status_code,
                    "error": response.text[:200],
                })
                all_results.append({
                    "category": "object_types",
                    "name": obj_type["name"],
                    "status": "error",
                    "http_status": response.status_code,
                    "error_message": response.text[:200],
                })
                print(f"[手动设计测试] 创建对象类型失败: {obj_type['name']} - HTTP {response.status_code}")

        print(f"[手动设计测试] 步骤2: 创建关系类型")
        link_types = test_data.get("link_types", [])
        for link_type in link_types:
            link_start = Timer().start()
            response = requests.post(
                f"{API_BASE}/api/ontologies/{ontology_id}/link-types",
                json=link_type,
                timeout=30,
            )
            link_time = link_start.stop()

            if response.status_code == 200:
                result = response.json()
                type_id = result.get("type_id") or result.get("id")
                created_ids.append({"category": "link_types", "id": type_id})
                log_step(test_run_id, f"创建关系类型成功: {link_type['name']}", {
                    "status": "success",
                    "type_id": type_id,
                    "response_time": link_time,
                })
                all_results.append({
                    "category": "link_types",
                    "name": link_type["name"],
                    "status": "success",
                    "type_id": type_id,
                    "response_time": link_time,
                })
                print(f"[手动设计测试] 创建关系类型成功: {link_type['name']}")
            else:
                log_step(test_run_id, f"创建关系类型失败: {link_type['name']}", {
                    "status": "error",
                    "http_status": response.status_code,
                    "error": response.text[:200],
                })
                all_results.append({
                    "category": "link_types",
                    "name": link_type["name"],
                    "status": "error",
                    "http_status": response.status_code,
                    "error_message": response.text[:200],
                })
                print(f"[手动设计测试] 创建关系类型失败: {link_type['name']} - HTTP {response.status_code}")

        print(f"[手动设计测试] 步骤3: 创建动作类型")
        action_types = test_data.get("action_types", [])
        for action_type in action_types:
            action_start = Timer().start()
            response = requests.post(
                f"{API_BASE}/api/ontologies/{ontology_id}/action-types",
                json=action_type,
                timeout=30,
            )
            action_time = action_start.stop()

            if response.status_code == 200:
                result = response.json()
                type_id = result.get("type_id") or result.get("id")
                created_ids.append({"category": "action_types", "id": type_id})
                log_step(test_run_id, f"创建动作类型成功: {action_type['name']}", {
                    "status": "success",
                    "type_id": type_id,
                    "response_time": action_time,
                })
                all_results.append({
                    "category": "action_types",
                    "name": action_type["name"],
                    "status": "success",
                    "type_id": type_id,
                    "response_time": action_time,
                })
                print(f"[手动设计测试] 创建动作类型成功: {action_type['name']}")
            else:
                log_step(test_run_id, f"创建动作类型失败: {action_type['name']}", {
                    "status": "error",
                    "http_status": response.status_code,
                    "error": response.text[:200],
                })
                all_results.append({
                    "category": "action_types",
                    "name": action_type["name"],
                    "status": "error",
                    "http_status": response.status_code,
                    "error_message": response.text[:200],
                })
                print(f"[手动设计测试] 创建动作类型失败: {action_type['name']} - HTTP {response.status_code}")

        print(f"[手动设计测试] 步骤4: 验证创建的类型")
        verify_start = Timer().start()
        verify_response = requests.get(
            f"{API_BASE}/api/ontologies/{ontology_id}/object-types",
            timeout=30,
        )
        verify_time = verify_start.stop()

        if verify_response.status_code == 200:
            obj_types = verify_response.json()
            save_intermediate(test_run_id, "object_types_list", obj_types)
            log_step(test_run_id, "验证对象类型列表", {
                "count": len(obj_types) if isinstance(obj_types, list) else 0,
                "response_time": verify_time,
            })
            print(f"[手动设计测试] 验证成功，当前对象类型数量: {len(obj_types) if isinstance(obj_types, list) else 0}")
        else:
            log_step(test_run_id, "验证失败", {
                "http_status": verify_response.status_code,
                "error": verify_response.text[:200],
            })
            print(f"[手动设计测试] 验证失败: HTTP {verify_response.status_code}")

        total_time = timer.stop()

        success_count = sum(1 for r in all_results if r["status"] == "success")
        error_count = sum(1 for r in all_results if r["status"] == "error")

        final_result = {
            "status": "success" if error_count == 0 else "partial",
            "test_run_id": test_run_id,
            "ontology_id": ontology_id,
            "all_results": all_results,
            "created_ids": created_ids,
            "total_time": total_time,
            "metrics": {
                "object_types_created": len([r for r in all_results if r["category"] == "object_types" and r["status"] == "success"]),
                "link_types_created": len([r for r in all_results if r["category"] == "link_types" and r["status"] == "success"]),
                "action_types_created": len([r for r in all_results if r["category"] == "action_types" and r["status"] == "success"]),
                "total_created": success_count,
                "total_errors": error_count,
            },
        }
        log_step(test_run_id, "手动设计测试完成", final_result)
        save_result(test_run_id, "manual", final_result)

        print(f"[手动设计测试] 测试完成")
        print(f"[手动设计测试] 成功创建: {success_count} 个类型")
        print(f"[手动设计测试] 创建失败: {error_count} 个类型")
        print(f"[手动设计测试] 总耗时: {total_time:.2f}秒")
        print_test_summary(final_result, "手动设计")
        return final_result

    except requests.exceptions.RequestException as e:
        error_result = {
            "status": "error",
            "step": "network",
            "error_message": str(e),
            "test_run_id": test_run_id,
            "total_time": timer.stop(),
            "all_results": all_results,
        }
        log_step(test_run_id, "网络错误", error_result)
        save_result(test_run_id, "manual", error_result)
        print(f"[手动设计测试] 网络错误: {e}")
        print_test_summary(error_result, "手动设计")
        return error_result

    except Exception as e:
        error_result = {
            "status": "error",
            "step": "unexpected",
            "error_message": str(e),
            "test_run_id": test_run_id,
            "total_time": timer.stop(),
            "all_results": all_results,
        }
        log_step(test_run_id, "未知错误", error_result)
        save_result(test_run_id, "manual", error_result)
        print(f"[手动设计测试] 未知错误: {e}")
        print_test_summary(error_result, "手动设计")
        return error_result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="手动本体设计测试脚本")
    parser.add_argument("--ontology-id", required=True, help="目标本体ID")
    parser.add_argument("--data-file", help="包含测试数据的JSON文件路径")
    parser.add_argument("--output-dir", help="测试输出目录")

    args = parser.parse_args()

    test_data = None
    if args.data_file:
        with open(args.data_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)

    if args.output_dir:
        os.environ["TEST_OUTPUT_DIR"] = args.output_dir

    run_manual_design_test(
        ontology_id=args.ontology_id,
        test_data=test_data,
    )