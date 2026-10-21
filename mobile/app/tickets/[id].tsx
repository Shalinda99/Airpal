import { useLocalSearchParams, useRouter } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { Alert } from 'react-native';

import { Badge, Banner, Body, Button, Card, ErrorView, H1, H2, Loading, Screen, colors } from '@/components/ui';
import { api, clearCaches } from '@/lib/api';
import { STATUS_COLORS, countdown, fmtDateTime, fmtTime } from '@/lib/format';
import { useAirport } from '@/lib/airport';
import type { Ticket } from '@/lib/types';
import { useAsync } from '@/lib/useAsync';

export default function TicketDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { airport } = useAirport();
  const t = useAsync(() => api<Ticket>(`/tickets/${id}`), [id]);
  const [, tick] = useState(0);

  useEffect(() => {
    const i = setInterval(() => tick((n) => n + 1), 30000);
    const r = setInterval(() => t.reload(), 120000);
    return () => {
      clearInterval(i);
      clearInterval(r);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (t.loading && !t.data) return <Loading />;
  if (t.error || !t.data) return <ErrorView message={t.error ?? 'Ticket not found'} onRetry={t.reload} />;
  const k = t.data;
  const status = k.status?.status ?? 'scheduled';
  const tz = airport?.tz;

  return (
    <Screen refreshing={t.loading} onRefresh={t.reload}>
      <H1>{k.flight_number}</H1>
      <Body muted>
        {k.origin ?? '?'} → {k.destination ?? '?'} · {k.flight_date}
      </Body>
      <Badge text={status} color={STATUS_COLORS[status] ?? STATUS_COLORS.unknown} />

      {k.leave_for_gate_at ? (
        <Banner
          tone={(new Date(k.leave_for_gate_at).getTime() - Date.now()) < 10 * 60000 ? 'warning' : 'info'}
          text={`Leave for the gate in ${countdown(k.leave_for_gate_at)} (${fmtTime(k.leave_for_gate_at, tz)}). Walking time ${k.gate_walk_minutes} min.`}
        />
      ) : null}

      <Card>
        <H2>Boarding</H2>
        <Body>Gate: {k.gate ?? 'Not assigned yet'}</Body>
        <Body>Terminal: {k.terminal ?? 'n/a'}</Body>
        <Body>Boarding: {fmtDateTime(k.boarding_time, tz) || 'unknown'}</Body>
        <Body>Seat: {k.seat ?? 'n/a'}</Body>
        {k.baggage_allowance ? <Body>Baggage: {k.baggage_allowance}</Body> : null}
      </Card>

      <Card>
        <H2>Passenger</H2>
        <Body>{k.passenger_name ?? 'n/a'}</Body>
        <Body muted>Booking reference: {k.pnr ?? 'n/a'}</Body>
      </Card>

      <Button title="Refresh" variant="secondary" onPress={t.reload} />
      <Button
        title="Delete ticket"
        variant="danger"
        onPress={() =>
          Alert.alert('Delete ticket?', 'This removes the ticket from our servers.', [
            { text: 'Cancel', style: 'cancel' },
            {
              text: 'Delete',
              style: 'destructive',
              onPress: async () => {
                await api(`/tickets/${id}`, { method: 'DELETE' });
                await clearCaches();
                router.back();
              },
            },
          ])
        }
      />
      <Body style={{ color: colors.muted, fontSize: 12 }}>Gate and time information comes from live flight data and may change.</Body>
    </Screen>
  );
}
