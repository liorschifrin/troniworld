"""Small request validators for comment, point, and player-sheet APIs."""
from functools import wraps
import math

from flask import jsonify, request
from werkzeug.exceptions import BadRequest, HTTPException

from .utils import get_current_user


def json_api(*, admin=False, public=False):
    """Keep scoped API authentication and HTTP errors in the JSON contract."""
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not public and user is None:
                return jsonify(error='Login required'), 401
            if admin and not user.is_admin:
                return jsonify(error='Admin access required'), 403
            try:
                for field, value in kwargs.items():
                    if field.endswith('_id'):
                        optional_id(value, field)
                return view(*args, **kwargs)
            except HTTPException as error:
                # Missing and invisible resources must be indistinguishable.
                message = 'Not found' if error.code == 404 else error.description
                return jsonify(error=message), error.code
        return wrapped
    return decorate


def json_object(allowed):
    try:
        data = request.get_json(silent=True)
    except RecursionError:
        raise BadRequest('JSON nesting is too deep') from None
    if not isinstance(data, dict):
        raise BadRequest('A JSON object is required')
    if data.keys() - set(allowed):
        raise BadRequest('Unsupported field')
    return data


def text_value(value, field, *, nullable=False, max_length=None):
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise BadRequest(f'{field} must be a string')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        raise BadRequest(f'{field} must contain valid Unicode') from None
    value = value.strip()
    if max_length is not None and len(value) > max_length:
        raise BadRequest(f'{field} must be at most {max_length} characters')
    return value


def optional_id(value, field):
    # Bound before binding to SQLite/Postgres integer parameters; bool is not an id.
    if value is not None and (type(value) is not int or not 1 <= value <= 2147483647):
        raise BadRequest(f'{field} must be a positive 32-bit integer or null')
    return value


def valid_timestamp(value):
    # Range first also handles arbitrarily large JSON integers without float overflow.
    return type(value) in (int, float) and 0 <= value <= 86400 and math.isfinite(value)


def timestamp(value, field):
    if value is not None and not valid_timestamp(value):
        raise BadRequest(f'{field} must be a finite number from 0 to 86400, or null')
    return value


def boolean(value, field):
    if type(value) is not bool:
        raise BadRequest(f'{field} must be a boolean')
    return value


def recipients(value):
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(name, str) for name in value):
        raise BadRequest('private_to must be a list of strings or null')
    names = [text_value(name, 'private_to entry') for name in value]
    return [name for name in names if name]


def comment_fields(data, *, default_type='Comment'):
    kind = data.get('comment_type', default_type)
    if kind not in ('Comment', 'Question', 'Highlight', 'Event'):
        raise BadRequest('Invalid comment type')
    content = text_value(data.get('content', ''), 'content')
    if not content and kind != 'Event':
        raise BadRequest('Content is required')
    return content, kind
