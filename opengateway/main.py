from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from opengateway.auth import AuthService, VirtualKey
from opengateway.config import get_settings
from opengateway.providers.base import ChatRequest
from opengateway.providers.openai import OpenAIProvider
from opengateway.router import Router

from pydantic import BaseModel, ConfigDict
from typing import Any


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stream: bool = False

    model_config = ConfigDict(extra="allow")


# --- Dependencies ---

def get_auth_service() -> AuthService:
    settings = get_settings()
    return AuthService(root_key=settings.root_key)


def get_router() -> Router:
    return Router()


async def get_virtual_key(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> VirtualKey:
    return await auth.authenticate(request)


# --- App ---

app = FastAPI(
    title="OpenGateway",
    version="0.1.0",
    description="Open-source AI gateway. All features free.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    virtual_key: VirtualKey = Depends(get_virtual_key),
    router: Router = Depends(get_router),
):
    if not virtual_key.has_model_access(body.model):
        raise HTTPException(status_code=403, detail="Model not allowed for this key")

    if not virtual_key.is_within_budget():
        raise HTTPException(status_code=429, detail="Budget exceeded")

    provider = router.select_provider(body.model)
    if provider is None:
        raise HTTPException(status_code=400, detail=f"Unknown model: {body.model}")

    chat_req = ChatRequest(
        model=body.model,
        messages=body.messages,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        top_p=body.top_p,
        stream=body.stream,
        extra=body.model_dump(exclude={"model", "messages", "temperature", "max_tokens", "top_p", "stream"}),
    )

    if body.stream:
        async def stream_generator():
            async for chunk in provider.chat_stream(chat_req):
                yield f"data: {chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
        )

    response = await provider.chat(chat_req)
    return JSONResponse(
        content={
            "id": response.id,
            "object": "chat.completion",
            "created": 0,
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response.content},
                    "finish_reason": response.finish_reason,
                }
            ],
            "usage": response.usage,
        }
    )


def cli() -> None:
    """CLI entry point for `opengateway` command."""
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "opengateway.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.debug,
    )
