import React, { useEffect, useState } from 'react';
import { FlatList, Pressable } from 'react-native';
import { useRouter } from 'expo-router';

import { Badge, Body, Card, ErrorView, H2, Input, Loading, Row, colors } from '@/components/ui';
import { api } from '@/lib/api';
import { useAirport } from '@/lib/airport';
import type { Airport } from '@/lib/types';

export default function AirportSelect() {
  const { select, airport } = useAirport();
  const router = useRouter();
  const [q, setQ] = useState('');
  const [items, setItems] = useState<Airport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const t = setTimeout(async () => {
      setLoading(true);
      setError('');
      try {
        setItems(await api<Airport[]>(`/airports?q=${encodeURIComponent(q)}`, { auth: false }));
      } catch {
        setError('Could not load airports. Check your connection.');
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <FlatList
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: 16, gap: 10 }}
      data={items}
      keyExtractor={(a) => a.id}
      keyboardShouldPersistTaps="handled"
      ListHeaderComponent={
        <Input placeholder="Search by name, city or code (e.g. CMB)" value={q} onChangeText={setQ} autoCapitalize="none" autoCorrect={false} />
      }
      ListEmptyComponent={
        loading ? <Loading /> : error ? <ErrorView message={error} /> : <Body muted>No airports found.</Body>
      }
      renderItem={({ item }) => (
        <Pressable
          accessibilityRole="button"
          onPress={async () => {
            await select(item);
            if (router.canGoBack() && airport) router.back();
            else router.replace('/(tabs)');
          }}
        >
          <Card>
            <Row style={{ justifyContent: 'space-between' }}>
              <H2>{item.name}</H2>
              {item.iata ? <Body muted>{item.iata}</Body> : null}
            </Row>
            <Body muted>{[item.city, item.country].filter(Boolean).join(', ')}</Body>
            <Row>
              <Badge text={item.badge} color={item.verified ? colors.ok : colors.warn} />
            </Row>
          </Card>
        </Pressable>
      )}
    />
  );
}
