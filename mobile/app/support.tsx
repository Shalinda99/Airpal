import React from 'react';
import { Linking } from 'react-native';

import { Banner, Body, Button, Card, ErrorView, H2, Loading, Screen } from '@/components/ui';
import { cachedGet } from '@/lib/api';
import { useAirport } from '@/lib/airport';
import type { SupportChannel } from '@/lib/types';
import { useAsync } from '@/lib/useAsync';

type Contact = { label: string; phone: string };

export default function Support() {
  const { airport } = useAirport();
  const s = useAsync(
    () => cachedGet<{ channels: SupportChannel[] }>(`support:${airport!.id}`, `/airports/${airport!.id}/support`),
    [airport?.id],
  );
  const e = useAsync(() => cachedGet<Contact[]>(`emergency:${airport!.id}`, `/airports/${airport!.id}/emergency-contacts`), [airport?.id]);

  return (
    <Screen refreshing={s.loading} onRefresh={() => { s.reload(); e.reload(); }}>
      {s.loading && !s.data ? <Loading /> : null}
      {s.error ? <ErrorView message={s.error} onRetry={s.reload} /> : null}
      {s.data?.fromCache ? <Banner text="Offline: showing saved contact details." /> : null}
      {s.data && !s.data.data.channels.length ? <Body muted>This airport has not published customer care contacts yet.</Body> : null}
      {s.data?.data.channels.map((c) => (
        <Card key={c.id}>
          <H2>{c.type === 'whatsapp' ? 'WhatsApp' : c.type === 'phone' ? 'Phone' : 'Email'}</H2>
          <Body>{c.value}</Body>
          {c.open_now ? (
            <Body muted>Open now</Body>
          ) : (
            <Banner tone="warning" text={c.out_of_hours_message ?? 'Currently closed.'} />
          )}
          <Button title="Contact" variant={c.open_now ? 'primary' : 'secondary'} onPress={() => Linking.openURL(c.link)} />
        </Card>
      ))}
      {e.data?.data.length ? (
        <Card>
          <H2>Emergency</H2>
          {e.data.data.map((c) => (
            <Button key={c.phone} title={`${c.label}: ${c.phone}`} variant="danger" onPress={() => Linking.openURL(`tel:${c.phone.replace(/[^\d+]/g, '')}`)} />
          ))}
        </Card>
      ) : null}
    </Screen>
  );
}
