#!/usr/bin/env python3
"""构建汽车B2B2C会员电商本体到 ODAP 平台

基于文档: B2B2C汽车会员电商本体研究_e5e874.docx

本脚本:
  1. 登录 ODAP 平台
  2. 创建/获取工作空间与场景
  3. 创建/获取知识库 kb_2260b4dcbc93
  4. 创建本体 (Ontology)
  5. 创建 19 个对象类型 (ObjectType)
  6. 创建 28 个关系类型 (LinkType)
  7. 创建 25 个动作类型 (ActionType)
  8. 创建 6 个业务流程类型 (ProcessType)
  9. 创建 6 个规则类型 (RuleType)
 10. 提交 Schema 版本 & 验证一致性

运行:
  cd E:\\DEMO\\AI\\ontology-graphiti
  python scripts/build_ecommerce_ontology.py
  python scripts/build_ecommerce_ontology.py --validate-only  # 仅验证
"""
import sys, os, time, json, logging, argparse

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_ecommerce")

# ============================================================
# 平台 API 薄封装
# ============================================================

class PlatformAPI:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.token: str = ""
        self.s = requests.Session()

    def login(self, username: str = "admin", password: str = "admin123"):
        r = self.s.post(f"{self.base}/api/auth/login",
                        json={"username": username, "password": password}, timeout=10)
        r.raise_for_status()
        data = r.json()
        self.token = data.get("access_token") or data.get("token", "")
        self.s.headers.update({"Authorization": f"Bearer {self.token}"})
        log.info("登录成功: %s", username)

    def _call(self, method: str, path: str, **kw):
        r = self.s.request(method, f"{self.base}{path}", timeout=15, **kw)
        if r.status_code >= 400:
            log.warning("%s %s -> %d %s", method, path, r.status_code, r.text[:200])
        return r

    def health(self) -> dict:
        return self._call("GET", "/health").json()

    # --- workspace ---
    def list_workspaces(self) -> list:
        r = self._call("GET", "/api/workspaces")
        data = r.json()
        if isinstance(data, dict):
            return data.get("workspaces", data.get("items", []))
        return data if isinstance(data, list) else []

    def find_workspace(self, name: str) -> dict | None:
        for ws in self.list_workspaces():
            if isinstance(ws, dict) and ws.get("name") == name:
                return ws
        return None

    def create_workspace(self, name: str, description: str = "") -> dict:
        r = self._call("POST", "/api/workspaces",
                       json={"name": name, "description": description})
        r.raise_for_status()
        return r.json()

    def get_or_create_workspace(self, name: str, desc: str = "") -> dict:
        ws = self.find_workspace(name)
        if ws: return ws
        return self.create_workspace(name, desc)

    # --- scenario ---
    def list_scenarios(self, ws_id: str) -> list:
        r = self._call("GET", f"/api/workspaces/{ws_id}/scenarios")
        data = r.json()
        if isinstance(data, dict):
            return data.get("scenarios", data.get("items", []))
        return data if isinstance(data, list) else []

    def get_or_create_scenario(self, ws_id: str, name: str, desc: str = "") -> dict:
        for sc in self.list_scenarios(ws_id):
            if isinstance(sc, dict) and sc.get("name") == name:
                return sc
        r = self._call("POST", f"/api/workspaces/{ws_id}/scenarios",
                       json={"name": name, "description": desc})
        r.raise_for_status()
        return r.json()

    # --- knowledge base ---
    def list_kbs(self) -> list:
        r = self._call("GET", "/api/knowledge-bases")
        data = r.json()
        if isinstance(data, list): return data
        if isinstance(data, dict): return data.get("items", data.get("knowledge_bases", []))
        return []

    def get_or_create_kb(self, name: str, kb_id: str = None, desc: str = "") -> dict:
        for kb in self.list_kbs():
            if isinstance(kb, dict) and (kb.get("kb_id") == kb_id or kb.get("name") == name):
                return kb
        r = self._call("POST", "/api/knowledge-bases", json={"name": name, "description": desc})
        if r.status_code == 201 or r.status_code == 200:
            return r.json()
        # 尝试用 raw dict 创建
        r2 = self._call("POST", "/api/knowledge-bases", json={"name": name, "description": desc,
                                                                "kb_id": kb_id})
        if r2.status_code < 400:
            return r2.json()
        # 再次尝试 list 获取
        for kb in self.list_kbs():
            if isinstance(kb, dict) and kb.get("name") == name:
                return kb
        raise RuntimeError(f"无法创建知识库: {name}")

    # --- ontology ---
    def list_ontologies(self, workspace_id: str = None) -> list:
        path = "/api/ontologies"
        if workspace_id: path += f"?workspace_id={workspace_id}"
        r = self._call("GET", path)
        data = r.json()
        if isinstance(data, list): return data
        if isinstance(data, dict):
            return data.get("ontologies", data.get("items", []))
        return []

    def create_ontology(self, name: str, description: str = "",
                        workspace_id: str = "", scenario_id: str = None) -> dict:
        payload = {"name": name, "description": description, "workspace_id": workspace_id}
        if scenario_id: payload["scenario_id"] = scenario_id
        r = self._call("POST", "/api/ontologies", json=payload)
        r.raise_for_status()
        return r.json()

    def get_or_create_ontology(self, name: str, workspace_id: str = "",
                               scenario_id: str = None, description: str = "") -> dict:
        for o in self.list_ontologies(workspace_id):
            if isinstance(o, dict) and o.get("name") == name:
                return o
        return self.create_ontology(name, description, workspace_id, scenario_id)

    # --- object type ---
    def list_object_types(self, ontology_id: str) -> list:
        r = self._call("GET", f"/api/ontologies/{ontology_id}/object-types")
        data = r.json()
        if isinstance(data, list): return data
        return data.get("object_types", data.get("items", []))

    def create_object_type(self, ontology_id: str, data: dict) -> dict:
        r = self._call("POST", f"/api/ontologies/{ontology_id}/object-types", json=data)
        if r.status_code >= 400:
            log.error("创建 ObjectType 失败: %s -> %s", data.get("name"), r.text[:300])
            return {}
        return r.json()

    # --- link type ---
    def list_link_types(self, ontology_id: str) -> list:
        r = self._call("GET", f"/api/ontologies/{ontology_id}/link-types")
        data = r.json()
        if isinstance(data, list): return data
        return data.get("link_types", data.get("items", []))

    def create_link_type(self, ontology_id: str, data: dict) -> dict:
        r = self._call("POST", f"/api/ontologies/{ontology_id}/link-types", json=data)
        if r.status_code >= 400:
            log.error("创建 LinkType 失败: %s -> %s", data.get("name"), r.text[:300])
            return {}
        return r.json()

    # --- action type ---
    def list_action_types(self, ontology_id: str) -> list:
        r = self._call("GET", f"/api/ontologies/{ontology_id}/action-types")
        data = r.json()
        if isinstance(data, list): return data
        return data.get("action_types", data.get("items", []))

    def create_action_type(self, ontology_id: str, data: dict) -> dict:
        r = self._call("POST", f"/api/ontologies/{ontology_id}/action-types", json=data)
        if r.status_code >= 400:
            log.error("创建 ActionType 失败: %s -> %s", data.get("name"), r.text[:300])
            return {}
        return r.json()

    # --- process type ---
    def list_process_types(self, ontology_id: str) -> list:
        r = self._call("GET", f"/api/ontologies/{ontology_id}/process-types")
        data = r.json()
        if isinstance(data, list): return data
        return data.get("process_types", data.get("items", []))

    def create_process_type(self, ontology_id: str, data: dict) -> dict:
        r = self._call("POST", f"/api/ontologies/{ontology_id}/process-types", json=data)
        if r.status_code >= 400:
            log.error("创建 ProcessType 失败: %s -> %s", data.get("name"), r.text[:300])
            return {}
        return r.json()

    # --- rule type ---
    def list_rule_types(self, ontology_id: str) -> list:
        r = self._call("GET", f"/api/ontologies/{ontology_id}/rule-types")
        data = r.json()
        if isinstance(data, list): return data
        return data.get("rule_types", data.get("items", []))

    def create_rule_type(self, ontology_id: str, data: dict) -> dict:
        r = self._call("POST", f"/api/ontologies/{ontology_id}/rule-types", json=data)
        if r.status_code >= 400:
            log.error("创建 RuleType 失败: %s -> %s", data.get("name"), r.text[:300])
            return {}
        return r.json()

    # --- schema version ---
    def commit_schema(self, ontology_id: str, changelog: str = "") -> dict:
        r = self._call("POST", f"/api/ontologies/{ontology_id}/commit",
                       json={"changelog": changelog})
        r.raise_for_status()
        return r.json()

    def list_versions(self, ontology_id: str) -> list:
        r = self._call("GET", f"/api/ontologies/{ontology_id}/versions")
        data = r.json()
        return data.get("versions", data.get("items", []))

    def get_graph(self, ontology_id: str) -> dict:
        return self._call("GET", f"/api/ontologies/{ontology_id}/graph").json()


