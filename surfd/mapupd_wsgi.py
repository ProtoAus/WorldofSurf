"""Gunicorn entry point for the P1746 map upload service (tools/install_mapupd.py writes its unit)."""
import json
import os
import re
import threading
import time
from werkzeug.middleware.proxy_fix import ProxyFix
from mapupd import create_app, log

app = create_app(os.environ['MAPUPD_STORE'], os.environ['MAPUPD_ACCOUNTS'], os.environ['MAPUPD_MAPS'],
                 zone_dirs=json.loads(os.environ.get('MAPUPD_ZONES', '[]')),
                 media_dir=os.environ.get('MAPUPD_MEDIA') or None, list_path=os.environ.get('MAPUPD_LIST') or None,
                 zone_check=json.loads(os.environ['MAPUPD_ZONECHECK']) if os.environ.get('MAPUPD_ZONECHECK') else None)
# Loopback only: the nginx location replaces X-Forwarded-For with its connection's address.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
source = os.environ['MAPUPD_SOURCE']
if not re.fullmatch('[0-9a-f]{40}', source): raise ValueError('Expected inspected mapupd source SHA')


@app.after_request
def source_header(response):
    response.headers['X-Mapupd-Source'] = source
    return response


def _healer(interval=60):
    while True:
        try: app.config['MAPUPD_HEAL']()
        except Exception as e: log('tick failed:', e)
        time.sleep(interval)


if os.environ.get('MAPUPD_NO_TICK') != '1':
    threading.Thread(target=_healer, name='mapupd-heal', daemon=True).start()
