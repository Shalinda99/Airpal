import React, { useState } from 'react';
import { View } from 'react-native';

import { Banner, Body, Card, Chip, ErrorView, H2, Loading, Row, Screen, colors } from '@/components/ui';
import { cachedGet } from '@/lib/api';
import { useAirport } from '@/lib/airport';
import type { MapFlow } from '@/lib/types';
import { useAsync } from '@/lib/useAsync';

type Flow = 'departure' | 'arrival' | 'transit';
type Scope = 'domestic' | 'international';

export default function MapScreen() {
  const { airport } = useAirport();
  const [flow, setFlow] = useState<Flow>('departure');
  const [scope, setScope] = useState<Scope>('international');
  const m = useAsync(
    () => cachedGet<MapFlow>(`map:${airport!.id}:${flow}:${scope}`, `/airports/${airport!.id}/map-flow?flow=${flow}&scope=${scope}`),
    [airport?.id, flow, scope],
  );
  const nodes = m.data?.data.nodes ?? [];

  return (
    <Screen refreshing={m.loading} onRefresh={m.reload}>
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
      {m.loading && !m.data ? <Loading /> : null}
      {m.error ? <ErrorView message={m.error} onRetry={m.reload} /> : null}
      {m.data?.fromCache ? <Banner text="Offline: showing the last saved map flow." /> : null}
      {m.data?.data.basic ? <Banner tone="warning" text="No verified map flow for this airport yet (Basic Mode)." /> : null}
      {nodes.length ? <Body muted>Total walking time about {m.data?.data.total_walking_minutes} min</Body> : null}

      {nodes.map((n, i) => (
        <View key={n.id} style={{ flexDirection: 'row', gap: 12 }}>
          <View style={{ alignItems: 'center', width: 28 }}>
            <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' }}>
              <Body style={{ color: '#fff', fontWeight: '700' }}>{i + 1}</Body>
            </View>
            {i < nodes.length - 1 ? <View style={{ flex: 1, width: 2, backgroundColor: colors.border, minHeight: 36 }} /> : null}
          </View>
          <View style={{ flex: 1, paddingBottom: 12 }}>
            <Card>
              <H2>{n.label}</H2>
              {n.notes ? <Body muted>{n.notes}</Body> : null}
              {i < nodes.length - 1 ? <Body muted>Walk about {n.walking_minutes} min to the next step</Body> : null}
            </Card>
          </View>
        </View>
      ))}
    </Screen>
  );
}
