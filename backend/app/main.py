import hashlib
import json
import logging
import os
import asyncio
from uuid import UUID
import jwt
import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from pydantic import ValidationError
from app.routers.api import router, Error, insert
from app.db import connection
from app.config import MEDIA_ROOT, JWT_SECRET

app = FastAPI(title='邻宠帮', version='0.2')
app.include_router(router)

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.exception_handler(Error)
async def domain_error(request, exc):
    return JSONResponse({'code': exc.code, 'message': exc.message}, status_code=exc.status)

@app.exception_handler(RequestValidationError)
@app.exception_handler(ValidationError)
async def validation(request, exc):
    return JSONResponse({'code': 'validation_error', 'message': '字段格式或业务输入不合法'}, status_code=422)

@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse({'code': 'not_found' if exc.status_code == 404 else 'invalid_request', 'message': str(exc.detail)}, status_code=exc.status_code)

async def transaction(request: Request, call_next):
    if request.url.path in ['/health', '/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc']:
        return await call_next(request)
    try:
        parts = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 6 * 1024 * 1024:
                raise Error(413, 'file_too_large')
            parts.append(chunk)
        raw = b''.join(parts)
        request._body = raw
        is_json = 'application/json' in request.headers.get('content-type', '')
        if is_json:
            try:
                body = json.loads(raw)
            except ValueError:
                raise Error(400, 'invalid_request')
            if isinstance(body, dict) and 'verification_status' in body and request.url.path != '/api/v0/helpers/me':
                raise Error(403, 'verification_read_only')
        key = request.headers.get('Idempotency-Key')
        if request.method not in ['POST', 'PUT', 'PATCH', 'DELETE']:
            key = None
        if key:
            try:
                key = str(UUID(key))
            except ValueError:
                raise Error(422, 'validation_error', 'Idempotency-Key 必须为 UUID')
        actor = None
        auth = request.headers.get('authorization', '')
        if auth:
            try:
                if auth.split(' ', 1)[0].lower() != 'bearer':
                    raise ValueError()
                actor = UUID(jwt.decode(auth.split(' ', 1)[1], JWT_SECRET, algorithms=['HS256'], options={'require': ['exp', 'sub']})['sub'])
            except (ValueError, IndexError, jwt.PyJWTError):
                raise Error(401, 'unauthorized')
        canonical = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode() if is_json else raw
        digest = hashlib.sha256(canonical).hexdigest()
        operation = request.method + ' ' + request.url.path
        op_hash = hashlib.sha256(operation.encode()).hexdigest()[:60]
        ident = hashlib.sha256((str(actor) + operation + str(key)).encode()).hexdigest()
        cache = MEDIA_ROOT / '.idempotency' / ident
        with connection() as c:
            request.state.db = c
            if actor and not c.execute('SELECT 1 FROM "User" WHERE id=%s AND deleted_at IS NULL', (actor,)).fetchone():
                raise Error(401, 'unauthorized')
            if key:
                c.execute('SELECT pg_advisory_xact_lock(%s)', (int(ident[:15], 16),))
                if cache.exists():
                    saved = json.loads(cache.read_text(encoding='utf8'))
                    if saved['hash'] != digest:
                        raise Error(409, 'idempotency_conflict')
                    return Response(saved['body'], status_code=saved['status'], media_type='application/json')
                old = c.execute('SELECT request_hash,response_snapshot FROM "TaskEvent" WHERE actor_id IS NOT DISTINCT FROM %s AND operation=%s AND idempotency_key=%s', (actor, op_hash, key)).fetchone()
                if old:
                    if old['request_hash'] != digest:
                        raise Error(409, 'idempotency_conflict')
                    saved = old['response_snapshot']
                    return JSONResponse(saved['body'], status_code=saved['status']) if saved['status'] != 204 else Response(status_code=204)
            response = await call_next(request)
            content = b''.join([chunk async for chunk in response.body_iterator])
            if response.status_code >= 400:
                c.rollback()
            elif key:
                result = json.loads(content) if content else None
                rid = None
                if request.url.path == '/api/v0/requests' and request.method == 'POST':
                    rid = result['id']
                elif request.url.path.startswith('/api/v0/requests/'):
                    try:
                        rid = str(UUID(request.url.path.split('/')[4]))
                    except (ValueError, IndexError):
                        pass
                if rid:
                    r = c.execute('SELECT * FROM "ServiceRequest" WHERE id=%s', (rid,)).fetchone()
                    insert(c, 'TaskEvent', dict(request_id=r['id'], actor_id=actor, event_type='idempotency_result', operation=op_hash, from_status=r['status'], to_status=r['status'], request_version=r['version'], idempotency_key=key, request_hash=digest, response_snapshot={'body': result, 'status': response.status_code}))
                else:
                    c.commit()
                    cache.parent.mkdir(exist_ok=True)
                    temp = cache.with_suffix('.tmp')
                    temp.write_text(json.dumps({'hash': digest, 'body': content.decode(), 'status': response.status_code}), encoding='utf8')
                    os.replace(temp, cache)
            return Response(content, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
    except Error as exc:
        return JSONResponse({'code': exc.code, 'message': exc.message}, status_code=exc.status)
    except psycopg.errors.UniqueViolation:
        return JSONResponse({'code': 'account_exists' if request.url.path.endswith('/register') else 'resource_conflict', 'message': '记录已存在'}, status_code=409)
    except psycopg.OperationalError:
        return JSONResponse({'code': 'service_unavailable', 'message': '数据库不可用'}, status_code=503)
    except Exception:
        logging.exception('Request failed')
        return JSONResponse({'code': 'internal_error', 'message': '服务器内部错误'}, status_code=500)

# A single local worker serializes requests so synchronous advisory locks cannot
# block the event loop while another request is committing its transaction.
request_lock = asyncio.Lock()

@app.middleware('http')
async def local_worker(request: Request, call_next):
    if request.url.path == '/health':
        return await call_next(request)
    async with request_lock:
        return await transaction(request, call_next)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(','),
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'],
)
