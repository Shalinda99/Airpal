import { useRouter } from 'expo-router';
import React from 'react';
import { Pressable } from 'react-native';

import { Banner, Body, Button, Card, ErrorView, H2, Loading, Screen } from '@/components/ui';
import { cachedGet } from '@/lib/api';
import type { Ticket } from '@/lib/types';
import { useAsync } from '@/lib/useAsync';

export default function Tickets() {
  const router = useRouter();
  const t = useAsync(() => cachedGet<Ticket[]>('tickets', '/tickets'), []);

  return (
    <Screen refreshing={t.loading} onRefresh={t.reload}>
      <Button title="Add ticket" onPress={() => router.push('/tickets/add')} />
      {t.loading && !t.data ? <Loading /> : null}
      {t.error ? <ErrorView message={t.error} onRetry={t.reload} /> : null}
      {t.data?.fromCache ? <Banner text="Offline: showing saved tickets." /> : null}
      {t.data && !t.data.data.length ? <Body muted>No tickets yet. Tickets are deleted automatically a few days after the flight.</Body> : null}
      {t.data?.data.map((x) => (
        <Pressable key={x.id} onPress={() => router.push(`/tickets/${x.id}`)} accessibilityRole="button">
          <Card>
            <H2>
              {x.flight_number} · {x.flight_date}
            </H2>
            <Body muted>
              {x.origin ?? '?'} → {x.destination ?? '?'} · Gate {x.gate ?? 'TBA'}
            </Body>
          </Card>
        </Pressable>
      ))}
    </Screen>
  );
}
