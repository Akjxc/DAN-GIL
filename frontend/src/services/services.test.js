import assert from 'node:assert/strict';
import test from 'node:test';
import { requestPlaces, requestRoute } from './routeService.js';
import { sendChatMessage } from './chatService.js';

test('places, routes and chat preserve local paths and request data', async (t) => {
  const requests = [];
  const bodies = [[], { status: 'ok', nodes: [{ id: 'mainGate' }], edges: [] }, { message: '안녕하세요' }];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    requests.push({ url, options });
    return Response.json(bodies.shift());
  });
  const signal = new AbortController().signal;
  assert.deepEqual(await requestPlaces(signal), []);
  assert.equal((await requestRoute('mainGate', 'mainGate', true, signal)).status, 'ok');
  assert.equal((await sendChatMessage('안녕', [
    { role: 'bot', text: '첫 안내', local: true },
    { role: 'bot', text: '어디로 가시나요?' },
  ])).message, '안녕하세요');
  assert.deepEqual(requests.map(r => r.url), ['/api/places', '/api/routes', '/api/chat']);
  assert.equal(requests[1].options.signal, signal);
  assert.equal(requests[1].options.method, 'POST');
  assert.deepEqual(JSON.parse(requests[1].options.body), {
    start_node_id: 'mainGate', end_node_id: 'mainGate', exclude_conditions: ['stair'], exclude_kinds: [],
  });
  assert.deepEqual(JSON.parse(requests[2].options.body), {
    message: '안녕', history: [{ role: 'assistant', content: '어디로 가시나요?' }],
  });
});

test('backend validation error remains visible to the route caller', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: '출발지 ID 오류' }, { status: 400 }));
  await assert.rejects(requestRoute('missing', 'mainGate', false), /출발지 ID 오류/);
});

test('non-JSON chat errors produce a readable message', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('<h1>Timeout</h1>', { status: 504 }));
  await assert.rejects(sendChatMessage('안녕'), /채팅 서버에서 답변을 받지 못했어요/);
});
