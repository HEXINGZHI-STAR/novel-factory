"""
盘古 · Dashboard 事件推送

Pipeline 每步进度实时推送到 Node.js WebSocket 面板。
用法:
    from pangu_core.dashboard_push import DashboardPusher
    pusher = DashboardPusher()
    pusher.start("开门见尸", 5, "workshop", ["W0","W1","W2","W3","W4","W5"])
    pusher.stage("W2", "done", 25.3)
    pusher.complete(2500, 60.0)
"""

from __future__ import annotations

import time
import requests
from typing import List

DASHBOARD_URL = "http://localhost:3100"


class DashboardPusher:
    """Pipeline 进度推送器"""

    def __init__(self, url: str = DASHBOARD_URL):
        self.url = url

    def start(self, project: str, chapter: int, mode: str,
              stages: List[str]):
        """Pipeline 开始"""
        self._post("/api/pipeline/start", {
            "project": project, "chapter": chapter,
            "mode": mode, "stages": stages,
        })

    def stage(self, stage_id: str, status: str, elapsed: float = 0):
        """Stage 状态更新"""
        self._post("/api/pipeline/stage", {
            "stage": stage_id, "status": status,
            "time": round(elapsed, 1) if elapsed else None,
        })

    def complete(self, words: int, elapsed: float):
        """Pipeline 完成"""
        self._post("/api/pipeline/complete", {
            "words": words, "elapsed": round(elapsed, 1),
        })

    def _post(self, path: str, data: dict):
        try:
            requests.post(f"{self.url}{path}", json=data, timeout=2)
        except Exception:
            pass  # Dashboard不可用不影响Pipeline
