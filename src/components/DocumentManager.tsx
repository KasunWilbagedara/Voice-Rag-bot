'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Upload,
  FileText,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Database,
  FileCode,
  Sparkles,
  Search,
  RefreshCw,
  FileSpreadsheet,
  FileImage,
} from 'lucide-react';

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
  const [docSearch, setDocSearch] = useState<string>('');

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
    setUploadStatus('Extracting content & generating RAG vector embeddings...');

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

      setUploadStatus(`Successfully ingested "${file.name}" into Vector DB (${data.document.chunkCount || 0} chunks)`);
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
    setUploadStatus('Pre-loading sample knowledge base documents into RAG Vector Store...');

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

      const count = data.seededDocuments?.length || 1;
      setUploadStatus(`Pre-loaded ${count} sample knowledge base document(s) into RAG Vector DB!`);
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

  const filteredDocs = documents.filter((doc) =>
    doc.title.toLowerCase().includes(docSearch.toLowerCase())
  );

  const getDocIcon = (title: string) => {
    const lower = title.toLowerCase();
    if (lower.endsWith('.pdf')) return <FileText className="w-4 h-4 text-rose-400" />;
    if (lower.endsWith('.docx') || lower.endsWith('.doc')) return <FileText className="w-4 h-4 text-blue-400" />;
    if (lower.endsWith('.xlsx') || lower.endsWith('.xls') || lower.endsWith('.csv')) return <FileSpreadsheet className="w-4 h-4 text-emerald-400" />;
    if (lower.endsWith('.png') || lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.webp')) return <FileImage className="w-4 h-4 text-violet-400" />;
    return <FileCode className="w-4 h-4 text-amber-400" />;
  };

  return (
    <div className="w-full glass-panel rounded-3xl p-5 md:p-6 flex flex-col gap-5 border border-white/10 shadow-2xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-100">Document Knowledge Base</h2>
            <p className="text-xs text-slate-400">
              Chunked & embedded with vector similarity search for cross-lingual RAG.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] px-2.5 py-1 rounded-full font-bold tracking-wider uppercase border flex items-center gap-1.5 ${
              dbActive
                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${dbActive ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
            <span>{dbActive ? 'pgvector Active' : 'Memory Store'}</span>
          </span>

          <button
            onClick={fetchDocuments}
            className="p-1.5 rounded-xl bg-black/40 hover:bg-black/60 border border-white/10 text-slate-300 hover:text-white transition-all"
            title="Refresh documents"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
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
        className={`border-2 border-dashed transition-all duration-200 rounded-2xl p-7 flex flex-col items-center justify-center gap-3 cursor-pointer group ${
          isDragging
            ? 'border-amber-500 bg-amber-500/15 scale-[0.99]'
            : 'border-white/15 hover:border-amber-500/60 bg-black/30 hover:bg-black/50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.png,.jpg,.jpeg,.webp,.txt,.csv,.json,.md,.markdown"
          onChange={(e) => handleFileUpload(e.target.files)}
          className="hidden"
        />

        <div className="w-12 h-12 rounded-2xl bg-slate-900 border border-white/10 flex items-center justify-center text-amber-400 group-hover:scale-110 transition-transform shadow-lg">
          {isUploading || isSeeding ? (
            <Loader2 className="w-6 h-6 animate-spin text-amber-400" />
          ) : (
            <Upload className="w-6 h-6 text-amber-400" />
          )}
        </div>

        <div className="text-center flex flex-col gap-1">
          <p className="text-sm font-bold text-slate-200">
            {isUploading ? 'Ingesting Document...' : 'Click or Drag Files Here'}
          </p>
          <p className="text-[11px] text-slate-400">
            PDF, DOCX, XLSX, PPTX, Images (OCR), CSV, Markdown, TXT
          </p>
        </div>
      </div>

      {/* Pre-load Sample Knowledge Base Button */}
      <button
        onClick={handleSeedDocument}
        disabled={isSeeding || isUploading}
        className="w-full py-2.5 px-4 rounded-xl bg-black/40 hover:bg-amber-500/15 border border-white/10 hover:border-amber-500/30 text-amber-300 text-xs font-bold flex items-center justify-center gap-2 transition-all shadow-sm active:scale-95 disabled:opacity-50"
      >
        {isSeeding ? (
          <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
        ) : (
          <Sparkles className="w-4 h-4 text-amber-400" />
        )}
        <span>Pre-load Sample Support Knowledge Base</span>
      </button>

      {/* Upload status message */}
      {uploadStatus && !errorMessage && (
        <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center gap-2 text-emerald-300 text-xs font-medium animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{uploadStatus}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 flex items-center gap-2 text-rose-300 text-xs font-medium animate-fade-in">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Document List Header & Search Filter */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Indexed Documents ({documents.length})
          </span>

          {documents.length > 0 && (
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
              <input
                type="text"
                value={docSearch}
                onChange={(e) => setDocSearch(e.target.value)}
                placeholder="Search docs..."
                className="pl-7 pr-3 py-1 rounded-lg bg-black/40 border border-white/10 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/60 w-36 transition-colors"
              />
            </div>
          )}
        </div>

        {documents.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500 italic border border-white/5 bg-black/20 rounded-2xl">
            No documents uploaded yet. Upload a PDF or click "Pre-load Sample Support Knowledge Base" above!
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="py-6 text-center text-xs text-slate-500 italic">
            No documents match "{docSearch}"
          </div>
        ) : (
          <div className="max-h-56 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
            {filteredDocs.map((doc) => (
              <div
                key={doc.id}
                className="p-3 rounded-xl bg-black/30 border border-white/5 flex items-center justify-between hover:border-white/20 hover:bg-black/50 transition-all"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded-lg bg-slate-900 border border-white/5 shrink-0">
                    {getDocIcon(doc.title)}
                  </div>

                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-200 truncate">{doc.title}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5 font-mono">
                      <span className="text-amber-400/80 font-bold">{doc.chunk_count || 0} chunks</span>
                      {' • '}
                      <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => handleDelete(doc.id)}
                  className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/15 rounded-lg transition-colors"
                  title="Delete Document"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
