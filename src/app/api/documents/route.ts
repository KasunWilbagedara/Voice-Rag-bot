import { NextResponse } from 'next/server';
import { getDbPool, isDbConnected, inMemoryStore } from '@/lib/db';
import { seedSampleDocuments } from '@/lib/seed-docs';

export async function GET() {
  try {
    const dbActive = await isDbConnected();

    if (dbActive) {
      const db = getDbPool();
      const query = `
        SELECT 
          d.id,
          d.title,
          d.file_type,
          d.created_at,
          COUNT(c.id)::int AS chunk_count
        FROM documents d
        LEFT JOIN document_chunks c ON d.id = c.document_id
        GROUP BY d.id
        ORDER BY d.created_at DESC;
      `;
      const res = await db.query(query);
      return NextResponse.json({ documents: res.rows, dbActive: true });
    } else {
      // In-memory list
      const docs = inMemoryStore.documents.map((doc) => {
        const chunkCount = inMemoryStore.chunks.filter((c) => c.document_id === doc.id).length;
        return {
          id: doc.id,
          title: doc.title,
          file_type: doc.file_type,
          created_at: doc.created_at,
          chunk_count: chunkCount,
        };
      });
      return NextResponse.json({ documents: docs, dbActive: false });
    }
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    const { apiKey } = body;

    const results = await seedSampleDocuments(apiKey);
    return NextResponse.json({
      success: true,
      seededDocuments: results,
    });
  } catch (error: any) {
    console.error('Seed error:', error);
    return NextResponse.json({ error: error.message || 'Failed to seed sample document' }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const id = searchParams.get('id');

    if (!id) {
      return NextResponse.json({ error: 'Missing document id' }, { status: 400 });
    }

    const dbActive = await isDbConnected();

    if (dbActive) {
      const db = getDbPool();
      await db.query(`DELETE FROM documents WHERE id = $1`, [id]);
    } else {
      inMemoryStore.documents = inMemoryStore.documents.filter((d) => d.id !== id);
      inMemoryStore.chunks = inMemoryStore.chunks.filter((c) => c.document_id !== id);
    }

    return NextResponse.json({ success: true, id });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
