import logging
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0
    provider: str = ""
    model: str = ""


class LLMClient:
    def __init__(
        self,
        enabled: bool = False,
        provider: str = "openai",
        api_key: str = "",
        api_base: str = "",
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        timeout: int = 30,
    ):
        self.enabled = enabled
        self.provider = provider.lower()
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        if not self.api_key:
            logger.warning("LLM is enabled but no API key configured")
            return False
        return True

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }

        if self.provider == "openai":
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.provider in ["zhipu", "glm"]:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.provider == "qwen" or self.provider == "dashscope":
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.provider == "openrouter":
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _get_api_base(self) -> str:
        if self.api_base:
            return self.api_base.rstrip("/")

        if self.provider == "openai":
            return "https://api.openai.com/v1"
        elif self.provider in ["zhipu", "glm"]:
            return "https://open.bigmodel.cn/api/paas/v4"
        elif self.provider == "qwen" or self.provider == "dashscope":
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"
        elif self.provider == "openrouter":
            return "https://openrouter.ai/api/v1"

        return "https://api.openai.com/v1"

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        start_time = time.time()

        if not self.is_available():
            return LLMResponse(
                success=False,
                error="LLM not configured or disabled",
                provider=self.provider,
                model=self.model,
            )

        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        api_base = self._get_api_base()
        url = f"{api_base}/chat/completions"

        payload = {
            "model": self.model,
            "messages": all_messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }

        try:
            import httpx

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                )

                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"LLM API error: {error_msg}")
                    return LLMResponse(
                        success=False,
                        error=error_msg,
                        provider=self.provider,
                        model=self.model,
                        duration_ms=int((time.time() - start_time) * 1000),
                    )

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    f"LLM call succeeded: {self.provider}/{self.model} in {duration_ms}ms"
                )

                return LLMResponse(
                    success=True,
                    content=content,
                    provider=self.provider,
                    model=self.model,
                    duration_ms=duration_ms,
                )

        except httpx.TimeoutException:
            error_msg = f"LLM request timeout after {self.timeout}s"
            logger.error(error_msg)
            return LLMResponse(
                success=False,
                error=error_msg,
                provider=self.provider,
                model=self.model,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            error_msg = f"LLM request failed: {str(e)}"
            logger.error(error_msg)
            return LLMResponse(
                success=False,
                error=error_msg,
                provider=self.provider,
                model=self.model,
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def analyze_logs(
        self,
        logs: str,
        error_code: Optional[str] = None,
        failure_phase: Optional[str] = None,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        system_prompt = """你是一个部署运维专家，擅长分析部署失败日志并给出实用的排查建议。

请分析以下部署失败日志，回答以下问题：
1. 你认为失败的根本原因是什么？
2. 最可能的问题出在哪里？
3. 你建议用户先检查什么？
4. 有哪些具体的命令可以帮助排查？

请以 JSON 格式返回，包含以下字段：
{
  "root_cause": "根本原因分析（简短）",
  "likely_problem": "最可能的问题",
  "first_checks": ["第一条检查", "第二条检查", "第三条检查"],
  "debug_commands": ["命令1", "命令2"],
  "explanation": "详细解释（用中文，通俗易懂）"
}

请只返回 JSON，不要有其他内容。"""

        user_message = f"""部署失败信息：
- 错误码: {error_code or '未知'}
- 失败阶段: {failure_phase or '未知'}

日志内容（截取最后部分）：
```
{logs[-15000:] if len(logs) > 15000 else logs}
```"""

        response = self.chat_completion(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )

        if not response.success:
            return {
                "llm_analysis_failed": True,
                "llm_error": response.error,
            }

        try:
            parsed = json.loads(response.content)
            return {
                "llm_analysis": parsed,
                "llm_provider": response.provider,
                "llm_model": response.model,
                "llm_duration_ms": response.duration_ms,
            }
        except json.JSONDecodeError:
            return {
                "llm_analysis_failed": True,
                "llm_error": "Failed to parse LLM response as JSON",
                "llm_raw_response": response.content[:500],
            }

    def generate_deploy_commands(
        self,
        project_summary: Dict[str, Any],
        system_info: Dict[str, Any],
        docs_context: List[Dict[str, str]],
        user_goal: Optional[str] = None,
        preferred_shell: Optional[str] = None,
        extra_context: Optional[str] = None,
        max_tokens: int = 2200,
    ) -> Dict[str, Any]:
        system_prompt = """你是一个资深部署工程师。你的任务是基于项目配置、README/docs 文档、以及目标机器运行时信息，生成一组可执行的部署命令。

要求：
1. 命令必须尽量贴合检测到的系统环境，例如 Linux/macOS/Windows、shell、docker compose 形式。
2. 优先生成保守、安全、可解释的命令，不要假设文档中没有出现的秘密值。
3. 如果信息不足，明确写出 assumptions，不要编造。
4. 输出必须是 JSON，字段如下：
{
  "assumptions": ["假设1", "假设2"],
  "prechecks": ["检查命令或检查项1", "检查项2"],
  "commands": [
    {
      "title": "步骤标题",
      "command": "具体命令",
      "purpose": "这一条命令的作用"
    }
  ],
  "verification": ["验证项1", "验证项2"],
  "explanation": "简要说明，中文"
}
5. command 字段里可以包含多行命令，但必须是完整可执行片段。
6. 如果检测到 docker compose plugin，则优先用 `docker compose`；如果检测到 docker-compose，则优先用 `docker-compose`。
7. 如果 shell 或系统信息不足，命令应保持尽量通用，并在 assumptions 中说明。"""

        docs_payload = []
        for item in docs_context:
            docs_payload.append(
                {
                    "path": item.get("path"),
                    "content": item.get("content", "")[:6000],
                }
            )

        user_message = json.dumps(
            {
                "project_summary": project_summary,
                "system_info": system_info,
                "user_goal": user_goal,
                "preferred_shell": preferred_shell,
                "extra_context": extra_context,
                "docs_context": docs_payload,
            },
            ensure_ascii=False,
            indent=2,
        )

        response = self.chat_completion(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )

        if not response.success:
            return {
                "llm_generation_failed": True,
                "llm_error": response.error,
            }

        try:
            parsed = json.loads(response.content)
            return {
                "plan": parsed,
                "llm_provider": response.provider,
                "llm_model": response.model,
                "llm_duration_ms": response.duration_ms,
            }
        except json.JSONDecodeError:
            return {
                "llm_generation_failed": True,
                "llm_error": "Failed to parse LLM response as JSON",
                "llm_raw_response": response.content[:1000],
            }
