"""T05 slice 3: validated image uploads, size limits, and nosniff on served uploads."""
from io import BytesIO
from pathlib import Path

import pytest
from conftest import synthetic_image

from flask_app import uploads


@pytest.fixture
def admin(client_for):
    return client_for('admin')


def post_image(client, data, name, **kwargs):
    return client.post('/upload_image', data={'upload': (BytesIO(data), name)}, **kwargs)


def stored(app):
    return sorted(p.name for p in Path(app.config['UPLOAD_FOLDER']).iterdir())


@pytest.mark.parametrize('fmt,name', [('PNG', 'a.png'), ('JPEG', 'a.jpg'), ('JPEG', 'b.JPEG'),
                                      ('GIF', 'a.gif'), ('WEBP', 'a.webp')])
def test_valid_images_are_accepted_unchanged(admin, app, fmt, name):
    data = synthetic_image(fmt)
    response = post_image(admin, data, name)
    assert response.status_code == 201
    url = response.get_json()['url']
    assert url.startswith('/static/uploads/')
    (path,) = Path(app.config['UPLOAD_FOLDER']).iterdir()
    assert url == f'/static/uploads/{path.name}'
    assert path.read_bytes() == data  # never re-encoded
    assert path.stat().st_mode & 0o044  # readable by the web server, not a 0600 temp file


def test_svg_is_rejected(admin, app):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    for name in ('x.svg', 'x.png'):
        assert post_image(admin, svg, name).status_code == 400
    assert stored(app) == []


@pytest.mark.parametrize('data', [
    b'just some text',
    b'',
    b'GIF89a<script>alert(1)</script>',
    b'\x89PNG\r\n\x1a\n<html><script>alert(1)</script></html>',
    b'\xff\xd8\xff<html><script>alert(1)</script></html>',
    synthetic_image('PNG')[:20],
])
def test_non_images_renamed_as_images_are_rejected(admin, app, data):
    for name in ('x.png', 'x.jpg', 'x.gif', 'x.webp'):
        response = post_image(admin, data, name)
        assert response.status_code == 400
        assert 'error' in response.get_json()
    assert stored(app) == []


def test_format_must_match_extension(admin, app):
    assert post_image(admin, synthetic_image('PNG'), 'x.jpg').status_code == 400
    assert stored(app) == []


def test_unlisted_extensions_are_rejected(admin, app):
    for name in ('x.bmp', 'x.html', 'x', 'x.png.html'):
        assert post_image(admin, synthetic_image('PNG'), name).status_code == 400
    assert stored(app) == []


def test_oversize_image_is_rejected_with_json_413(admin, app):
    data = synthetic_image('PNG') + b'\0' * (uploads.MAX_IMAGE_BYTES + 1)
    response = post_image(admin, data, 'big.png')
    assert response.status_code == 413
    assert response.get_json() == {'error': 'Image is larger than the 20 MB limit'}
    assert stored(app) == []  # no partial or temp file remains


def test_image_limit_constant_is_what_the_check_uses(admin, app, monkeypatch):
    data = synthetic_image('PNG')
    monkeypatch.setattr(uploads, 'MAX_IMAGE_BYTES', len(data) - 1)
    assert post_image(admin, data, 'a.png').status_code == 413
    monkeypatch.setattr(uploads, 'MAX_IMAGE_BYTES', len(data))
    assert post_image(admin, data, 'a.png').status_code == 201


def test_limits_are_20_and_25_megabytes(app):
    assert uploads.MAX_IMAGE_BYTES == 20 * 1024 * 1024
    assert app.config['MAX_CONTENT_LENGTH'] == 25 * 1024 * 1024


def test_global_cap_returns_json_413_on_json_route(admin, app):
    data = synthetic_image('PNG') + b'\0' * (25 * 1024 * 1024)
    response = post_image(admin, data, 'huge.png')
    assert response.status_code == 413
    assert response.get_json() == {'error': 'Request is larger than the 25 MB limit'}
    assert stored(app) == []


def test_global_cap_applies_to_csv_form_route(admin, records):
    body = b'a,b\n' + b'0' * (25 * 1024 * 1024)
    response = admin.post(f"/film/games/{records['game'].id}/upload_csv",
                          data={'csv_file': (BytesIO(body), 'x.csv')})
    assert response.status_code == 413
    assert response.get_json() is None  # HTML form route keeps a normal error page


def test_csv_under_the_cap_is_unchanged(admin, records):
    response = admin.post(f"/film/games/{records['game'].id}/upload_csv",
                          data={'csv_file': (BytesIO(b'a,b\n'), 'x.csv')})
    assert response.status_code == 200


def test_traversal_filenames_are_stored_safely(admin, app):
    for name in ('../../evil.png', '..\\..\\evil.png', '/etc/x.png', 'a/../../b.png'):
        response = post_image(admin, synthetic_image('PNG'), name)
        assert response.status_code == 201
    folder = Path(app.config['UPLOAD_FOLDER'])
    names = stored(app)
    assert len(names) == 4
    assert all('/' not in n and '\\' not in n and not n.startswith('.') for n in names)
    assert {p.parent for p in folder.rglob('*')} == {folder}
    assert not (folder.parent / 'evil.png').exists()


def test_stored_names_are_unguessable_and_unique(admin, app):
    for _ in range(2):
        post_image(admin, synthetic_image('PNG'), 'same.png')
    first, second = stored(app)
    assert first != second
    assert all(len(n.split('_')[0]) == 32 for n in (first, second))


def test_nosniff_on_served_uploads(app):
    from flask_app import app as application
    folder = Path(application.config['UPLOAD_FOLDER'])
    # The static route serves from the real static folder; place a file there via the route's own folder.
    static_uploads = Path(application.static_folder) / 'uploads'
    static_uploads.mkdir(exist_ok=True)
    probe = static_uploads / 'synthetic-nosniff-probe.png'
    probe.write_bytes(synthetic_image('PNG'))
    try:
        response = application.test_client().get('/static/uploads/synthetic-nosniff-probe.png')
        assert response.status_code == 200
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        other = application.test_client().get('/')
        assert 'X-Content-Type-Options' not in other.headers
    finally:
        probe.unlink()
    assert folder.is_dir()
