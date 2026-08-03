import { parseDocument } from './document-parser';
import mammoth from 'mammoth';
import pdfParse from 'pdf-parse';

jest.mock('mammoth');
jest.mock('pdf-parse');

describe('document-parser', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should parse text files correctly', async () => {
    const buffer = Buffer.from('Hello world');
    const result = await parseDocument(buffer, 'test.txt', 'text/plain');
    expect(result).toBe('Hello world');
  });

  it('should parse markdown files correctly', async () => {
    const buffer = Buffer.from('# Hello world');
    const result = await parseDocument(buffer, 'test.md', 'text/markdown');
    expect(result).toBe('# Hello world');
  });

  it('should call pdfParse for pdf files', async () => {
    const buffer = Buffer.from('mock pdf content');
    (pdfParse as jest.Mock).mockResolvedValue({ text: 'parsed pdf' });
    
    const result = await parseDocument(buffer, 'test.pdf', 'application/pdf');
    expect(pdfParse).toHaveBeenCalledWith(buffer);
    expect(result).toBe('parsed pdf');
  });

  it('should call mammoth for docx files', async () => {
    const buffer = Buffer.from('mock docx content');
    (mammoth.extractRawText as jest.Mock).mockResolvedValue({ value: 'parsed docx' });
    
    const result = await parseDocument(buffer, 'test.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    expect(mammoth.extractRawText).toHaveBeenCalledWith({ buffer });
    expect(result).toBe('parsed docx');
  });
});
