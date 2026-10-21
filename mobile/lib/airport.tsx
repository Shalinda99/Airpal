import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useState } from 'react';

import { api } from './api';
import type { Airport } from './types';

const KEY = 'airpal.airport';

type State = {
  airport: Airport | null;
  ready: boolean;
  select: (a: Airport) => Promise<void>;
  clear: () => Promise<void>;
};

const Ctx = createContext<State>(null as unknown as State);
export const useAirport = () => useContext(Ctx);

export function AirportProvider({ children }: { children: React.ReactNode }) {
  const [airport, setAirport] = useState<Airport | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      const raw = await AsyncStorage.getItem(KEY);
      if (raw) {
        const stored: Airport = JSON.parse(raw);
        setAirport(stored);
        // refresh verification status in the background; keep stored copy if offline
        api<Airport>(`/airports/${stored.id}`, { auth: false })
          .then((fresh) => {
            setAirport(fresh);
            return AsyncStorage.setItem(KEY, JSON.stringify(fresh));
          })
          .catch(() => {});
      }
      setReady(true);
    })();
  }, []);

  const value: State = {
    airport,
    ready,
    select: async (a) => {
      setAirport(a);
      await AsyncStorage.setItem(KEY, JSON.stringify(a));
    },
    clear: async () => {
      setAirport(null);
      await AsyncStorage.removeItem(KEY);
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