# ============================================================
# 本体模型定义
# ============================================================

# ---- 对象类型 (ObjectType) ----

def _prop(name, data_type="string", description="", required=False):
    return {"name": name, "data_type": data_type,
            "description": description, "required": required}

OBJECT_TYPES = [
    {
        "name": "Member",
        "display_name": "会员",
        "description": "C端会员/车主/潜在客户，平台的核心用户群体",
        "icon": "user",
        "color": "#4A90D9",
        "classification_level": "C",
        "properties": [
            _prop("member_no", "string", "会员编号", True),
            _prop("real_name", "string", "真实姓名"),
            _prop("nickname", "string", "昵称"),
            _prop("phone", "string", "手机号（加密存储）", True),
            _prop("email", "string", "邮箱（加密存储）"),
            _prop("id_card", "string", "身份证号（加密存储）"),
            _prop("gender", "string", "性别"),
            _prop("birthday", "date", "出生日期"),
            _prop("city", "string", "所在城市"),
            _prop("register_time", "datetime", "注册时间"),
            _prop("last_login_time", "datetime", "最后登录时间"),
            _prop("status", "string", "状态: active/frozen/cancelled"),
            _prop("total_growth", "integer", "累计成长值"),
            _prop("total_points", "integer", "当前积分余额"),
            _prop("total_consumption", "float", "累计消费金额（元）"),
            _prop("referrer_id", "string", "推荐人会员ID"),
            _prop("device_fingerprint", "string", "设备指纹（防欺诈）"),
        ],
        "primary_key": ["member_no"],
    },
    {
        "name": "Vehicle",
        "display_name": "车辆",
        "description": "会员拥有的车辆信息，记录车辆档案与状态",
        "icon": "car",
        "color": "#E67E22",
        "classification_level": "U",
        "properties": [
            _prop("vin", "string", "车辆识别码（VIN）", True),
            _prop("license_plate", "string", "车牌号", True),
            _prop("brand", "string", "品牌"),
            _prop("model", "string", "车型"),
            _prop("year", "integer", "年款"),
            _prop("color", "string", "车身颜色"),
            _prop("engine_no", "string", "发动机号"),
            _prop("mileage", "integer", "当前里程（公里）"),
            _prop("battery_status", "json", "电池状态（新能源车）"),
            _prop("purchase_date", "date", "购车日期"),
            _prop("purchase_dealer_id", "string", "购车经销商ID"),
            _prop("insurance_expiry", "date", "保险到期日"),
            _prop("last_maintenance_date", "date", "最近保养日期"),
            _prop("status", "string", "状态: active/sold/scrapped"),
        ],
        "primary_key": ["vin"],
    },
    {
        "name": "Order",
        "display_name": "订单",
        "description": "交易订单，记录会员的每一次购买行为",
        "icon": "shopping-cart",
        "color": "#2ECC71",
        "classification_level": "C",
        "properties": [
            _prop("order_no", "string", "订单编号", True),
            _prop("order_type", "string", "订单类型: product/service/appointment/vehicle_booking"),
            _prop("total_amount", "float", "订单金额"),
            _prop("discount_amount", "float", "优惠金额"),
            _prop("points_used", "integer", "使用积分"),
            _prop("points_deduct_amount", "float", "积分抵扣金额"),
            _prop("actual_amount", "float", "实付金额"),
            _prop("status", "string", "状态: pending/paid/shipping/delivered/completed/cancelled/refunded"),
            _prop("create_time", "datetime", "创建时间"),
            _prop("pay_time", "datetime", "支付时间"),
            _prop("deliver_time", "datetime", "发货/服务完成时间"),
            _prop("complete_time", "datetime", "完成时间"),
            _prop("cancel_reason", "string", "取消原因"),
            _prop("source", "string", "来源渠道: app/miniprogram/h5/offline"),
        ],
        "primary_key": ["order_no"],
    },
    {
        "name": "Product",
        "display_name": "商品",
        "description": "商品/服务/配件等可交易产品",
        "icon": "package",
        "color": "#9B59B6",
        "classification_level": "U",
        "properties": [
            _prop("spu_code", "string", "SPU编码", True),
            _prop("sku_code", "string", "SKU编码", True),
            _prop("name", "string", "商品名称"),
            _prop("category", "string", "品类: new_vehicle/parts/accessory/insurance/maintenance/charging"),
            _prop("brand", "string", "品牌"),
            _prop("price", "float", "标准价格"),
            _prop("member_price", "float", "会员价"),
            _prop("cost_price", "float", "成本价"),
            _prop("unit", "string", "单位"),
            _prop("stock", "integer", "库存数量"),
            _prop("min_order_qty", "integer", "最小起订量"),
            _prop("status", "string", "状态: draft/published/offline"),
            _prop("description", "string", "商品描述"),
            _prop("images", "array", "商品图片URL列表"),
            _prop("specifications", "json", "规格参数"),
            _prop("warranty_period", "integer", "质保期（月）"),
        ],
        "primary_key": ["sku_code"],
    },
    {
        "name": "Dealer",
        "display_name": "经销商",
        "description": "B端经销商，线下履约触点，负责库存管理、订单履约、售后服务",
        "icon": "store",
        "color": "#1ABC9C",
        "classification_level": "C",
        "properties": [
            _prop("dealer_code", "string", "经销商编码", True),
            _prop("name", "string", "经销商名称", True),
            _prop("dealer_type", "string", "类型: authorized/direct/partner"),
            _prop("business_license", "string", "营业执照编号"),
            _prop("legal_person", "string", "法人代表"),
            _prop("contact_name", "string", "联系人"),
            _prop("contact_phone", "string", "联系电话"),
            _prop("province", "string", "省份"),
            _prop("city", "string", "城市"),
            _prop("district", "string", "区县"),
            _prop("address", "string", "详细地址"),
            _prop("longitude", "float", "经度"),
            _prop("latitude", "float", "纬度"),
            _prop("service_radius", "integer", "服务半径（公里）"),
            _prop("qualification_docs", "array", "资质文件URL列表"),
            _prop("rating_nps", "float", "NPS评分"),
            _prop("rating_star", "float", "星级评价"),
            _prop("order_fulfill_rate", "float", "履约准时率"),
            _prop("status", "string", "状态: pending/approved/suspended/terminated"),
            _prop("join_time", "datetime", "入驻时间"),
        ],
        "primary_key": ["dealer_code"],
    },
    {
        "name": "ServiceProvider",
        "display_name": "服务商",
        "description": "B端第三方服务商，提供配件、充电桩、保险、保养维修等产品或服务",
        "icon": "tool",
        "color": "#3498DB",
        "classification_level": "C",
        "properties": [
            _prop("provider_code", "string", "服务商编码", True),
            _prop("name", "string", "服务商名称", True),
            _prop("service_type", "string", "服务类型: parts/charging/insurance/maintenance/recycling"),
            _prop("business_license", "string", "营业执照编号"),
            _prop("legal_person", "string", "法人代表"),
            _prop("contact_name", "string", "联系人"),
            _prop("contact_phone", "string", "联系电话"),
            _prop("city", "string", "城市"),
            _prop("address", "string", "地址"),
            _prop("certifications", "array", "行业资质认证列表（如CQC认证）"),
            _prop("qualification_docs", "array", "资质文件URL列表"),
            _prop("technician_count", "integer", "技术人员数量"),
            _prop("equipment_list", "json", "服务设备清单"),
            _prop("rating_nps", "float", "NPS评分"),
            _prop("rating_star", "float", "星级评价"),
            _prop("response_speed", "float", "服务响应速度（分钟）"),
            _prop("problem_resolve_rate", "float", "问题解决率"),
            _prop("status", "string", "状态: pending/approved/suspended/terminated"),
            _prop("join_time", "datetime", "入驻时间"),
        ],
        "primary_key": ["provider_code"],
    },
    {
        "name": "Platform",
        "display_name": "平台方",
        "description": "平台运营方/车企，规则制定者，会员资产持有者",
        "icon": "building",
        "color": "#E74C3C",
        "classification_level": "U",
        "properties": [
            _prop("platform_code", "string", "平台编码", True),
            _prop("name", "string", "平台名称", True),
            _prop("company_name", "string", "公司全称"),
            _prop("contact_email", "string", "联系邮箱"),
            _prop("contact_phone", "string", "联系电话"),
            _prop("api_gateway_url", "string", "API网关地址"),
            _prop("status", "string", "状态: active/maintenance/suspended"),
            _prop("commission_rate", "float", "默认平台佣金率"),
            _prop("settlement_cycle", "string", "结算周期: T+1/T+7"),
        ],
        "primary_key": ["platform_code"],
    },
    {
        "name": "MembershipLevel",
        "display_name": "会员等级",
        "description": "会员等级定义，包含5级：普通/银卡/金卡/钻石/黑金",
        "icon": "trophy",
        "color": "#F39C12",
        "classification_level": "U",
        "properties": [
            _prop("level_code", "string", "等级编码: normal/silver/gold/diamond/black_gold", True),
            _prop("level_name", "string", "等级名称", True),
            _prop("level_order", "integer", "等级排序"),
            _prop("min_growth", "integer", "最低成长值要求"),
            _prop("max_growth", "integer", "最高成长值要求"),
            _prop("upgrade_cycle_months", "integer", "升/降级周期（月）"),
            _prop("degrade_protection_months", "integer", "降级保护期（月）"),
            _prop("discount_rate", "float", "商品折扣率（如0.88=88折）"),
            _prop("labor_discount_rate", "float", "工时费折扣率"),
            _prop("free_services_per_year", "integer", "每年免费服务次数"),
            _prop("icon_url", "string", "等级图标URL"),
            _prop("description", "string", "等级说明"),
        ],
        "primary_key": ["level_code"],
    },
    {
        "name": "GrowthRecord",
        "display_name": "成长值记录",
        "description": "会员成长值变动明细记录，支持区块链审计",
        "icon": "trending-up",
        "color": "#27AE60",
        "classification_level": "C",
        "properties": [
            _prop("record_id", "string", "记录ID", True),
            _prop("change_type", "string", "变动类型: earn/expire/adjust/deduct"),
            _prop("change_amount", "integer", "变动数值"),
            _prop("balance_before", "integer", "变动前余额"),
            _prop("balance_after", "integer", "变动后余额"),
            _prop("source_type", "string", "来源: order/activity/sign/referral/system"),
            _prop("source_id", "string", "来源ID"),
            _prop("blockchain_tx_hash", "string", "区块链交易哈希"),
            _prop("remark", "string", "备注"),
            _prop("create_time", "datetime", "创建时间"),
        ],
        "primary_key": ["record_id"],
    },
    {
        "name": "PointsTransaction",
        "display_name": "积分交易记录",
        "description": "会员积分获取与消耗的完整记录，支持区块链审计",
        "icon": "coins",
        "color": "#F1C40F",
        "classification_level": "C",
        "properties": [
            _prop("tx_id", "string", "交易ID", True),
            _prop("tx_type", "string", "交易类型: earn/consume/expire/refund/adjust"),
            _prop("tx_amount", "integer", "积分数量"),
            _prop("balance_before", "integer", "变动前余额"),
            _prop("balance_after", "integer", "变动后余额"),
            _prop("earn_source", "string", "获取来源: order/task/activity/referral"),
            _prop("consume_scene", "string", "消耗场景: exchange/deduct/coupon/gift"),
            _prop("expiry_date", "date", "过期日期"),
            _prop("blockchain_tx_hash", "string", "区块链交易哈希"),
            _prop("rate", "float", "积分汇率（跨品牌兑换时）"),
            _prop("remark", "string", "备注"),
            _prop("create_time", "datetime", "交易时间"),
        ],
        "primary_key": ["tx_id"],
    },
    {
        "name": "PointsAccount",
        "display_name": "积分账户",
        "description": "按品牌划分的独立积分账户，支持跨品牌积分汇率互通",
        "icon": "wallet",
        "color": "#E67E22",
        "classification_level": "C",
        "properties": [
            _prop("account_id", "string", "账户ID", True),
            _prop("account_name", "string", "账户名称（如品牌名）"),
            _prop("brand", "string", "所属品牌"),
            _prop("balance", "integer", "积分余额"),
            _prop("total_earned", "integer", "累计获取积分"),
            _prop("total_consumed", "integer", "累计消耗积分"),
            _prop("cross_brand_rate", "float", "跨品牌汇率"),
            _prop("status", "string", "状态: active/frozen"),
            _prop("create_time", "datetime", "创建时间"),
        ],
        "primary_key": ["account_id"],
    },
    {
        "name": "Benefit",
        "display_name": "权益",
        "description": "会员权益定义，包括基础权益、等级权益、付费权益、活动权益",
        "icon": "shield",
        "color": "#8E44AD",
        "classification_level": "U",
        "properties": [
            _prop("benefit_code", "string", "权益编码", True),
            _prop("benefit_name", "string", "权益名称", True),
            _prop("benefit_type", "string", "类型: basic/level/paid/event"),
            _prop("scope", "string", "适用范围: global/brand_specific"),
            _prop("content", "string", "权益内容描述"),
            _prop("value_amount", "float", "权益价值金额"),
            _prop("usage_limit_count", "integer", "使用次数限制"),
            _prop("valid_period_days", "integer", "有效天数"),
            _prop("requires_verification", "boolean", "是否需要核销"),
            _prop("auto_grant", "boolean", "是否自动发放"),
            _prop("status", "string", "状态: active/inactive"),
        ],
        "primary_key": ["benefit_code"],
    },
    {
        "name": "Coupon",
        "display_name": "优惠券",
        "description": "平台发放的代金券/折扣券",
        "icon": "ticket",
        "color": "#E91E63",
        "classification_level": "U",
        "properties": [
            _prop("coupon_code", "string", "优惠券编码", True),
            _prop("coupon_name", "string", "优惠券名称", True),
            _prop("coupon_type", "string", "类型: cash/discount/exchange"),
            _prop("face_value", "float", "面值（元）"),
            _prop("discount_rate", "float", "折扣率"),
            _prop("min_order_amount", "float", "最低订单金额"),
            _prop("applicable_categories", "array", "适用品类"),
            _prop("total_quantity", "integer", "发行总量"),
            _prop("remain_quantity", "integer", "剩余数量"),
            _prop("per_user_limit", "integer", "每人限领"),
            _prop("valid_start", "datetime", "有效期起始"),
            _prop("valid_end", "datetime", "有效期截止"),
            _prop("status", "string", "状态: active/expired/exhausted"),
            _prop("issue_channel", "string", "发放渠道: auto/activity/manual"),
        ],
        "primary_key": ["coupon_code"],
    },
    {
        "name": "Inventory",
        "display_name": "库存记录",
        "description": "B端经销商/服务商的库存管理记录",
        "icon": "archive",
        "color": "#795548",
        "classification_level": "C",
        "properties": [
            _prop("inventory_id", "string", "库存记录ID", True),
            _prop("owner_type", "string", "所有者类型: dealer/service_provider"),
            _prop("owner_id", "string", "所有者ID"),
            _prop("quantity", "integer", "库存数量"),
            _prop("safe_threshold", "integer", "安全库存阈值"),
            _prop("alert_threshold", "integer", "预警阈值"),
            _prop("warehouse_location", "string", "仓库位置"),
            _prop("price", "float", "库存单价"),
            _prop("last_sync_time", "datetime", "最后同步时间"),
            _prop("status", "string", "状态: normal/low_stock/out_of_stock"),
        ],
        "primary_key": ["inventory_id"],
    },
    {
        "name": "SettlementRecord",
        "display_name": "结算记录",
        "description": "平台与B端的分账与结算记录",
        "icon": "calculator",
        "color": "#607D8B",
        "classification_level": "C",
        "properties": [
            _prop("settlement_id", "string", "结算记录ID", True),
            _prop("settlement_cycle", "string", "结算周期: T+1/T+7"),
            _prop("settlement_type", "string", "类型: normal_split/refund_split"),
            _prop("platform_share", "float", "平台分账金额"),
            _prop("dealer_share", "float", "经销商分账金额"),
            _prop("service_provider_share", "float", "服务商分账金额"),
            _prop("split_ratio", "json", "分账比例详情"),
            _prop("status", "string", "状态: pending/settled/disputed"),
            _prop("settle_time", "datetime", "结算时间"),
            _prop("bill_url", "string", "对账单URL"),
            _prop("remark", "string", "备注"),
        ],
        "primary_key": ["settlement_id"],
    },
    {
        "name": "Invoice",
        "display_name": "发票",
        "description": "交易发票记录",
        "icon": "file-text",
        "color": "#555",
        "classification_level": "C",
        "properties": [
            _prop("invoice_no", "string", "发票号码", True),
            _prop("invoice_type", "string", "类型: electronic/paper/special_vat"),
            _prop("invoice_amount", "float", "发票金额"),
            _prop("tax_amount", "float", "税额"),
            _prop("tax_rate", "float", "税率"),
            _prop("buyer_name", "string", "购买方名称"),
            _prop("buyer_tax_no", "string", "购买方税号"),
            _prop("seller_name", "string", "销售方名称"),
            _prop("seller_tax_no", "string", "销售方税号"),
            _prop("status", "string", "状态: pending/issued/voided"),
            _prop("issue_time", "datetime", "开票时间"),
            _prop("file_url", "string", "发票文件URL"),
        ],
        "primary_key": ["invoice_no"],
    },
    {
        "name": "ServiceAppointment",
        "display_name": "服务预约",
        "description": "会员的保养/维修/充电等服务预约记录",
        "icon": "calendar",
        "color": "#00BCD4",
        "classification_level": "U",
        "properties": [
            _prop("appointment_id", "string", "预约ID", True),
            _prop("service_type", "string", "服务类型: maintenance/repair/charging/insurance_inspection"),
            _prop("appointment_time", "datetime", "预约时间"),
            _prop("service_location", "string", "服务地点"),
            _prop("service_notes", "string", "服务备注/需求描述"),
            _prop("status", "string", "状态: booked/confirmed/in_progress/completed/cancelled"),
            _prop("verification_code", "string", "核销码"),
            _prop("create_time", "datetime", "预约创建时间"),
        ],
        "primary_key": ["appointment_id"],
    },
    {
        "name": "Evaluation",
        "display_name": "评价",
        "description": "会员对B端服务商/经销商/商品的评价记录",
        "icon": "star",
        "color": "#FF9800",
        "classification_level": "U",
        "properties": [
            _prop("evaluation_id", "string", "评价ID", True),
            _prop("target_type", "string", "评价对象类型: dealer/service_provider/product"),
            _prop("target_id", "string", "评价对象ID"),
            _prop("star_rating", "integer", "星级评分（1-5）"),
            _prop("content", "string", "评价内容"),
            _prop("images", "array", "评价图片URL列表"),
            _prop("tags", "array", "标签列表"),
            _prop("is_anonymous", "boolean", "是否匿名"),
            _prop("status", "string", "状态: pending/approved/rejected"),
            _prop("create_time", "datetime", "评价时间"),
        ],
        "primary_key": ["evaluation_id"],
    },
    {
        "name": "Campaign",
        "display_name": "营销活动",
        "description": "平台发起的营销活动，如限时折扣、会员日等",
        "icon": "megaphone",
        "color": "#FF5722",
        "classification_level": "U",
        "properties": [
            _prop("campaign_id", "string", "活动ID", True),
            _prop("campaign_name", "string", "活动名称", True),
            _prop("campaign_type", "string", "类型: discount/growth_boost/points_multiplier/limited_time"),
            _prop("start_time", "datetime", "开始时间"),
            _prop("end_time", "datetime", "结束时间"),
            _prop("target_member_levels", "array", "目标会员等级"),
            _prop("discount_rate", "float", "额外折扣率"),
            _prop("growth_multiplier", "float", "成长值倍数"),
            _prop("points_multiplier", "float", "积分倍数"),
            _prop("budget", "float", "活动预算"),
            _prop("status", "string", "状态: draft/active/ended/cancelled"),
            _prop("description", "string", "活动描述"),
            _prop("rules", "json", "活动规则详情"),
        ],
        "primary_key": ["campaign_id"],
    },
]


