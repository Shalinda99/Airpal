export function fmtTime(iso: string | null | undefined, tz?: string): string {
  if (!iso) return '--:--';
  try {
    return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', timeZone: tz }).format(new Date(iso));
  } catch {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
}

export function fmtDateTime(iso: string | null | undefined, tz?: string): string {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(undefined, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: tz,
    }).format(new Date(iso));
  } catch {
    return new Date(iso).toLocaleString();
  }
}

export function minutesUntil(iso: string | null | undefined): number | null {
  if (!iso) return null;
  return Math.round((new Date(iso).getTime() - Date.now()) / 60000);
}

export function countdown(iso: string | null | undefined): string {
  const m = minutesUntil(iso);
  if (m === null) return '';
  if (m <= 0) return 'now';
  const h = Math.floor(m / 60);
  return h ? `${h}h ${m % 60}m` : `${m}m`;
}

export function todayISO(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export const STATUS_COLORS: Record<string, string> = {
  scheduled: '#64748b',
  boarding: '#d97706',
  departed: '#0ea5e9',
  delayed: '#dc2626',
  landed: '#16a34a',
  cancelled: '#7f1d1d',
  unknown: '#94a3b8',
};
