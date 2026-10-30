"""Bounded CSV import. Source profiles are validated in memory, never persisted."""
import csv
import io

from fastapi import HTTPException, Request
from pydantic import ValidationError

from schema.user_input import UserRequest

MAX_CSV_BYTES = 128 * 1024
MAX_BATCH_ROWS = 50
CSV_COLUMNS = list(UserRequest.model_fields)
REQUIRED_COLUMNS = {name for name, field in UserRequest.model_fields.items() if field.is_required()}
BINARY_COLUMNS = {'diabetes', 'heart_disease', 'hypertension', 'asthma'}


async def read_csv_body(request: Request) -> str:
    media_type = request.headers.get('content-type', '').split(';')[0].strip().lower()
    if media_type != 'text/csv':
        raise HTTPException(415, 'Send a UTF-8 CSV body with Content-Type: text/csv.')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_CSV_BYTES:
            raise HTTPException(413, f'CSV uploads must be no larger than {MAX_CSV_BYTES} bytes.')
        body.extend(chunk)
    try:
        return body.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise HTTPException(400, 'The CSV must use UTF-8 encoding.') from None


def parse_profiles(text: str) -> list[dict]:
    if '\x00' in text:
        raise HTTPException(400, 'The CSV contains unsupported null characters.')
    try:
        reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
        if not reader.fieldnames:
            raise HTTPException(400, 'The CSV must include a header and at least one profile.')
        headers = [name.strip() for name in reader.fieldnames]
        if len(headers) != len(set(headers)) or any(name not in CSV_COLUMNS for name in headers):
            raise HTTPException(400, 'CSV headers must be unique API field names. Download the template for the supported columns.')
        if not REQUIRED_COLUMNS.issubset(headers):
            raise HTTPException(400, 'Required CSV columns are missing. Download the template for the supported columns.')
        reader.fieldnames = headers
        rows = []
        for index, raw in enumerate(reader, start=2):
            if len(rows) >= MAX_BATCH_ROWS:
                raise HTTPException(413, f'CSV uploads are limited to {MAX_BATCH_ROWS} profiles.')
            row = {'row': index, 'profile': None, 'errors': []}
            if None in raw or any(value is None for value in raw.values()):
                row['errors'] = [{'field': 'row', 'message': 'The number of values must match the CSV columns.'}]
            else:
                values = {name: value.strip() for name, value in raw.items() if value is not None and value.strip()}
                for name in BINARY_COLUMNS:
                    if values.get(name) in {'0', '1'}:
                        values[name] = int(values[name])
                try:
                    row['profile'] = UserRequest.model_validate(values)
                except ValidationError as exc:
                    row['errors'] = [
                        {'field': str(error['loc'][0]) if error['loc'] else 'profile', 'message': error['msg']}
                        for error in exc.errors()
                    ]
            rows.append(row)
        if not rows:
            raise HTTPException(400, 'The CSV must contain at least one profile.')
        return rows
    except csv.Error:
        raise HTTPException(400, 'Invalid CSV quoting or structure. Use the downloadable template.') from None


def describe_rows(rows: list[dict], operation: str) -> dict:
    valid = sum(row['profile'] is not None for row in rows)
    return {
        'operation': operation, 'total_rows': len(rows), 'valid_rows': valid,
        'invalid_rows': len(rows) - valid, 'predicted_rows': 0, 'failed_rows': 0,
        'rows': [{'row': row['row'], 'status': 'valid' if row['profile'] is not None else 'invalid', 'errors': row['errors'], 'prediction': None} for row in rows],
    }
