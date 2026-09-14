import { NextResponse } from 'next/server';

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ id: string }> | { id: string } }
) {
  try {
    const resolvedParams = await Promise.resolve(params);
    const { id } = resolvedParams;

    const res = await fetch(`${PYTHON_BACKEND_URL}/api/memory/${id}`, {
      method: 'DELETE',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    console.error('Memory Item DELETE Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to delete memory item' },
      { status: 502 }
    );
  }
}
