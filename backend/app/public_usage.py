"""Fail-closed public budget. Redis, never browser state, owns all allowances."""
from contextvars import ContextVar
import hashlib
import hmac
import ipaddress
import os
import re
import secrets

import httpx
from fastapi import HTTPException, Request

PREFIX = 'tweeq:{public-v1}:'  # Stable across deploys. Never change to reset a budget.
context = ContextVar('public_usage', default=None)

# One script handles status, session creation, and reservation. Redis serializes it.
# Quota keys have NO TTL. Only short-window abuse counters expire.
SCRIPT = r'''
local function count(key, field)
  local raw = redis.call('HGET', key, field)
  if not raw or not string.match(raw, '^%d+$') then return nil end
  return tonumber(raw)
end
local g = count(KEYS[1], 'used')
if redis.call('HGET', KEYS[1], 'schema') ~= '1' or not g then return {'storage'} end
if redis.call('HGET', KEYS[1], 'enabled') ~= '1' then return {'disabled'} end
local v = count(KEYS[2], 'used')
local i = 0
if redis.call('EXISTS', KEYS[3]) == 1 then
  i = count(KEYS[3], 'used')
  if not i then return {'storage'} end
end
if ARGV[1] == 'create' then
  if v then return {'storage'} end
  if g >= 10 then return {'global'} end
  if i >= 2 then return {'ip'} end
  local n = tonumber(redis.call('GET', KEYS[4]) or '0')
  if not n then return {'storage'} end
  if n >= 10 then return {'rate'} end
  redis.call('INCR', KEYS[4])
  if n == 0 then redis.call('EXPIRE', KEYS[4], 3600) end
  redis.call('HSET', KEYS[2], 'used', 0, 'ip', ARGV[2])
  return {'ok', 0, g, i}
end
if not v or redis.call('HGET', KEYS[2], 'ip') ~= ARGV[2] then return {'session'} end
if ARGV[1] == 'reserve' then
  if g >= 10 then return {'global'} end
  if v >= 2 then return {'visitor'} end
  if i >= 2 then return {'ip'} end
  local n = tonumber(redis.call('GET', KEYS[4]) or '0')
  if not n then return {'storage'} end
  if n >= 2 then return {'rate'} end
  -- All checks precede mutations. No refunds: timeouts may already be billable.
  redis.call('HINCRBY', KEYS[1], 'used', 1)
  redis.call('HINCRBY', KEYS[2], 'used', 1)
  redis.call('HINCRBY', KEYS[3], 'used', 1)
  redis.call('INCR', KEYS[4])
  if n == 0 then redis.call('EXPIRE', KEYS[4], 60) end
  v = v + 1; g = g + 1; i = i + 1
end
return {'ok', v, g, i}
'''


def mode():
    value = os.getenv('AI_ACCESS_MODE', 'demo')
    if value not in ('demo', 'public'):
        raise HTTPException(503, 'AI access configuration is invalid.')
    return value


def enabled():
    if os.getenv('PUBLIC_GENERATIONS_ENABLED', 'false').lower() != 'true':
        raise HTTPException(503, 'Public AI generation is currently disabled.')


async def command(*args):
    url = os.getenv('UPSTASH_REDIS_REST_URL', '').rstrip('/')
    token = os.getenv('UPSTASH_REDIS_REST_TOKEN', '')
    if not url.startswith('https://') or not token:
        raise HTTPException(503, 'Public usage storage is unavailable. No AI request was sent.')
    try:
        # No automatic retries: an ambiguous response may have committed a reservation.
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            response = await client.post(url, headers={'Authorization': 'Bearer ' + token}, json=list(args))
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or 'error' in result or 'result' not in result:
                raise ValueError()
            return result['result']
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(503, 'Public usage storage is unavailable. No AI request was sent.') from None


def ip_key(request: Request):
    secret = os.getenv('PUBLIC_IP_HASH_SECRET', '')
    if len(secret) < 32:
        raise HTTPException(503, 'Public IP protection is not configured.')
    # Default ignores user-supplied forwarding headers. Behind Render, only opt into
    # an edge-overwritten header after validating the ingress trust boundary.
    source = os.getenv('PUBLIC_IP_SOURCE', 'peer')
    if source == 'peer':
        if os.getenv('RENDER') == 'true':
            raise HTTPException(503, 'Verify the Render ingress IP configuration before enabling public AI.')
        raw = request.client.host if request.client else ''
    elif source == 'render':
        if os.getenv('RENDER') != 'true' or os.getenv('PUBLIC_RENDER_IP_VERIFIED') != 'true':
            raise HTTPException(503, 'Render IP protection is not configured.')
        raw = request.headers.get('true-client-ip', '')
    else:
        raise HTTPException(503, 'Public IP protection is not configured.')
    try:
        if '%' in raw:
            raise ValueError()
        address = ipaddress.ip_address(raw)
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        normalized = str(address) if address.version == 4 else str(ipaddress.ip_network(f'{address}/64', strict=False))
    except ValueError:
        raise HTTPException(503, 'Cannot verify the visitor network. No AI request was sent.') from None
    return hmac.new(secret.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def token_key(token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token or ''):
        raise HTTPException(401, 'Start a new anonymous session to use free AI editing.')
    return hashlib.sha256(token.encode()).hexdigest()


async def evaluate(action, token, ip):
    enabled()
    visitor = token_key(token)
    window = 'issue' if action == 'create' else 'rate'
    keys = [PREFIX + 'budget', PREFIX + 'visitor:' + visitor, PREFIX + 'ip:' + ip, PREFIX + window + ':' + ip]
    result = await command('EVAL', SCRIPT, len(keys), *keys, action, ip)
    if not isinstance(result, list) or not result:
        raise HTTPException(503, 'Public usage storage returned an invalid result.')
    errors = {
        'storage': (503, 'Public usage storage is unavailable. No AI request was sent.'),
        'disabled': (503, 'Public AI generation is currently disabled.'),
        'session': (401, 'Your anonymous session is invalid or your network changed. Start a new session.'),
        'global': (429, 'All 10 public AI uses have been reserved. Public AI editing has ended.'),
        'visitor': (429, 'You have used your 2 free AI operations. Playback, editing and export remain available.'),
        'ip': (429, 'The free AI allowance for this network has been reached. Playback and export remain available.'),
        'rate': (429, 'Too many AI requests from this network. Please wait before trying again.'),
    }
    if result[0] != 'ok':
        status, message = errors.get(result[0], errors['storage'])
        raise HTTPException(status, message)
    if len(result) != 4 or any(type(n) is not int or n < 0 for n in result[1:]):
        raise HTTPException(503, 'Public usage storage returned an invalid result.')
    return {'mode': 'public', 'remaining': max(0, min(2-result[1], 10-result[2], 2-result[3])),
            'visitor_remaining': max(0, 2-result[1]), 'global_remaining': max(0, 10-result[2]),
            'message': 'Each voice setup, speech detection and generation attempt uses one allowance. Failed attempts are not refunded.'}


async def reserve_operation():
    access = context.get()
    if not access:
        raise HTTPException(403, 'AI operations require a verified access context.')
    if access == 'demo':
        # Only set by the existing backend demo dependency, never a public header.
        if mode() != 'demo':
            raise HTTPException(403, 'Public usage authorization is required.')
        return
    if mode() != 'public':
        raise HTTPException(503, 'Public AI access is unavailable.')
    await evaluate('reserve', *access)
