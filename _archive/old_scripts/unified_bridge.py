#!/usr/bin/env python3
"""
盘古统一桥梁 (Pangu Unified Bridge)

解决CLI版和API版两套系统不互通的问题。
核心思路：后端已有完整实现（rag_engine.py / observability.py），
直接复用，不重写。

复用策略：
1. RAG检索 → 直接用 backend/rag_engine.py (FAISS-HNSW + GraphRAG + COSO)
2. 质检审计 → 直接用 backend/observability.py (50个检测器类)
3. AI调用 → 优先LiteLLM，降级requests
4. 记忆管理 → CLI版MemoryBank + API版MemoryChecker
5. 项目目录 → 统一入口，优先projects/
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List


class PanguBridge:
    """盘古统一桥梁"""
    
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.projects_dir = self.base_dir / "projects"
        self.novel_libraries_dir = self.base_dir / "novel_libraries"
        self.backend_dir = self.base_dir / "backend"
        
        # 确保backend在sys.path中
        backend_str = str(self.backend_dir)
        if backend_str not in sys.path and self.backend_dir.exists():
            sys.path.insert(0, backend_str)
    
    # ============================================================
    # 1. 统一项目目录
    # ============================================================
    
    def get_project_dir(self, project_name: str) -> Path:
        """获取项目目录（统一入口）"""
        cli_dir = self.projects_dir / project_name
        if cli_dir.exists():
            return cli_dir
        api_dir = self.novel_libraries_dir / project_name
        if api_dir.exists():
            return api_dir
        return cli_dir
    
    def list_all_projects(self) -> List[Dict]:
        """列出所有项目（合并两个目录）"""
        projects = []
        if self.projects_dir.exists():
            for d in self.projects_dir.iterdir():
                if d.is_dir() and (d / "state.json").exists():
                    try:
                        state = json.loads((d / "state.json").read_text(encoding='utf-8'))
                        projects.append({
                            "name": d.name, "dir": str(d), "source": "cli",
                            "title": state.get("project_info", {}).get("title", d.name),
                            "chapters": state.get("progress", {}).get("current_chapter", 0),
                        })
                    except Exception:
                        pass
        if self.novel_libraries_dir.exists():
            for d in self.novel_libraries_dir.iterdir():
                if d.is_dir() and (d / "_writing_state.json").exists():
                    try:
                        state = json.loads((d / "_writing_state.json").read_text(encoding='utf-8'))
                        projects.append({
                            "name": d.name, "dir": str(d), "source": "api",
                            "title": d.name,
                            "chapters": len(state.get("已完成章节", [])),
                        })
                    except Exception:
                        pass
        return projects
    
    def migrate_api_to_cli(self, project_name: str) -> bool:
        """将API版项目迁移到CLI版目录结构"""
        api_dir = self.novel_libraries_dir / project_name
        cli_dir = self.projects_dir / project_name
        if not api_dir.exists() or cli_dir.exists():
            return False
        cli_dir.mkdir(parents=True, exist_ok=True)
        (cli_dir / "正文").mkdir(exist_ok=True)
        (cli_dir / "大纲").mkdir(exist_ok=True)
        for md_file in api_dir.glob("第*.md"):
            txt_name = md_file.stem + ".txt"
            content = md_file.read_text(encoding='utf-8')
            content = re.sub(r'^#\s+.*$', '', content, flags=re.MULTILINE).strip()
            (cli_dir / "正文" / txt_name).write_text(content, encoding='utf-8')
        api_state_file = api_dir / "_writing_state.json"
        if api_state_file.exists():
            api_state = json.loads(api_state_file.read_text(encoding='utf-8'))
            unified_state = self._merge_states(api_state, project_name)
            (cli_dir / "state.json").write_text(
                json.dumps(unified_state, ensure_ascii=False, indent=2), encoding='utf-8')
        return True
    
    def _merge_states(self, api_state: dict, project_name: str) -> dict:
        return {
            "project_info": {"title": project_name, "genre": "general", "platform": "qimao",
                             "current_chapter": len(api_state.get("已完成章节", [])), "total_chapters": 200},
            "characters": {}, "foreshadowing": [], "setting_log": [],
            "progress": {"current_chapter": len(api_state.get("已完成章节", []))},
            "chapter_meta": {}, "writing_state": api_state,
        }
    
    # ============================================================
    # 2. 统一RAG接口 — 直接复用backend/rag_engine.py
    # ============================================================
    
    _rag_engine = None
    
    def get_rag(self):
        """获取RAG引擎（直接复用backend/rag_engine.py）"""
        if PanguBridge._rag_engine is not None:
            return PanguBridge._rag_engine
        try:
            from rag_engine import PanguRAG
            knowledge_dir = self.base_dir / "knowledge"
            PanguBridge._rag_engine = PanguRAG(str(knowledge_dir))
            print("[Bridge] RAG引擎加载成功（FAISS-HNSW + GraphRAG）")
            return PanguBridge._rag_engine
        except ImportError as e:
            print(f"[Bridge] backend/rag_engine.py 不可用: {e}")
        except Exception as e:
            print(f"[Bridge] RAG引擎初始化失败: {e}")
        return None
    
    def search_knowledge(self, query: str, top_k: int = 3,
                         workshop: str = None) -> List[Dict]:
        """
        知识检索（统一入口）
        优先级：backend/rag_engine(FAISS-HNSW) → rag_injector(关键词) → 空
        """
        # 1. 后端RAG引擎（FAISS-HNSW + GraphRAG）
        rag = self.get_rag()
        if rag:
            try:
                if workshop:
                    results = rag.search_for_workshop(query, workshop, top_k)
                else:
                    results = rag.search(query, top_k)
                if results:
                    return results
            except Exception as e:
                print(f"[Bridge] RAG检索失败: {e}")
        
        # 2. CLI版关键词匹配降级
        try:
            from knowledge.rag_injector import get_writing_hints
            hints = get_writing_hints("general", query, "qimao", 1)
            if hints:
                return [{"category": "rag_injector", "text": hints, "score": 0.3}]
        except ImportError:
            pass
        
        return []
    
    # ============================================================
    # 3. 统一质检接口 — 直接复用backend/observability.py
    # ============================================================
    
    def full_quality_check(self, text: str, project_dir: str = None,
                           chapter_num: int = 0) -> Dict:
        """
        全量质检（统一入口）
        优先级：backend/observability(50个检测器) → CLI版QualityGate → 基础检测
        """
        results = {"checks": [], "total": 0, "passed": 0, "failed": 0, "score": 0.0}
        
        # 1. 后端AutoRewriteEngine（37+项检测）
        try:
            from observability import AutoRewriteEngine
            engine = AutoRewriteEngine()
            inspection = engine.full_inspection(text)
            if inspection:
                defects = inspection.get("defects", [])
                results["checks"].append({
                    "dim": "AutoRewrite(37+项)", "severity": "critical" if defects else "pass",
                    "detail": f"检测完成，{len(defects)}个缺陷" if defects else "37+项全部通过"
                })
                for d in defects[:10]:
                    results["checks"].append({
                        "dim": d.get("type", "unknown"), "severity": "warning",
                        "detail": d.get("description", str(d))[:100]
                    })
        except ImportError:
            # 2. CLI版QualityGate降级
            try:
                from workflow_engine import QualityGate
                qc = QualityGate.check(2, text)
                for issue in qc.get("issues", []):
                    results["checks"].append({"dim": "QualityGate", "severity": "warning", "detail": issue})
            except ImportError:
                # 3. 基础检测
                results["checks"] = self._basic_quality_check(text)
        
        total = len(results["checks"])
        passed = sum(1 for c in results["checks"] if c.get("severity") == "pass")
        failed = sum(1 for c in results["checks"] if c.get("severity") in ("critical", "warning"))
        results["total"] = total
        results["passed"] = passed
        results["failed"] = failed
        results["score"] = passed / max(total, 1)
        return results
    
    def _basic_quality_check(self, text: str) -> List[Dict]:
        """最基础的质量检测（无任何外部依赖）"""
        checks = []
        banned = ["他感到", "缓缓地", "突然", "瞳孔", "嘴角勾起", "不禁", "心中一惊"]
        found = [w for w in banned if w in text]
        checks.append({"dim": "AI味词", "severity": "critical" if found else "pass",
                       "detail": f"发现{len(found)}个: {', '.join(found[:3])}" if found else "未发现"})
        
        dialogue_lines = len(re.findall(r'[""「].*?[""」]', text))
        total_lines = max(text.count('\n') + 1, 1)
        rate = dialogue_lines / total_lines
        checks.append({"dim": "对话率", "severity": "critical" if rate < 0.35 else "pass",
                       "detail": f"{rate:.0%}"})
        
        return checks
    
    # ============================================================
    # 4. 统一记忆接口
    # ============================================================
    
    def get_memory_context(self, project_dir: str, chapter_num: int) -> str:
        """获取记忆上下文（统一入口）"""
        context_parts = []
        
        # 1. 后端MemoryChecker（InkOS 42条规则）
        try:
            from observability import MemoryChecker
            checker = MemoryChecker()
            constraint = checker.build_constraint_block(project_dir)
            if constraint:
                context_parts.append(f"【设定约束】\n{constraint[:500]}")
        except (ImportError, Exception):
            pass
        
        # 2. CLI版MemoryBank
        try:
            from memory_bank import MemoryBank
            mb = MemoryBank(project_dir)
            ctx = mb.get_context_for_chapter(chapter_num)
            if ctx:
                context_parts.append(f"【记忆银行】\n{ctx[:500]}")
        except ImportError:
            pass
        
        return "\n\n".join(context_parts) if context_parts else ""
    
    def update_memory(self, project_dir: str, chapter_num: int,
                      chapter_text: str, chapter_task: str = "", mode: str = "general"):
        """更新记忆（统一入口）"""
        # 1. CLI版MemoryBank
        try:
            from memory_bank import MemoryBank
            mb = MemoryBank(project_dir)
            mb.extract_from_chapter(chapter_num, chapter_content=chapter_text)
        except ImportError:
            pass
        
        # 2. API版WritingStateManager
        try:
            state_file = Path(project_dir) / "_writing_state.json"
            if state_file.exists():
                state = json.loads(state_file.read_text(encoding='utf-8'))
                state.setdefault("已完成章节", []).append(chapter_num)
                state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass
    
    # ============================================================
    # 5. 统一AI调用接口
    # ============================================================
    
    def get_ai_client(self, prefer_litellm: bool = True):
        """获取AI客户端（统一入口）"""
        if prefer_litellm:
            try:
                import litellm
                litellm.set_verbose = False
                return self._litellm_call
            except ImportError:
                pass
        from pangu_core.ai_client import AIClient
        from pangu_core.config import get_config
        return AIClient(get_config())
    
    def _litellm_call(self, prompt: str, system_msg: str = None,
                      model: str = None, temperature: float = 0.7,
                      max_tokens: int = 4000) -> str:
        """LiteLLM调用（兼容CLI版call_ai接口，含多模型fallback链）"""
        import litellm
        from pangu_core.config import get_config
        cfg = get_config()
        primary_model = model or cfg.model

        # 构建fallback链：主模型 → 备用模型列表 → requests降级
        fallback_models = [primary_model]
        # 从环境变量读取备用模型
        import os
        backup = os.environ.get("PANGU_BACKUP_MODELS", "")
        if backup:
            fallback_models.extend([m.strip() for m in backup.split(",") if m.strip()])

        messages = []
        if system_msg:
            messages.append({"role": "system", "content": system_msg})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for i, m in enumerate(fallback_models):
            # 自动添加provider前缀
            if "/" not in m:
                if "deepseek" in m:
                    m = f"deepseek/{m}"
                elif "gpt" in m:
                    m = f"openai/{m}"
            try:
                response = litellm.completion(
                    model=m, messages=messages, temperature=temperature,
                    max_tokens=max_tokens, api_key=cfg.api_key, api_base=cfg.base_url)
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                print(f"[LiteLLM] 模型{m}失败: {e}")
                if i < len(fallback_models) - 1:
                    print(f"[LiteLLM] 切换到备用模型: {fallback_models[i+1]}")
                continue

        # 所有LiteLLM模型都失败，降级到requests
        print(f"[LiteLLM] 全部模型失败，降级requests")
        from pangu_core.ai_client import AIClient
        return AIClient(cfg)(prompt, system_msg=system_msg)


_bridge = None

def get_bridge(base_dir: str = None) -> PanguBridge:
    global _bridge
    if _bridge is None:
        _bridge = PanguBridge(base_dir)
    return _bridge
