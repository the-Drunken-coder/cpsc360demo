import json

from fastapi import FastAPI, Header, HTTPException

app = FastAPI()


@app.get('/v1/models')
def models():
    return {'data': [
        {'id': 'deepseek-v4.1-flash', 'api': {'chat-completions': {}}},
        {'id': 'glm-5.3-flash', 'api': {'chat-completions': {}}},
        {'id': 'glm-5.3-flash', 'api': {'chat-completions': {}}},
        {'id': 'messages-only', 'api': {'messages': {}}},
    ]}


@app.post('/openai/v1/chat/completions')
def complete(body: dict, x_opencode_session: str | None = Header(default=None)):
    if not x_opencode_session:
        raise HTTPException(400, 'Missing session header')
    narrative = body['messages'][-1]['content']
    content = {'hazards': [
        {'hazard': 'fire', 'evidence': [narrative[:100]]},
        {'hazard': 'burn', 'evidence': ['Invented stub evidence that does not occur in a real narrative.']},
        {'hazard': 'invented_hazard', 'evidence': [narrative[:100]]},
    ]}
    return {'choices': [{'message': {'content': '```json\n' + json.dumps(content) + '\n```'}}]}
