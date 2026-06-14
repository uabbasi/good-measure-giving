import { useState, useEffect } from 'react';

// Mobile breakpoint via matchMedia. The motif uses inline styles, so responsive
// behavior is driven by this hook rather than CSS media queries.
export const useIsMobile = (query = '(max-width: 768px)'): boolean => {
  const [match, setMatch] = useState(
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false,
  );
  useEffect(() => {
    const mql = window.matchMedia(query);
    const on = () => setMatch(mql.matches);
    on();
    mql.addEventListener('change', on);
    return () => mql.removeEventListener('change', on);
  }, [query]);
  return match;
};
