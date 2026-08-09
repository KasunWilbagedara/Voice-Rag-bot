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
    <div className="w-full glass-panel rounded-3xl p-6 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="w-5 h-5 text-brand-400" />
          <h2 className="text-lg font-bold text-gray-100">Knowledge Base Documents</h2>
        </div>
        <span
          className={`text-xs px-2.5 py-1 rounded-full border ${
            dbActive
              ? 'bg-emerald-950/60 text-emerald-400 border-emerald-800/40'
              : 'bg-amber-950/60 text-amber-400 border-amber-800/40'
          }`}
        >
          {dbActive ? 'PostgreSQL pgvector Active' : 'In-Memory Vector Fallback'}
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
        className={`border-2 border-dashed transition-all rounded-2xl p-6 flex flex-col items-center justify-center gap-3 cursor-pointer group ${
          isDragging
            ? 'border-brand-400 bg-brand-950/40'
            : 'border-gray-800 hover:border-brand-500/50 bg-gray-900/40 hover:bg-gray-900/80'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.png,.jpg,.jpeg,.webp,.txt,.csv,.json,.md,.markdown"
          onChange={(e) => handleFileUpload(e.target.files)}
          className="hidden"
        />

        <div className="w-12 h-12 rounded-full bg-brand-950/60 border border-brand-800/50 flex items-center justify-center text-brand-400 group-hover:scale-110 transition-transform">
          {isUploading || isSeeding ? (
            <Loader2 className="w-6 h-6 animate-spin" />
          ) : (
            <Upload className="w-6 h-6" />
          )}
        </div>

        <div className="text-center">
          <p className="text-sm font-semibold text-gray-200">
            {isUploading ? 'Ingesting Document...' : 'Click or Drag File Here to Upload'}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            Supports PDF, Word, Excel, PowerPoint, Images/OCR, TXT, CSV & Code
          </p>
        </div>
      </div>

      {/* Pre-load Sample Document Button */}
      <button
        onClick={handleSeedDocument}
        disabled={isSeeding || isUploading}
        className="w-full py-2.5 px-4 rounded-xl bg-violet-950/50 hover:bg-violet-900/50 border border-violet-800/60 text-violet-300 hover:text-violet-200 text-xs font-semibold flex items-center justify-center gap-2 transition-all shadow-md disabled:opacity-50"
      >
        {isSeeding ? (
          <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
        ) : (
          <Sparkles className="w-4 h-4 text-violet-400" />
        )}
        <span>Pre-load Sample Document into RAG Model</span>
      </button>

      {/* Upload status message */}
      {uploadStatus && !errorMessage && (
        <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800/50 flex items-center gap-2 text-emerald-300 text-xs">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{uploadStatus}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-3 rounded-xl bg-red-950/40 border border-red-800/50 flex items-center gap-2 text-red-300 text-xs">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Document List */}
      <div className="flex flex-col gap-2 mt-2">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Indexed Documents ({documents.length})
        </h3>

        {documents.length === 0 ? (
          <div className="py-6 text-center text-xs text-gray-500 italic border border-gray-800/50 rounded-xl">
            No documents uploaded yet. Click "Pre-load Sample Document" or upload your own file to get started!
          </div>
        ) : (
          <div className="max-h-60 overflow-y-auto space-y-2 pr-1">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="p-3 rounded-xl bg-gray-900/80 border border-gray-800 flex items-center justify-between hover:border-gray-700 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded-lg bg-gray-800 text-brand-400 shrink-0">
                    {doc.title.endsWith('.pdf') ? (
                      <FileText className="w-4 h-4 text-red-400" />
                    ) : doc.title.endsWith('.docx') ? (
                      <FileText className="w-4 h-4 text-blue-400" />
                    ) : (
                      <FileCode className="w-4 h-4 text-emerald-400" />
                    )}
                  </div>

                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-200 truncate">{doc.title}</p>
                    <p className="text-[11px] text-gray-500">
                      {doc.chunk_count} vector chunks • {new Date(doc.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => handleDelete(doc.id)}
                  className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-950/30 rounded-lg transition-colors"
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
