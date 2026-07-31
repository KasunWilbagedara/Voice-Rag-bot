import pdfParse from 'pdf-parse';
import mammoth from 'mammoth';

export async function parseDocument(fileBuffer: Buffer, fileName: string, mimeType: string): Promise<string> {
  const extension = fileName.split('.').pop()?.toLowerCase() || '';

  if (extension === 'pdf' || mimeType.includes('pdf')) {
    const data = await pdfParse(fileBuffer);
    return data.text || '';
  }

  if (extension === 'docx' || mimeType.includes('officedocument.wordprocessingml')) {
    const result = await mammoth.extractRawText({ buffer: fileBuffer });
    return result.value || '';
  }

  if (['txt', 'md', 'markdown', 'json', 'csv'].includes(extension) || mimeType.includes('text')) {
    return fileBuffer.toString('utf-8');
  }

  // Fallback to utf-8 string parsing
  return fileBuffer.toString('utf-8');
}