# ---- 关系类型 (LinkType) ----

LINK_TYPES = [
    # 平台管理关系
    {"name": "MANAGES_DEALER",        "source_type": "Platform",        "target_type": "Dealer",          "cardinality": "MANY_TO_MANY", "link_type": "ASSOCIATION",  "description": "平台审核与管理经销商"},
    {"name": "MANAGES_SERVICE_PROVIDER","source_type": "Platform",       "target_type": "ServiceProvider", "cardinality": "MANY_TO_MANY", "link_type": "ASSOCIATION",  "description": "平台审核与管理服务商"},
    {"name": "DEFINES_LEVEL",         "source_type": "Platform",        "target_type": "MembershipLevel", "cardinality": "ONE_TO_MANY",   "link_type": "COMPOSITION", "description": "平台定义会员等级体系"},
    {"name": "HOSTS_CAMPAIGN",        "source_type": "Platform",        "target_type": "Campaign",        "cardinality": "ONE_TO_MANY",   "link_type": "ASSOCIATION",   "description": "平台发起营销活动"},
    # 供应关系
    {"name": "SUPPLIES_PRODUCT",      "source_type": "Dealer",          "target_type": "Product",         "cardinality": "MANY_TO_MANY", "link_type": "ASSOCIATION",   "description": "经销商供应商品"},
    {"name": "PROVIDES_PRODUCT",      "source_type": "ServiceProvider", "target_type": "Product",         "cardinality": "MANY_TO_MANY", "link_type": "ASSOCIATION",  "description": "服务商提供商品/服务"},
    # 会员核心关系
    {"name": "OWNS_VEHICLE",          "source_type": "Member",          "target_type": "Vehicle",         "cardinality": "ONE_TO_MANY",   "link_type": "ASSOCIATION",  "description": "会员拥有车辆"},
    {"name": "PLACES_ORDER",          "source_type": "Member",          "target_type": "Order",           "cardinality": "ONE_TO_MANY",   "link_type": "ASSOCIATION",   "description": "会员下单"},
    {"name": "HAS_LEVEL",             "source_type": "Member",          "target_type": "MembershipLevel", "cardinality": "MANY_TO_ONE",   "link_type": "ASSOCIATION", "description": "会员拥有会员等级"},
    {"name": "EARNS_GROWTH",          "source_type": "Member",          "target_type": "GrowthRecord",    "cardinality": "ONE_TO_MANY",   "link_type": "COMPOSITION",  "description": "会员获取成长值"},
    {"name": "HAS_POINTS_ACCOUNT",    "source_type": "Member",          "target_type": "PointsAccount",   "cardinality": "ONE_TO_MANY",   "link_type": "COMPOSITION",  "description": "会员拥有积分账户"},
    {"name": "EXECUTES_POINTS_TX",    "source_type": "Member",          "target_type": "PointsTransaction","cardinality":"ONE_TO_MANY",  "link_type": "COMPOSITION","description": "会员执行积分交易"},
    {"name": "REDEEMS_COUPON",        "source_type": "Member",          "target_type": "Coupon",          "cardinality": "MANY_TO_MANY", "link_type": "ASSOCIATION",  "description": "会员领取/使用优惠券"},
    {"name": "MAKES_APPOINTMENT",     "source_type": "Member",          "target_type": "ServiceAppointment","cardinality":"ONE_TO_MANY",  "link_type": "ASSOCIATION",  "description": "会员预约服务"},
    {"name": "WRITES_EVALUATION",     "source_type": "Member",          "target_type": "Evaluation",      "cardinality": "ONE_TO_MANY",   "link_type": "ASSOCIATION",   "description": "会员撰写评价"},
    # 订单关联
    {"name": "CONTAINS_PRODUCT",      "source_type": "Order",           "target_type": "Product",         "cardinality": "MANY_TO_MANY", "link_type": "COMPOSITION",  "description": "订单包含商品"},
    {"name": "ROUTES_TO_DEALER",      "source_type": "Order",           "target_type": "Dealer",          "cardinality": "MANY_TO_ONE",   "link_type": "ASSOCIATION",  "description": "订单路由到经销商履约"},
    {"name": "ROUTES_TO_PROVIDER",    "source_type": "Order",           "target_type": "ServiceProvider", "cardinality": "MANY_TO_ONE",  "link_type": "ASSOCIATION","description": "订单路由到服务商履约"},
    {"name": "GENERATES_SETTLEMENT",  "source_type": "Order",           "target_type": "SettlementRecord","cardinality":"ONE_TO_MANY",   "link_type": "COMPOSITION", "description": "订单生成结算记录"},
    {"name": "GENERATES_INVOICE",     "source_type": "Order",           "target_type": "Invoice",         "cardinality": "ONE_TO_MANY",   "link_type": "COMPOSITION",  "description": "订单生成发票"},
    # 等级权益
    {"name": "GRANTS_BENEFIT",        "source_type": "MembershipLevel", "target_type": "Benefit",         "cardinality": "MANY_TO_MANY", "link_type": "ASSOCIATION","description": "等级授予权益"},
    # 库存管理
    {"name": "MANAGES_INVENTORY_D",   "source_type": "Dealer",          "target_type": "Inventory",       "cardinality": "ONE_TO_MANY",  "link_type": "COMPOSITION","description": "经销商管理库存"},
    {"name": "MANAGES_INVENTORY_S",   "source_type": "ServiceProvider", "target_type": "Inventory",       "cardinality": "ONE_TO_MANY",  "link_type": "COMPOSITION","description": "服务商管理库存"},
    # 库存关联商品
    {"name": "STOCKS_PRODUCT",        "source_type": "Inventory",       "target_type": "Product",         "cardinality": "MANY_TO_ONE",  "link_type": "ASSOCIATION","description": "库存对应商品"},
    # 评价关联
    {"name": "EVALUATES_DEALER",      "source_type": "Evaluation",      "target_type": "Dealer",          "cardinality": "MANY_TO_ONE",  "link_type": "ASSOCIATION","description": "评价对象为经销商"},
    {"name": "EVALUATES_PROVIDER",    "source_type": "Evaluation",      "target_type": "ServiceProvider", "cardinality": "MANY_TO_ONE",  "link_type": "ASSOCIATION","description": "评价对象为服务商"},
    {"name": "EVALUATES_PRODUCT",     "source_type": "Evaluation",      "target_type": "Product",         "cardinality": "MANY_TO_ONE",  "link_type": "ASSOCIATION","description": "评价对象为商品"},
    # 交易审计
    {"name": "GROWTH_ISSUED_BY",      "source_type": "GrowthRecord",    "target_type": "Platform",        "cardinality": "MANY_TO_ONE",  "link_type": "ASSOCIATION","description": "成长值由平台发放"},
    {"name": "POINTS_ISSUED_BY",      "source_type": "PointsTransaction","target_type": "Platform",        "cardinality": "MANY_TO_ONE",  "link_type": "ASSOCIATION","description": "积分由平台发放/管理"},
]


