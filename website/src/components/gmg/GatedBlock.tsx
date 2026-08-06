// Motif-native wrapper around CommunityGate. The shared JoinCommunityPrompt is
// Tailwind-styled and would read as a different site inside this page.
//
// A fallback is always supplied: CommunityGate with none renders nothing, which
// would leave a signed-out visitor staring at a hole with no clue that anything
// exists there.

import React from 'react';
import { CommunityGate } from '../../auth/CommunityGate';
import { SignInButton } from '../../auth/SignInButton';
import { GmgPalette, FONT_MONO } from './tokens';

export const GatedBlock: React.FC<{
  label: string;
  p: GmgPalette;
  children: React.ReactNode;
}> = ({ label, p, children }) => (
  <CommunityGate
    fallback={
      <div
        style={{
          border: `1px dashed ${p.rule2}`,
          borderRadius: 6,
          padding: '14px 16px',
          background: p.bg2,
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <span
          style={{
            fontFamily: FONT_MONO,
            fontSize: 10,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: p.sub2,
          }}
        >
          {label}
        </span>
        <span style={{ fontSize: 12.5, color: p.sub, flex: '1 1 240px' }}>
          Sign in to see this — it's free.
        </span>
        <SignInButton variant="button" />
      </div>
    }
  >
    {children}
  </CommunityGate>
);

export default GatedBlock;
