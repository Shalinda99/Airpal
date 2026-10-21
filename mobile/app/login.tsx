import React, { useState } from 'react';

import { Body, Button, Card, Input, Screen } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';

export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      if (mode === 'login') await login(email.trim(), password);
      else await register(email.trim(), password);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Card>
        <Input label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
        <Input
          label={mode === 'register' ? 'Password (10+ characters)' : 'Password'}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
        />
        {error ? <Body style={{ color: '#dc2626' }}>{error}</Body> : null}
        <Button title={mode === 'login' ? 'Sign in' : 'Create account'} onPress={submit} loading={busy} disabled={!email || password.length < 8} />
        <Button
          title={mode === 'login' ? 'Need an account? Register' : 'Have an account? Sign in'}
          variant="secondary"
          onPress={() => setMode(mode === 'login' ? 'register' : 'login')}
        />
      </Card>
    </Screen>
  );
}
