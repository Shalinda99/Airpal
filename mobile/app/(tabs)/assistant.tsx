import React, { useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Linking, Platform, View } from 'react-native';

import { Body, Button, Card, Input, Row, colors } from '@/components/ui';
import { ApiError, api } from '@/lib/api';
import { useAirport } from '@/lib/airport';
import type { ChatReply } from '@/lib/types';

type Msg = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  reply?: ChatReply;
  feedback?: 'up' | 'down' | 'reported';
};

export default function Assistant() {
  const { airport } = useAirport();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const conv = useRef<string | null>(null);
  const list = useRef<FlatList<Msg>>(null);

  const send = async () => {
    const message = text.trim();
    if (!message || busy || !airport) return;
    setText('');
    setBusy(true);
    setMsgs((m) => [...m, { id: `u${Date.now()}`, role: 'user', text: message }]);
    try {
      const reply = await api<ChatReply>(`/airports/${airport.id}/agent/chat`, {
        method: 'POST',
        body: { message, conversation_id: conv.current, lang: 'en' },
      });
      conv.current = reply.conversation_id;
      setMsgs((m) => [...m, { id: reply.message_id ?? `a${Date.now()}`, role: 'assistant', text: reply.answer, reply }]);
    } catch (e) {
      const detail = e instanceof ApiError && e.status === 429 ? 'You are asking too fast. Please wait a moment.' : 'The assistant is unavailable right now. Please try again.';
      setMsgs((m) => [...m, { id: `e${Date.now()}`, role: 'assistant', text: detail }]);
    } finally {
      setBusy(false);
      setTimeout(() => list.current?.scrollToEnd({ animated: true }), 50);
    }
  };

  const feedback = async (m: Msg, kind: 'up' | 'down' | 'reported') => {
    if (!m.reply?.message_id || m.feedback) return;
    setMsgs((all) => all.map((x) => (x.id === m.id ? { ...x, feedback: kind } : x)));
    try {
      if (kind === 'reported') await api(`/agent/messages/${m.reply.message_id}/report`, { method: 'POST', body: {} });
      else await api(`/agent/messages/${m.reply.message_id}/feedback`, { method: 'POST', body: { helpful: kind === 'up' } });
    } catch {
      /* feedback is best effort */
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: colors.bg }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
      <FlatList
        ref={list}
        data={msgs}
        keyExtractor={(m) => m.id}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        ListHeaderComponent={
          <Body muted>
            Ask about {airport?.name ?? 'your airport'}. Answers come only from published airport information and live data, with sources. Confirm visa and customs rules with authorities.
          </Body>
        }
        renderItem={({ item: m }) => (
          <View style={{ alignItems: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <Card style={{ maxWidth: '88%', backgroundColor: m.role === 'user' ? colors.primary : colors.card }}>
              <Body style={{ color: m.role === 'user' ? '#fff' : colors.text }}>{m.text}</Body>
              {m.reply?.sources.length ? (
                <Body muted style={{ fontSize: 12 }}>
                  Sources: {m.reply.sources.map((s) => `${s.label} ${s.title}`).join(' · ')}
                </Body>
              ) : null}
              {m.reply && !m.reply.answered && m.reply.support_options.length ? (
                <View style={{ gap: 6 }}>
                  {m.reply.support_options.map((o) => (
                    <Button
                      key={o.id}
                      variant="secondary"
                      title={`${o.type}: ${o.value}${o.open_now ? '' : ' (closed)'}`}
                      onPress={() => Linking.openURL(o.link)}
                    />
                  ))}
                </View>
              ) : null}
              {m.reply?.message_id ? (
                <Row>
                  <Button title={m.feedback === 'up' ? 'Thanks' : 'Helpful'} variant="secondary" disabled={!!m.feedback} onPress={() => feedback(m, 'up')} />
                  <Button title="Not helpful" variant="secondary" disabled={!!m.feedback} onPress={() => feedback(m, 'down')} />
                  <Button title={m.feedback === 'reported' ? 'Reported' : 'Report wrong'} variant="secondary" disabled={!!m.feedback} onPress={() => feedback(m, 'reported')} />
                </Row>
              ) : null}
            </Card>
          </View>
        )}
      />
      <View style={{ padding: 12, gap: 8, backgroundColor: '#fff' }}>
        <Input placeholder="Ask a question" value={text} onChangeText={setText} onSubmitEditing={send} returnKeyType="send" maxLength={500} />
        <Button title="Send" onPress={send} loading={busy} disabled={!text.trim()} />
      </View>
    </KeyboardAvoidingView>
  );
}
