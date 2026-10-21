import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';

import { Loading } from '@/components/ui';
import { AirportProvider, useAirport } from '@/lib/airport';
import { AuthProvider, useAuth } from '@/lib/auth';

function Gate({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  const { airport, ready } = useAirport();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (loading || !ready) return;
    const first = segments[0] as string | undefined;
    if (!me) {
      if (first !== 'welcome' && first !== 'login') router.replace('/welcome');
    } else if (!airport) {
      if (first !== 'airport-select') router.replace('/airport-select');
    } else if (first === 'welcome' || first === 'login' || first === undefined) {
      router.replace('/(tabs)');
    }
  }, [me, airport, loading, ready, segments, router]);

  if (loading || !ready) return <Loading />;
  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <AirportProvider>
        <StatusBar style="auto" />
        <Gate>
          <Stack screenOptions={{ headerTitleStyle: { fontWeight: '600' } }}>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="welcome" options={{ headerShown: false }} />
            <Stack.Screen name="login" options={{ title: 'Sign in' }} />
            <Stack.Screen name="airport-select" options={{ title: 'Choose your airport' }} />
            <Stack.Screen name="journey" options={{ title: 'Airport journey' }} />
            <Stack.Screen name="map" options={{ title: 'Map flow' }} />
            <Stack.Screen name="support" options={{ title: 'Customer care' }} />
            <Stack.Screen name="tickets/index" options={{ title: 'My tickets' }} />
            <Stack.Screen name="tickets/add" options={{ title: 'Add ticket' }} />
            <Stack.Screen name="tickets/[id]" options={{ title: 'Ticket' }} />
            <Stack.Screen name="places" options={{ title: 'Saved places' }} />
          </Stack>
        </Gate>
      </AirportProvider>
    </AuthProvider>
  );
}
