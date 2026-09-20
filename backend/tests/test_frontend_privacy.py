from pathlib import Path
import tempfile
import unittest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.frontend import mount_frontend, resolve_frontend_file

class FrontendPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / 'dist'
        self.root.mkdir()
        (self.root / 'index.html').write_text('SPA HOME')
        (self.root / 'allowed.txt').write_text('PUBLIC FILE')
        (self.parent / 'secret.txt').write_text('PRIVATE OUTSIDE FILE')
        (self.root / 'assets').mkdir()
        (self.root / 'assets' / 'app.js').write_text('PUBLIC ASSET')
        app = FastAPI()
        mount_frontend(app, self.root)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_normal_routes_and_fallback(self):
        for path, expected in [('/', 'SPA HOME'), ('/allowed.txt', 'PUBLIC FILE'),
                               ('/project/example', 'SPA HOME'), ('/assets/app.js', 'PUBLIC ASSET')]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.text, expected)

    def test_encoded_traversals_and_absolute_paths(self):
        for path in ['/%2e%2e/secret.txt', '/%2E%2E%2Fsecret.txt', '/..%5csecret.txt',
                     '/%00secret.txt', '/%2Fetc/passwd', '/.git/config']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, path)
            self.assertNotIn('PRIVATE OUTSIDE FILE', response.text)

    def test_raw_helper_rejects_escapes(self):
        for path in ['../secret.txt', str(self.parent / 'secret.txt'), '..\\secret.txt', 'x\\..\\secret.txt']:
            with self.assertRaises(HTTPException):
                resolve_frontend_file(self.root, path)

    def test_symlink_escape(self):
        (self.root / 'linked.txt').symlink_to(self.parent / 'secret.txt')
        (self.root / 'assets' / 'linked.txt').symlink_to(self.parent / 'secret.txt')
        self.assertEqual(self.client.get('/linked.txt').status_code, 404)
        self.assertEqual(self.client.get('/assets/linked.txt').status_code, 404)

    def test_reserved_api_does_not_fall_back_to_html(self):
        self.assertEqual(self.client.get('/api/missing').status_code, 404)

if __name__ == '__main__':
    unittest.main()
