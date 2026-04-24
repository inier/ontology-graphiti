
import sys
sys.path.insert(0, '/app')

import traceback
from odap.infra.security import audit_logger

print('Testing audit_logger.get_stats():')
try:
    stats = audit_logger.get_stats()
    print(f'Success! Stats: {stats}')
except Exception as e:
    print(f'Error: {e}')
    print('Stack trace:')
    traceback.print_exc()

print()
print('Testing MongoDBAuditChannel class:')
from odap.infra.security.audit_mongodb_channel import MongoDBAuditChannel

print('Creating channel:')
try:
    channel = MongoDBAuditChannel()
    print('Channel created')
    print(f'channel.collection is None: {channel.collection is None}')
    print('Calling get_stats():')
    stats2 = channel.get_stats()
    print(f'Success! Stats2: {stats2}')
except Exception as e:
    print(f'Error: {e}')
    traceback.print_exc()

