"""
安全审计模块 - Security Audit
WR-21: 安全审计与渗透测试 (OWASP Top 10 检查 + 报告)

功能：
- OWASP Top 10 漏洞检测
- 安全配置审计
- 认证鉴权审计
- 输入验证审计
- 敏感数据审计
"""

import sys
import os
import json
import re
import hashlib
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid


import logging

logger = logging.getLogger(__name__)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class VulnerabilitySeverity(str, Enum):
    """漏洞严重等级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityCategory(str, Enum):
    """漏洞类别 (OWASP Top 10)"""
    A01_BROKEN_ACCESS = "A01-Broken Access Control"
    A02_CRYPTO_FAILURES = "A02-Cryptographic Failures"
    A03_INJECTION = "A03-Injection"
    A04_INSECURE_DESIGN = "A04-Insecure Design"
    A05_SEC_MISCONFIG = "A05-Security Misconfiguration"
    A06_VULN_COMPONENTS = "A06-Vulnerable Components"
    A07_AUTH_FAILURES = "A07-Authentication Failures"
    A08_INTEGRITY_FAILURES = "A08-Software and Data Integrity Failures"
    A09_LOGGING_FAILURES = "A09-Security Logging Failures"
    A10_SSRF = "A10-Server-Side Request Forgery"


@dataclass
class Vulnerability:
    """漏洞"""
    vuln_id: str
    category: VulnerabilityCategory
    title: str
    description: str
    severity: VulnerabilitySeverity
    location: str
    evidence: str
    remediation: str
    references: List[str] = field(default_factory=list)
    cwe_id: Optional[str] = None


@dataclass
class SecurityCheck:
    """安全检查项"""
    check_id: str
    name: str
    category: VulnerabilityCategory
    description: str
    enabled: bool = True
    severity_override: Optional[VulnerabilitySeverity] = None


@dataclass
class AuditReport:
    """审计报告"""
    report_id: str
    timestamp: str
    target: str
    checks_run: int
    vulnerabilities_found: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    vulnerabilities: List[Vulnerability]
    summary: str
    recommendations: List[str]


class OWASPTop10Checker:
    """OWASP Top 10 漏洞检查器"""

    def __init__(self):
        self._checks: Dict[str, SecurityCheck] = {}
        self._setup_checks()

    def _setup_checks(self):
        """设置检查项"""
        checks = [
            SecurityCheck(
                check_id="A01-001",
                name="未授权访问检查",
                category=VulnerabilityCategory.A01_BROKEN_ACCESS,
                description="检查是否存在未授权访问漏洞"
            ),
            SecurityCheck(
                check_id="A01-002",
                name="IDOR 检查",
                category=VulnerabilityCategory.A01_BROKEN_ACCESS,
                description="检查是否存在直接对象引用漏洞"
            ),
            SecurityCheck(
                check_id="A02-001",
                name="敏感数据暴露检查",
                category=VulnerabilityCategory.A02_CRYPTO_FAILURES,
                description="检查是否暴露敏感数据"
            ),
            SecurityCheck(
                check_id="A03-001",
                name="SQL 注入检查",
                category=VulnerabilityCategory.A03_INJECTION,
                description="检查是否存在 SQL 注入漏洞"
            ),
            SecurityCheck(
                check_id="A03-002",
                name="XSS 检查",
                category=VulnerabilityCategory.A03_INJECTION,
                description="检查是否存在跨站脚本漏洞"
            ),
            SecurityCheck(
                check_id="A05-001",
                name="安全配置检查",
                category=VulnerabilityCategory.A05_SEC_MISCONFIG,
                description="检查安全配置是否正确"
            ),
            SecurityCheck(
                check_id="A07-001",
                name="认证绕过检查",
                category=VulnerabilityCategory.A07_AUTH_FAILURES,
                description="检查认证机制是否可被绕过"
            ),
        ]

        for check in checks:
            self._checks[check.check_id] = check

    def check_sql_injection(self, code: str) -> List[Vulnerability]:
        """检查 SQL 注入"""
        vulnerabilities = []

        patterns = [
            (r'execute\s*\(\s*["\'].*\%s', "可能存在 SQL 注入风险"),
            (r'"\s*\+\s*.*\+\s*"', "字符串拼接 SQL 可能导致注入"),
            (r'f["\'].*\{.*\}', "f-string 中包含 SQL 可能导致注入"),
        ]

        for pattern, desc in patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                vuln = Vulnerability(
                    vuln_id=str(uuid.uuid4()),
                    category=VulnerabilityCategory.A03_INJECTION,
                    title="可能的 SQL 注入",
                    description=desc,
                    severity=VulnerabilitySeverity.HIGH,
                    location=f"行号未知: {match.group()[:50]}",
                    evidence=match.group(),
                    remediation="使用参数化查询代替字符串拼接"
                )
                vulnerabilities.append(vuln)

        return vulnerabilities

    def check_xss(self, code: str) -> List[Vulnerability]:
        """检查 XSS"""
        vulnerabilities = []

        patterns = [
            (r'innerHTML\s*=', "使用 innerHTML 可能导致 XSS"),
            (r'document\.write\s*\(', "使用 document.write 可能导致 XSS"),
            (r'eval\s*\(.*request', "使用 eval 处理请求可能导致 XSS"),
        ]

        for pattern, desc in patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                vuln = Vulnerability(
                    vuln_id=str(uuid.uuid4()),
                    category=VulnerabilityCategory.A03_INJECTION,
                    title="可能的 XSS 漏洞",
                    description=desc,
                    severity=VulnerabilitySeverity.HIGH,
                    location=f"行号未知: {match.group()[:50]}",
                    evidence=match.group(),
                    remediation="使用 textContent 或 DOMPurify 替代 innerHTML"
                )
                vulnerabilities.append(vuln)

        return vulnerabilities

    def check_hardcoded_secrets(self, code: str) -> List[Vulnerability]:
        """检查硬编码密钥"""
        vulnerabilities = []

        patterns = [
            (r'password\s*=\s*["\'][^"\']{8,}["\']', "发现硬编码密码"),
            (r'api[_-]?key\s*=\s*["\'][^"\']{16,}["\']', "发现硬编码 API Key"),
            (r'secret\s*=\s*["\'][^"\']{16,}["\']', "发现硬编码密钥"),
            (r'Bearer\s+[A-Za-z0-9\-_\.]+', "发现硬编码 Token"),
        ]

        for pattern, desc in patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                vuln = Vulnerability(
                    vuln_id=str(uuid.uuid4()),
                    category=VulnerabilityCategory.A02_CRYPTO_FAILURES,
                    title="敏感信息硬编码",
                    description=desc,
                    severity=VulnerabilitySeverity.CRITICAL,
                    location=f"行号未知: {match.group()[:50]}",
                    evidence=hashlib.md5(match.group().encode()).hexdigest()[:8] + "...",
                    remediation="使用环境变量或密钥管理服务存储敏感信息"
                )
                vulnerabilities.append(vuln)

        return vulnerabilities

    def check_authentication(self, code: str) -> List[Vulnerability]:
        """检查认证问题"""
        vulnerabilities = []

        if 'session' in code.lower() and 'httponly' not in code.lower():
            vuln = Vulnerability(
                vuln_id=str(uuid.uuid4()),
                category=VulnerabilityCategory.A07_AUTH_FAILURES,
                title="Session Cookie 缺少 HttpOnly 标记",
                description="Session Cookie 未设置 HttpOnly 标志",
                severity=VulnerabilitySeverity.MEDIUM,
                location="Cookie 配置",
                evidence="未设置 HttpOnly",
                remediation="设置 Cookie 的 HttpOnly 标志"
            )
            vulnerabilities.append(vuln)

        if 'jwt' in code.lower() and 'verify' not in code.lower():
            vuln = Vulnerability(
                vuln_id=str(uuid.uuid4()),
                category=VulnerabilityCategory.A07_AUTH_FAILURES,
                title="JWT 未验证签名",
                description="代码中使用 JWT 但未验证签名",
                severity=VulnerabilitySeverity.CRITICAL,
                location="JWT 配置",
                evidence="未调用 verify 方法",
                remediation="始终验证 JWT 签名"
            )
            vulnerabilities.append(vuln)

        return vulnerabilities

    def check_insecure_design(self, code: str) -> List[Vulnerability]:
        """检查不安全设计"""
        vulnerabilities = []

        if 'debug' in code.lower() and 'True' in code:
            vuln = Vulnerability(
                vuln_id=str(uuid.uuid4()),
                category=VulnerabilityCategory.A04_INSECURE_DESIGN,
                title="调试模式开启",
                description="代码中包含调试模式配置",
                severity=VulnerabilitySeverity.MEDIUM,
                location="配置项",
                evidence="debug=True",
                remediation="生产环境关闭调试模式"
            )
            vulnerabilities.append(vuln)

        if 'cors' in code.lower() and ('*' in code):
            vuln = Vulnerability(
                vuln_id=str(uuid.uuid4()),
                category=VulnerabilityCategory.A04_INSECURE_DESIGN,
                title="CORS 配置允许所有来源",
                description="CORS 配置为允许所有来源",
                severity=VulnerabilitySeverity.HIGH,
                location="CORS 配置",
                evidence="Access-Control-Allow-Origin: *",
                remediation="限制 CORS 允许的来源"
            )
            vulnerabilities.append(vuln)

        return vulnerabilities


class SecurityAuditEngine:
    """
    安全审计引擎
    完整的安全审计系统
    """

    def __init__(self):
        self._checker = OWASPTop10Checker()
        self._reports: Dict[str, AuditReport] = {}
        self._history: List[AuditReport] = []
        self._max_history = 100
        self._lock = threading.RLock()

    def audit_code(self, code: str, target: str = "unknown") -> AuditReport:
        """
        审计代码

        Args:
            code: 要审计的代码
            target: 审计目标

        Returns:
            AuditReport
        """
        all_vulnerabilities = []

        all_vulnerabilities.extend(self._checker.check_sql_injection(code))
        all_vulnerabilities.extend(self._checker.check_xss(code))
        all_vulnerabilities.extend(self._checker.check_hardcoded_secrets(code))
        all_vulnerabilities.extend(self._checker.check_authentication(code))
        all_vulnerabilities.extend(self._checker.check_insecure_design(code))

        critical = sum(1 for v in all_vulnerabilities if v.severity == VulnerabilitySeverity.CRITICAL)
        high = sum(1 for v in all_vulnerabilities if v.severity == VulnerabilitySeverity.HIGH)
        medium = sum(1 for v in all_vulnerabilities if v.severity == VulnerabilitySeverity.MEDIUM)
        low = sum(1 for v in all_vulnerabilities if v.severity == VulnerabilitySeverity.LOW)

        report = AuditReport(
            report_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            target=target,
            checks_run=len(self._checker._checks),
            vulnerabilities_found=len(all_vulnerabilities),
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            vulnerabilities=all_vulnerabilities,
            summary=self._generate_summary(all_vulnerabilities, critical, high, medium, low),
            recommendations=self._generate_recommendations(all_vulnerabilities)
        )

        with self._lock:
            self._reports[report.report_id] = report
            self._history.append(report)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        return report

    def audit_file(self, file_path: str) -> AuditReport:
        """审计文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            return self.audit_code(code, target=file_path)
        except Exception as e:
            raise ValueError(f"无法读取文件: {e}")

    def audit_directory(self, dir_path: str, extensions: List[str] = None) -> List[AuditReport]:
        """审计目录"""
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.tsx']

        reports = []

        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', '.venv']]

            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    try:
                        report = self.audit_file(file_path)
                        reports.append(report)
                    except Exception:
                        pass

        return reports

    def _generate_summary(self, vulnerabilities: List[Vulnerability],
                        critical: int, high: int,
                        medium: int, low: int) -> str:
        """生成总结"""
        if not vulnerabilities:
            return "未发现安全漏洞"

        summary_parts = []
        if critical > 0:
            summary_parts.append(f"发现 {critical} 个严重漏洞需要立即修复")
        if high > 0:
            summary_parts.append(f"发现 {high} 个高危漏洞需要尽快修复")
        if medium > 0:
            summary_parts.append(f"发现 {medium} 个中危漏洞建议修复")
        if low > 0:
            summary_parts.append(f"发现 {low} 个低危漏洞")

        return "; ".join(summary_parts)

    def _generate_recommendations(self, vulnerabilities: List[Vulnerability]) -> List[str]:
        """生成建议"""
        recommendations = []

        categories = {}
        for vuln in vulnerabilities:
            cat = vuln.category.value
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(vuln)

        for cat, vulns in categories.items():
            if cat == VulnerabilityCategory.A03_INJECTION.value:
                recommendations.append("建议使用参数化查询和输入验证防止注入攻击")
            elif cat == VulnerabilityCategory.A02_CRYPTO_FAILURES.value:
                recommendations.append("建议使用密钥管理服务，不要在代码中硬编码敏感信息")
            elif cat == VulnerabilityCategory.A07_AUTH_FAILURES.value:
                recommendations.append("建议强化认证机制，确保 JWT 等令牌正确验证")
            elif cat == VulnerabilityCategory.A04_INSECURE_DESIGN.value:
                recommendations.append("建议进行威胁建模，在设计阶段考虑安全因素")

        return list(set(recommendations))

    def get_report(self, report_id: str) -> Optional[AuditReport]:
        """获取报告"""
        return self._reports.get(report_id)

    def get_latest_report(self) -> Optional[AuditReport]:
        """获取最新报告"""
        if self._history:
            return self._history[-1]
        return None

    def get_history(self, limit: int = 10) -> List[AuditReport]:
        """获取历史报告"""
        return self._history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_vulns = sum(r.vulnerabilities_found for r in self._history)
        total_checks = sum(r.checks_run for r in self._history)

        by_category: Optional[Dict[str, int]] = None
        if by_category is None:
            by_category = {}
        for report in self._history:
            for vuln in report.vulnerabilities:
                cat = vuln.category.value
                by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_reports": len(self._history),
            "total_vulnerabilities": total_vulns,
            "total_checks": total_checks,
            "by_category": by_category,
            "latest_report_id": self._history[-1].report_id if self._history else None
        }


