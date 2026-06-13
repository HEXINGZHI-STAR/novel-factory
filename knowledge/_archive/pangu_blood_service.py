#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI血液层 — Python HTTP微服务
=================================
将数学引擎暴露为REST API，供Java骨架后端通过HTTP调用。

启动方式:
    python pangu_blood_service.py
    # 或指定端口:
    python pangu_blood_service.py --port 5000

端点:
    POST /analyze         — 完整数学分析
    POST /compare         — 两章对比
    POST /sequence        — 序列分析
    POST /guidance        — 优化指引
    GET  /health          — 健康检查
"""

import json
import sys
import math
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# 确保能导入本地模块
sys.path.insert(0, str(Path(__file__).parent))

from pangu_math_core import PanguMathEngine

# 全局引擎实例（线程安全，请求间复用）
_engine = PanguMathEngine()


class PanguAPIHandler(BaseHTTPRequestHandler):
    """盘古AI血液层HTTP处理器"""

    def _send_json(self, data, status=200):
        """发送JSON响应"""
        body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        """读取请求体JSON"""
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body.decode('utf-8'))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path == '/health' or path == '':
            self._send_json({
                "service": "pangu-blood-service",
                "status": "healthy",
                "python_version": sys.version.split()[0],
                "engine_ready": _engine is not None,
            })

        elif path == '/info':
            self._send_json({
                "service": "pangu-blood-service",
                "description": "盘古AI数学引擎HTTP服务",
                "endpoints": [
                    "POST /analyze    — 完整数学分析",
                    "POST /compare    — 两章对比",
                    "POST /sequence   — 序列分析",
                    "POST /guidance   — 优化指引",
                    "POST /breathe    — 呼吸工作流(全阶段编排)",
                    "POST /statistics — 医学统计诊断",
                    "GET  /health     — 健康检查",
                ],
                "math_branches": [
                    "线性代数(Vector/Matrix/PCA/SVD)",
                    "傅里叶分析(DFT/功率谱/节律)",
                    "拉普拉斯变换(钩子衰减/s域)",
                    "积分学(梯形积分/累积函数/总变差)",
                    "马尔可夫链(转移矩阵/稳态分布)",
                    "信息论(熵/KL散度/JS距离)",
                ],
            })

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        try:
            data = self._read_body()

            if path == '/analyze':
                text = data.get('text', '')
                chapter_num = data.get('chapter_num', 1)
                if len(text) < 200:
                    self._send_json({"error": "文本过短，至少200字"}, 400)
                    return
                result = _engine.full_analysis(text, chapter_num)
                self._send_json(result)

            elif path == '/compare':
                text1 = data.get('text1', '')
                text2 = data.get('text2', '')
                result = _engine.compare_chapters(text1, text2)
                self._send_json(result)

            elif path == '/sequence':
                chapters = data.get('chapters', [])
                if len(chapters) < 2:
                    self._send_json({"error": "至少需要2章"}, 400)
                    return
                result = _engine.sequence_analysis(chapters)
                self._send_json(result)

            elif path == '/guidance':
                analysis_result = data.get('analysis_result', {})
                platform = data.get('platform', 'qimao')
                guidance = _engine.get_guidance_prompt(analysis_result, platform)
                self._send_json({"guidance": guidance})

            elif path == '/corpus':
                texts = data.get('texts', [])
                if len(texts) < 3:
                    self._send_json({"error": "至少需要3个文本"}, 400)
                    return
                result = _engine.corpus_pca(texts)
                self._send_json(result)

            elif path == '/breathe':
                """呼吸系统：完整工作流编排"""
                text = data.get('text', '')
                chapter_num = data.get('chapter_num', 1)
                platform = data.get('platform', 'qimao')
                genre = data.get('genre', 'unknown')
                history = data.get('history', [])
                
                try:
                    from workflow_orchestrator import breathe
                    result = breathe(text, chapter_num, platform, genre, 
                                   chapter_history=history)
                    self._send_json({
                        "passed": result.passed,
                        "final_score": result.final_score,
                        "revision_count": result.revision_count,
                        "audit_trail": [
                            {"stage": r.stage.value, "verdict": r.verdict.value, 
                             "score": r.score} for r in result.audit_trail
                        ],
                        "guidance": result.guidance,
                    })
                except ImportError as e:
                    self._send_json({"error": f"呼吸系统模块加载失败: {e}"}, 503)

            elif path == '/statistics':
                """医学统计诊断"""
                text = data.get('text', '')
                chapter_num = data.get('chapter_num', 1)
                try:
                    from medical_statistics import MedicalStatistics
                    stats = MedicalStatistics()
                    result = stats.comprehensive_diagnosis(text, chapter_num)
                    self._send_json(result)
                except ImportError as e:
                    self._send_json({"error": f"医学统计模块加载失败: {e}"}, 503)

            else:
                self._send_json({"error": "未知端点: " + path}, 404)

        except Exception as e:
            self._send_json({
                "error": str(e),
                "type": type(e).__name__,
            }, 500)

    def do_OPTIONS(self):
        """CORS预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        """精简日志输出"""
        print(f"[血液层] {args[0]}")


def main():
    port = 5000
    if len(sys.argv) > 2 and sys.argv[1] == '--port':
        port = int(sys.argv[2])

    server = HTTPServer(('0.0.0.0', port), PanguAPIHandler)
    print(f"""
╔══════════════════════════════════════════════════════╗
║       盘古AI血液层 HTTP服务 v1.0                     ║
║       端口: {port}                                    ║
║       数学分支: 线性代数/傅里叶/拉普拉斯/积分/马尔可夫/信息论 ║
║       http://localhost:{port}/health                    ║
╚══════════════════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[血液层] 服务已停止")
        server.shutdown()


if __name__ == '__main__':
    main()
