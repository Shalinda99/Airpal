import React, { useMemo, useState } from 'react';
import { FlatList } from 'react-native';

import { Badge, Banner, Body, Card, Chip, ErrorView, H2, Input, Loading, Row, colors } from '@/components/ui';
import { cachedGet } from '@/lib/api';
import { useAirport } from '@/lib/airport';
import { STATUS_COLORS, fmtTime } from '@/lib/format';
import type { Board } from '@/lib/types';
import { useAsync } from '@/lib/useAsync';

const STATUSES = ['all', 'scheduled', 'boarding', 'delayed', 'departed', 'landed', 'cancelled'];

export default function Flights() {
  const { airport } = useAirport();
  const [dir, setDir] = useState<'departure' | 'arrival'>('departure');
  const [status, setStatus] = useState('all');
  const [q, setQ] = useState('');

  const board = useAsync(
    () => cachedGet<Board>(`board:${airport!.id}`, `/airports/${airport!.id}/flights`),
    [airport?.id],
  );

  const flights = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return (board.data?.data.flights ?? [])
      .filter((f) => f.direction === dir)
      .filter((f) => status === 'all' || f.status === status)
      .filter(
        (f) =>
          !ql ||
          f.flight_number.toLowerCase().includes(ql) ||
          (f.other_airport_name ?? '').toLowerCase().includes(ql) ||
          (f.other_airport_iata ?? '').toLowerCase() === ql ||
          (f.airline ?? '').toLowerCase().includes(ql),
      )
      .sort((a, b) => (a.scheduled ?? '').localeCompare(b.scheduled ?? ''));
  }, [board.data, dir, status, q]);

  if (!airport) return <Loading />;

  return (
    <FlatList
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: 16, gap: 10 }}
      data={flights}
      keyExtractor={(f, i) => `${f.flight_number}-${f.scheduled}-${i}`}
      refreshing={board.loading}
      onRefresh={board.reload}
      ListHeaderComponent={
        <>
          <Row style={{ marginBottom: 8 }}>
            <Chip label="Departures" active={dir === 'departure'} onPress={() => setDir('departure')} />
            <Chip label="Arrivals" active={dir === 'arrival'} onPress={() => setDir('arrival')} />
          </Row>
          <Input placeholder="Search flight, airline or city" value={q} onChangeText={setQ} autoCapitalize="none" />
          <Row style={{ flexWrap: 'wrap', marginVertical: 8 }}>
            {STATUSES.map((s) => (
              <Chip key={s} label={s} active={status === s} onPress={() => setStatus(s)} />
            ))}
          </Row>
          {board.data?.fromCache ? <Banner text="Offline: showing the last saved board." /> : null}
          {board.data?.data.stale && !board.data.fromCache ? (
            <Banner tone="warning" text="Live data is temporarily unavailable. Showing the most recent board." />
          ) : null}
          {board.data?.data.provider === 'mock' ? <Banner text="Demo data (mock flight provider)." /> : null}
        </>
      }
      ListEmptyComponent={
        board.loading ? <Loading /> : board.error ? <ErrorView message={board.error} onRetry={board.reload} /> : <Body muted>No flights match.</Body>
      }
      renderItem={({ item: f }) => (
        <Card>
          <Row style={{ justifyContent: 'space-between' }}>
            <H2>
              {f.flight_number} · {f.other_airport_name ?? f.other_airport_iata ?? ''}
            </H2>
            <Badge text={f.status} color={STATUS_COLORS[f.status] ?? STATUS_COLORS.unknown} />
          </Row>
          <Body>
            {fmtTime(f.scheduled, airport.tz)}
            {f.estimated && f.estimated !== f.scheduled ? `  → ${fmtTime(f.estimated, airport.tz)}` : ''}
          </Body>
          <Body muted>
            {f.airline ?? ''}
            {f.terminal ? ` · Terminal ${f.terminal}` : ''}
            {f.direction === 'departure' ? ` · Gate ${f.gate ?? 'TBA'}` : f.baggage_belt ? ` · Belt ${f.baggage_belt}` : ''}
          </Body>
        </Card>
      )}
    />
  );
}
