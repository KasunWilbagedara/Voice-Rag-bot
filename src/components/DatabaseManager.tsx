'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Database,
  Table as TableIcon,
  Plus,
  Play,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Terminal,
  FileSpreadsheet,
  Server,
  Download,
  Search,
  Sparkles,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';

interface DatabaseItem {
  id: string;
  name: string;
  type: string;
  status: string;
  is_builtin: boolean;
  table_count: number;
  tables: string[];
}

interface TableColumn {
  column: string;
  type: string;
}

interface TableSchema {
  table_name: string;
  columns: TableColumn[];
}

export const DatabaseManager: React.FC = () => {
  const [databases, setDatabases] = useState<DatabaseItem[]>([]);
  const [schemas, setSchemas] = useState<Record<string, TableSchema[]>>({});
  const [selectedDbId, setSelectedDbId] = useState<string>('customer_support_db');
  
  const [activeTab, setActiveTab] = useState<'tables' | 'connect' | 'upload' | 'sandbox'>('tables');
  const [isLoading, setIsLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [schemaSearch, setSchemaSearch] = useState<string>('');

  // Connect Form State
  const [connectName, setConnectName] = useState('');
  const [connectType, setConnectType] = useState('postgresql');
  const [connectString, setConnectString] = useState('');

  // CSV Upload State
  const [csvTableName, setCsvTableName] = useState('');
  const [isUploadingCsv, setIsUploadingCsv] = useState(false);
  const csvInputRef = useRef<HTMLInputElement | null>(null);

  // SQL Sandbox State
  const [sandboxQuery, setSandboxQuery] = useState('SELECT * FROM customers LIMIT 5;');
  const [sandboxResult, setSandboxResult] = useState<any>(null);
  const [isExecutingSql, setIsExecutingSql] = useState(false);

  const fetchDatabases = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/databases');
      const data = await res.json();
      if (res.ok) {
        setDatabases(data.databases || []);
      }
    } catch (err: any) {
      console.error('Failed to fetch databases:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchSchemas = async () => {
    try {
      const res = await fetch('/api/databases', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setSchemas(data.schemas || {});
      }
    } catch (err: any) {
      console.error('Failed to fetch schemas:', err);
    }
  };

  useEffect(() => {
    fetchDatabases();
    fetchSchemas();
  }, []);

  const handleConnectDb = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!connectName || !connectString) return;
    setStatusMsg('Testing connection and registering database...');
    setErrorMsg(null);

    try {
      const res = await fetch('/api/databases?action=connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: connectName,
          dbType: connectType,
          connectionString: connectString,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Connection failed');

      setStatusMsg(`Connected database '${connectName}' successfully!`);
      setConnectName('');
      setConnectString('');
      fetchDatabases();
      fetchSchemas();
      setActiveTab('tables');
    } catch (err: any) {
      setErrorMsg(err.message || 'Database connection error');
      setStatusMsg(null);
    }
  };

  const handleCsvUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];

    setIsUploadingCsv(true);
    setErrorMsg(null);
    setStatusMsg(`Parsing dataset '${file.name}' into SQL table...`);

    const formData = new FormData();
    formData.append('file', file);
    if (csvTableName.trim()) {
      formData.append('tableName', csvTableName.trim());
    }

    try {
      const res = await fetch('/api/databases?action=upload-csv', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'CSV upload failed');

      setStatusMsg(data.message || `Dataset '${file.name}' ingested into SQL store!`);
      setCsvTableName('');
      fetchDatabases();
      fetchSchemas();
      setActiveTab('tables');
    } catch (err: any) {
      setErrorMsg(err.message || 'CSV upload failed');
      setStatusMsg(null);
    } finally {
      setIsUploadingCsv(false);
    }
  };

  const handleRunSqlQuery = async (overrideQuery?: string) => {
    const queryToRun = overrideQuery || sandboxQuery;
    if (!queryToRun.trim()) return;
    setIsExecutingSql(true);
    setErrorMsg(null);
    setSandboxResult(null);

    try {
      const res = await fetch('/api/databases?action=query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sqlQuery: queryToRun,
          dbId: selectedDbId,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || data.detail || 'Query execution error');
      setSandboxResult(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to execute query');
    } finally {
      setIsExecutingSql(false);
    }
  };

  const handleDeleteDb = async (dbId: string) => {
    if (!confirm('Are you sure you want to remove this database connection?')) return;
    try {
      const res = await fetch(`/api/databases?dbId=${dbId}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to delete');
      fetchDatabases();
      fetchSchemas();
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  const handleSeedData = async () => {
    try {
      setStatusMsg('Seeding sample customer, order, and student database records...');
      const res = await fetch('/api/databases?action=seed', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setStatusMsg(data.message || 'Sample database seeded successfully!');
        fetchSchemas();
      } else {
        setErrorMsg(data.error || 'Failed to seed data');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Seeding error');
    }
  };

  const handleResetData = async () => {
    if (!confirm('Are you sure you want to clear all test database records?')) return;
    try {
      setStatusMsg('Clearing test database records...');
      const res = await fetch('/api/databases?action=reset', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setStatusMsg(data.message || 'Test database records cleared successfully!');
        fetchSchemas();
      } else {
        setErrorMsg(data.error || 'Failed to clear data');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Clear data error');
    }
  };

  const currentDbSchemas = schemas[selectedDbId] || [];
  const filteredSchemas = currentDbSchemas.filter((s) =>
    s.table_name.toLowerCase().includes(schemaSearch.toLowerCase()) ||
    s.columns.some((c) => c.column.toLowerCase().includes(schemaSearch.toLowerCase()))
  );

  return (
    <div className="w-full glass-panel rounded-3xl p-5 md:p-6 flex flex-col gap-5 border border-white/10 shadow-2xl">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Database className="w-4 h-4" />
            </div>
            <h2 className="text-base font-bold text-slate-100">Multi-Database Hub</h2>
            <span className="px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 text-[11px] font-bold">
              {databases.length} Connected
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Query SQL databases & uploaded CSV datasets seamlessly with AI Text-to-SQL RAG.
          </p>
        </div>

        {/* Quick Seeding and Refresh actions */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleSeedData}
            className="px-3 py-1.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm active:scale-95"
            title="Populate test customer, order, and student records"
          >
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>Seed Test Data</span>
          </button>
          <button
            onClick={handleResetData}
            className="px-2.5 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-300 text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm active:scale-95"
            title="Clear test records"
          >
            <Trash2 className="w-3.5 h-3.5 text-rose-400" />
            <span>Clear</span>
          </button>
          <button
            onClick={() => {
              fetchDatabases();
              fetchSchemas();
            }}
            className="p-1.5 rounded-xl bg-black/40 hover:bg-black/60 border border-white/10 text-slate-300 hover:text-white transition-all"
            title="Refresh database metadata"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-amber-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Notifications */}
      {statusMsg && (
        <div className="p-3.5 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-medium flex items-center gap-2 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{statusMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-3.5 rounded-2xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs font-medium flex items-center gap-2 animate-fade-in">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Tab Controls */}
      <div className="flex items-center gap-1.5 p-1 bg-black/40 border border-white/10 rounded-2xl overflow-x-auto">
        <button
          onClick={() => setActiveTab('tables')}
          className={`flex-1 min-w-[100px] py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
            activeTab === 'tables'
              ? 'bg-amber-500 text-slate-950 font-extrabold shadow-md shadow-amber-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <TableIcon className="w-3.5 h-3.5" />
          <span>Schemas</span>
        </button>

        <button
          onClick={() => setActiveTab('sandbox')}
          className={`flex-1 min-w-[110px] py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
            activeTab === 'sandbox'
              ? 'bg-amber-500 text-slate-950 font-extrabold shadow-md shadow-amber-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>SQL Sandbox</span>
        </button>

        <button
          onClick={() => setActiveTab('upload')}
          className={`flex-1 min-w-[100px] py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
            activeTab === 'upload'
              ? 'bg-amber-500 text-slate-950 font-extrabold shadow-md shadow-amber-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileSpreadsheet className="w-3.5 h-3.5" />
          <span>Upload CSV</span>
        </button>

        <button
          onClick={() => setActiveTab('connect')}
          className={`flex-1 min-w-[110px] py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
            activeTab === 'connect'
              ? 'bg-amber-500 text-slate-950 font-extrabold shadow-md shadow-amber-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Server className="w-3.5 h-3.5" />
          <span>Connect DB</span>
        </button>
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-5">
        {/* Left Side: Registered Databases List (4 cols) */}
        <div className="md:col-span-4 flex flex-col gap-2.5">
          <div className="flex items-center justify-between px-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              Active Databases ({databases.length})
            </span>
          </div>

          <div className="flex flex-col gap-2 max-h-[380px] overflow-y-auto pr-1 custom-scrollbar">
            {databases.map((db) => {
              const isSelected = selectedDbId === db.id;
              return (
                <div
                  key={db.id}
                  onClick={() => setSelectedDbId(db.id)}
                  className={`p-3.5 rounded-2xl border transition-all cursor-pointer flex flex-col gap-2 ${
                    isSelected
                      ? 'bg-amber-500/15 border-amber-500/60 shadow-lg shadow-amber-500/10'
                      : 'bg-black/30 border-white/5 hover:border-white/20 hover:bg-black/50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className={`p-1.5 rounded-lg ${isSelected ? 'bg-amber-500/20 text-amber-400' : 'bg-slate-800 text-slate-400'}`}>
                        <Database className="w-3.5 h-3.5" />
                      </div>
                      <span className="text-xs font-bold text-slate-200 truncate">{db.name}</span>
                    </div>

                    {!db.is_builtin && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteDb(db.id);
                        }}
                        className="p-1 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/15 transition-all"
                        title="Delete database connection"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                    <span className="px-1.5 py-0.5 rounded bg-black/50 text-slate-300 uppercase border border-white/5">
                      {db.type}
                    </span>
                    <span className="text-emerald-400 flex items-center gap-1 font-sans font-semibold">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      {db.table_count || db.tables?.length || 0} Tables
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Side: Tab Details (8 cols) */}
        <div className="md:col-span-8">
          {/* Tab 1: Table Schemas Explorer */}
          {activeTab === 'tables' && (
            <div className="bg-black/30 rounded-2xl border border-white/10 p-4 md:p-5 flex flex-col gap-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-3">
                <div>
                  <h3 className="text-sm font-bold text-slate-200">Discovered Table Schemas</h3>
                  <p className="text-[11px] text-slate-400 font-mono">DB: {selectedDbId}</p>
                </div>

                {/* Schema Search Filter */}
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={schemaSearch}
                    onChange={(e) => setSchemaSearch(e.target.value)}
                    placeholder="Filter tables & columns..."
                    className="pl-8 pr-3 py-1.5 rounded-xl bg-black/50 border border-white/10 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/60 transition-colors w-full sm:w-48"
                  />
                </div>
              </div>

              {filteredSchemas.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-500 italic">
                  {currentDbSchemas.length === 0
                    ? 'No table schemas discovered yet for this database. Click "Seed Test Data" to populate sample data.'
                    : 'No tables or columns match your search filter.'}
                </div>
              ) : (
                <div className="flex flex-col gap-3 max-h-[360px] overflow-y-auto pr-1 custom-scrollbar">
                  {filteredSchemas.map((schema) => (
                    <div
                      key={schema.table_name}
                      className="bg-black/40 rounded-xl border border-white/10 p-3.5 flex flex-col gap-2 hover:border-amber-500/30 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <TableIcon className="w-4 h-4 text-amber-400" />
                          <h4 className="text-xs font-bold text-slate-200 font-mono">
                            {schema.table_name}
                          </h4>
                        </div>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {schema.columns.length} columns
                        </span>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 mt-1">
                        {schema.columns.map((col) => (
                          <div
                            key={col.column}
                            className="bg-slate-950/80 p-2 rounded-lg border border-white/5 flex items-center justify-between text-[11px]"
                          >
                            <span className="text-slate-300 font-medium truncate">{col.column}</span>
                            <span className="text-amber-400/80 font-mono text-[9px] uppercase shrink-0 pl-1">
                              {col.type}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tab 2: SQL Sandbox */}
          {activeTab === 'sandbox' && (
            <div className="bg-black/30 rounded-2xl border border-white/10 p-4 md:p-5 flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-amber-400" />
                  <h3 className="text-sm font-bold text-slate-200">Interactive SQL Sandbox</h3>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-mono font-bold">
                  SELECT Only Safe Execution
                </span>
              </div>

              {/* Sample Queries Quick Run */}
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] text-slate-400">Quick Templates:</span>
                {[
                  { label: 'Customers', query: 'SELECT * FROM customers LIMIT 5;' },
                  { label: 'Orders Status', query: 'SELECT order_number, customer_name, total_amount, status FROM orders LIMIT 5;' },
                  { label: 'Students GPA', query: 'SELECT student_id, name, department, gpa FROM students ORDER BY gpa DESC LIMIT 5;' },
                ].map((t, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setSandboxQuery(t.query);
                      handleRunSqlQuery(t.query);
                    }}
                    className="px-2 py-1 rounded-lg bg-black/50 hover:bg-amber-500/15 border border-white/10 text-amber-300 text-[10px] font-mono transition-all"
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div className="flex flex-col gap-2">
                <textarea
                  value={sandboxQuery}
                  onChange={(e) => setSandboxQuery(e.target.value)}
                  rows={3}
                  className="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-xs text-amber-300 font-mono focus:outline-none focus:border-amber-500/60 transition-colors"
                  placeholder="Enter SQL SELECT query..."
                />
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-slate-500">Querying DB: {selectedDbId}</span>
                  <button
                    onClick={() => handleRunSqlQuery()}
                    disabled={isExecutingSql}
                    className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold flex items-center gap-1.5 transition-all shadow-md shadow-amber-500/20 active:scale-95 disabled:opacity-50"
                  >
                    {isExecutingSql ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-slate-950" />}
                    <span>Execute SQL</span>
                  </button>
                </div>
              </div>

              {sandboxResult && (
                <div className="flex flex-col gap-2 pt-3 border-t border-white/10">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span className="font-semibold text-emerald-400">
                      Returned {sandboxResult.rowCount || sandboxResult.rows?.length || 0} rows
                    </span>
                    {sandboxResult.rows && sandboxResult.rows.length > 0 && (
                      <button
                        onClick={() => {
                          const cols = sandboxResult.columns || Object.keys(sandboxResult.rows[0] || {});
                          const header = cols.join(',');
                          const rows = sandboxResult.rows.map((r: any) =>
                            cols.map((c: string) => `"${String(r[c] ?? '').replace(/"/g, '""')}"`).join(',')
                          );
                          const csvContent = 'data:text/csv;charset=utf-8,' + [header, ...rows].join('\n');
                          const encodedUri = encodeURI(csvContent);
                          const link = document.createElement('a');
                          link.setAttribute('href', encodedUri);
                          link.setAttribute('download', `query_results_${Date.now()}.csv`);
                          document.body.appendChild(link);
                          link.click();
                          document.body.removeChild(link);
                        }}
                        className="px-2 py-1 rounded-lg bg-black/40 hover:bg-amber-500/15 border border-white/10 text-amber-300 text-[10px] font-bold flex items-center gap-1 transition-all"
                      >
                        <Download className="w-3 h-3" />
                        <span>Export CSV</span>
                      </button>
                    )}
                  </div>

                  {sandboxResult.columns && sandboxResult.columns.length > 0 && (
                    <div className="overflow-x-auto rounded-xl border border-white/10 max-h-56 custom-scrollbar bg-black/40">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-900 border-b border-white/10 text-slate-400 font-mono text-[10px]">
                          <tr>
                            {sandboxResult.columns.map((col: string) => (
                              <th key={col} className="p-2.5 whitespace-nowrap">{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 text-slate-300 font-mono text-[11px]">
                          {sandboxResult.rows.map((row: any, i: number) => (
                            <tr key={i} className="hover:bg-white/5 transition-colors">
                              {sandboxResult.columns.map((col: string) => (
                                <td key={col} className="p-2.5 whitespace-nowrap">{String(row[col] ?? '')}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Upload CSV Dataset */}
          {activeTab === 'upload' && (
            <div className="bg-black/30 rounded-2xl border border-white/10 p-4 md:p-5 flex flex-col gap-4">
              <div>
                <h3 className="text-sm font-bold text-slate-200">Upload CSV / JSON Dataset</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Upload raw tabular datasets. The backend automatically creates queryable SQL tables!
                </p>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs text-slate-400">Optional Custom Target Table Name</label>
                <input
                  type="text"
                  placeholder="e.g. support_tickets_2026"
                  value={csvTableName}
                  onChange={(e) => setCsvTableName(e.target.value)}
                  className="w-full bg-black/50 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500/60 font-mono transition-colors"
                />
              </div>

              <div
                onClick={() => csvInputRef.current?.click()}
                className="border-2 border-dashed border-white/15 hover:border-amber-500/60 bg-black/40 hover:bg-black/60 rounded-2xl p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3 group"
              >
                {isUploadingCsv ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
                    <span className="text-xs text-amber-300 font-medium">Processing CSV dataset into SQL tables...</span>
                  </div>
                ) : (
                  <>
                    <div className="w-12 h-12 rounded-2xl bg-slate-900 border border-white/10 flex items-center justify-center text-amber-400 group-hover:scale-110 transition-transform shadow-lg">
                      <FileSpreadsheet className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-200">Click or drag CSV/JSON file here</p>
                      <p className="text-[10px] text-slate-500 mt-0.5">Supports CSV, TSV, and JSON tabular formats</p>
                    </div>
                  </>
                )}
                <input
                  ref={csvInputRef}
                  type="file"
                  accept=".csv,.tsv,.json"
                  className="hidden"
                  onChange={(e) => handleCsvUpload(e.target.files)}
                />
              </div>
            </div>
          )}

          {/* Tab 4: Connect External DB */}
          {activeTab === 'connect' && (
            <form onSubmit={handleConnectDb} className="bg-black/30 rounded-2xl border border-white/10 p-4 md:p-5 flex flex-col gap-4">
              <div>
                <h3 className="text-sm font-bold text-slate-200">Register External Database Connection</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Connect live PostgreSQL, MySQL, or local SQLite database instances.
                </p>
              </div>
              
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Database Display Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Production Analytics DB"
                    value={connectName}
                    onChange={(e) => setConnectName(e.target.value)}
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500/60 transition-colors"
                    required
                  />
                </div>

                <div>
                  <label className="text-xs text-slate-400 block mb-1">Database Engine</label>
                  <select
                    value={connectType}
                    onChange={(e) => setConnectType(e.target.value)}
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500/60 transition-colors"
                  >
                    <option value="postgresql">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="sqlite">SQLite (File Path)</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs text-slate-400 block mb-1">Connection String / File Path</label>
                  <input
                    type="text"
                    placeholder={connectType === 'sqlite' ? '/path/to/database.db' : 'postgresql://user:pass@localhost:5432/dbname'}
                    value={connectString}
                    onChange={(e) => setConnectString(e.target.value)}
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-amber-500/60 transition-colors"
                    required
                  />
                </div>

                <button
                  type="submit"
                  className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-all shadow-lg shadow-amber-500/20 active:scale-95"
                >
                  Test Connection & Register DB
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
