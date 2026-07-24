/**
 * Firestore's `updateDoc`/`setDoc`/`WriteBatch.update()` reject any field
 * whose value is explicitly `undefined`, anywhere in the payload — including
 * nested objects and array elements. A plain object with a key set to
 * `undefined` is NOT the same thing as that key being absent: Vitest's
 * `toEqual`/`toBeUndefined()` treat the two as equal, but Firestore does not.
 *
 * Walks a value the same way Firestore's SDK validates a write and throws
 * with the same error shape, so a test can catch a reintroduced
 * `field: possiblyUndefinedValue` bug without a live Firestore connection.
 * See giving-plan-undefined-field-writes memory / commit 8caccf5.
 */
export function assertFirestoreWritable(value: unknown, path = '$'): void {
  if (value === undefined) {
    throw new Error(`Unsupported field value: undefined (found at ${path})`);
  }
  if (Array.isArray(value)) {
    value.forEach((v, i) => assertFirestoreWritable(v, `${path}[${i}]`));
    return;
  }
  if (value !== null && typeof value === 'object') {
    for (const key of Object.keys(value as Record<string, unknown>)) {
      assertFirestoreWritable((value as Record<string, unknown>)[key], `${path}.${key}`);
    }
  }
}
