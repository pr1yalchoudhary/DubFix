"""Private operator CLI. Never exposed as a public HTTP endpoint. No Fish calls."""
import argparse
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env')
from app.public_usage import PREFIX, command

INITIALIZE = """
if redis.call('EXISTS', KEYS[1]) == 1 then return 'already_initialized' end
redis.call('HSET', KEYS[1], 'schema', '1', 'enabled', '0', 'used', '0')
return 'initialized_disabled'
"""
TOGGLE = """
local used = redis.call('HGET', KEYS[1], 'used')
if redis.call('HGET', KEYS[1], 'schema') ~= '1' or not used or not string.match(used, '^%d+$') then
  return 'invalid_budget_no_change'
end
redis.call('HSET', KEYS[1], 'enabled', ARGV[1])
return 'updated'
"""


async def manage(action):
    key = PREFIX + 'budget'
    if action == 'initialize':
        return await command('EVAL', INITIALIZE, 1, key)
    if action in ('enable', 'disable'):
        return await command('EVAL', TOGGLE, 1, key, '1' if action == 'enable' else '0')
    return await command('HGETALL', key)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('initialize', 'enable', 'disable', 'inspect'))
    args = parser.parse_args()
    try:
        print(asyncio.run(manage(args.action)))
    except Exception:
        raise SystemExit('Usage storage operation failed; no automatic retry. Check configuration and inspect the budget.') from None
