export type Airport = {
  id: string;
  iata: string | null;
  icao: string | null;
  name: string;
  city: string | null;
  country: string;
  lat: number;
  lon: number;
  tz: string;
  status: string;
  badge: string;
  verified: boolean;
  last_verified_at: string | null;
  content_version: number;
};

export type Flight = {
  flight_number: string;
  airline: string | null;
  direction: 'departure' | 'arrival';
  other_airport_iata: string | null;
  other_airport_name: string | null;
  scheduled: string | null;
  estimated: string | null;
  status: string;
  terminal: string | null;
  gate: string | null;
  baggage_belt: string | null;
};

export type Board = {
  flights: Flight[];
  stale: boolean;
  fetched_at: string | null;
  provider: string | null;
};

export type Step = {
  id: string;
  title: string;
  instructions: string;
  documents: string[];
  typical_minutes: number | null;
  tips: string[];
  prohibited_items: string[];
};

export type Journey = { basic: boolean; version: number; steps: Step[]; last_verified_at?: string | null };

export type MapNode = { id: string; label: string; type: string; walking_minutes: number; notes: string | null };
export type MapFlow = { basic: boolean; total_walking_minutes: number; nodes: MapNode[] };

export type Notice = {
  id: string;
  title: string;
  body: string;
  severity: 'info' | 'warning' | 'critical';
  is_urgent: boolean;
};

export type SupportChannel = {
  id: string;
  type: 'phone' | 'whatsapp' | 'email';
  value: string;
  link: string;
  open_now: boolean;
  out_of_hours_message: string | null;
};

export type Ticket = {
  id: string;
  flight_number: string;
  flight_date: string;
  origin: string | null;
  destination: string | null;
  airport_id: string | null;
  passenger_name: string | null;
  pnr: string | null;
  seat: string | null;
  gate: string | null;
  terminal: string | null;
  boarding_time: string | null;
  baggage_allowance: string | null;
  status: { status: string; estimated?: string; gate?: string } | null;
  gate_walk_minutes: number | null;
  leave_for_gate_at: string | null;
};

export type PickupPoint = {
  id: string;
  terminal: string | null;
  level: string | null;
  zone_name: string;
  lat: number;
  lon: number;
  walking_instructions: string | null;
  notes: string | null;
};

export type RideOptions = {
  providers: { key: string; label: string; config: { info?: string; url?: string } }[];
  pickup_points: PickupPoint[];
};

export type RideLink = {
  provider: string;
  label: string;
  app_link: string | null;
  web_link: string | null;
  note: string | null;
};

export type RideTiming = {
  book_at: string;
  leave_by: string;
  arrive_at_airport?: string;
  ready_at_pickup?: string;
  estimated_arrival_at_destination?: string;
  travel_minutes: number;
  airport_process_minutes: number;
  routing_source: string;
};

export type SavedPlace = {
  id: string;
  kind: string;
  label: string;
  nickname: string;
  formatted_address: string | null;
  lat: number;
  lon: number;
};

export type ChatReply = {
  answer: string;
  answered: boolean;
  sources: { label: string; type: string; title: string }[];
  message_id: string | null;
  conversation_id: string | null;
  support_options: SupportChannel[];
  disclaimer: string | null;
};

export type Me = {
  id: string;
  email: string | null;
  is_guest: boolean;
  roles: string[];
  locale: string;
};
