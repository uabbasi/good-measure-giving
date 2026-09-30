import React from 'react';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { GmgContentFrame, ContentHero, Em, CtaLink, ALink } from '../src/components/gmg/content';

export const NotFoundPage: React.FC = () => {
  const { isDark } = useLandingTheme();

  return (
    <GmgContentFrame isDark={isDark}>
      {(ctx) => (
        <>
          <ContentHero
            ctx={ctx}
            title={<>Page <Em p={ctx.p}>not found.</Em></>}
            lead="The page you're looking for doesn't exist or may have moved."
          />
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 24 }}>
            <CtaLink p={ctx.p} to="/browse/">Browse charities</CtaLink>
            <ALink p={ctx.p} to="/">Go home</ALink>
          </div>
        </>
      )}
    </GmgContentFrame>
  );
};
