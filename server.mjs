import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = Number(process.env.PORT || 5173);
const HOST = process.env.HOST || '127.0.0.1';

function sendJson(res, statusCode, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

async function readBody(req) {
  return await new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', (chunk) => {
      raw += chunk;
      if (raw.length > 2_000_000) {
        reject(new Error('Body too large'));
      }
    });
    req.on('end', () => resolve(raw));
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  try {
    // Simple routing
    if (req.method === 'GET' && (req.url === '/' || req.url?.startsWith('/?'))) {
      const htmlPath = path.join(__dirname, 'faolex_food_dashboard.html');
      const html = await readFile(htmlPath);
      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store',
      });
      res.end(html);
      return;
    }

    if (req.method === 'GET' && req.url === '/health') {
      sendJson(res, 200, { ok: true });
      return;
    }

    if (req.method === 'POST' && req.url === '/api/ai') {
      const raw = await readBody(req);
      let payload;
      try {
        payload = JSON.parse(raw || '{}');
      } catch {
        sendJson(res, 400, { error: 'Invalid JSON' });
        return;
      }

      const prompt = String(payload.prompt || '').trim();
      const system = String(payload.system || '').trim();
      const apiKey = String(process.env.ANTHROPIC_API_KEY || payload.apiKey || '').trim();

      if (!prompt) {
        sendJson(res, 400, { error: 'Missing prompt' });
        return;
      }
      if (!apiKey) {
        sendJson(res, 400, { error: 'Missing API key. Set env ANTHROPIC_API_KEY or pass apiKey (demo only).' });
        return;
      }

      const upstream = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': apiKey,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({
          model: 'claude-sonnet-4-20250514',
          max_tokens: 1000,
          system,
          messages: [{ role: 'user', content: prompt }],
        }),
      });

      const data = await upstream.json().catch(() => ({}));
      if (!upstream.ok) {
        const msg = data?.error?.message || data?.message || `HTTP ${upstream.status}`;
        sendJson(res, upstream.status, { error: msg });
        return;
      }

      const blocks = Array.isArray(data?.content) ? data.content : [];
      const text = blocks.map((b) => b?.text || '').join('').trim();
      sendJson(res, 200, { text });
      return;
    }

    // Static fallback (only the dashboard file)
    if (req.method === 'GET' && req.url === '/faolex_food_dashboard.html') {
      const htmlPath = path.join(__dirname, 'faolex_food_dashboard.html');
      const html = await readFile(htmlPath);
      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store',
      });
      res.end(html);
      return;
    }

    sendJson(res, 404, { error: 'Not found' });
  } catch (e) {
    sendJson(res, 500, { error: e?.message || 'Server error' });
  }
});

server.listen(PORT, HOST, () => {
  // eslint-disable-next-line no-console
  console.log(`Dashboard server running: http://${HOST}:${PORT}`);
  console.log('Tip: set ANTHROPIC_API_KEY env var for best practice.');
});
