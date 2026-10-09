"""Offline behavioral checks; no SDK install, network requests or real keys."""
import argparse
import asyncio
import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL / 'scripts'))
import image_gen as wrapper


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.calls = []
        self.opts = []
        self.key = 'offline-fake-secret-123'
        self.env = patch.dict(os.environ, {'TEST_IMAGE_KEY': self.key}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.tmp.cleanup)

    def invoke(self, args, fail=False):
        outer = self
        class Images:
            def generate(self, **kwargs):
                outer.calls.append(('generate', kwargs))
                if fail:
                    raise RuntimeError('provider echoed ' + outer.key)
                return types.SimpleNamespace(data=[types.SimpleNamespace(b64_json=base64.b64encode(b'image-bytes').decode())])
            def edit(self, **kwargs):
                outer.calls.append(('edit', kwargs))
                outer.assertEqual(kwargs['image'].read(), b'source-image')
                return self.generate(**kwargs)
        class Client:
            def __init__(self, **opts):
                outer.opts.append(opts)
                self.images = Images()
        class AsyncImages(Images):
            async def generate(self, **kwargs):
                return super().generate(**kwargs)
        class AsyncClient(Client):
            def __init__(self, **opts):
                super().__init__(**opts)
                self.images = AsyncImages()
        output = io.StringIO()
        sdk = types.SimpleNamespace(OpenAI=Client, AsyncOpenAI=AsyncClient)
        with patch.dict(sys.modules, {'openai': sdk}), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = wrapper.main(args)
        self.assertNotIn(self.key, output.getvalue())
        return code, output.getvalue()

    def args(self, command='generate'):
        return [command, '--api-key-env', 'TEST_IMAGE_KEY', '--base-url', 'https://example.test/v1', '--prompt', 'test', '--out', str(self.root / 'out.png')]

    def test_generate_explicit_endpoint_key(self):
        code, _ = self.invoke(self.args())
        self.assertEqual(code, 0)
        self.assertEqual(self.opts[0]['base_url'], 'https://example.test/v1/')
        self.assertEqual(self.opts[0]['api_key'], self.key)
        self.assertEqual(self.opts[0]['max_retries'], 0)
        self.assertEqual((self.root / 'out.png').read_bytes(), b'image-bytes')

    def test_edit(self):
        source = self.root / 'source.jpg'
        source.write_bytes(b'source-image')
        self.assertEqual(self.invoke(self.args('edit') + ['--image', str(source)])[0], 0)
        self.assertEqual(self.calls[0][0], 'edit')

    def test_batch(self):
        jobs = self.root / 'jobs.jsonl'
        jobs.write_text(json.dumps({'prompt':'first'}) + '\n' + json.dumps({'prompt':'second'}))
        code, _ = self.invoke(['generate-batch', '--api-key-env', 'TEST_IMAGE_KEY', '--base-url', 'http://localhost:9876/v1', '--input', str(jobs), '--out-dir', str(self.root / 'batch')])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(list((self.root / 'batch').glob('*.png'))), 2)

    def test_profile_keyfile_relative_and_override(self):
        (self.root / 'key.txt').write_text('profile-secret')
        config = self.root / 'profiles.json'
        config.write_text(json.dumps({'profiles':{'studio':{'base_url':'https://profile.test/v1', 'api_key_file':'key.txt', 'model':'gpt-image-1.5'}}}))
        args = ['generate', '--config', str(config), '--profile', 'studio', '--prompt', 'test', '--out', str(self.root / 'one.png')]
        self.assertEqual(self.invoke(args)[0], 0)
        self.assertEqual(self.opts[-1]['api_key'], 'profile-secret')
        self.assertEqual(self.calls[-1][1]['model'], 'gpt-image-1.5')
        self.assertEqual(self.invoke(args + ['--api-key-env','TEST_IMAGE_KEY','--base-url','https://override.test/v1','--out',str(self.root / 'two.png')])[0], 0)
        self.assertEqual(self.opts[-1]['api_key'], self.key)
        self.assertEqual(self.opts[-1]['base_url'], 'https://override.test/v1/')

    def test_missing_selected_key_no_fallback(self):
        os.environ['OPENAI_API_KEY'] = 'other-account'
        code, _ = self.invoke(self.args() + ['--api-key-env', 'MISSING'])
        self.assertEqual(code, 2)
        self.assertFalse(self.opts)

    def test_dry_run_no_key_no_sdk_or_client(self):
        code, output = self.invoke(self.args() + ['--api-key-env', 'MISSING', '--dry-run'])
        self.assertEqual(code, 0)
        self.assertIn('/v1/images/generations', output)
        self.assertFalse(self.opts)

    def test_bad_urls_and_timeout(self):
        for url in ['https://user:secret@example.test/v1', 'file:///tmp', 'https://example.test/v1/images/edits', 'https://example.test/v1?key=secret']:
            self.assertEqual(self.invoke(self.args() + ['--base-url', url])[0], 2)
        self.assertEqual(self.invoke(self.args() + ['--timeout', 'nan'])[0], 2)

    def test_errors_do_not_echo_key(self):
        code, _ = self.invoke(self.args(), fail=True)
        self.assertEqual(code, 1)
        jobs = self.root / 'jobs.jsonl'
        jobs.write_text('{"prompt":"test"}')
        code, output = self.invoke(['generate-batch','--api-key-env','TEST_IMAGE_KEY','--input',str(jobs),'--out-dir',str(self.root / 'batch')], fail=True)
        self.assertEqual(code, 1)
        self.assertIn('[REDACTED]', output)

    def test_response_normalization_supports_data_uri(self):
        result = wrapper._normalize_image_result(
            types.SimpleNamespace(data=[types.SimpleNamespace(url='data:image/png;base64,aW1hZ2UtYnl0ZXM=')]),
            {'timeout': 5},
        )
        self.assertEqual(result.data[0].b64_json, 'aW1hZ2UtYnl0ZXM=')

    def test_response_normalization_rejects_unknown_shape(self):
        with self.assertRaises(TypeError):
            wrapper._normalize_image_result(types.SimpleNamespace(data=[types.SimpleNamespace(foo='bar')]), {'timeout': 5})


if __name__ == '__main__':
    unittest.main(verbosity=2)