# ---- 动作类型 (ActionType) ----
# name, target_object_type, description, parameters, required_roles

ACTION_TYPES = [
    # 会员操作
    {"name": "member_register",            "target_object_type": "Member",       "description": "会员注册",     "parameters": [{"name":"phone","type":"string","required":True},{"name":"password","type":"string","required":True},{"name":"referral_code","type":"string","required":False}], "required_roles": ["guest"]},
    {"name": "member_login",               "target_object_type": "Member",       "description": "会员登录",     "parameters": [{"name":"phone","type":"string","required":True},{"name":"password","type":"string","required":True}], "required_roles": ["guest"]},
    {"name": "member_upgrade_level",       "target_object_type": "Member",       "description": "会员等级升级", "parameters": [{"name":"member_id","type":"string","required":True},{"name":"new_level","type":"string","required":True}], "required_roles": ["system"]},
    {"name": "member_place_order",         "target_object_type": "Order",        "description": "会员下单",     "parameters": [{"name":"products","type":"array","required":True},{"name":"address","type":"string","required":True},{"name":"use_points","type":"integer","required":False},{"name":"coupon_code","type":"string","required":False}], "required_roles": ["member"]},
    {"name": "member_earn_growth",         "target_object_type": "GrowthRecord", "description": "获取成长值",   "parameters": [{"name":"member_id","type":"string","required":True},{"name":"amount","type":"integer","required":True},{"name":"source_type","type":"string","required":True}], "required_roles": ["system"]},
    {"name": "member_earn_points",         "target_object_type": "PointsTransaction","description":"获取积分", "parameters": [{"name":"member_id","type":"string","required":True},{"name":"amount","type":"integer","required":True},{"name":"earn_source","type":"string","required":True}], "required_roles": ["system"]},
    {"name": "member_redeem_points",       "target_object_type": "PointsTransaction","description":"积分兑换", "parameters": [{"name":"member_id","type":"string","required":True},{"name":"amount","type":"integer","required":True},{"name":"consume_scene","type":"string","required":True}], "required_roles": ["member"]},
    {"name": "member_redeem_coupon",       "target_object_type": "Coupon",      "description": "领取优惠券",   "parameters": [{"name":"member_id","type":"string","required":True},{"name":"coupon_code","type":"string","required":True}], "required_roles": ["member"]},
    {"name": "member_use_coupon",          "target_object_type": "Coupon",      "description": "使用优惠券",   "parameters": [{"name":"member_id","type":"string","required":True},{"name":"coupon_code","type":"string","required":True},{"name":"order_id","type":"string","required":True}], "required_roles": ["member"]},
    {"name": "member_book_service",        "target_object_type": "ServiceAppointment","description":"预约服务","parameters":[{"name":"member_id","type":"string","required":True},{"name":"service_type","type":"string","required":True},{"name":"appointment_time","type":"datetime","required":True}],"required_roles":["member"]},
    {"name": "member_write_evaluation",    "target_object_type": "Evaluation",  "description": "撰写评价",     "parameters": [{"name":"order_id","type":"string","required":True},{"name":"star_rating","type":"integer","required":True},{"name":"content","type":"string","required":True}], "required_roles": ["member"]},
    # 经销商操作
    {"name": "dealer_sync_inventory",      "target_object_type": "Inventory",   "description": "同步库存",     "parameters": [{"name":"dealer_code","type":"string","required":True},{"name":"product_sku","type":"string","required":True},{"name":"quantity","type":"integer","required":True}], "required_roles": ["dealer"]},
    {"name": "dealer_fulfill_order",       "target_object_type": "Order",       "description": "履约订单",     "parameters": [{"name":"order_no","type":"string","required":True},{"name":"dealer_code","type":"string","required":True}], "required_roles": ["dealer"]},
    {"name": "dealer_confirm_delivery",    "target_object_type": "Order",       "description": "确认交付",     "parameters": [{"name":"order_no","type":"string","required":True},{"name":"delivery_info","type":"json","required":True}], "required_roles": ["dealer"]},
    # 服务商操作
    {"name": "provider_register_service",  "target_object_type": "Product",     "description": "注册服务/商品","parameters": [{"name":"provider_code","type":"string","required":True},{"name":"product_info","type":"json","required":True}], "required_roles": ["service_provider"]},
    {"name": "provider_manage_product",    "target_object_type": "Product",     "description": "管理商品",     "parameters": [{"name":"provider_code","type":"string","required":True},{"name":"sku_code","type":"string","required":True},{"name":"updates","type":"json","required":True}], "required_roles": ["service_provider"]},
    # 平台方操作
    {"name": "platform_approve_merchant",  "target_object_type": "Dealer",     "description": "审核商户入驻",  "parameters": [{"name":"dealer_code","type":"string","required":True},{"name":"approve","type":"boolean","required":True},{"name":"remark","type":"string","required":False}], "required_roles": ["platform_admin"]},
    {"name": "platform_settle_account",    "target_object_type": "SettlementRecord","description":"执行结算", "parameters": [{"name":"settlement_id","type":"string","required":True}], "required_roles": ["platform_admin"]},
    {"name": "platform_create_campaign",   "target_object_type": "Campaign",   "description": "创建营销活动",  "parameters": [{"name":"campaign_info","type":"json","required":True}], "required_roles": ["platform_admin"]},
    {"name": "platform_issue_coupon",      "target_object_type": "Coupon",     "description": "发放优惠券",    "parameters": [{"name":"coupon_info","type":"json","required":True},{"name":"target_members","type":"array","required":False}], "required_roles": ["platform_admin"]},
    {"name": "platform_manage_level",      "target_object_type": "MembershipLevel","description":"管理会员等级","parameters": [{"name":"level_code","type":"string","required":True},{"name":"updates","type":"json","required":True}], "required_roles": ["platform_admin"]},
    {"name": "platform_audit_order",       "target_object_type": "Order",      "description": "审核异常订单",  "parameters": [{"name":"order_no","type":"string","required":True},{"name":"action","type":"string","required":True}], "required_roles": ["platform_admin"]},
    # 订单操作
    {"name": "order_pay",                  "target_object_type": "Order",      "description": "支付订单",     "parameters": [{"name":"order_no","type":"string","required":True},{"name":"payment_method","type":"string","required":True}], "required_roles": ["member"]},
    {"name": "order_cancel",               "target_object_type": "Order",      "description": "取消订单",     "parameters": [{"name":"order_no","type":"string","required":True},{"name":"reason","type":"string","required":True}], "required_roles": ["member"]},
    {"name": "order_refund",               "target_object_type": "Order",      "description": "退款处理",     "parameters": [{"name":"order_no","type":"string","required":True},{"name":"refund_amount","type":"float","required":True},{"name":"reason","type":"string","required":True}], "required_roles": ["platform_admin"]},
]


