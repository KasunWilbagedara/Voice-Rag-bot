import { NextResponse } from 'next/server';
import { AUTH_COOKIE, BACKEND1_URL, userHeaders } from '../../_lib/backend';

// POST /api/auth/login | /api/auth/register | /api/auth/logout
// GET  /api/auth/me
// The backend's token is kept in an httpOnly cookie; the browser only gets the user.

const COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: 'lax' as const,
  path: '/',
  secure: process.env.NODE_ENV === 'production',
  maxAge: 60 * 60 * 24 * 30, // 30 days, same as the backend token
};

type Params = { params: { action: string } };

export async function POST(req: Request, { params }: Params) {
  const { action } = params;
  try {
    if (action === 'logout') {
      await fetch(`${BACKEND1_URL}/api/auth/logout`, { method: 'POST', headers: userHeaders() }).catch(() => {});
      const res = NextResponse.json({ success: true });
      res.cookies.delete(AUTH_COOKIE);
      return res;
    }
    if (action !== 'login' && action !== 'register') {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    const backendRes = await fetch(`${BACKEND1_URL}/api/auth/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: await req.text(),
    });
    const data = await backendRes.json();
    if (!backendRes.ok) {
      return NextResponse.json({ error: data.detail || 'Login failed' }, { status: backendRes.status });
    }

    const res = NextResponse.json({ user: data.user });
    res.cookies.set(AUTH_COOKIE, data.token, COOKIE_OPTIONS);
    return res;
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Failed to connect to backend' }, { status: 502 });
  }
}

export async function GET(_req: Request, { params }: Params) {
  if (params.action !== 'me') {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }
  try {
    const res = await fetch(`${BACKEND1_URL}/api/auth/me`, { headers: userHeaders(), cache: 'no-store' });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Failed to connect to backend' }, { status: 502 });
  }
}
