import React, { useState } from 'react';
import { View } from 'react-native';

import { Banner, Body, Button, Card, Chip, ErrorView, H2, Input, Loading, Row, Screen } from '@/components/ui';
import { ApiError, api } from '@/lib/api';
import type { SavedPlace } from '@/lib/types';
import { useAsync } from '@/lib/useAsync';

const KINDS = ['home', 'hotel', 'work', 'saved'] as const;

export default function Places() {
  const places = useAsync(() => api<SavedPlace[]>('/me/places'), []);
  const [kind, setKind] = useState<(typeof KINDS)[number]>('home');
  const [label, setLabel] = useState('');
  const [address, setAddress] = useState('');
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [error, setError] = useState('');

  const valid = label.trim() && !isNaN(parseFloat(lat)) && !isNaN(parseFloat(lon));

  const add = async () => {
    setError('');
    try {
      await api('/me/places', {
        method: 'POST',
        body: { kind, label: label.trim(), nickname: label.trim(), formatted_address: address.trim() || null, lat: parseFloat(lat), lon: parseFloat(lon) },
      });
      setLabel('');
      setAddress('');
      setLat('');
      setLon('');
      places.reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Could not save the place.');
    }
  };

  return (
    <Screen refreshing={places.loading} onRefresh={places.reload}>
      {places.loading && !places.data ? <Loading /> : null}
      {places.error ? <ErrorView message={places.error} onRetry={places.reload} /> : null}
      {places.data?.map((p) => (
        <Card key={p.id}>
          <H2>{p.label}</H2>
          <Body muted>{p.formatted_address ?? `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}`}</Body>
          <Button
            title="Remove"
            variant="secondary"
            onPress={async () => {
              await api(`/me/places/${p.id}`, { method: 'DELETE' });
              places.reload();
            }}
          />
        </Card>
      ))}
      <Card>
        <H2>Add a place</H2>
        <Row style={{ flexWrap: 'wrap' }}>
          {KINDS.map((k) => (
            <Chip key={k} label={k} active={kind === k} onPress={() => setKind(k)} />
          ))}
        </Row>
        <Input label="Name (e.g. Home)" value={label} onChangeText={setLabel} />
        <Input label="Address (optional)" value={address} onChangeText={setAddress} />
        <Row>
          <View style={{ flex: 1 }}><Input label="Latitude" value={lat} onChangeText={setLat} keyboardType="numeric" /></View>
          <View style={{ flex: 1 }}><Input label="Longitude" value={lon} onChangeText={setLon} keyboardType="numeric" /></View>
        </Row>
        <Button title="Save place" onPress={add} disabled={!valid} />
        {error ? <Banner tone="critical" text={error} /> : null}
      </Card>
    </Screen>
  );
}