# ---- 业务流程类型 (ProcessType) ----

PROCESS_TYPES = [
    {
        "name": "member_registration_and_growth",
        "display_name": "会员注册与成长流程",
        "description": "C端用户注册→等级成长→权益获取的全生命周期管理流程",
        "flow_node_schema": [
            {"step": 1, "name": "用户注册", "description": "填写手机号/身份信息完成注册", "related_types": ["Member"]},
            {"step": 2, "name": "初始等级分配", "description": "注册后分配普通会员等级", "related_types": ["Member", "MembershipLevel"]},
            {"step": 3, "name": "消费/互动获取成长值", "description": "购车、消费、签到等活动获取成长值", "related_types": ["GrowthRecord"]},
            {"step": 4, "name": "成长值达标自动升级", "description": "近12个月成长值达标自动升级会员等级", "related_types": ["Member", "MembershipLevel"]},
            {"step": 5, "name": "降级保护期", "description": "成长值不足但有3个月保护期", "related_types": ["Member", "MembershipLevel"]},
            {"step": 6, "name": "权益解锁", "description": "升级后自动解锁对应等级权益", "related_types": ["Benefit"]},
        ],
    },
    {
        "name": "product_onboarding_and_management",
        "display_name": "商品上架与管理流程",
        "description": "B端服务商/经销商提交商品→平台审核→上架→库存管理的全流程",
        "flow_node_schema": [
            {"step": 1, "name": "B端提交商品", "description": "经销商/服务商提交商品信息与资质", "related_types": ["Dealer", "ServiceProvider"]},
            {"step": 2, "name": "平台审核", "description": "平台审核商品合规性与定价", "related_types": ["Platform"]},
            {"step": 3, "name": "商品上架", "description": "审核通过后正式发布上架", "related_types": ["Product"]},
            {"step": 4, "name": "库存同步", "description": "B端实时同步库存至平台", "related_types": ["Inventory"]},
            {"step": 5, "name": "库存预警", "description": "低于安全阈值时自动预警并触发补货", "related_types": ["Inventory"]},
            {"step": 6, "name": "防超卖控制", "description": "一盘货策略避免多渠道重复销售", "related_types": ["Product", "Inventory"]},
        ],
    },
    {
        "name": "order_routing_and_distribution",
        "display_name": "交易路由与分发流程",
        "description": "C端下单→智能路由选择最优B端→订单分发→履约→结算的全流程",
        "flow_node_schema": [
            {"step": 1, "name": "C端下单", "description": "会员选择商品/服务并提交订单", "related_types": ["Member", "Order"]},
            {"step": 2, "name": "智能路由", "description": "基于地理位置、库存、价格、评分选择最优B端", "related_types": ["Order", "Dealer", "ServiceProvider"]},
            {"step": 3, "name": "订单分发", "description": "将订单路由至选定的B端执行", "related_types": ["Order"]},
            {"step": 4, "name": "B端履约", "description": "B端完成备货/服务/发货", "related_types": ["Dealer", "ServiceProvider"]},
            {"step": 5, "name": "确认交付", "description": "C端确认收货或服务完成", "related_types": ["Member"]},
            {"step": 6, "name": "自动结算", "description": "按分账规则自动结算至各方账户", "related_types": ["SettlementRecord"]},
        ],
    },
    {
        "name": "cross_region_collaboration",
        "display_name": "跨区域协作流程",
        "description": "多区域B端协同，包括跨区域订单分配、异地提车、全国联保等场景",
        "flow_node_schema": [
            {"step": 1, "name": "跨区域订单分配", "description": "根据区域库存与服务能力动态分配订单", "related_types": ["Order"]},
            {"step": 2, "name": "数据同步", "description": "多区域库存、订单数据实时同步", "related_types": ["Inventory"]},
            {"step": 3, "name": "跨品牌权益", "description": "会员跨品牌权益共享与积分通兑", "related_types": ["Member", "PointsAccount"]},
            {"step": 4, "name": "异地服务", "description": "支持异地保养、维修、提车等场景", "related_types": ["ServiceAppointment"]},
        ],
    },
    {
        "name": "points_earn_and_consume",
        "display_name": "积分获取与消耗流程",
        "description": "积分获取（消费/任务/活动）→ 积分管理（有效期/冻结）→ 积分消耗（兑换/抵扣）的全流程",
        "flow_node_schema": [
            {"step": 1, "name": "消费积分获取", "description": "消费1元=1积分自动累积", "related_types": ["PointsTransaction"]},
            {"step": 2, "name": "任务积分获取", "description": "完成签到/评价/分享等任务获取积分", "related_types": ["PointsTransaction"]},
            {"step": 3, "name": "活动积分获取", "description": "参与营销活动获取额外积分", "related_types": ["PointsTransaction", "Campaign"]},
            {"step": 4, "name": "积分有效期管理", "description": "分批次有效期管理与过期提醒", "related_types": ["PointsTransaction"]},
            {"step": 5, "name": "积分消耗", "description": "兑换商品/抵扣现金/服务抵扣/权益兑换", "related_types": ["PointsTransaction", "Order"]},
            {"step": 6, "name": "积分回流", "description": "退货积分按原有效期退回", "related_types": ["PointsTransaction"]},
            {"step": 7, "name": "区块链审计", "description": "积分变动记录上链确保不可篡改", "related_types": ["PointsTransaction"]},
        ],
    },
    {
        "name": "settlement_and_reconciliation",
        "display_name": "结算与分账流程",
        "description": "订单完成后按多维度分账规则自动分账、结算、生成对账单的全流程",
        "flow_node_schema": [
            {"step": 1, "name": "分账计算", "description": "按商品品类/B端等级/促销活动等多维度计算分账比例", "related_types": ["Order"]},
            {"step": 2, "name": "自动分账", "description": "自动将金额分配至平台/B端各方账户", "related_types": ["SettlementRecord"]},
            {"step": 3, "name": "生成对账单", "description": "按T+1/T+7生成明细对账单", "related_types": ["SettlementRecord"]},
            {"step": 4, "name": "发票管理", "description": "自动对接税务系统生成并推送电子发票", "related_types": ["Invoice"]},
            {"step": 5, "name": "逆向分账", "description": "退款/售后赔付等逆向分账标准化处理", "related_types": ["SettlementRecord"]},
            {"step": 6, "name": "争议处理", "description": "对账差异时启动人工审核流程", "related_types": ["Platform"]},
        ],
    },
]


