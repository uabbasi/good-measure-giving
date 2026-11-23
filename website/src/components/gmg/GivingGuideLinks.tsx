import { Link } from 'react-router-dom';
import { givingGuidePaths } from '../../lib/paths';
import type { GmgPalette } from './tokens';

export function GivingGuideLinks({ p, centered = false }: { p: GmgPalette; centered?: boolean }) {
  const linkStyle = { color: p.accent, textUnderlineOffset: 3 };
  return (
    <nav aria-label="Charity comparison guides" style={{
      display: 'flex', flexWrap: 'wrap', gap: '8px 20px', marginTop: 16, fontSize: 14,
      justifyContent: centered ? 'center' : undefined,
    }}>
      <Link style={linkStyle} to={givingGuidePaths.ranked}>Best Muslim charities in the USA</Link>
      <Link style={linkStyle} to={givingGuidePaths.zakat}>Where to give zakat</Link>
    </nav>
  );
}
