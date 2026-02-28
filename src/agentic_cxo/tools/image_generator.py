"""
Image Generation Tool — the CMO's creative engine.

Generates images for campaigns, social posts, landing pages,
and ads using DALL-E or Nano Banana.
"""

from __future__ import annotations

import os
from typing import Any

from agentic_cxo.integrations.live.base import CredentialStore
from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult


class ImageGeneratorTool(BaseTool):
    @property
    def name(self) -> str:
        return "image_generator"

    @property
    def description(self) -> str:
        return (
            "Generate images for marketing campaigns, social posts, "
            "ads, banners, and landing pages. Uses DALL-E or Nano Banana. "
            "Describe what you need and the tool creates it."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(
                name="prompt",
                description="Description of the image to generate",
            ),
            ToolParam(
                name="provider",
                description="dalle or nano_banana (default: auto)",
                required=False,
            ),
        ]

    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "generate image", "create image", "make image",
            "create banner", "design", "generate creative",
            "create ad", "make a poster", "generate logo",
            "create visual", "image for", "banner for",
            "creative for", "design for",
        ]

    def execute(self, prompt: str = "", provider: str = "auto", **kwargs: Any) -> ToolResult:
        if not prompt:
            return ToolResult(tool_name=self.name, success=False, error="Prompt required")

        cred_store = CredentialStore()

        if provider == "auto":
            if os.getenv("OPENAI_API_KEY"):
                provider = "dalle"
            elif cred_store.is_connected("nano_banana"):
                provider = "nano_banana"
            else:
                provider = "dalle"

        if provider == "dalle":
            return self._generate_dalle(prompt, cred_store)
        elif provider == "nano_banana":
            return self._generate_nano_banana(prompt, cred_store)
        return ToolResult(tool_name=self.name, success=False, error=f"Unknown provider: {provider}")

    def _generate_dalle(self, prompt: str, cred_store: CredentialStore) -> ToolResult:
        import httpx

        api_key = os.getenv("OPENAI_API_KEY", "")
        creds = cred_store.load("dalle")
        if creds:
            api_key = creds.get("api_key", api_key)

        if not api_key:
            return ToolResult(self.name, False, error="No OpenAI API key. Set OPENAI_API_KEY or connect DALL-E in Settings.")

        try:
            resp = httpx.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1024x1024"},
                timeout=60,
            )
            data = resp.json()
            if resp.status_code == 200:
                images = data.get("data", [])
                url = images[0].get("url", "") if images else ""
                return ToolResult(
                    self.name, True,
                    data={"url": url, "provider": "dall-e-3", "prompt": prompt},
                    summary=f"Image generated with DALL-E: {url[:80]}...",
                )
            return ToolResult(self.name, False, error=data.get("error", {}).get("message", "Failed"))
        except Exception as e:
            return ToolResult(self.name, False, error=str(e))

    def _generate_nano_banana(self, prompt: str, cred_store: CredentialStore) -> ToolResult:
        import httpx

        creds = cred_store.load("nano_banana")
        api_key = creds.get("api_key", "") if creds else os.getenv("NANO_BANANA_API_KEY", "")

        if not api_key:
            return ToolResult(self.name, False, error="No Nano Banana API key. Connect in Settings.")

        try:
            resp = httpx.post(
                "https://api.nanobananaapi.dev/v1/images/generate",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"prompt": prompt, "num": 1, "model": "gemini-2.5-flash-image-preview", "image_size": "16:9"},
                timeout=60,
            )
            data = resp.json()
            if data.get("code") == 0:
                images = data.get("data", [])
                return ToolResult(
                    self.name, True,
                    data={"images": images, "provider": "nano_banana", "prompt": prompt},
                    summary="Image generated with Nano Banana",
                )
            return ToolResult(self.name, False, error=data.get("message", "Failed"))
        except Exception as e:
            return ToolResult(self.name, False, error=str(e))
