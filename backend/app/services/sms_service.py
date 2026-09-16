"""
短信通知（模拟）
生产环境应替换为短信网关。此处落内存日志，便于审核链路自测。
"""

from datetime import datetime
from typing import Dict, List, Optional

_sent: List[Dict[str, str]] = []


def send_sms(phone: str, content: str) -> Dict[str, str]:
    rec = {
        "phone": (phone or "").strip(),
        "content": content or "",
        "sent_at": datetime.now().isoformat(timespec="seconds"),
    }
    _sent.append(rec)
    print(f"[sms] to={rec['phone']} {rec['content']}")
    return rec


def last_sms(phone: str) -> Optional[Dict[str, str]]:
    target = (phone or "").strip()
    for rec in reversed(_sent):
        if rec["phone"] == target:
            return rec
    return None


def clear_sms_log() -> None:
    _sent.clear()
