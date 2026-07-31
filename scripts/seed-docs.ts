import fs from 'fs';
import path from 'path';
import { parseDocument } from '../src/lib/document-parser';
import { ingestDocument } from '../src/lib/rag-service';

export async function seedSampleDocuments(customApiKey?: string) {
  const docsDir = path.join(process.cwd(), 'docs');

  if (!fs.existsSync(docsDir)) {
    console.log('No docs directory found.');
    return [];
  }

  const files = fs.readdirSync(docsDir);
  const results = [];

  for (const file of files) {
    if (file.startsWith('.')) continue;

    const filePath = path.join(docsDir, file);
    const stat = fs.statSync(filePath);

    if (stat.isFile()) {
      console.log(`Seeding document into RAG Vector Store: ${file}...`);
      const fileBuffer = fs.readFileSync(filePath);
      const textContent = await parseDocument(fileBuffer, file, 'text/markdown');

      if (textContent && textContent.trim().length > 0) {
        const result = await ingestDocument(
          file,
          'text/markdown',
          textContent,
          customApiKey || process.env.OPENAI_API_KEY
        );
        console.log(`✓ Seeded "${file}" into RAG Vector DB (${result.chunkCount} vector chunks)`);
        results.push(result);
      }
    }
  }

  return results;
}

// Execute direct seeding if run via CLI
if (require.main === module) {
  seedSampleDocuments()
    .then((results) => {
      console.log(`🎉 Seeding complete! Ingested ${results.length} document(s) into RAG Vector Model.`);
      process.exit(0);
    })
    .catch((err) => {
      console.error('❌ Seeding failed:', err);
      process.exit(1);
    });
}
