import { CameraView, useCameraPermissions } from 'expo-camera';
import { useRouter } from 'expo-router';
import React, { useRef, useState } from 'react';
import { View } from 'react-native';

import { Banner, Body, Button, Card, H2, Input, Screen } from '@/components/ui';
import { ApiError, api } from '@/lib/api';
import { clearCaches } from '@/lib/api';
import type { Ticket } from '@/lib/types';

export default function AddTicket() {
  const router = useRouter();
  const [permission, requestPermission] = useCameraPermissions();
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [flight, setFlight] = useState('');
  const [date, setDate] = useState('');
  const handled = useRef(false);

  const create = async (body: object) => {
    setBusy(true);
    setError('');
    try {
      const t = await api<Ticket>('/tickets', { method: 'POST', body });
      await clearCaches();
      router.replace(`/tickets/${t.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Could not add the ticket.');
      handled.current = false;
    } finally {
      setBusy(false);
    }
  };

  if (scanning) {
    return (
      <View style={{ flex: 1, backgroundColor: '#000' }}>
        <CameraView
          style={{ flex: 1 }}
          barcodeScannerSettings={{ barcodeTypes: ['pdf417', 'qr', 'aztec', 'datamatrix'] }}
          onBarcodeScanned={({ data }: { data: string }) => {
            if (handled.current) return;
            handled.current = true;
            setScanning(false);
            create({ raw_bcbp: data });
          }}
        />
        <View style={{ padding: 16 }}>
          <Button title="Cancel" variant="secondary" onPress={() => setScanning(false)} />
        </View>
      </View>
    );
  }

  return (
    <Screen>
      <Card>
        <H2>Scan boarding pass</H2>
        <Body muted>Point the camera at the barcode on your boarding pass. Your name and booking reference are stored encrypted and deleted after your trip.</Body>
        <Button
          title="Scan barcode"
          loading={busy}
          onPress={async () => {
            if (!permission?.granted && !(await requestPermission()).granted) {
              setError('Camera permission is required to scan. You can add the ticket manually below.');
              return;
            }
            handled.current = false;
            setScanning(true);
          }}
        />
      </Card>
      <Card>
        <H2>Add manually</H2>
        <Input label="Flight number (e.g. UL225)" value={flight} onChangeText={setFlight} autoCapitalize="characters" />
        <Input label="Date (YYYY-MM-DD)" value={date} onChangeText={setDate} keyboardType="numbers-and-punctuation" />
        <Button
          title="Add ticket"
          variant="secondary"
          loading={busy}
          disabled={!/^[A-Za-z0-9]{2}\d{1,4}[A-Za-z]?$/.test(flight.trim()) || !/^\d{4}-\d{2}-\d{2}$/.test(date.trim())}
          onPress={() => create({ flight_number: flight.trim().toUpperCase(), flight_date: date.trim() })}
        />
      </Card>
      {error ? <Banner tone="critical" text={error} /> : null}
    </Screen>
  );
}