# ---- 规则类型 (RuleType) ----

RULE_TYPES = [
    {
        "name": "member_level_upgrade_downgrade",
        "display_name": "会员等级升降级规则",
        "description": "定义会员等级升级与降级的条件与保护机制",
        "condition_schema": {
            "upgrade": "近{upgrade_cycle_months}个月累计成长值 >= target_level.min_growth",
            "downgrade": "到期前12个月累计成长值 < current_level.min_growth",
            "protection": "降级前有{degrade_protection_months}个月保护期",
        },
        "consequence_schema": {
            "upgrade": "自动升级会员等级 + 解锁新等级权益",
            "downgrade": "自动降级 + 权益降级通知",
        },
        "priority_levels": ["high", "critical"],
        "related_object_types": ["Member", "MembershipLevel", "GrowthRecord"],
    },
    {
        "name": "points_earning_rules",
        "display_name": "积分获取规则",
        "description": "定义不同场景下积分获取的比例与限制",
        "condition_schema": {
            "consumption": "每消费1元获得1积分",
            "task": "签到+5积分/日 | 评价+20积分/次 | 分享+10积分/次",
            "activity": "活动期间积分倍数由Campaign.points_multiplier决定",
            "referral": "邀请新会员注册并消费获得500积分/人",
        },
        "consequence_schema": {
            "action": "向PointsAccount增加积分 + 写入PointsTransaction + 区块链上链",
        },
        "priority_levels": ["medium"],
        "related_object_types": ["PointsTransaction", "PointsAccount", "Campaign"],
    },
    {
        "name": "points_expiry_rules",
        "display_name": "积分有效期规则",
        "description": "分批次有效期管理与过期提醒策略",
        "condition_schema": {
            "consumption_points": "有效期24个月",
            "activity_points": "有效期6个月",
            "task_points": "有效期12个月",
            "special_points": "有效期按活动规则设定",
        },
        "consequence_schema": {
            "expiry_reminder": "到期前30天/7天/1天发送提醒",
            "expiry_action": "过期积分自动清零 + 写入PointsTransaction(type=expire)",
            "refund_return": "退货积分按原有效期退回",
        },
        "priority_levels": ["medium"],
        "related_object_types": ["PointsTransaction", "PointsAccount"],
    },
    {
        "name": "order_routing_rules",
        "display_name": "订单分发路由规则",
        "description": "基于多维度权重计算最优履约B端",
        "condition_schema": {
            "distance_weight": "距离用户最近的B端优先级高",
            "inventory_weight": "库存充足且未超卖的B端优先",
            "rating_weight": "NPS评分与星级评价高的B端优先",
            "cost_weight": "物流/服务成本最低的B端优先",
            "fulfill_rate_weight": "历史履约率高（>95%）的B端优先",
            "time_weight": "预计服务/配送时间最短的优先",
        },
        "consequence_schema": {
            "route": "计算加权综合得分后选择得分最高的B端",
            "fallback": "首选B端不可用时自动切换至次优B端",
            "exception": "所有B端不可用时触发人工干预流程",
        },
        "priority_levels": ["high"],
        "related_object_types": ["Order", "Dealer", "ServiceProvider"],
    },
    {
        "name": "settlement_split_rules",
        "display_name": "分账比例计算规则",
        "description": "多维度分账比例的计算规则",
        "condition_schema": {
            "base_rate": "平台默认佣金率{commission_rate}%",
            "dealer_level_discount": "高评级经销商佣金率降低0.5-2%",
            "campaign_discount": "参与促销活动的商品佣金率按活动规则调整",
            "high_value_discount": "单笔订单超10万元佣金率降低1%",
        },
        "consequence_schema": {
            "split": "平台抽取佣金后剩余金额归B端所有",
            "cycle": "T+1自动结算（促销活动期间T+7）",
        },
        "priority_levels": ["critical"],
        "related_object_types": ["SettlementRecord", "Order", "Platform"],
    },
    {
        "name": "anti_fraud_risk_control",
        "display_name": "防作弊风控规则",
        "description": "防范成长值作弊、积分滥用的风控规则",
        "condition_schema": {
            "growth_abuse_detection": "设备指纹分析 + 行为异常检测 + 同一设备多账号",
            "points_abuse_detection": "单日积分消耗上限 + 高频交易监控 + 设备指纹",
            "transaction_fraud": "机器学习异常交易检测 + 风险评分",
            "merchant_fraud": "B端价格异常监控 + 履约质量持续监控",
        },
        "consequence_schema": {
            "lock_account": "风险评分>阈值时自动冻结账户",
            "manual_review": "触发可疑交易人工审核流程",
            "merchant_penalty": "B端违规时自动处罚（降权/罚款/清退）",
        },
        "priority_levels": ["critical"],
        "related_object_types": ["Member", "PointsTransaction", "GrowthRecord", "Dealer", "ServiceProvider"],
    },
]


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="构建汽车B2B2C会员电商本体")
    parser.add_argument("--base-url", default="http://localhost:5174", help="API 基地址")
    parser.add_argument("--username", default="admin", help="用户名")
    parser.add_argument("--password", default="admin123", help="密码")
    parser.add_argument("--validate-only", action="store_true", help="仅验证已存在的本体")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划不执行")
    args = parser.parse_args()

    api = PlatformAPI(args.base_url)

    # ===== 0. 健康检查 & 登录 =====
    try:
        h = api.health()
        log.info("平台状态: %s", h.get("status", "unknown"))
    except Exception:
        log.error("无法连接平台 %s，请确认服务已启动", args.base_url)
        return

    api.login(args.username, args.password)

    # ===== 1. 基础设施 =====
    ws = api.get_or_create_workspace("汽车B2B2C会员电商", "汽车B2B2C会员电商本体建模工作空间")
    ws_id = ws.get("workspace_id") or ws.get("id", "")
    log.info("工作空间: %s (%s)", ws.get("name"), ws_id)

    sc = api.get_or_create_scenario(ws_id, "电商本体建模", "汽车B2B2C会员电商全业务建模")
    sc_id = sc.get("scenario_id") or sc.get("id", "")
    log.info("场景: %s (%s)", sc.get("name"), sc_id)

    kb = api.get_or_create_kb("汽车B2B2C会员电商知识库", "kb_2260b4dcbc93",
                               "汽车B2B2C会员电商业务知识库")
    kb_id = kb.get("kb_id") or kb.get("id", "")
    log.info("知识库: %s (%s)", kb.get("name"), kb_id)

    # ===== 2. 创建/获取本体 =====
    ontology = api.get_or_create_ontology(
        "汽车B2B2C会员电商本体",
        workspace_id=ws_id,
        scenario_id=sc_id,
        description="B2B2C汽车会员电商平台全业务本体模型，涵盖3种商业模式、4类角色、5级会员体系"
    )
    ontology_id = ontology.get("ontology_id") or ontology.get("id", "")
    log.info("本体: %s (%s)", ontology.get("name"), ontology_id)

    if args.validate_only:
        log.info("=== 仅验证模式 ===")
        _validate(api, ontology_id)
        return

    if args.dry_run:
        log.info("=== DRY RUN 模式，仅打印计划 ===")
        log.info("  ObjectTypes: %d", len(OBJECT_TYPES))
        log.info("  LinkTypes: %d", len(LINK_TYPES))
        log.info("  ActionTypes: %d", len(ACTION_TYPES))
        log.info("  ProcessTypes: %d", len(PROCESS_TYPES))
        log.info("  RuleTypes: %d", len(RULE_TYPES))
        return

    # ===== 3. 创建 ObjectTypes =====
    log.info("=== 创建 %d 个对象类型 ===", len(OBJECT_TYPES))
    existing_names = {t.get("name") for t in api.list_object_types(ontology_id)}
    created_objs = 0
    for obj in OBJECT_TYPES:
        if obj["name"] in existing_names:
            log.info("  [SKIP] %s (已存在)", obj["name"])
            continue
        result = api.create_object_type(ontology_id, obj)
        if result and result.get("status") != "error":
            log.info("  [OK] %s -> %s", obj["name"], result.get("type_id", "")[:20])
            created_objs += 1
        else:
            log.error("  [FAIL] %s", obj["name"])
        time.sleep(0.05)
    log.info("对象类型: 新建 %d / 总计 %d", created_objs, len(OBJECT_TYPES))

    # ===== 4. 创建 LinkTypes =====
    log.info("=== 创建 %d 个关系类型 ===", len(LINK_TYPES))
    existing_links = {t.get("name") for t in api.list_link_types(ontology_id)}
    created_links = 0
    for link in LINK_TYPES:
        if link["name"] in existing_links:
            log.info("  [SKIP] %s (已存在)", link["name"])
            continue
        result = api.create_link_type(ontology_id, link)
        if result and result.get("status") != "error":
            log.info("  [OK] %s: %s -> %s", link["name"], link["source_type"], link["target_type"])
            created_links += 1
        else:
            log.error("  [FAIL] %s", link["name"])
        time.sleep(0.05)
    log.info("关系类型: 新建 %d / 总计 %d", created_links, len(LINK_TYPES))

    # ===== 5. 创建 ActionTypes =====
    log.info("=== 创建 %d 个动作类型 ===", len(ACTION_TYPES))
    existing_actions = {t.get("name") for t in api.list_action_types(ontology_id)}
    created_actions = 0
    for act in ACTION_TYPES:
        if act["name"] in existing_actions:
            log.info("  [SKIP] %s (已存在)", act["name"])
            continue
        result = api.create_action_type(ontology_id, act)
        if result and result.get("status") != "error":
            log.info("  [OK] %s -> %s", act["name"], act["target_object_type"])
            created_actions += 1
        else:
            log.error("  [FAIL] %s", act["name"])
        time.sleep(0.05)
    log.info("动作类型: 新建 %d / 总计 %d", created_actions, len(ACTION_TYPES))

    # ===== 6. 创建 ProcessTypes =====
    log.info("=== 创建 %d 个业务流程类型 ===", len(PROCESS_TYPES))
    existing_processes = {t.get("name") for t in api.list_process_types(ontology_id)}
    created_procs = 0
    for proc in PROCESS_TYPES:
        if proc["name"] in existing_processes:
            log.info("  [SKIP] %s (已存在)", proc["name"])
            continue
        result = api.create_process_type(ontology_id, proc)
        if result and result.get("status") != "error":
            log.info("  [OK] %s", proc["display_name"])
            created_procs += 1
        else:
            log.error("  [FAIL] %s", proc["name"])
        time.sleep(0.05)
    log.info("业务流程类型: 新建 %d / 总计 %d", created_procs, len(PROCESS_TYPES))

    # ===== 7. 创建 RuleTypes =====
    log.info("=== 创建 %d 个规则类型 ===", len(RULE_TYPES))
    existing_rules = {t.get("name") for t in api.list_rule_types(ontology_id)}
    created_rules = 0
    for rule in RULE_TYPES:
        if rule["name"] in existing_rules:
            log.info("  [SKIP] %s (已存在)", rule["name"])
            continue
        result = api.create_rule_type(ontology_id, rule)
        if result and result.get("status") != "error":
            log.info("  [OK] %s", rule["display_name"])
            created_rules += 1
        else:
            log.error("  [FAIL] %s", rule["name"])
        time.sleep(0.05)
    log.info("规则类型: 新建 %d / 总计 %d", created_rules, len(RULE_TYPES))

    # ===== 8. 提交 Schema 版本 =====
    log.info("=== 提交 Schema 版本 ===")
    try:
        ver = api.commit_schema(ontology_id,
            "汽车B2B2C会员电商本体 v0.1.0: "
            f"{len(OBJECT_TYPES)} ObjectTypes + {len(LINK_TYPES)} LinkTypes + "
            f"{len(ACTION_TYPES)} ActionTypes + {len(PROCESS_TYPES)} Processes + "
            f"{len(RULE_TYPES)} Rules"
        )
        log.info("版本已提交: %s", ver.get("version_number", ver.get("version_id", "")))
    except Exception as e:
        log.warning("提交版本异常: %s (可能已提交)", e)

    # ===== 9. 验证 =====
    _validate(api, ontology_id)

    # ===== 10. 输出统计 =====
    log.info("=" * 60)
    log.info("本体构建完成!")
    log.info("  本体ID: %s", ontology_id)
    log.info("  对象类型: %d", len(OBJECT_TYPES))
    log.info("  关系类型: %d", len(LINK_TYPES))
    log.info("  动作类型: %d", len(ACTION_TYPES))
    log.info("  业务流程: %d", len(PROCESS_TYPES))
    log.info("  规则类型: %d", len(RULE_TYPES))
    log.info("=" * 60)


