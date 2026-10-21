import React, { useState } from 'react';

import { Banner, Body, Card, Chip, ErrorView, H2, Loading, Row, Screen } from '@/components/ui';
import { cachedGet } from '@/lib/api';
import { useAirport } from '@/lib/airport';
import { fmtDateTime } from '@/lib/format';
import type { Journey } from '@/lib/types';
import { useAsync } from '@/lib/useAsync';

type Flow = 'departure' | 'arrival' | 'transit';
type Scope = 'domestic' | 'international';

export default function JourneyScreen() {
  const { airport } = useAirport();
  const [flow, setFlow] = useState<Flow>('departure');
  const [scope, setScope] = useState<Scope>('international');
  const j = useAsync(
    () => cachedGet<Journey>(`journey:${airport!.id}:${flow}:${scope}`, `/airports/${airport!.id}/journey?flow=${flow}&scope=${scope}`),
    [airport?.id, flow, scope],
  );

  return (
    <Screen refreshing={j.loading} onRefresh={j.reload}>
      <Row style={{ flexWrap: 'wrap' }}>
        {(['departure', 'arrival', 'transit'] as Flow[]).map((f) => (
          <Chip key={f} label={f} active={flow === f} onPress={() => setFlow(f)} />
        ))}
      </Row>
      <Row>
        {(['international', 'domestic'] as Scope[]).map((s) => (
          <Chip key={s} label={s} active={scope === s} onPress={() => setScope(s)} />
        ))}
      </Row>

      {j.loading && !j.data ? <Loading /> : null}
      {j.error ? <ErrorView message={j.error} onRetry={j.reload} /> : null}
      {j.data?.fromCache ? <Banner text="Offline: showing the last saved journey." /> : null}
      {j.data?.data.basic ? (
        <Banner tone="warning" text="This airport has not published verified procedures yet (Basic Mode). Please check airport signs and your airline." />
      ) : null}
      {j.data && !j.data.data.basic && j.data.data.last_verified_at ? (
        <Body muted>Last verified {fmtDateTime(j.data.data.last_verified_at, airport?.tz)}</Body>
      ) : null}

      {j.data?.data.steps.map((s, i) => (
        <Card key={s.id}>
          <H2>
            {i + 1}. {s.title}
            {s.typical_minutes ? `  (about ${s.typical_minutes} min)` : ''}
          </H2>
          {s.instructions ? <Body>{s.instructions}</Body> : null}
          {s.documents.length ? <Body>Documents: {s.documents.join(', ')}</Body> : null}
          {s.prohibited_items.length ? <Body>Not allowed: {s.prohibited_items.join(', ')}</Body> : null}
          {s.tips.map((t) => (
            <Body key={t} muted>Tip: {t}</Body>
          ))}
        </Card>
      ))}
    </Screen>
  );
}
