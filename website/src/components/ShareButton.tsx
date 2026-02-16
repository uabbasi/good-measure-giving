/**
 * ShareButton: Share charity via various channels
 *
 * Uses Web Share API on supported devices (mobile), falls back to
 * dropdown menu with copy link, social media, and email options.
 */

import React, { useState, useRef, useEffect } from 'react';
import { Share2, Check, X, Link2, Mail } from 'lucide-react';
import { trackShare, type ShareMethod } from '../utils/analytics';

interface ShareButtonProps {
  charityId: string;
  charityName: string;
  /** Visual variant: icon (default), button (pill), or text (inline link) */
  variant?: 'icon' | 'button' | 'text';
  /** Additional CSS classes */
  className?: string;
  /** Dark mode */
  isDark?: boolean;
}

// Social share URLs
const getShareUrl = (platform: string, url: string, text: string): string => {
  const encodedUrl = encodeURIComponent(url);
  const encodedText = encodeURIComponent(text);

  switch (platform) {
    case 'twitter':
      return `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${encodedText}`;
    case 'facebook':
      return `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`;
    case 'linkedin':
      return `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`;
    case 'email':
      return `mailto:?subject=${encodedText}&body=${encodedUrl}`;
    default:
      return url;
  }
};

// X/Twitter icon (SVG)
const XIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);

// Facebook icon (SVG)
const FacebookIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
  </svg>
);

// LinkedIn icon (SVG)
const LinkedInIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
  </svg>
);

export const ShareButton: React.FC<ShareButtonProps> = ({
  charityId,
  charityName,
  variant = 'icon',
  className = '',
  isDark = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const shareUrl = `${window.location.origin}/charity/${charityId}`;
  const shareText = `Check out ${charityName} on Good Measure`;

  // Close menu on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  // Check if native share is available
  const canNativeShare = typeof navigator !== 'undefined' && !!navigator.share;

  const handleShare = async () => {
    // For text variant, always use dropdown (native share is jarring for inline links)
    // For other variants on mobile, use native share API
    if (canNativeShare && variant !== 'text') {
      try {
        await navigator.share({
          title: charityName,
          text: shareText,
          url: shareUrl,
        });
        trackShare(charityId, charityName, 'native');
      } catch (err) {
        // User cancelled or error - fall back to menu
        if ((err as Error).name !== 'AbortError') {
          setIsOpen(true);
        }
      }
    } else {
      setIsOpen(!isOpen);
    }
  };

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      trackShare(charityId, charityName, 'copy');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const input = document.createElement('input');
      input.value = shareUrl;
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      document.body.removeChild(input);
      setCopied(true);
      trackShare(charityId, charityName, 'copy');
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSocialShare = (platform: ShareMethod) => {
    const url = getShareUrl(platform, shareUrl, shareText);
    if (platform === 'email') {
      window.location.href = url;
    } else {
      window.open(url, '_blank', 'width=600,height=400');
    }
    trackShare(charityId, charityName, platform);
    setIsOpen(false);
  };

  const buttonClasses = variant === 'button'
    ? `inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full font-medium text-sm ${
        isDark
          ? 'bg-slate-700 hover:bg-slate-600 text-white'
          : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
      }`
    : variant === 'text'
    ? `hover:underline ${isDark ? 'hover:text-slate-300' : 'hover:text-slate-600'}`
    : `inline-flex items-center gap-1.5 text-sm ${
        isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-600 hover:text-slate-700'
      }`;

  const menuItemClasses = `flex items-center gap-3 w-full px-3 py-2 text-sm transition-colors ${
    isDark
      ? 'hover:bg-slate-700 text-slate-300'
      : 'hover:bg-slate-100 text-slate-700'
  }`;

  return (
    <div className={`relative ${className}`}>
      <button
        ref={buttonRef}
        onClick={handleShare}
        className={buttonClasses}
        aria-label="Share this charity"
        aria-expanded={isOpen}
      >
        {variant === 'text' ? (
          <span className="inline-flex items-center gap-1">
            <Share2 className="w-3 h-3" />
            Share
          </span>
        ) : (
          <>
            <Share2 className="w-4 h-4" />
            {variant === 'button' && 'Share'}
          </>
        )}
      </button>

      {isOpen && (
        <div
          ref={menuRef}
          className={`absolute right-0 top-full mt-2 w-48 rounded-lg shadow-lg border z-50 ${
            isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
          }`}
        >
          <div className="py-1">
            {/* Copy Link */}
            <button onClick={handleCopyLink} className={menuItemClasses}>
              {copied ? (
                <Check className="w-4 h-4 text-emerald-500" />
              ) : (
                <Link2 className="w-4 h-4" />
              )}
              {copied ? 'Copied!' : 'Copy link'}
            </button>

            {/* Divider */}
            <div className={`my-1 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`} />

            {/* Twitter/X */}
            <button onClick={() => handleSocialShare('twitter')} className={menuItemClasses}>
              <XIcon />
              Share on X
            </button>

            {/* Facebook */}
            <button onClick={() => handleSocialShare('facebook')} className={menuItemClasses}>
              <FacebookIcon />
              Share on Facebook
            </button>

            {/* LinkedIn */}
            <button onClick={() => handleSocialShare('linkedin')} className={menuItemClasses}>
              <LinkedInIcon />
              Share on LinkedIn
            </button>

            {/* Divider */}
            <div className={`my-1 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`} />

            {/* Email */}
            <button onClick={() => handleSocialShare('email')} className={menuItemClasses}>
              <Mail className="w-4 h-4" />
              Send via email
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ShareButton;
