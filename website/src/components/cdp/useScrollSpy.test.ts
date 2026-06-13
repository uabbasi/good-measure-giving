import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useScrollSpy } from './useScrollSpy';

beforeEach(() => {
  // @ts-expect-error jsdom lacks IntersectionObserver
  global.IntersectionObserver = class {
    constructor(public cb: any) {}
    observe() {}
    disconnect() {}
  };
});

describe('useScrollSpy', () => {
  it('defaults active id to the first section', () => {
    const { result } = renderHook(() => useScrollSpy(['about', 'evidence']));
    expect(result.current).toBe('about');
  });

  it('returns empty string for an empty list', () => {
    const { result } = renderHook(() => useScrollSpy([]));
    expect(result.current).toBe('');
  });
});
