import { describe, expect, it, vi } from 'vitest';

import worker from './worker';

/**
 * Stands in for the Workers static-asset binding. `paths` is the set of URLs
 * the deployed bundle actually contains; anything else 404s, which is what
 * wrangler's `not_found_handling: "none"` gives us.
 */
function makeAssets(paths: Record<string, string>) {
  const fetch = vi.fn(async (request: Request) => {
    const { pathname } = new URL(request.url);
    const body = paths[pathname];
    return body === undefined
      ? new Response('not found', { status: 404 })
      : new Response(body, { status: 200, headers: { 'content-type': 'text/html' } });
  });
  return { fetch };
}

const PRERENDERED = {
  '/': '<title>Good Measure Giving</title>',
  '/methodology/': '<title>Methodology</title>',
  '/charity/13-5660870/': '<title>International Rescue Committee</title>',
  '/assets/index-abc123.js': 'console.log(1)',
};

function get(path: string) {
  return new Request(`https://goodmeasuregiving.org${path}`);
}

describe('worker asset routing', () => {
  it('serves each prerendered page instead of the SPA shell', async () => {
    // The regression this guards: rewriting every extensionless path to "/"
    // served the homepage for all 196 prerendered URLs, erasing the SSG output
    // that the whole SEO setup depends on.
    const env = { ASSETS: makeAssets(PRERENDERED) };

    for (const path of ['/methodology/', '/charity/13-5660870/']) {
      const response = await worker.fetch(get(path), env);
      expect(await response.text()).toBe(PRERENDERED[path as keyof typeof PRERENDERED]);
    }
  });

  it('serves hashed assets untouched', async () => {
    const env = { ASSETS: makeAssets(PRERENDERED) };
    const response = await worker.fetch(get('/assets/index-abc123.js'), env);

    expect(response.status).toBe(200);
    expect(await response.text()).toBe('console.log(1)');
  });

  it('falls back to the SPA shell for a route with no prerendered page', async () => {
    const env = { ASSETS: makeAssets(PRERENDERED) };
    const response = await worker.fetch(get('/bookmarks/'), env);

    expect(response.status).toBe(200);
    expect(await response.text()).toBe(PRERENDERED['/']);
  });

  it('404s a missing file rather than handing back HTML', async () => {
    const env = { ASSETS: makeAssets(PRERENDERED) };
    const response = await worker.fetch(get('/assets/deleted-xyz789.js'), env);

    expect(response.status).toBe(404);
  });

  it('proxies Firebase auth paths without touching assets', async () => {
    const env = { ASSETS: makeAssets(PRERENDERED) };
    const upstream = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response('auth handler', { status: 200 }));

    try {
      const response = await worker.fetch(get('/__/auth/handler?foo=1'), env);

      expect(await response.text()).toBe('auth handler');
      expect(env.ASSETS.fetch).not.toHaveBeenCalled();
      expect(upstream.mock.calls[0][0]).toBe(
        'https://good-measure-giving.firebaseapp.com/__/auth/handler?foo=1',
      );
    } finally {
      upstream.mockRestore();
    }
  });
});
