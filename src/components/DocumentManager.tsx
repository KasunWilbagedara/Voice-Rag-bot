'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, Trash2, CheckCircle2, AlertCircle, Loader2, Database, FileCode, Sparkles } from 'lucide-react';

interface DocumentItem {
  id: string;
  title: string;
  file_type: string;
  created_at: string;
  chunk_count: number;
}

interface DocumentManagerProps {
  apiKey?: string;
  onDocumentsChange?: () => void;
}

export const DocumentManager: React.FC<DocumentManagerProps> = ({ apiKey, onDocumentsChange }) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dbActive, setDbActive] = useState<boolean>(true);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const fetchDocuments = async () => {
    try {
      const res = await fetch('/api/documents');
      const data = await res.json();
      if (res.ok) {
        setDocuments(data.documents || []);
        setDbActive(data.dbActive ?? true);
      }
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    setIsUploading(true);
    setErrorMessage(null);
    setUploadStatus('Extracting text & generating vector embeddings...');

    const file = files[0];
    const formData = new FormData();
    formData.append('file', file);
    if (apiKey) formData.append('apiKey', apiKey);

    try {
      const res = await fetch('/api/documents/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Failed to upload document');
      }

      setUploadStatus(`Successfully ingested "${file.name}" into RAG Vector DB (${data.document.chunkCount} chunks)`);
      fetchDocuments();
      if (onDocumentsChange) onDocumentsChange();
    } catch (err: any) {
      console.error('Upload Error:', err);
      setErrorMessage(err.message || 'Error processing document');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSeedDocument = async () => {
    setIsSeeding(true);
    setErrorMessage(null);
    setUploadStatus('Pre-loading sample knowledge base document into RAG Model...');

    try {
      const res = await fetch('/api/documents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ apiKey }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Failed to seed sample document');
      }

      const count = data.seededDocuments?.length || 0;
      setUploadStatus(`Pre-loaded ${count} sample document(s) directly into RAG Vector Store!`);
      fetchDocuments();
      if (onDocumentsChange) onDocumentsChange();
    } catch (err: any) {
      console.error('Seeding error:', err);
      setErrorMessage(err.message || 'Error seeding sample document');
    } finally {
      setIsSeeding(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await fetch(`/api/documents?id=${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchDocuments();
        if (onDocumentsChange) onDocumentsChange();
      }
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  return (
    <div className="w-full glass-panel rounded-lg p-6 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="w-5 h-5 text-emerald-500" />
          <h2 className="text-lg font-bold text-black">Knowledge Base Documents</h2>
        </div>
        <span
          className={`text-xs px-2.5 py-1 rounded border font-bold tracking-wider uppercase ${
            dbActive
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-amber-50 text-amber-700 border-amber-200'
          }`}
        >
          {dbActive ? 'PostgreSQL pgvector' : 'In-Memory Fallback'}
        </span>
      </div>

      {/* Drag & Drop Upload Zone */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          handleFileUpload(e.dataTransfer.files);
        }}
        className={`border transition-all rounded p-8 flex flex-col items-center justify-center gap-3 cursor-pointer group ${
          isDragging
            ? 'border-emerald-500 bg-emerald-50'
            : 'border-gray-300 hover:border-black bg-gray-50 hover:bg-gray-100'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.png,.jpg,.jpeg,.webp,.txt,.csv,.json,.md,.markdown"
          onChange={(e) => handleFileUpload(e.target.files)}
          className="hidden"
        />

        <div className="w-12 h-12 rounded-full bg-white border border-gray-200 flex items-center justify-center text-black group-hover:scale-110 transition-transform shadow-sm">
          {isUploading || isSeeding ? (
            <Loader2 className="w-6 h-6 animate-spin" />
          ) : (
            <Upload className="w-6 h-6 text-emerald-600" />
          )}
        </div>

        <div className="text-center">
          <p className="text-sm font-bold text-black uppercase tracking-wider">
            {isUploading ? 'Ingesting Document...' : 'Click or Drag File Here'}
          </p>
          <p className="text-xs text-gray-500 mt-1 font-mono">
            PDF, DOCX, XLSX, PPTX, Images (OCR), CSV
          </p>
        </div>
      </div>

      {/* Pre-load Sample Document Button */}
      <button
        onClick={handleSeedDocument}
        disabled={isSeeding || isUploading}
        className="w-full py-2.5 px-4 rounded bg-gray-100 hover:bg-black border border-gray-200 text-black hover:text-white text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-50"
      >
        {isSeeding ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Sparkles className="w-4 h-4" />
        )}
        <span>Pre-load Sample Data</span>
      </button>

      {/* Upload status message */}
      {uploadStatus && !errorMessage && (
        <div className="p-3 rounded bg-emerald-50 border border-emerald-200 flex items-center gap-2 text-emerald-800 text-xs font-bold">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{uploadStatus}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-3 rounded bg-red-50 border border-red-200 flex items-center gap-2 text-red-800 text-xs font-bold">
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Document List */}
      <div className="flex flex-col gap-2 mt-2">
        <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest border-b border-gray-100 pb-2">
          Indexed Documents ({documents.length})
        </h3>

        {documents.length === 0 ? (
          <div className="py-6 text-center text-xs text-gray-400 font-mono border border-gray-200 bg-gray-50 rounded">
            NO DOCUMENTS UPLOADED
          </div>
        ) : (
          <div className="max-h-60 overflow-y-auto space-y-2 pr-1">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="p-3 rounded bg-white border border-gray-200 flex items-center justify-between hover:border-black transition-colors shadow-sm"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded bg-gray-50 text-gray-600 border border-gray-100 shrink-0">
                    {doc.title.endsWith('.pdf') ? (
                      <FileText className="w-4 h-4 text-gray-800" />
                    ) : doc.title.endsWith('.docx') ? (
                      <FileText className="w-4 h-4 text-gray-800" />
                    ) : (
                      <FileCode className="w-4 h-4 text-emerald-600" />
                    )}
                  </div>

                  <div className="min-w-0">
                    <p className="text-sm font-bold text-black truncate">{doc.title}</p>
                    <p className="text-[10px] font-mono text-gray-500 mt-0.5">
                      {doc.chunk_count} chunks • {new Date(doc.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => handleDelete(doc.id)}
                  className="p-2 text-gray-400 hover:text-white hover:bg-red-500 rounded transition-colors"
                  title="Delete Document"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
