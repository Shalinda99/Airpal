import * as Location from 'expo-location';
import React, { useState } from 'react';
import { Alert, Linking, View } from 'react-native';

import { Banner, Body, Button, Card, Chip, ErrorView, H2, Input, Loading, Row, Screen } from '@/components/ui';
import { ApiError, api } from '@/lib/api';
import { useAirport } from '@/lib/airport';
import { fmtDateTime } from '@/lib/format';
import type { RideLink, RideOptions, RideTiming, SavedPlace, Ticket } from '@/lib/types';
import { useAsync } from '@/lib/useAsync';

type Dest = { lat: number; lon: number; nickname: string; formatted_address?: string };

export default function Rides() {
  const { airport } = useAirport();
  const [mode, setMode] = useState<'from_airport' | 'to_airport'>('from_airport');
  const [dest, setDest] = useState<Dest | null>(null);
  const [custom, setCustom] = useState({ name: '', lat: '', lon: '' });
  const [pickupId, setPickupId] = useState<string | null>(null);
  const [timing, setTiming] = useState<RideTiming | null>(null);
  const [bag, setBag] = useState(false);
  const [scope, setScope] = useState<'domestic' | 'international'>('international');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const opts = useAsync(() => api<RideOptions>(`/airports/${airport!.id}/rides/options`, { auth: false }), [airport?.id]);
  const places = useAsync(() => api<SavedPlace[]>('/me/places'), []);
  const tickets = useAsync(() => api<Ticket[]>('/tickets'), []);

  if (!airport) return <Loading />;

  const otherPlace = () => (dest ? { lat: dest.lat, lon: dest.lon, nickname: dest.nickname, formatted_address: dest.formatted_address } : null);

  const useCurrentAsDest = async () => {
    const perm = await Location.requestForegroundPermissionsAsync();
    if (perm.status !== 'granted') return Alert.alert('Location permission denied', 'Enter the address coordinates or pick a saved place instead.');
    const pos = await Location.getCurrentPositionAsync({});
    setDest({ lat: pos.coords.latitude, lon: pos.coords.longitude, nickname: 'My location' });
  };

  const openProvider = async (key: string) => {
    const place = otherPlace();
    if (!place) return setMsg('Choose a destination first.');
    setBusy(true);
    setMsg('');
    try {
      const airportPlace = { lat: airport.lat, lon: airport.lon, nickname: airport.name };
      const point = opts.data?.pickup_points.find((p) => p.id === pickupId) ?? opts.data?.pickup_points[0];
      const ap = point ? { lat: point.lat, lon: point.lon, nickname: point.zone_name } : airportPlace;
      const body =
        mode === 'from_airport'
          ? { pickup: ap, dropoff: place, route_type: 'from_airport' }
          : { pickup: { ...place, current_location: false }, dropoff: ap, route_type: 'to_airport' };
      const link = await api<RideLink>('/rides/link', { method: 'POST', body: { airport_id: airport.id, provider: key, ...body } });
      api('/rides/intent', { method: 'POST', body: { airport_id: airport.id, provider: key, route_type: mode } }).catch(() => {});
      const target = link.app_link ?? link.web_link;
      if (!target) return setMsg(link.note ?? 'No link available for this provider.');
      try {
        await Linking.openURL(target);
      } catch {
        if (link.web_link) await Linking.openURL(link.web_link);
      }
      if (link.note) setMsg(link.note);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.detail : 'Could not open the provider.');
    } finally {
      setBusy(false);
    }
  };

  const computeTiming = async () => {
    const place = otherPlace();
    const t = tickets.data?.[0];
    if (!place) return setMsg('Choose a destination or origin first.');
    if (!t) return setMsg('Add a ticket to get smart timing.');
    setBusy(true);
    setMsg('');
    try {
      setTiming(
        await api<RideTiming>('/rides/timing', {
          method: 'POST',
          body: { airport_id: airport.id, kind: mode, other: place, ticket_id: t.id, scope, has_checked_bag: bag, pickup_point_id: pickupId },
        }),
      );
    } catch (e) {
      setMsg(e instanceof ApiError ? e.detail : 'Could not compute timing.');
    } finally {
      setBusy(false);
    }
  };

  const point = opts.data?.pickup_points.find((p) => p.id === pickupId) ?? opts.data?.pickup_points[0];

  return (
    <Screen refreshing={opts.loading} onRefresh={opts.reload}>
      <Row>
        <Chip label="From airport" active={mode === 'from_airport'} onPress={() => setMode('from_airport')} />
        <Chip label="To airport" active={mode === 'to_airport'} onPress={() => setMode('to_airport')} />
      </Row>

      <Card>
        <H2>{mode === 'from_airport' ? 'Where to?' : 'Where from?'}</H2>
        {dest ? <Body>Selected: {dest.nickname}</Body> : <Body muted>Pick a saved place, use your location, or enter coordinates.</Body>}
        <Row style={{ flexWrap: 'wrap' }}>
          {places.data?.map((p) => (
            <Chip key={p.id} label={p.label} active={dest?.nickname === p.nickname} onPress={() => setDest({ lat: p.lat, lon: p.lon, nickname: p.nickname, formatted_address: p.formatted_address ?? undefined })} />
          ))}
          <Chip label="My location" onPress={useCurrentAsDest} />
        </Row>
        <Input label="Place name" value={custom.name} onChangeText={(v) => setCustom({ ...custom, name: v })} />
        <Row>
          <View style={{ flex: 1 }}><Input label="Latitude" value={custom.lat} onChangeText={(v) => setCustom({ ...custom, lat: v })} keyboardType="numeric" /></View>
          <View style={{ flex: 1 }}><Input label="Longitude" value={custom.lon} onChangeText={(v) => setCustom({ ...custom, lon: v })} keyboardType="numeric" /></View>
        </Row>
        <Button
          title="Use this place"
          variant="secondary"
          disabled={!custom.name || isNaN(parseFloat(custom.lat)) || isNaN(parseFloat(custom.lon))}
          onPress={() => setDest({ lat: parseFloat(custom.lat), lon: parseFloat(custom.lon), nickname: custom.name })}
        />
      </Card>

      {opts.loading ? <Loading /> : opts.error ? <ErrorView message={opts.error} onRetry={opts.reload} /> : null}

      {opts.data?.pickup_points.length ? (
        <Card>
          <H2>{mode === 'from_airport' ? 'Pickup point' : 'Drop-off point'}</H2>
          <Row style={{ flexWrap: 'wrap' }}>
            {opts.data.pickup_points.map((p) => (
              <Chip key={p.id} label={p.zone_name} active={(pickupId ?? opts.data!.pickup_points[0].id) === p.id} onPress={() => setPickupId(p.id)} />
            ))}
          </Row>
          {point ? (
            <Body muted>
              {[point.terminal, point.level ? `Level ${point.level}` : null].filter(Boolean).join(' · ')}
              {point.walking_instructions ? `\n${point.walking_instructions}` : ''}
              {point.notes ? `\n${point.notes}` : ''}
            </Body>
          ) : null}
        </Card>
      ) : null}

      <Card>
        <H2>Smart timing</H2>
        <Row>
          <Chip label="International" active={scope === 'international'} onPress={() => setScope('international')} />
          <Chip label="Domestic" active={scope === 'domestic'} onPress={() => setScope('domestic')} />
          <Chip label={bag ? 'Checked bag' : 'Cabin bag only'} active={bag} onPress={() => setBag(!bag)} />
        </Row>
        <Button title="Calculate when to book" variant="secondary" onPress={computeTiming} loading={busy} />
        {timing ? (
          <View style={{ gap: 4 }}>
            <Body>Book by: {fmtDateTime(timing.book_at, airport.tz)}</Body>
            {mode === 'to_airport' ? <Body>Leave by: {fmtDateTime(timing.leave_by, airport.tz)}</Body> : null}
            {timing.arrive_at_airport ? <Body>Be at the airport: {fmtDateTime(timing.arrive_at_airport, airport.tz)}</Body> : null}
            {timing.estimated_arrival_at_destination ? <Body>Estimated arrival: {fmtDateTime(timing.estimated_arrival_at_destination, airport.tz)}</Body> : null}
            <Body muted>
              Trip about {timing.travel_minutes} min ({timing.routing_source}); airport process {timing.airport_process_minutes} min.
            </Body>
            <Button
              title="Remind me to book"
              variant="secondary"
              onPress={async () => {
                try {
                  await api('/me/reminders', { method: 'POST', body: { title: 'Time to book your ride', body: 'Book your airport ride now.', when: timing.book_at, key: `ride:${timing.book_at}` } });
                  setMsg('Reminder scheduled.');
                } catch {
                  setMsg('Could not schedule the reminder.');
                }
              }}
            />
          </View>
        ) : null}
      </Card>

      <Card>
        <H2>Book with</H2>
        {opts.data?.providers.length ? (
          opts.data.providers.map((p) => (
            <View key={p.key} style={{ gap: 4 }}>
              <Button title={p.label} onPress={() => openProvider(p.key)} loading={busy} />
              {p.config.info ? <Body muted>{p.config.info}</Body> : null}
            </View>
          ))
        ) : (
          <Body muted>This airport has not enabled any ride options yet.</Body>
        )}
        <Body muted style={{ fontSize: 12 }}>Prices are shown in the provider app. Options are listed in the airport's own order.</Body>
      </Card>

      {msg ? <Banner text={msg} /> : null}
    </Screen>
  );
}
