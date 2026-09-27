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
  '/404.html': '<h1>Page not found</h1>',
  '/methodology/': '<title>Methodology</title>',
  '/charity/13-5660870/': '<title>International Rescue Committee</title>',
  '/assets/index-abc123.js': 'console.log(1)',
  '/data/charities/charity-04-2535767.json': '{"name":"Unlisted charity"}',
  '/data/prompts/planned_prompt.json': '{"status":"planned"}',
};

function get(path: string) {
  return new Request(`https://goodmeasuregiving.org${path}`);
}

describe('worker asset routing', () => {
  it.each([
    ['/?type=instrument', '/'],
    ['/charity/13-5660870/?view=terminal', '/charity/13-5660870/'],
    ['/compare/?eins=81-3451645%2C81-2566656&type=caslon&view=terminal', '/compare/?eins=81-3451645%2C81-2566656'],
    ['/methodology/?type=&type=unknown&view=&utm_source=newsletter&q=food+aid', '/methodology/?utm_source=newsletter&q=food+aid'],
  ])('permanently redirects retired display parameters in %s', async (path, target) => {
    const env = { ASSETS: makeAssets(PRERENDERED) };
    const response = await worker.fetch(get(path), env);
    expect(response.status).toBe(301);
    expect(response.headers.get('location')).toBe(`https://goodmeasuregiving.org${target}`);
    expect((await worker.fetch(get(target), env)).status).toBe(200);
  });

  it('normalizes HEAD requests but leaves POST requests and file queries alone', async () => {
    const env = { ASSETS: makeAssets(PRERENDERED) };
    const url = 'https://goodmeasuregiving.org/?view=terminal';
    expect((await worker.fetch(new Request(url, { method: 'HEAD' }), env)).status).toBe(301);
    expect((await worker.fetch(new Request(url, { method: 'POST' }), env)).status).toBe(200);
    expect((await worker.fetch(get('/assets/index-abc123.js?type=module&view=raw'), env)).status).toBe(200);
  });

  it.each(['/missing/', '/charity/00-0000000/', '/guides/missing/', '/plan/join/'])('returns custom HTML with a 404 status for %s', async (path) => {
    const response = await worker.fetch(get(path), { ASSETS: makeAssets(PRERENDERED) });
    expect(response.status).toBe(404);
    expect(await response.text()).toBe('<h1>Page not found</h1>');
  });

  it.each(['/profile/', '/compare/', '/plan/join/plan-id/invite-token/', '/charity/04-2535767/', '/prompts/planned_prompt/'])('preserves client-only route %s', async (path) => {
    const response = await worker.fetch(get(path), { ASSETS: makeAssets(PRERENDERED) });
    expect(response.status).toBe(200);
  });

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
      const response = await worker.fetch(get('/__/auth/handler?type=signIn&view=popup'), env);

      expect(await response.text()).toBe('auth handler');
      expect(env.ASSETS.fetch).not.toHaveBeenCalled();
      expect(upstream.mock.calls[0][0]).toBe(
        'https://good-measure-giving.firebaseapp.com/__/auth/handler?type=signIn&view=popup',
      );
    } finally {
      upstream.mockRestore();
    }
  });
});
