import os
import time

import httpx

# Open weights, cheap, and served in the US/EU, so it works under Go's default region setting.
DEFAULT_MODEL = 'glm-5.3-flash'
DEFAULT_BASE_URL = 'https://opencode.ai/inference/go'
_model_cache: tuple[str, float, list[str]] | None = None


class UpstreamError(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def base_url():
    return os.environ.get('CPSC360_OPENCODE_GO_BASE_URL', DEFAULT_BASE_URL).rstrip('/')


async def request(method, path, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.request(method, base_url() + path, **kwargs)
    except httpx.HTTPError as exc:
        raise UpstreamError('OpenCode Go request failed', 502) from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise UpstreamError('OpenCode Go returned an invalid response', response.status_code) from exc
    if response.is_error:
        error = data.get('error', {}) if isinstance(data, dict) else {}
        message = error.get('message', 'OpenCode Go request failed') if isinstance(error, dict) else str(error)
        raise UpstreamError(str(message), response.status_code)
    return data


async def list_chat_models():
    global _model_cache
    base = base_url()
    if _model_cache and _model_cache[0] == base and time.monotonic() < _model_cache[1]:
        return _model_cache[2]
    data = await request('GET', '/v1/models')
    try:
        ids = sorted({item['id'] for item in data['data'] if 'chat-completions' in item.get('api', {})})
        if not all(isinstance(model, str) for model in ids):
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise UpstreamError('OpenCode Go returned an invalid model list', 502) from exc
    _model_cache = (base, time.monotonic() + 600, ids)
    return ids


async def chat_complete(key, model, messages, session):
    data = await request('POST', '/openai/v1/chat/completions',
                         headers={'Authorization': f'Bearer {key}', 'x-opencode-session': session},
                         json={'model': model, 'messages': messages, 'temperature': 0})
    try:
        content = data['choices'][0]['message']['content']
        if not isinstance(content, str):
            raise ValueError()
        return content
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise UpstreamError('OpenCode Go returned an invalid chat response', 502) from exc
