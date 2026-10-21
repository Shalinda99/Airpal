import { useRouter } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { Alert, Pressable, Switch } from 'react-native';

import { Body, Button, Card, H2, Row, Screen } from '@/components/ui';
import { api } from '@/lib/api';
import { useAirport } from '@/lib/airport';
import { useAuth } from '@/lib/auth';
import { registerForPush } from '@/lib/notifications';

type Prefs = { gate_change: boolean; delay: boolean; boarding: boolean; ride_reminder: boolean };
const PREF_LABELS: Record<keyof Prefs, string> = {
  gate_change: 'Gate changes',
  delay: 'Delays',
  boarding: 'Boarding',
  ride_reminder: 'Ride reminders',
};

export default function Profile() {
  const { me, logout, deleteAccount } = useAuth();
  const { airport } = useAirport();
  const router = useRouter();
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [analytics, setAnalytics] = useState(false);
  const [pushOk, setPushOk] = useState<boolean | null>(null);

  useEffect(() => {
    api<Prefs>('/me/notification-prefs').then(setPrefs).catch(() => {});
    api<Record<string, boolean>>('/me/consents').then((c) => setAnalytics(!!c.analytics)).catch(() => {});
  }, []);

  const setPref = async (k: keyof Prefs, v: boolean) => {
    if (!prefs) return;
    const next = { ...prefs, [k]: v };
    setPrefs(next);
    try {
      await api('/me/notification-prefs', { method: 'PUT', body: next });
    } catch {
      setPrefs(prefs);
    }
  };

  const confirmDelete = () =>
    Alert.alert('Delete account', 'This permanently erases your tickets, saved places, chat history and account. This cannot be undone.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => deleteAccount().catch(() => Alert.alert('Could not delete the account. Try again.')) },
    ]);

  return (
    <Screen>
      <Card>
        <H2>{me?.is_guest ? 'Guest' : me?.email}</H2>
        <Body muted>{me?.is_guest ? 'Guest data is stored on this device account only. Register to keep it.' : 'Signed in'}</Body>
        {me?.is_guest ? <Button title="Create account or sign in" variant="secondary" onPress={() => logout().then(() => router.replace('/login'))} /> : null}
      </Card>

      <Card>
        <H2>Airport</H2>
        <Body>{airport?.name}</Body>
        <Button title="Change airport" variant="secondary" onPress={() => router.push('/airport-select')} />
      </Card>

      <Card>
        <H2>My data</H2>
        <Pressable onPress={() => router.push('/tickets')}><Body style={{ color: '#0b5fff' }}>My tickets</Body></Pressable>
        <Pressable onPress={() => router.push('/places')}><Body style={{ color: '#0b5fff' }}>Saved places</Body></Pressable>
      </Card>

      <Card>
        <H2>Notifications</H2>
        {pushOk === false ? <Body muted>Notifications are disabled or unavailable on this device.</Body> : null}
        <Button title={pushOk ? 'Notifications enabled' : 'Enable push notifications'} variant="secondary" disabled={!!pushOk} onPress={async () => setPushOk(await registerForPush().catch(() => false))} />
        {prefs &&
          (Object.keys(PREF_LABELS) as (keyof Prefs)[]).map((k) => (
            <Row key={k} style={{ justifyContent: 'space-between' }}>
              <Body>{PREF_LABELS[k]}</Body>
              <Switch value={prefs[k]} onValueChange={(v) => setPref(k, v)} accessibilityLabel={PREF_LABELS[k]} />
            </Row>
          ))}
      </Card>

      <Card>
        <H2>Privacy</H2>
        <Row style={{ justifyContent: 'space-between' }}>
          <Body style={{ flex: 1 }}>Share anonymous usage analytics</Body>
          <Switch
            value={analytics}
            accessibilityLabel="Share anonymous usage analytics"
            onValueChange={async (v) => {
              setAnalytics(v);
              try {
                await api('/me/consents', { method: 'PUT', body: { type: 'analytics', granted: v } });
              } catch {
                setAnalytics(!v);
              }
            }}
          />
        </Row>
        <Body muted style={{ fontSize: 12 }}>Off by default. Never includes your name, ticket or messages.</Body>
      </Card>

      <Button title="Sign out" variant="secondary" onPress={() => logout()} />
      <Button title="Delete my account and data" variant="danger" onPress={confirmDelete} />
    </Screen>
  );
}