_global_security_engine: Optional[SecurityAuditEngine] = None


def get_security_audit_engine() -> SecurityAuditEngine:
    """获取全局安全审计引擎"""
    global _global_security_engine
    if _global_security_engine is None:
        _global_security_engine = SecurityAuditEngine()
    return _global_security_engine


if __name__ == "__main__":
    engine = get_security_audit_engine()

    logger.info('=' * 60)
    logger.info('安全审计引擎测试')
    logger.info('=' * 60)

    logger.info('\n1. 审计代码样本:')

    sample_code = '''
    def login(username, password):
        query = "SELECT * FROM users WHERE username = ? AND password = ?"
        cursor.execute(query, (username, password))
        response = {"result": cursor.fetchall()}
        return response

    def set_session(user_id):
        response.set_cookie("session_id", user_id)
        return {"status": "ok"}

    DEBUG = True
    CORS_ORIGIN = "*"
    '''

    report = engine.audit_code(sample_code, target="sample.py")

    logger.info(f'   报告ID: {report.report_id}')
    logger.info(f'   漏洞数: {report.vulnerabilities_found}')
    logger.info(f'   严重: {report.critical_count}')
    logger.info(f'   高危: {report.high_count}')
    logger.info(f'   中危: {report.medium_count}')
    logger.info(f'   低危: {report.low_count}')

    logger.info('\n2. 发现的漏洞:')
    for vuln in report.vulnerabilities[:5]:
        logger.info(f'   [{vuln.severity.value}] {vuln.title}')
        logger.info(f'      类别: {vuln.category.value}')
        logger.info(f'      修复: {vuln.remediation[:30]}...')

    logger.info('\n3. 建议:')
    for rec in report.recommendations:
        logger.info(f'   - {rec}')

    logger.info('\n4. 统计信息:')
    stats = engine.get_statistics()
    logger.info(f"   总报告数: {stats['total_reports']}")
    logger.info(f"   总漏洞数: {stats['total_vulnerabilities']}")

    logger.info('\n' + '=' * 60)
    logger.info('安全审计引擎测试完成')
    logger.info('=' * 60)