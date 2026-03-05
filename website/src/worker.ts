/**
 * Worker entry point:
 * 1. Proxies /__/auth/* to Firebase (same-origin auth for Safari)
 * 2. All other requests handled by Cloudflare's asset serving + SPA fallback
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

    // Everything else: static assets + SPA fallback (handled by wrangler config)
    return env.ASSETS.fetch(request);
  },
};
