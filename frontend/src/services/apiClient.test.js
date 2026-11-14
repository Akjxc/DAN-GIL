import assert from 'node:assert/strict';
import test from 'node:test';
import { buildApiUrl } from './apiClient.js';

test('local requests keep the development proxy path', () => {
  assert.equal(buildApiUrl('', '/api/places'), '/api/places');
});

test('all API requests use the configured backend origin', () => {
  for (const path of ['/api/places', '/api/routes', '/api/chat']) {
    assert.equal(buildApiUrl('https://backend.example.com/', path), `https://backend.example.com${path}`);
  }
});

test('production domain sends chat to dangil-api', () => {
  assert.equal(buildApiUrl('https://dangil-api.vercel.app/', '/api/chat'), 'https://dangil-api.vercel.app/api/chat');
});

test('rejects bases with credentials, paths, queries or insecure schemes', () => {
  for (const base of ['https://example.com/api', 'https://user:pass@example.com', 'https://example.com?key=x', 'https://example.com#x', 'http://example.com', 'not-a-url']) {
    assert.throws(() => buildApiUrl(base, '/api/chat'), /VITE_API_BASE_URL/);
  }
});
