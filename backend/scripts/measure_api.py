import json
import statistics
import subprocess
import sys
import time

from fastapi.testclient import TestClient

from cpsc360.app import app


def stats(values):
    return {'median_ms': round(statistics.median(values), 2), 'min_ms': round(min(values), 2), 'max_ms': round(max(values), 2), 'runs': len(values)}


def main():
    startup = []
    for _ in range(5):
        code = '''import time
start=time.perf_counter()
from fastapi.testclient import TestClient
from cpsc360.app import app
with TestClient(app) as c:
 assert c.get('/api/health').status_code == 200
 print((time.perf_counter()-start)*1000)
'''
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True)
        startup.append(float(result.stdout.strip()))
    search, related = [], []
    with TestClient(app) as client:
        token = client.post('/api/session', json={'handle': 'jrivera'}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        errors = 0
        results = []
        for _ in range(7):
            response = client.get('/api/incidents', params={'q': 'fire', 'hazard': 'fire', 'product_category': 'Kitchen'}, headers=headers)
            errors += response.status_code != 200
            response.raise_for_status()
            body = response.json()
            assert body['total'] > 0 and len(body['items']) == 50
            assert all('fire' in r['hazards'] and r['product_category'] == 'Kitchen' for r in body['items'])
            search.append(body['took_ms'])
            report = body['items'][0]['report_no']
            start = time.perf_counter()
            response = client.get(f'/api/incidents/{report}/related', headers=headers)
            related.append((time.perf_counter()-start)*1000)
            errors += response.status_code != 200
            response.raise_for_status()
            assert response.json()
            assert all(r['score'] == min(1, sum(v['weight'] for v in r['reasons'])) for r in response.json())
            results.append(len(response.json()))
        print(json.dumps({'warm_cache_process_startup': stats(startup), 'search_server': stats(search), 'related_http_in_process': stats(related), 'errors': errors, 'matching_search_rows': body['total'], 'related_rows_per_run': results}, indent=2))


if __name__ == '__main__':
    main()
