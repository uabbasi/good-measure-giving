/**
 * Worker entry point:
 * 1. Proxies /__/auth/* to Firebase (same-origin auth for Safari)
 * 2. Serves static assets from dist/
 * 3. Falls back to /index.html for SPA client-side routing
 *
 * wrangler not_found_handling must be "none" so the assets layer doesn't
 * intercept /__/auth/* navigation requests before the Worker runs.
 * We handle SPA fallback here by fetching /index.html explicitly.
 */

interface Env {
  ASSETS: { fetch: (request: Request) => Promise<Response> };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Proxy Firebase auth handler requests
    if (url.pathname.startsWith('/__/auth/')) {
      const firebaseUrl = `https://good-measure-giving.firebaseapp.com${url.pathname}${url.search}`;
      const headers = new Headers(request.headers);
      headers.delete('host');

      const response = await fetch(firebaseUrl, {
        method: request.method,
        headers,
        body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : undefined,
        redirect: 'manual',
      });

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    }

    // Serve static assets; fall back to / for SPA routing
    try {
      const response = await env.ASSETS.fetch(request);
      if (response.ok || response.status === 304) {
        return response;
      }
    } catch {
      // Assets throws for non-existent paths when not_found_handling is "none"
    }

    // SPA fallback: fetch / which serves index.html
    // (don't fetch /index.html directly — assets redirects it to / causing a loop)
    return env.ASSETS.fetch(new Request(new URL('/', url), { headers: request.headers }));
  },
};
