"""Data Health - NotificationDispatcher (T339)

支持 3 种通道：email / webhook / im
- email: smtplib stub（开发模式），生产应替换为真实 SMTP
- webhook: aiohttp.ClientSession 异步 HTTP POST
- im: HTTP POST（企业微信/钉钉 webhook）

发送失败不抛异常；所有调用通过 asyncio.create_task 异步派发。
"""
from __future__ import annotations

import asyncio
import json
import logging
import smtplib
from typing import Any, Dict, List, Optional

try:
    import aiohttp  # type: ignore
    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover - 可选依赖
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """3 通道通知派发器"""

    def __init__(self, aiohttp_session: Any = None, smtp_factory: Any = None):
        # 测试时可注入 mock；默认 None 表示按需创建
        self._aiohttp_session = aiohttp_session
        self._smtp_factory = smtp_factory or _default_smtp_factory
        self._sent_history: List[Dict[str, Any]] = []

    def dispatch(
        self,
        channel_config: Dict[str, Any],
        subject: str,
        body: str,
        reports: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """异步派发通知；fire-and-forget"""
        if not channel_config:
            logger.debug("dispatch called with empty channel_config; skip")
            return
        try:
            loop = asyncio.get_running_loop()
            # 处于 event loop 中：调度为 task
            task = loop.create_task(
                self._dispatch_async(channel_config, subject, body, reports or [])
            )
            # 防止 task 被 GC（fire-and-forget）
            task.add_done_callback(_log_task_exception)
        except RuntimeError as exc:
            # 没有运行中的 event loop（同步环境）；降级为同步发送
            logger.debug("no running loop, fallback to sync: %s", exc)
            self._dispatch_sync(channel_config, subject, body, reports or [])

    def history(self) -> List[Dict[str, Any]]:
        """返回已派发的历史（用于测试断言）"""
        return list(self._sent_history)

    # ---------- 内部派发 ----------

    async def _dispatch_async(
        self,
        channel_config: Dict[str, Any],
        subject: str,
        body: str,
        reports: List[Dict[str, Any]],
    ) -> None:
        """异步派发入口"""
        channels: List[str] = channel_config.get("channels", []) or []
        for ch in channels:
            try:
                await self._send_one(ch, channel_config, subject, body, reports)
            except Exception as exc:  # 失败降级，记录 warning
                logger.warning("notification %s failed: %s", ch, exc)

    def _dispatch_sync(
        self,
        channel_config: Dict[str, Any],
        subject: str,
        body: str,
        reports: List[Dict[str, Any]],
    ) -> None:
        """同步派发（无 event loop 时使用）"""
        for ch in channel_config.get("channels", []) or []:
            try:
                if ch == "email":
                    sent = self._send_email(cfg=channel_config, subject=subject, body=body, reports=reports)
                    if sent:
                        self._record(ch, subject, body, reports, "ok_sync")
                else:
                    # 同步模式下 webhook/im 只记录，不实际发送
                    logger.debug("sync mode: skip %s send", ch)
            except Exception as exc:
                logger.warning("sync notification %s failed: %s", ch, exc)

    async def _send_one(
        self,
        channel: str,
        cfg: Dict[str, Any],
        subject: str,
        body: str,
        reports: List[Dict[str, Any]],
    ) -> None:
        """异步发送单通道"""
        if channel == "email":
            sent = self._send_email(cfg, subject, body, reports)
            if not sent:
                return
        elif channel == "webhook":
            await self._send_webhook(cfg, subject, body, reports)
        elif channel == "im":
            await self._send_im(cfg, subject, body, reports)
        else:
            logger.warning("unknown channel: %s", channel)
            return
        self._record(channel, subject, body, reports, "ok")

    # ---------- 3 通道实现 ----------

    def _send_email(
        self,
        cfg: Dict[str, Any],
        subject: str,
        body: str,
        reports: List[Dict[str, Any]],
    ) -> bool:
        """email 通道：使用 smtplib stub（开发模式）

        Returns:
            True 表示已实际发送，False 表示跳过（无收件人 / 失败）。
        """
        smtp_cfg = cfg.get("email", {}) or {}
        host = smtp_cfg.get("host", "localhost")
        port = int(smtp_cfg.get("port", 25))
        sender = smtp_cfg.get("sender", "health@odap.local")
        recipients: List[str] = smtp_cfg.get("recipients", []) or []
        if not recipients:
            logger.debug("email: no recipients; skip")
            return False
        message = self._build_email(sender, recipients, subject, body, reports)
        try:
            with self._smtp_factory(host, port) as client:
                client.sendmail(sender, recipients, message)
            return True
        except Exception as exc:
            logger.debug("smtp send failed (stub): %s", exc)
            return False

    async def _send_webhook(
        self,
        cfg: Dict[str, Any],
        subject: str,
        body: str,
        reports: List[Dict[str, Any]],
    ) -> None:
        """webhook 通道：HTTP POST JSON"""
        wh_cfg = cfg.get("webhook", {}) or {}
        url = wh_cfg.get("url", "")
        if not url:
            logger.debug("webhook: no url; skip")
            return
        payload = {
            "subject": subject,
            "body": body,
            "reports": reports,
            "timestamp": _now_iso(),
        }
        await self._http_post(url, payload, wh_cfg.get("headers", {}))

    async def _send_im(
        self,
        cfg: Dict[str, Any],
        subject: str,
        body: str,
        reports: List[Dict[str, Any]],
    ) -> None:
        """im 通道：HTTP POST（企业微信/钉钉 webhook 风格）"""
        im_cfg = cfg.get("im", {}) or {}
        url = im_cfg.get("url", "")
        if not url:
            logger.debug("im: no url; skip")
            return
        # im 通道采用 markdown / text 形式
        text = f"### {subject}\n\n{body}\n\n"
        if reports:
            text += f"共 {len(reports)} 条报告"
        payload = {
            "msgtype": "markdown" if im_cfg.get("format") == "markdown" else "text",
            "markdown" if im_cfg.get("format") == "markdown" else "text": {
                "content" if im_cfg.get("format") == "markdown" else "text": text
            },
        }
        await self._http_post(url, payload, im_cfg.get("headers", {}))

    # ---------- 工具 ----------

    async def _http_post(self, url: str, payload: Dict[str, Any], headers: Dict[str, Any]) -> None:
        """异步 HTTP POST；优先使用注入的 session"""
        if self._aiohttp_session is not None:
            session = self._aiohttp_session
            async with session.post(url, json=payload, headers=headers) as resp:
                await resp.read()
            return
        if not AIOHTTP_AVAILABLE:
            logger.debug("aiohttp not available; skip HTTP POST")
            return
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                await resp.read()

    def _build_email(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        body: str,
        reports: List[Dict[str, Any]],
    ) -> str:
        """构造 RFC822 邮件文本"""
        lines = [
            f"From: {sender}",
            f"To: {', '.join(recipients)}",
            f"Subject: {subject}",
            "Content-Type: text/plain; charset=utf-8",
            "",
            body,
        ]
        if reports:
            lines.append("")
            lines.append(f"--- Reports ({len(reports)}) ---")
            for r in reports[:20]:
                lines.append(json.dumps(r, ensure_ascii=False))
        return "\n".join(lines)

    def _record(
        self,
        channel: str,
        subject: str,
        body: str,
        reports: List[Dict[str, Any]],
        status: str,
    ) -> None:
        """记录发送历史"""
        self._sent_history.append(
            {
                "channel": channel,
                "subject": subject,
                "body": body,
                "report_count": len(reports),
                "status": status,
            }
        )


def _now_iso() -> str:
    """返回当前时间 ISO 字符串"""
    from datetime import datetime
    return datetime.now().isoformat()


def _default_smtp_factory(host: str, port: int):
    """默认 SMTP 工厂：smtplib.SMTP stub（开发模式无网络）"""
    client = smtplib.SMTP(host, port, timeout=2)
    return client


def _log_task_exception(task: asyncio.Task) -> None:
    """异步 task 异常回调；避免 unhandled exception"""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning("notification task failed: %s", exc)
