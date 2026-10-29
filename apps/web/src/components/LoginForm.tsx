'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api, setToken, getToken } from '@/lib/api';

// The panel is an internal admin tool, so the default account is prefilled to
// make signing in a single click. Change these (or clear them) for any
// deployment that is reachable outside a trusted network.
const DEFAULT_USERNAME = 'admin';
const DEFAULT_PASSWORD = 'admin';

export default function LoginForm({ notice }: { notice?: string }) {
  const router = useRouter();
  const [username, setUsername] = useState(DEFAULT_USERNAME);
  const [password, setPassword] = useState(DEFAULT_PASSWORD);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (token) {
      router.push('/projects');
    }
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await api.login(username, password);
      setToken(result.access_token);
      router.push('/projects');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <img src="/logo.svg" alt="ShipSmith" className="w-12 h-12" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">ShipSmith</h1>
          <p className="text-gray-600">Deployment & Feature Flag Control Plane</p>
        </div>

        <div className="card p-6">
          {notice && (
            <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {notice}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Username</label>
              <input
                type="text"
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                autoComplete="username"
              />
            </div>

            <div>
              <label className="label">Password</label>
              <input
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>

            {error && (
              <div className="text-red-600 text-sm bg-red-50 px-3 py-2 rounded-md">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={loading}
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
