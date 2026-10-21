import { countdown, minutesUntil, todayISO } from '../format';

describe('format helpers', () => {
  it('returns null/empty for missing times', () => {
    expect(minutesUntil(null)).toBeNull();
    expect(countdown(undefined)).toBe('');
  });

  it('formats a countdown', () => {
    const inNinety = new Date(Date.now() + 90 * 60000 + 5000).toISOString();
    expect(countdown(inNinety)).toBe('1h 30m');
    expect(countdown(new Date(Date.now() - 60000).toISOString())).toBe('now');
  });

  it('produces an ISO date', () => {
    expect(todayISO()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
