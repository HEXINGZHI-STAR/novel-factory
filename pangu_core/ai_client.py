"""
盘古AI - 多Provider AI调用客户端

Provider 架构:
- DeepSeek / OpenAI-compatible → OpenAICompatibleProvider
- Claude / Anthropic Messages API → AnthropicProvider

路由规则（自动检测）:
- model 以 "claude" / "anthropic" 开头 → AnthropicProvider
- 其他 → OpenAICompatibleProvider（默认）

Stage 级路由:
- Config.stage_model_map 可为每个 Stage 指定不同模型
- 实现 "DeepSeek 打骨架(W2) + Claude 做精装(W4)" 的分层策略

用法:
    client = AIClient()
    # 自动路由到 DeepSeek
    result = client(prompt, model="deepseek-chat", system_msg="你是小说家")
    # 自动路由到 Claude
    result = client(prompt, model="claude-sonnet-4-6-20250514", system_msg="你是小说家")
    # Stage 感知调用（自动从 Config.stage_model_map 查找模型）
    result = client.stage_call(prompt, stage_id="W4", system_msg="你是小说家")
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from .config import get_config

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ============ AI输出清理（不变） ============

_CLEANUP_RULES = [
    (r'^```(?:\w+)?\s*\n?', ''),
    (r'\n?```\s*$', ''),
    (r'^\s+', ''),
    (r'\s+$', ''),
    (r'^(?:好的|以下是|根据|基于|作为|我理解|我来|让我|下面)[，,]?\s*(?:为你|我|帮|给|开始|来)?\s*(?:写|生成|创作|续写|展开|描述|呈现|输出|提供)[^\n]*\n', ''),
    (r'^[【\[]?(?:正文|小说|章节|内容|故事|开始)[】\]]?[：:]*\s*\n', ''),
    (r'\n(?:---+|===+)?\s*\n(?:以上|希望|如果|需要|可以|欢迎|祝|感谢|备注|说明|注：)[\s\S]*$', ''),
    (r'^第\d+章[^\n]*\n', ''),
]

_COMPILED_RULES = [(re.compile(p, re.MULTILINE), r) for p, r in _CLEANUP_RULES]


def clean_ai_output(text: str) -> str:
    """清理AI输出中的冗余内容。"""
    if not text:
        return ""
    result = text.strip()
    for pattern, replacement in _COMPILED_RULES:
        result = pattern.sub(replacement, result)
    return result.strip()


# ============ Provider 类型判断 ============

_ANTHROPIC_MODEL_PREFIXES = ("claude", "anthropic", "claude-")


def _is_anthropic_model(model: str) -> bool:
    """根据模型名判断是否为 Anthropic/Claude 模型。"""
    return model.lower().startswith(_ANTHROPIC_MODEL_PREFIXES)


# ============ Provider 抽象基类 ============

class AIProvider(ABC):
    """AI Provider 抽象基类。

    所有 Provider 实现统一的 call() 接口，
    AIClient 据此无差别路由。
    """

    @abstractmethod
    def call(
        self,
        messages: list,
        system_msg: Optional[str],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        retry_times: int,
    ) -> Optional[str]:
        """调用 AI 并返回生成的文本，失败返回 None。"""
        ...


# ============ OpenAI-Compatible Provider ============

class OpenAICompatibleProvider(AIProvider):
    """OpenAI-compatible API Provider。

    支持: DeepSeek, OpenAI, 及所有兼容 /v1/chat/completions 的服务。
    """

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def call(
        self,
        messages: list,
        system_msg: Optional[str],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        retry_times: int,
    ) -> Optional[str]:
        if not self.api_key:
            print("[ERROR] 未配置 OpenAI-compatible API Key！")
            return None

        # 构建消息列表
        api_messages = []
        if system_msg:
            api_messages.append({"role": "system", "content": system_msg})
        api_messages.extend(messages)

        last_error = None
        for attempt in range(retry_times):
            try:
                if attempt > 0:
                    print(f"  重试 {attempt}/{retry_times}...")
                    time.sleep(min(2 ** attempt, 10))

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                data = {
                    "model": model,
                    "messages": api_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }

                sys_label = f"(system:{len(system_msg)}字) " if system_msg else ""
                print(f"  [AI/OpenAI] {model} {sys_label}...")

                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=data,
                    headers=headers,
                    timeout=timeout,
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    return clean_ai_output(content)
                elif response.status_code == 429:
                    wait = min(30, 5 * (attempt + 1))
                    print(f"  [AI/OpenAI] 限流(429)，等待{wait}秒...")
                    time.sleep(wait)
                else:
                    print(f"  [AI/OpenAI] HTTP {response.status_code}: {response.text[:200]}")

            except requests.exceptions.Timeout:
                last_error = "timeout"
                print(f"  [AI/OpenAI] 超时，重试...")
            except Exception as e:
                last_error = str(e)
                print(f"  [AI/OpenAI] 调用失败: {e}")

        print(f"  [AI/OpenAI] 全部重试失败 ({retry_times}次)")
        return None


# ============ Anthropic (Claude) Provider ============

class AnthropicProvider(AIProvider):
    """Anthropic Messages API Provider。

    使用原生 Anthropic Messages API (POST /v1/messages)。
    system 作为顶层字段传入，而非消息角色。
    """

    def __init__(self, api_key: str, base_url: str, api_version: str = "2023-06-01"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version

    def call(
        self,
        messages: list,
        system_msg: Optional[str],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        retry_times: int,
    ) -> Optional[str]:
        if not self.api_key:
            print("[ERROR] 未配置 Anthropic API Key！")
            return None

        # Anthropic 要求 max_tokens 必填，且 ≤ 模型上限
        max_tokens = max_tokens or 4096

        last_error = None
        for attempt in range(retry_times):
            try:
                if attempt > 0:
                    print(f"  重试 {attempt}/{retry_times}...")
                    time.sleep(min(2 ** attempt, 15))

                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": self.api_version,
                    "Content-Type": "application/json",
                }

                body: Dict[str, Any] = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": messages,
                }

                if system_msg:
                    body["system"] = system_msg

                if temperature > 0:
                    body["temperature"] = temperature

                sys_label = f"(system:{len(system_msg)}字) " if system_msg else ""
                print(f"  [AI/Claude] {model} {sys_label}...")

                response = requests.post(
                    f"{self.base_url}/messages",
                    json=body,
                    headers=headers,
                    timeout=timeout,
                )

                if response.status_code == 200:
                    result = response.json()
                    # Anthropic 返回 content 数组
                    content_blocks = result.get("content", [])
                    text_parts = []
                    for block in content_blocks:
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                    content = "".join(text_parts)
                    if not content:
                        print(f"  [AI/Claude] 响应中无文本内容")
                        return None
                    return clean_ai_output(content)
                elif response.status_code == 429:
                    wait = min(30, 5 * (attempt + 1))
                    print(f"  [AI/Claude] 限流(429)，等待{wait}秒...")
                    time.sleep(wait)
                elif response.status_code == 400:
                    print(f"  [AI/Claude] HTTP 400: {response.text[:300]}")
                    # 400 通常是参数错误，不重试
                    return None
                else:
                    print(f"  [AI/Claude] HTTP {response.status_code}: {response.text[:200]}")

            except requests.exceptions.Timeout:
                last_error = "timeout"
                print(f"  [AI/Claude] 超时，重试...")
            except Exception as e:
                last_error = str(e)
                print(f"  [AI/Claude] 调用失败: {e}")

        print(f"  [AI/Claude] 全部重试失败 ({retry_times}次)")
        return None


# ============ 多Provider统一客户端 ============

class AIClient:
    """多Provider统一AI调用客户端。

    自动根据模型名路由到正确的 Provider。
    支持 Stage 感知模型选择。

    用法:
        client = AIClient()

        # 自动路由
        result = client("写一段小说", model="deepseek-chat")
        result = client("写一段小说", model="claude-sonnet-4-6-20250514")

        # Stage 路由（从 Config.stage_model_map 获取模型）
        result = client.stage_call("写一段小说", stage_id="W4")
    """

    def __init__(self, config=None):
        self._config = config or get_config()
        self._call_count = 0
        self._total_tokens_estimate = 0
        self._provider_cache: Dict[str, AIProvider] = {}

    @property
    def call_count(self) -> int:
        return self._call_count

    def _get_provider(self, model: str) -> tuple:
        """根据模型名获取对应的 Provider 和实际使用的模型名。

        Returns:
            (AIProvider, resolved_model_name)
        """
        cfg = self._config

        if _is_anthropic_model(model):
            # Claude → AnthropicProvider
            provider = self._provider_cache.get("anthropic")
            if provider is None:
                provider = AnthropicProvider(
                    api_key=cfg.anthropic_api_key,
                    base_url=cfg.anthropic_base_url,
                )
                self._provider_cache["anthropic"] = provider

            # 使用 anthropic 的配置参数
            resolved_model = model or cfg.anthropic_model
            return provider, resolved_model

        else:
            # 其他 → OpenAICompatibleProvider
            provider = self._provider_cache.get("openai_compatible")
            if provider is None:
                provider = OpenAICompatibleProvider(
                    api_key=cfg.api_key,
                    base_url=cfg.base_url,
                )
                self._provider_cache["openai_compatible"] = provider

            resolved_model = model or cfg.model
            return provider, resolved_model

    def _get_params_for_provider(self, is_anthropic: bool) -> dict:
        """获取当前 Provider 对应的参数。"""
        cfg = self._config
        if is_anthropic:
            return {
                "temperature": cfg.temperature,
                "max_tokens": cfg.anthropic_max_tokens,
                "timeout": cfg.anthropic_timeout,
                "retry_times": cfg.anthropic_retry_times,
            }
        else:
            return {
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
                "timeout": cfg.timeout,
                "retry_times": cfg.retry_times,
            }

    def __call__(
        self,
        prompt: str,
        model: str = None,
        system_msg: str = None,
    ) -> Optional[str]:
        """调用AI生成（自动路由到正确的 Provider）。

        Args:
            prompt: 用户消息内容
            model: 模型名。None=使用默认。以 "claude" 开头自动走 Anthropic。
            system_msg: 系统消息（可选，推荐提供以提高质量）

        Returns:
            清理后的AI生成文本，失败返回 None
        """
        if not HAS_REQUESTS:
            print("[ERROR] 未安装requests库，无法调用AI")
            return None

        cfg = self._config
        model = model or cfg.model

        # 路由到 Provider
        provider, resolved_model = self._get_provider(model)
        is_anthropic = isinstance(provider, AnthropicProvider)
        params = self._get_params_for_provider(is_anthropic)

        # 构建消息列表
        messages = [{"role": "user", "content": prompt}]

        # 调用 Provider
        content = provider.call(
            messages=messages,
            system_msg=system_msg,
            model=resolved_model,
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
            timeout=params["timeout"],
            retry_times=params["retry_times"],
        )

        if content:
            self._call_count += 1
            self._total_tokens_estimate += len(prompt) // 4 + len(content) // 4

        return content

    def stage_call(
        self,
        prompt: str,
        stage_id: str,
        system_msg: str = None,
    ) -> Optional[str]:
        """Stage 感知调用：从 Config.stage_model_map 查找该 Stage 的模型。

        如果 stage_model_map 中配置了该 Stage，使用指定模型；
        否则使用默认模型。

        Args:
            prompt: 用户消息内容
            stage_id: Stage ID（"W0"-"W5"）
            system_msg: 系统消息

        Returns:
            清理后的AI生成文本
        """
        cfg = self._config
        model = cfg.get_model_for_stage(stage_id)
        print(f"  [StageRouter] {stage_id} → {model}")
        return self(prompt, model=model, system_msg=system_msg)


# ============ 全局便捷函数（向后兼容）============

_default_client: Optional[AIClient] = None


def _get_default_client() -> AIClient:
    """获取默认客户端（懒初始化）"""
    global _default_client
    if _default_client is None:
        _default_client = AIClient()
    return _default_client


def call_ai(
    prompt: str,
    model: str = None,
    system_msg: str = None,
    stage_id: str = None,
) -> Optional[str]:
    """全局便捷函数：调用AI生成。向后兼容旧版 call_ai()。

    Args:
        prompt: 用户消息内容
        model: 模型名。None=使用默认。支持 Stage 路由。
        system_msg: 系统消息
        stage_id: 可选 Stage ID（"W2"/"W4"等），用于 Stage 级模型路由。
                  传入后从 Config.stage_model_map 查找该 Stage 的模型。
    """
    client = _get_default_client()
    if stage_id:
        return client.stage_call(prompt, stage_id=stage_id, system_msg=system_msg)
    return client(prompt, model=model, system_msg=system_msg)


def reset_ai_client():
    """重置全局客户端（主要用于测试）"""
    global _default_client
    _default_client = None
