// API timestamps without an offset are UTC (Python datetime.utcnow()).
// Explicit offsets are kept intact so the browser can display local time.
export function parseApiTimestamp(value: string): Date {
  const timestamp = value.trim().replace(' ', 'T');
  const hasOffset = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(timestamp);
  return new Date(hasOffset ? timestamp : `${timestamp}Z`);
}
