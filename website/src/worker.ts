/**
 * Worker entry point:
 * 1. Proxies /__/auth/* to Firebase (same-origin auth for Safari)
 * 2. Serves static assets from dist/
 * 3. Falls back to index.html for SPA client-side routing
 *
 * We handle SPA fallback here instead of wrangler's not_found_handling
 * because that setting intercepts navigation requests before the Worker
 * runs, which prevents the auth proxy from working.
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

    // Try serving the static asset; fall back to index.html for SPA routing
    try {
      const response = await env.ASSETS.fetch(request);
      if (response.status >= 400) {
        return env.ASSETS.fetch(new URL('/', url).toString());
      }
      return response;
    } catch {
      // Assets handler may throw for non-existent paths
      return env.ASSETS.fetch(new URL('/', url).toString());
    }
  },
};
