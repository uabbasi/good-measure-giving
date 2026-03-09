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
  const rounded = text.replace(/(\d+)\.(\d{4,})/g, (_match, intPart, decPart) => {
    const full = parseFloat(`${intPart}.${decPart}`);
    return String(Math.round(full));
  });

  // Donor-facing language should reflect public website claims, not a GMG
  // verification of fiqh compliance. Soften a few common generated phrases.
  return rounded
    .replace(/\bverified zakat eligibility\b/gi, 'a public zakat claim on its website')
    .replace(/\bverified zakat-eligible status\b/gi, 'a public zakat claim on its website')
    .replace(/\bofficially recognized as zakat-eligible\b/gi, 'described on its website as accepting zakat')
    .replace(/\brecognized as zakat-eligible\b/gi, 'described on its website as accepting zakat')
    .replace(/\bis verified as zakat-eligible\b/gi, 'says it accepts zakat on its website')
    .replace(/\bis a zakat-eligible organization\b/gi, 'says on its website that it accepts zakat')
    .replace(/\bis a zakat-eligible entity\b/gi, 'says on its website that it accepts zakat')
    .replace(/\bmaintains a zakat-eligible status\b/gi, 'says on its website that it accepts zakat')
    .replace(/\bclearly state whether donations are zakat-eligible\b/gi, 'clearly state whether the charity accepts zakat')
    .replace(/\bzakat-eligible status\b/gi, 'publicly stated zakat acceptance')
    .replace(/\bzakat eligibility\b/gi, 'a public zakat claim');
}
