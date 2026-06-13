/** Smooth-scroll to a single-scroll CDP section by its element id. */
export function scrollToSection(id: string): void {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
