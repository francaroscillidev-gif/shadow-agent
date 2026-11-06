"""OpenAI-compatible FastAPI proxy server for Shadow Agent."""
import time
import json
import uuid
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from shadow_agent.core.config import ServerConfig, load_config
from shadow_agent.core.vault import EphemeralVault
from shadow_agent.engine.masker import MaskingEngine
from shadow_agent.engine.code_guard import CodeObfuscator
from shadow_agent.engine.deanonymizer import DeAnonymizer
from shadow_agent.router.policy_router import Router
from shadow_agent.storage.audit import AuditLogger
from shadow_agent.storage.cache import SemanticCache

def create_app(config: ServerConfig = None) -> FastAPI:
    if config is None:
        config = load_config()

    app = FastAPI(
        title="Shadow Agent Proxy",
        description="Local Privacy Guard & Masking Proxy for LLMs",
        version="0.1.0"
    )

    vault = EphemeralVault(ttl_seconds=3600)
    masker = MaskingEngine(use_synthetic=config.privacy.synthetic_replacement)
    code_guard = CodeObfuscator(use_synthetic=config.privacy.synthetic_replacement)
    deanonymizer = DeAnonymizer(vault)
    router = Router(config)
    audit = AuditLogger(config.audit_log_path)
    cache = SemanticCache() if config.privacy.enable_cache else None
    client = httpx.AsyncClient(timeout=120.0)

    @app.get("/health")
    async def health():
        return {
            "status": "active",
            "active_vault_entries": len(vault.get_all_mappings()),
            "cache_stats": cache.stats() if cache else {"status": "disabled"},
            "cloud_upstream": config.upstream.cloud_url,
            "local_upstream": config.upstream.local_url
        }

    @app.get("/v1/models")
    async def list_models():
        """Returns standard list of available models including local and cloud aliases."""
        return {
            "object": "list",
            "data": [
                {"id": "shadow-auto", "object": "model", "owned_by": "shadow-agent"},
                {"id": config.upstream.cloud_default_model, "object": "model", "owned_by": "cloud"},
                {"id": config.upstream.local_default_model, "object": "model", "owned_by": "local-ollama"},
            ]
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        start_time = time.time()
        req_id = str(uuid.uuid4())
        
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        messages = body.get("messages", [])
        is_stream = body.get("stream", False)
        requested_model = body.get("model", "shadow-auto")

        # 1. Masking Phase
        total_masked_entities = []
        sanitized_messages = []

        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                # Standard PII & Secret Masking
                masked_content, detected = masker.mask(content, vault)
                total_masked_entities.extend(detected)
                
                # Code & Database Connection Masking
                masked_content, code_detected = code_guard.detect_and_mask(masked_content, vault)
                total_masked_entities.extend(code_detected)

                sanitized_messages.append({**msg, "content": masked_content})
            else:
                sanitized_messages.append(msg)

        # 2. Intelligent Routing Phase
        destination, target_model, route_meta = router.inspect_and_route(messages, len(total_masked_entities))
        
        # Override model if requested specifically
        if requested_model not in ("shadow-auto", "default"):
            effective_model = requested_model
        else:
            effective_model = target_model

        # Determine upstream target
        if destination == "local":
            upstream_url = f"{config.upstream.local_url.rstrip('/')}/chat/completions"
            auth_header = f"Bearer {config.upstream.local_api_key}"
            payload_messages = sanitized_messages
        else:
            upstream_url = f"{config.upstream.cloud_url.rstrip('/')}/chat/completions"
            auth_header = f"Bearer {config.upstream.cloud_api_key or ''}"
            payload_messages = sanitized_messages

        # Check Cache before upstream dispatch for non-streaming requests
        if not is_stream and cache:
            cached_resp = cache.get(effective_model, sanitized_messages)
            if cached_resp:
                # De-anonymize cached response with current session's vault
                data = json.loads(json.dumps(cached_resp))
                if "choices" in data:
                    for choice in data["choices"]:
                        if "message" in choice and "content" in choice["message"]:
                            choice["message"]["content"] = deanonymizer.restore_batch(choice["message"]["content"])
                data["_shadow_cached"] = True
                return JSONResponse(content=data)

        forward_body = {
            **body,
            "model": effective_model,
            "messages": payload_messages
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header
        }

        # 3. Upstream Dispatch
        if is_stream:
            async def event_generator():
                try:
                    async with client.stream("POST", upstream_url, json=forward_body, headers=headers) as resp:
                        if resp.status_code != 200:
                            err_content = await resp.aread()
                            yield f"data: {json.dumps({'error': err_content.decode('utf-8', errors='ignore')})}\n\n"
                            yield "data: [DONE]\n\n"
                            return

                        async def raw_chunks():
                            async for raw_bytes in resp.aiter_bytes():
                                yield raw_bytes.decode("utf-8", errors="ignore")

                        # Pass raw chunks through sliding-window streaming de-anonymizer
                        async for restored_chunk in deanonymizer.restore_stream(raw_chunks()):
                            yield restored_chunk
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    yield "data: [DONE]\n\n"

            # Log audit record
            audit.log_transaction(
                request_id=req_id,
                destination=destination,
                model=effective_model,
                entities_masked=len(total_masked_entities),
                entity_types=[e.entity_type for e in total_masked_entities],
                route_meta=route_meta,
                raw_prompt_preview=str(messages[:1]),
                latency_ms=(time.time() - start_time) * 1000
            )

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        else:
            # Batch mode
            try:
                resp = await client.post(upstream_url, json=forward_body, headers=headers)
                latency = (time.time() - start_time) * 1000
                
                audit.log_transaction(
                    request_id=req_id,
                    destination=destination,
                    model=effective_model,
                    entities_masked=len(total_masked_entities),
                    entity_types=[e.entity_type for e in total_masked_entities],
                    route_meta=route_meta,
                    raw_prompt_preview=str(messages[:1]),
                    latency_ms=latency
                )

                if resp.status_code != 200:
                    return JSONResponse(status_code=resp.status_code, content=resp.json() if resp.headers.get("content-type") == "application/json" else {"error": resp.text})

                data = resp.json()

                # Save raw sanitized response to cache
                if cache and "choices" in data:
                    cache.set(effective_model, sanitized_messages, data)
                
                # De-anonymize output choices
                if "choices" in data:
                    for choice in data["choices"]:
                        if "message" in choice and "content" in choice["message"]:
                            choice["message"]["content"] = deanonymizer.restore_batch(choice["message"]["content"])

                return JSONResponse(content=data)

            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Upstream communication error: {str(e)}")

    return app
