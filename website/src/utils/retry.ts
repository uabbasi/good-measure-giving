/**
 * Retry utilities for handling transient errors
 *
 * Implements exponential backoff retry logic for network requests
 * and other operations that may fail temporarily.
 */

export interface RetryOptions {
  maxAttempts?: number;
  initialDelayMs?: number;
  maxDelayMs?: number;
  backoffMultiplier?: number;
  shouldRetry?: (error: any) => boolean;
}

const DEFAULT_OPTIONS: Required<RetryOptions> = {
  maxAttempts: 3,
  initialDelayMs: 1000,
  maxDelayMs: 10000,
  backoffMultiplier: 2,
  shouldRetry: isTransientError,
};

/**
 * Determine if an error is transient and should be retried
 */
export function isTransientError(error: any): boolean {
  // Network errors
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return true;
  }

  // HTTP status codes that indicate transient errors
  if (error?.status) {
    const transientStatusCodes = [
      408, // Request Timeout
      429, // Too Many Requests
      500, // Internal Server Error
      502, // Bad Gateway
      503, // Service Unavailable
      504, // Gateway Timeout
    ];
    return transientStatusCodes.includes(error.status);
  }

  // Error messages that indicate network issues
  if (error?.message) {
    const transientMessages = [
      'network error',
      'timeout',
      'connection',
      'econnrefused',
      'enotfound',
      'etimedout',
    ];
    const lowerMessage = error.message.toLowerCase();
    return transientMessages.some(msg => lowerMessage.includes(msg));
  }

  return false;
}

/**
 * Sleep for a specified duration
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Retry an async operation with exponential backoff
 *
 * @param fn - The async function to retry
 * @param options - Retry configuration options
 * @returns The result of the successful operation
 * @throws The last error if all retries fail
 *
 * @example
 * const data = await retryWithBackoff(
 *   () => fetch('/api/data'),
 *   { maxAttempts: 5, initialDelayMs: 500 }
 * );
 */
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  let lastError: any;
  let delay = opts.initialDelayMs;

  for (let attempt = 1; attempt <= opts.maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      // Don't retry if this is the last attempt
      if (attempt === opts.maxAttempts) {
        break;
      }

      // Check if error should be retried
      if (!opts.shouldRetry(error)) {
        throw error;
      }

      // Log retry attempt (optional - can be configured)
      console.debug(
        `Retry attempt ${attempt}/${opts.maxAttempts} after ${delay}ms due to:`,
        error
      );

      // Wait before retrying
      await sleep(delay);

      // Calculate next delay with exponential backoff
      delay = Math.min(delay * opts.backoffMultiplier, opts.maxDelayMs);
    }
  }

  // All retries exhausted
  throw lastError;
}

/**
 * Higher-order function to wrap a function with retry logic
 *
 * @example
 * const fetchWithRetry = withRetry(
 *   (url: string) => fetch(url),
 *   { maxAttempts: 3 }
 * );
 * const response = await fetchWithRetry('/api/data');
 */
export function withRetry<TArgs extends any[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
  options: RetryOptions = {}
): (...args: TArgs) => Promise<TResult> {
  return (...args: TArgs) => retryWithBackoff(() => fn(...args), options);
}
