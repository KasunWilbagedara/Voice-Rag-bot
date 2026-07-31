import fs from 'fs';
import path from 'path';
import { parseDocument } from './document-parser';
import { ingestDocument } from './rag-service';

export async function seedSampleDocuments(customApiKey?: string) {
  const docsDir = path.join(process.cwd(), 'docs');

  if (!fs.existsSync(docsDir)) {
    return [];
  }

  const files = fs.readdirSync(docsDir);
  const results = [];

  for (const file of files) {
    if (file.startsWith('.')) continue;

    const filePath = path.join(docsDir, file);
    const stat = fs.statSync(filePath);

    if (stat.isFile()) {
      const fileBuffer = fs.readFileSync(filePath);
      const textContent = await parseDocument(fileBuffer, file, 'text/markdown');

      if (textContent && textContent.trim().length > 0) {
        const result = await ingestDocument(
          file,
          'text/markdown',
          textContent,
          customApiKey || process.env.OPENAI_API_KEY
        );
        results.push(result);
      }
    }
  }

  return results;
}
