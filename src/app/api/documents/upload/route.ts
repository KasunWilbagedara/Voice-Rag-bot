import { NextResponse } from 'next/server';
import { parseDocument } from '@/lib/document-parser';
import { ingestDocument } from '@/lib/rag-service';

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const file = formData.get('file') as File | null;
    const apiKey = formData.get('apiKey') as string | null;

    if (!file) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 });
    }

    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // Extract text from document
    const extractedText = await parseDocument(buffer, file.name, file.type);

    if (!extractedText || extractedText.trim().length === 0) {
      return NextResponse.json(
        { error: 'Could not extract readable text from document' },
        { status: 422 }
      );
    }

    // Ingest into database with chunking & vector embedding
    const result = await ingestDocument(
      file.name,
      file.type || 'text/plain',
      extractedText,
      apiKey || undefined
    );

    return NextResponse.json({
      success: true,
      document: result,
    });
  } catch (error: any) {
    console.error('Document Upload Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to process and ingest document' },
      { status: 500 }
    );
  }
}
