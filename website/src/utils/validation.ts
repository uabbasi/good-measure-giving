/**
 * Client-side validation utilities
 *
 * Validates input before sending to API to reduce unnecessary
 * server requests and provide immediate user feedback.
 */

/**
 * Validate EIN (Employer Identification Number) format
 * Format: XX-XXXXXXX (9 digits with hyphen after 2nd digit)
 */
export function isValidEIN(ein: string): boolean {
  if (!ein || typeof ein !== 'string') {
    return false;
  }

  // Remove whitespace
  const cleaned = ein.trim();

  // Check format: XX-XXXXXXX
  const einRegex = /^\d{2}-\d{7}$/;
  return einRegex.test(cleaned);
}

/**
 * Validate EIN and return error message if invalid
 */
export function validateEIN(ein: string): string | null {
  if (!ein) {
    return 'EIN is required';
  }

  if (!isValidEIN(ein)) {
    return 'Invalid EIN format. Expected format: XX-XXXXXXX (e.g., 12-3456789)';
  }

  return null;
}

/**
 * Validate page number for pagination
 */
export function validatePageNumber(page: number): string | null {
  if (!Number.isInteger(page)) {
    return 'Page number must be an integer';
  }

  if (page < 1) {
    return 'Page number must be at least 1';
  }

  if (page > 10000) {
    return 'Page number too large';
  }

  return null;
}

/**
 * Validate page size for pagination
 */
export function validatePageSize(limit: number): string | null {
  if (!Number.isInteger(limit)) {
    return 'Page size must be an integer';
  }

  if (limit < 1) {
    return 'Page size must be at least 1';
  }

  if (limit > 100) {
    return 'Page size cannot exceed 100';
  }

  return null;
}

/**
 * Validate search query string
 */
export function validateSearchQuery(query: string): string | null {
  if (!query) {
    return null; // Empty query is valid (returns all results)
  }

  if (typeof query !== 'string') {
    return 'Search query must be a string';
  }

  const trimmed = query.trim();

  if (trimmed.length < 2) {
    return 'Search query must be at least 2 characters';
  }

  if (trimmed.length > 200) {
    return 'Search query is too long (max 200 characters)';
  }

  return null;
}

/**
 * Validate charity search parameters
 */
export interface CharitySearchParams {
  search?: string;
  page?: number;
  limit?: number;
  category?: string;
}

export function validateCharitySearchParams(
  params: CharitySearchParams
): { valid: boolean; errors: Record<string, string> } {
  const errors: Record<string, string> = {};

  if (params.search !== undefined) {
    const error = validateSearchQuery(params.search);
    if (error) {
      errors.search = error;
    }
  }

  if (params.page !== undefined) {
    const error = validatePageNumber(params.page);
    if (error) {
      errors.page = error;
    }
  }

  if (params.limit !== undefined) {
    const error = validatePageSize(params.limit);
    if (error) {
      errors.limit = error;
    }
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  };
}

import DOMPurify from 'dompurify';

/**
 * Sanitize user input to prevent XSS using DOMPurify
 *
 * DOMPurify provides comprehensive protection against XSS attacks by:
 * - Parsing HTML and removing malicious content
 * - Preventing script execution
 * - Handling edge cases that basic regex replacement misses
 */
export function sanitizeInput(input: string): string {
  if (!input || typeof input !== 'string') {
    return '';
  }

  // Use DOMPurify with strict settings
  return DOMPurify.sanitize(input, {
    ALLOWED_TAGS: [], // Strip all HTML tags by default
    ALLOWED_ATTR: [], // Strip all attributes
    KEEP_CONTENT: true, // Keep text content
  });
}

/**
 * Sanitize HTML content while preserving safe tags
 * Use this when you need to allow some HTML formatting
 */
export function sanitizeHTML(html: string): string {
  if (!html || typeof html !== 'string') {
    return '';
  }

  // Allow safe formatting tags only
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: [],
  });
}
