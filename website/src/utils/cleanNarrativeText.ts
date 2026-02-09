/**
 * Cleans narrative text for display by rounding long floating-point decimals
 * that leak from pipeline data (e.g., "98.33333333333333/100" → "98/100").
 *
 * Handles patterns like:
 *  - "98.33333333333333/100" → "98/100"
 *  - "score of 72.66666666666667" → "score of 73"
 *  - "85.9%" stays as-is (short decimals are intentional)
 */
export function cleanNarrativeText(text: string): string {
  // Match numbers with 4+ decimal places (pipeline artifacts) and round them.
  // Captures the integer part and decimal part separately.
  return text.replace(/(\d+)\.(\d{4,})/g, (_match, intPart, decPart) => {
    const full = parseFloat(`${intPart}.${decPart}`);
    return String(Math.round(full));
  });
}
