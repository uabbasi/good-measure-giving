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
    const writable = new Writable({
      write(chunk, _enc, cb) { chunks.push(Buffer.from(chunk)); cb(); },
      final(cb) { cb(); },
    });
    writable.on('finish', () => resolve(Buffer.concat(chunks).toString('utf8')));

    let didError = false;
    const { pipe, abort } = renderToPipeableStream(
      <AppProviders queryClient={queryClient}>
        <StaticRouter location={url}>
          <AppContent />
        </StaticRouter>
      </AppProviders>,
      {
        onAllReady() { pipe(writable); },
        onError(err) { didError = true; reject(err); },
      }
    );
    setTimeout(() => { if (!didError) abort(); }, 15000);
  });
}
