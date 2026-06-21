import React from 'react';
import { renderToPipeableStream } from 'react-dom/server';
import { Writable } from 'node:stream';
import { StaticRouter } from 'react-router-dom/server';
import { AppProviders, AppContent, createAppQueryClient } from './App';

export type SeedEntry = { queryKey: unknown[]; data: unknown };

export function render(url: string, seed: SeedEntry[]): Promise<string> {
  const queryClient = createAppQueryClient();
  for (const { queryKey, data } of seed) queryClient.setQueryData(queryKey, data);

  return new Promise<string>((resolve, reject) => {
    const chunks: Buffer[] = [];
    let settled = false;
    let errored = false;
    let timer: ReturnType<typeof setTimeout>;

    const settle = (fn: () => void) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      fn();
    };

    const writable = new Writable({
      write(chunk, _enc, cb) { chunks.push(Buffer.from(chunk)); cb(); },
    });
    writable.on('finish', () => {
      if (!errored) settle(() => resolve(Buffer.concat(chunks).toString('utf8')));
    });

    const { pipe, abort } = renderToPipeableStream(
      <AppProviders queryClient={queryClient}>
        <StaticRouter location={url}>
          <AppContent />
        </StaticRouter>
      </AppProviders>,
      {
        onAllReady() { pipe(writable); },
        onError(err) { errored = true; settle(() => reject(err)); },
      }
    );

    timer = setTimeout(() => settle(() => { abort(); reject(new Error(`SSR render timeout for ${url}`)); }), 15000);
  });
}
