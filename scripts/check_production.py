"""Check the public release with ordinary HTTPS and synthetic template inputs only."""
import argparse
import ast
import csv
import io
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


class RejectRedirects(HTTPRedirectHandler):
    """A public app must respond directly, including on generated production URLs."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def check(base_url: str) -> None:
    opener = build_opener(RejectRedirects())
    def fetch(path, body=None, content_type=None):
        headers = {'User-Agent': 'CareEstimate-release-check/1.0', 'Cache-Control': 'no-cache'}
        if content_type:
            headers['Content-Type'] = content_type
        with opener.open(Request(base_url + path, data=body, headers=headers), timeout=20) as response:
            return response.read(), response.headers

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    expected_version = next(
        node.value.value for node in ast.parse((ROOT / 'app.py').read_text()).body
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'APP_VERSION' for target in node.targets)
    )
    health = json.loads(fetch('/health')[0])
    require(health.get('status') == 'ok' and health.get('version') == expected_version, 'Production has not reached the expected application version.')
    homepage = fetch('/')[0].decode('utf-8')
    for marker in ['id="waterfall-table"', 'id="workspace-panel"', 'id="batch-panel"']:
        require(marker in homepage, 'Production homepage is missing a release feature.')
    for path, source in [('/static/app.js', 'static/app.js'), ('/static/charts.js', 'static/charts.js'),
                         ('/static/i18n.js', 'static/i18n.js'), ('/sw.js', 'static/sw.js'),
                         ('/static/batch-template.csv', 'static/batch-template.csv')]:
        require(fetch(path)[0] == (ROOT / source).read_bytes(), f'Production asset does not match this commit: {path}')
    manifest = json.loads(fetch('/static/manifest.webmanifest')[0])
    require(manifest.get('start_url') == '/', 'Installable app manifest is invalid.')
    spec = json.loads(fetch('/openapi.json')[0])
    require(all(path in spec.get('paths', {}) for path in ['/predict', '/batch/validate', '/batch/predict']), 'Prediction API documentation is incomplete.')
    template = (ROOT / 'static/batch-template.csv').read_text()
    reader = csv.DictReader(io.StringIO(template))
    profile = next(reader)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerow(profile)
    writer.writerow({**profile, 'age': '17'})
    batch_body = output.getvalue().encode('utf-8')
    for operation in ['validate', 'predict']:
        payload, headers = fetch('/batch/' + operation, batch_body, 'text/csv')
        data = json.loads(payload)
        require(headers.get('Cache-Control') == 'no-store', 'Batch response may be cached.')
        require(data.get('valid_rows') == 1 and data.get('invalid_rows') == 1, 'Batch row validation failed.')
        require(data['rows'][1]['status'] == 'invalid', 'Invalid batch record was not retained.')
        if operation == 'validate':
            require(data['predicted_rows'] == 0 and all(row['prediction'] is None for row in data['rows']), 'Validation unexpectedly performed inference.')
        else:
            prediction = data['rows'][0]['prediction']
            require(data['predicted_rows'] == 1 and data['failed_rows'] == 0, 'Batch inference failed.')
            require(len(prediction['explanation']['contributions']) == 20, 'Full explanation is missing.')
            total = prediction['explanation']['base_value'] + sum(item['contribution'] for item in prediction['explanation']['contributions'])
            require(abs(total - prediction['predicted_medical_cost']) <= 0.0051, 'Explanation does not reconcile.')
            # JSON accepts numeric strings for most fields, but condition flags are literals.
            for key in ['diabetes', 'heart_disease', 'hypertension', 'asthma']:
                profile[key] = int(profile[key])
            single_body, single_headers = fetch('/predict', json.dumps(profile).encode('utf-8'), 'application/json')
            single = json.loads(single_body)
            require(single_headers.get('Cache-Control') == 'no-store', 'Individual prediction may be cached.')
            require(single['predicted_medical_cost'] == prediction['predicted_medical_cost'], 'Batch and individual inference disagree.')
    print(f'PASS: {base_url} serves v{expected_version}, matching assets, PWA shell, API docs, CSV validation and consistent predictions.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://medical-cost-app-king-09.vercel.app')
    parser.add_argument('--attempts', type=int, default=8)
    parser.add_argument('--delay', type=float, default=10)
    args = parser.parse_args()
    url = urlsplit(args.url)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        parser.error('--url must be an HTTPS origin without credentials, query or path')
    if not 1 <= args.attempts <= 12 or not 0 <= args.delay <= 30:
        parser.error('use 1–12 attempts and a delay of 0–30 seconds')
    for attempt in range(1, args.attempts + 1):
        try:
            check(args.url.rstrip('/'))
            return
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError, IndexError) as error:
            # Print no response bodies, submitted profile values or credentials.
            detail = f'HTTP {error.code} at {urlsplit(error.url).path}' if isinstance(error, HTTPError) else str(error) if isinstance(error, ValueError) else type(error).__name__
            print(f'Attempt {attempt}/{args.attempts} failed: {detail}', flush=True)
            if attempt == args.attempts:
                raise SystemExit('Production verification failed; inspect deployment readiness and public connectivity.') from None
            time.sleep(args.delay)


if __name__ == '__main__':
    main()