def _validate(api: PlatformAPI, ontology_id: str):
    """验证本体完整性"""
    log.info("=== 验证本体完整性 ===")

    obj_types = api.list_object_types(ontology_id)
    link_types = api.list_link_types(ontology_id)
    action_types = api.list_action_types(ontology_id)
    proc_types = api.list_process_types(ontology_id)
    rule_types = api.list_rule_types(ontology_id)

    log.info("  对象类型: %d", len(obj_types))
    log.info("  关系类型: %d", len(link_types))
    log.info("  动作类型: %d", len(action_types))
    log.info("  业务流程: %d", len(proc_types))
    log.info("  规则类型: %d", len(rule_types))

    # 引用完整性检查
    obj_names = {t.get("name") for t in obj_types}
    issues = []
    for link in link_types:
        src = link.get("source_type", "")
        tgt = link.get("target_type", "")
        if src and src not in obj_names:
            issues.append(f"LinkType '{link.get('name')}' source_type '{src}' 未定义")
        if tgt and tgt not in obj_names:
            issues.append(f"LinkType '{link.get('name')}' target_type '{tgt}' 未定义")

    for act in action_types:
        tgt = act.get("target_object_type", "")
        if tgt and tgt not in obj_names:
            issues.append(f"ActionType '{act.get('name')}' target_object_type '{tgt}' 未定义")

    if issues:
        log.warning("发现 %d 个引用完整性问题:", len(issues))
        for i in issues:
            log.warning("  - %s", i)
    else:
        log.info("  [OK] 引用完整性验证通过")

    # 图谱检查
    try:
        graph = api.get_graph(ontology_id)
        if graph.get("status") != "error":
            nodes = len(graph.get("nodes", []))
            edges = len(graph.get("edges", []))
            log.info("  图谱: %d 节点, %d 边", nodes, edges)
    except Exception:
        pass


if __name__ == "__main__":
    main()
