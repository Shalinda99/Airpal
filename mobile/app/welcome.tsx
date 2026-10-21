import { useRouter } from 'expo-router';
import React, { useState } from 'react';
import { View } from 'react-native';

import { Body, Button, H1, Screen } from '@/components/ui';
import { useAuth } from '@/lib/auth';

export default function Welcome() {
  const { guest } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  return (
    <Screen>
      <View style={{ height: 80 }} />
      <H1>Airpal</H1>
      <Body muted>
        Your airport guide: live flights, step-by-step journeys, rides and an assistant that only answers from
        information published by the airport.
      </Body>
      <View style={{ height: 24 }} />
      <Button
        title="Continue as guest"
        loading={busy}
        onPress={async () => {
          setBusy(true);
          setError('');
          try {
            await guest();
          } catch {
            setError('Could not reach the server. Check your connection and try again.');
          } finally {
            setBusy(false);
          }
        }}
      />
      <Button title="Sign in or create account" variant="secondary" onPress={() => router.push('/login')} />
      {error ? <Body style={{ color: '#dc2626' }}>{error}</Body> : null}
      <Body muted style={{ fontSize: 12 }}>
        Guest mode needs no personal details. Create an account to keep tickets and saved places across devices.
      </Body>
    </Screen>
  );
}
