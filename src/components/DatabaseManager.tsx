'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Database,
  Table as TableIcon,
  Plus,
  Upload,
  Play,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Terminal,
  FileSpreadsheet,
  Server,
  Layers,
  Download,
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

      setStatusMsg(data.message || 'Dataset uploaded successfully!');
      setCsvTableName('');
      fetchDatabases();
      fetchSchemas();
    } catch (err: any) {
      setErrorMsg(err.message || 'CSV upload failed');
      setStatusMsg(null);
    } finally {
      setIsUploadingCsv(false);
    }
  };

  const handleRunSqlQuery = async () => {
    if (!sandboxQuery.trim()) return;
    setIsExecutingSql(true);
    setErrorMsg(null);
    setSandboxResult(null);

    try {
      const res = await fetch('/api/databases?action=query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sqlQuery: sandboxQuery,
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
      setStatusMsg('Seeding sample customer & order database records...');
      const res = await fetch('/api/databases?action=seed', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setStatusMsg(data.message || 'Sample customer database seeded successfully!');
        fetchSchemas();
      } else {
        setErrorMsg(data.error || 'Failed to seed data');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Seeding error');
    }
  };

  const handleResetData = async () => {
    if (!confirm('Are you sure you want to clear all customer database records?')) return;
    try {
      setStatusMsg('Clearing customer database records...');
      const res = await fetch('/api/databases?action=reset', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setStatusMsg(data.message || 'All customer database records cleared successfully!');
        fetchSchemas();
      } else {
        setErrorMsg(data.error || 'Failed to clear data');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Clear data error');
    }
  };

  const currentDbSchemas = schemas[selectedDbId] || [];

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="glass-panel p-6 rounded-2xl border border-gray-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Database className="w-6 h-6 text-amber-400" />
            <h2 className="text-lg font-bold text-gray-100">Multi-Database Manager</h2>
            <span className="px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-800/60 text-[10px] font-bold">
              {databases.length} Active Databases
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Connect multiple databases (PostgreSQL, MySQL, SQLite) or upload CSV datasets to query with AI Text-to-SQL RAG.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleSeedData}
            className="px-2.5 py-1.5 rounded-xl bg-emerald-950/80 hover:bg-emerald-900/80 border border-emerald-800/60 text-emerald-300 text-[11px] font-bold flex items-center gap-1 transition-all"
            title="Populate test customer & order records"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-400" />
            <span>Seed Test Data</span>
          </button>
          <button
            onClick={handleResetData}
            className="px-2.5 py-1.5 rounded-xl bg-rose-950/80 hover:bg-rose-900/80 border border-rose-800/60 text-rose-300 text-[11px] font-bold flex items-center gap-1 transition-all"
            title="Clear test customer records"
          >
            <Trash2 className="w-3.5 h-3.5 text-rose-400" />
            <span>Clear Data</span>
          </button>

          <button
            onClick={() => setActiveTab('tables')}
            className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === 'tables' ? 'bg-amber-500 text-black shadow-lg shadow-amber-500/20' : 'bg-gray-900 text-gray-400 hover:text-white border border-gray-800'
            }`}
          >
            <TableIcon className="w-4 h-4" />
            <span>Schemas</span>
          </button>
          <button
            onClick={() => setActiveTab('connect')}
            className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === 'connect' ? 'bg-amber-500 text-black shadow-lg shadow-amber-500/20' : 'bg-gray-900 text-gray-400 hover:text-white border border-gray-800'
            }`}
          >
            <Server className="w-4 h-4" />
            <span>Connect DB</span>
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === 'upload' ? 'bg-amber-500 text-black shadow-lg shadow-amber-500/20' : 'bg-gray-900 text-gray-400 hover:text-white border border-gray-800'
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>Upload CSV</span>
          </button>
          <button
            onClick={() => setActiveTab('sandbox')}
            className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === 'sandbox' ? 'bg-amber-500 text-black shadow-lg shadow-amber-500/20' : 'bg-gray-900 text-gray-400 hover:text-white border border-gray-800'
            }`}
          >
            <Terminal className="w-4 h-4" />
            <span>SQL Sandbox</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {statusMsg && (
        <div className="p-4 rounded-xl bg-emerald-950/60 border border-emerald-800/80 text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>{statusMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Main Content Area */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Side: Databases List */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider px-1">Registered Databases</h3>
          <div className="space-y-2">
            {databases.map((db) => (
              <div
                key={db.id}
                onClick={() => setSelectedDbId(db.id)}
                className={`p-4 rounded-xl border transition-all cursor-pointer ${
                  selectedDbId === db.id
                    ? 'bg-amber-950/40 border-amber-500/80 shadow-md'
                    : 'bg-gray-900/60 border-gray-800 hover:border-gray-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <Database className={`w-4 h-4 ${selectedDbId === db.id ? 'text-amber-400' : 'text-gray-400'}`} />
                    <span className="text-sm font-semibold text-gray-200">{db.name}</span>
                  </div>
                  {!db.is_builtin && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteDb(db.id);
                      }}
                      className="p-1 rounded text-gray-500 hover:text-rose-400 transition-all"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-3 mt-2 text-[11px] text-gray-400">
                  <span className="px-1.5 py-0.5 rounded bg-gray-800 text-gray-300 font-mono text-[10px] uppercase">
                    {db.type}
                  </span>
                  <span>{db.table_count} Tables</span>
                  <span className="text-emerald-400">● Connected</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Side: Tab Details */}
        <div className="md:col-span-2 space-y-4">
          {activeTab === 'tables' && (
            <div className="glass-panel p-6 rounded-2xl border border-gray-800 space-y-4">
              <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                <div>
                  <h3 className="text-sm font-bold text-gray-200">Discovered Table Schemas</h3>
                  <p className="text-xs text-gray-400">Viewing structure for DB: {selectedDbId}</p>
                </div>
                <span className="text-xs px-2.5 py-1 rounded-lg bg-gray-900 text-amber-400 border border-gray-800 font-mono">
                  {currentDbSchemas.length} Tables
                </span>
              </div>

              {currentDbSchemas.length === 0 ? (
                <p className="text-xs text-gray-500 italic py-6 text-center">No table schemas discovered yet for this database.</p>
              ) : (
                <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
                  {currentDbSchemas.map((schema) => (
                    <div key={schema.table_name} className="bg-gray-900/80 rounded-xl border border-gray-800 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <TableIcon className="w-4 h-4 text-amber-400" />
                        <h4 className="text-xs font-bold text-gray-200 font-mono">Table: {schema.table_name}</h4>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-2">
                        {schema.columns.map((col) => (
                          <div key={col.column} className="bg-gray-950 p-2 rounded-lg border border-gray-800/60 flex items-center justify-between text-[11px]">
                            <span className="text-gray-300 font-medium">{col.column}</span>
                            <span className="text-amber-400/80 font-mono text-[10px]">{col.type}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'connect' && (
            <form onSubmit={handleConnectDb} className="glass-panel p-6 rounded-2xl border border-gray-800 space-y-4">
              <h3 className="text-sm font-bold text-gray-200">Register External Database Connection</h3>
              
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-gray-400 block mb-1">Database Display Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Sales Production PostgreSQL DB"
                    value={connectName}
                    onChange={(e) => setConnectName(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-amber-500"
                    required
                  />
                </div>

                <div>
                  <label className="text-xs text-gray-400 block mb-1">Database Type</label>
                  <select
                    value={connectType}
                    onChange={(e) => setConnectType(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-amber-500"
                  >
                    <option value="postgresql">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="sqlite">SQLite File Path</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs text-gray-400 block mb-1">Connection String / File Path</label>
                  <input
                    type="text"
                    placeholder={connectType === 'sqlite' ? '/path/to/database.db' : 'postgresql://user:pass@localhost:5432/dbname'}
                    value={connectString}
                    onChange={(e) => setConnectString(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-gray-200 font-mono focus:outline-none focus:border-amber-500"
                    required
                  />
                </div>

                <button
                  type="submit"
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-black text-xs font-bold hover:opacity-90 transition-all shadow-md"
                >
                  Test Connection & Save
                </button>
              </div>
            </form>
          )}

          {activeTab === 'upload' && (
            <div className="glass-panel p-6 rounded-2xl border border-gray-800 space-y-4">
              <h3 className="text-sm font-bold text-gray-200">Upload CSV / JSON Dataset into SQL Store</h3>
              <p className="text-xs text-gray-400">
                Upload raw tabular datasets (CSV/JSON). The backend parses rows automatically into queryable SQL tables!
              </p>

              <div>
                <label className="text-xs text-gray-400 block mb-1">Optional Target Table Name</label>
                <input
                  type="text"
                  placeholder="e.g. support_tickets_2026"
                  value={csvTableName}
                  onChange={(e) => setCsvTableName(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div
                onClick={() => csvInputRef.current?.click()}
                className="border-2 border-dashed border-gray-700 hover:border-amber-500 bg-gray-900/50 rounded-2xl p-8 text-center cursor-pointer transition-all space-y-3"
              >
                {isUploadingCsv ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
                    <span className="text-xs text-amber-300 font-medium">Processing CSV dataset into SQL tables...</span>
                  </div>
                ) : (
                  <>
                    <FileSpreadsheet className="w-10 h-10 text-amber-400 mx-auto" />
                    <div>
                      <p className="text-xs font-semibold text-gray-200">Click to select CSV or JSON file</p>
                      <p className="text-[11px] text-gray-500 mt-1">Supports CSV, TSV, JSON tabular files</p>
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

          {activeTab === 'sandbox' && (
            <div className="glass-panel p-6 rounded-2xl border border-gray-800 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-gray-200 flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-amber-400" />
                  <span>Read-Only SQL Sandbox</span>
                </h3>
                <span className="text-[11px] text-emerald-400 font-mono">SELECT Only</span>
              </div>

              <div className="space-y-2">
                <textarea
                  value={sandboxQuery}
                  onChange={(e) => setSandboxQuery(e.target.value)}
                  rows={3}
                  className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-xs text-amber-300 font-mono focus:outline-none focus:border-amber-500"
                  placeholder="Enter SELECT query..."
                />
                <button
                  onClick={handleRunSqlQuery}
                  disabled={isExecutingSql}
                  className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-black text-xs font-bold flex items-center gap-2 transition-all"
                >
                  {isExecutingSql ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-black" />}
                  <span>Execute Test Query</span>
                </button>
              </div>

              {sandboxResult && (
                <div className="space-y-2 pt-2 border-t border-gray-800">
                  <div className="flex items-center justify-between text-xs text-gray-400">
                    <span>Retrieved {sandboxResult.rowCount} rows</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-amber-400/80">{sandboxResult.query}</span>
                      {sandboxResult.rows && sandboxResult.rows.length > 0 && (
                        <button
                          onClick={() => {
                            const cols = sandboxResult.columns || [];
                            const header = cols.join(',');
                            const rows = sandboxResult.rows.map((r: any) => cols.map((c: string) => `"${String(r[c] ?? '').replace(/"/g, '""')}"`).join(','));
                            const csvContent = 'data:text/csv;charset=utf-8,' + [header, ...rows].join('\n');
                            const encodedUri = encodeURI(csvContent);
                            const link = document.createElement('a');
                            link.setAttribute('href', encodedUri);
                            link.setAttribute('download', `query_results_${Date.now()}.csv`);
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                          }}
                          className="px-2 py-1 rounded bg-amber-950 text-amber-300 border border-amber-800/80 hover:bg-amber-900 text-[10px] font-bold flex items-center gap-1 transition-all"
                        >
                          <Download className="w-3 h-3" />
                          <span>Export CSV</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {sandboxResult.columns && sandboxResult.columns.length > 0 && (
                    <div className="overflow-x-auto rounded-xl border border-gray-800 max-h-60 custom-scrollbar">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-gray-900 border-b border-gray-800 text-gray-400 font-mono text-[11px]">
                          <tr>
                            {sandboxResult.columns.map((col: string) => (
                              <th key={col} className="p-2.5">{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-800 text-gray-300 font-mono text-[11px]">
                          {sandboxResult.rows.map((row: any, i: number) => (
                            <tr key={i} className="hover:bg-gray-900/50">
                              {sandboxResult.columns.map((col: string) => (
                                <td key={col} className="p-2.5">{String(row[col] ?? '')}</td>
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
        </div>
      </div>
    </div>
  );
};
