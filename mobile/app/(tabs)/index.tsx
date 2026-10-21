import { useRouter } from 'expo-router';
import React from 'react';
import { Pressable } from 'react-native';

import { Badge, Banner, Body, Card, ErrorView, H1, H2, Loading, Row, Screen, colors } from '@/components/ui';
import { cachedGet } from '@/lib/api';
import { useAirport } from '@/lib/airport';
import { countdown, fmtDateTime, fmtTime } from '@/lib/format';
import type { Notice, Ticket } from '@/lib/types';
import { useAsync } from '@/lib/useAsync';

const LINKS: { title: string; path: string; hint: string }[] = [
  { title: 'Airport journey', path: '/journey', hint: 'Check-in, security, immigration' },
  { title: 'Map flow', path: '/map', hint: 'Step-by-step route with walking times' },
  { title: 'Customer care', path: '/support', hint: 'Call, WhatsApp or email' },
  { title: 'My tickets', path: '/tickets', hint: 'Gate, boarding and countdown' },
];

export default function Home() {
  const { airport } = useAirport();
  const router = useRouter();
  const notices = useAsync(
    () => cachedGet<Notice[]>(`notices:${airport!.id}`, `/airports/${airport!.id}/notices`),
    [airport?.id],
  );
  const tickets = useAsync(() => cachedGet<Ticket[]>('tickets', '/tickets'), [airport?.id]);

  if (!airport) return <Loading />;
  const next = tickets.data?.data.find((t) => !t.boarding_time || new Date(t.boarding_time) > new Date());

  return (
    <Screen
      refreshing={notices.loading || tickets.loading}
      onRefresh={() => {
        notices.reload();
        tickets.reload();
      }}
    >
      <Pressable onPress={() => router.push('/airport-select')} accessibilityRole="button" accessibilityLabel="Change airport">
        <H1>{airport.name}</H1>
        <Row>
          <Badge text={airport.badge} color={airport.verified ? colors.ok : colors.warn} />
          <Body muted>Tap to change</Body>
        </Row>
      </Pressable>

      {!airport.verified ? (
        <Banner
          tone="warning"
          text="Basic Mode: this airport has not published verified information yet. Live flights and weather work; procedures, maps and the assistant's airport answers are limited."
        />
      ) : null}

      {notices.data?.fromCache ? <Banner text="Offline: showing the last saved information." /> : null}
      {notices.data?.data.map((n) => (
        <Banner key={n.id} tone={n.severity} text={`${n.title}: ${n.body}`} />
      ))}

      {next ? (
        <Pressable onPress={() => router.push(`/tickets/${next.id}`)} accessibilityRole="button">
          <Card>
            <H2>
              {next.flight_number} {next.origin ?? ''} → {next.destination ?? ''}
            </H2>
            <Body>
              Gate {next.gate ?? 'TBA'} · Boarding {fmtTime(next.boarding_time, airport.tz)}
            </Body>
            {next.leave_for_gate_at ? (
              <Body muted>Leave for the gate in {countdown(next.leave_for_gate_at)} ({fmtDateTime(next.leave_for_gate_at, airport.tz)})</Body>
            ) : null}
          </Card>
        </Pressable>
      ) : tickets.loading ? null : (
        <Card>
          <Body>Add your boarding pass to see gate changes and a leave-for-gate countdown.</Body>
        </Card>
      )}

      {notices.error ? <ErrorView message={notices.error} onRetry={notices.reload} /> : null}

      {LINKS.map((l) => (
        <Pressable key={l.path} onPress={() => router.push(l.path as never)} accessibilityRole="button">
          <Card>
            <H2>{l.title}</H2>
            <Body muted>{l.hint}</Body>
          </Card>
        </Pressable>
      ))}
    </Screen>
  );
}
