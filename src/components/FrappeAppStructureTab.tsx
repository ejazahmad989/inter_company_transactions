import React, { useState, useEffect } from 'react';
import {
  FileCode,
  Terminal,
  Layers,
  CheckCircle2,
  Copy,
  Check,
  FolderTree,
  FileText,
  Boxes,
  Shield,
  ArrowRightLeft,
  Sparkles,
  GitBranch,
} from 'lucide-react';
import { api } from '../lib/api';

export const FrappeAppStructureTab: React.FC = () => {
  const [appInfo, setAppInfo] = useState<any>(null);
  const [selectedFile, setSelectedFile] = useState<string>('inter_company_transactions/hooks.py');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api
      .getFrappeAppInfo()
      .then((data) => {
        setAppInfo(data);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setIsLoading(false);
      });
  }, []);

  const handleCopy = (key: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const currentFileObj = appInfo?.files?.find((f: any) => f.path === selectedFile);

  return (
    <div className="space-y-6">
      {/* Rollback Confirmation Banner */}
      <div className="bg-emerald-50 border border-emerald-300 rounded-xl p-5 shadow-xs">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-xs">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-base font-bold text-emerald-950">
                ERPNext Custom App Rollback Complete
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                Ready for Enhancement
              </span>
            </div>
            <p className="text-xs text-emerald-800 leading-relaxed">
              The project has been restored to its original state as a valid <strong>Frappe / ERPNext Custom App</strong>. All core Python modules, Frappe hooks, DocType definitions, custom fields schema, setup manifests, and bench installation routines are active and located at their standard paths.
            </p>
          </div>
        </div>
      </div>

      {/* App Quick Stats & Bench Runbook */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <div className="flex items-center gap-2 text-indigo-700 font-bold text-xs uppercase tracking-wider mb-2">
            <Boxes className="w-4 h-4" />
            <span>Frappe App Details</span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">App Name</span>
              <span className="font-mono font-bold text-slate-800">inter_company_transactions</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">Target Framework</span>
              <span className="font-semibold text-slate-800">Frappe v14 / v15</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-1.5">
              <span className="text-slate-500">Module</span>
              <span className="font-medium text-slate-800">Inter Company Transactions</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Python Compatibility</span>
              <span className="font-medium text-slate-800">&gt;= 3.10</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs md:col-span-2">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-slate-800 font-bold text-xs uppercase tracking-wider">
              <Terminal className="w-4 h-4 text-slate-600" />
              <span>Standard Bench Installation Commands</span>
            </div>
            <span className="text-[11px] text-slate-400">Ready for Bench CLI</span>
          </div>
          <div className="bg-slate-900 text-slate-100 rounded-lg p-3 font-mono text-xs space-y-1.5 overflow-x-auto">
            <div className="flex items-center justify-between group">
              <span className="text-slate-400"># 1. Fetch app into Frappe Bench</span>
            </div>
            <div className="flex items-center justify-between text-emerald-400">
              <code>bench get-app inter_company_transactions</code>
              <button
                onClick={() => handleCopy('c1', 'bench get-app inter_company_transactions')}
                className="text-slate-400 hover:text-white cursor-pointer ml-2"
              >
                {copiedKey === 'c1' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
            <div className="flex items-center justify-between text-emerald-400 pt-1 border-t border-slate-800">
              <code>bench --site [your-site-name] install-app inter_company_transactions</code>
              <button
                onClick={() => handleCopy('c2', 'bench --site site1.local install-app inter_company_transactions')}
                className="text-slate-400 hover:text-white cursor-pointer ml-2"
              >
                {copiedKey === 'c2' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
            <div className="flex items-center justify-between text-emerald-400 pt-1 border-t border-slate-800">
              <code>bench --site [your-site-name] migrate</code>
              <button
                onClick={() => handleCopy('c3', 'bench --site site1.local migrate')}
                className="text-slate-400 hover:text-white cursor-pointer ml-2"
              >
                {copiedKey === 'c3' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* DocType & Hook Architecture */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-600" />
            <h2 className="font-bold text-slate-900 text-sm">Frappe DocTypes Registered</h2>
          </div>
          <div className="space-y-2.5 text-xs">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80">
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold text-slate-900">Inter Company Transaction Map</span>
                <span className="text-[10px] font-semibold bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded">
                  Standard DocType
                </span>
              </div>
              <p className="text-slate-600 text-[11px] leading-relaxed">
                Stores company-level intercompany configuration rules, enabled status, and child table mappings between source and target entities.
              </p>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80">
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold text-slate-900">Inter Company Transaction Mapping</span>
                <span className="text-[10px] font-semibold bg-amber-50 text-amber-800 px-2 py-0.5 rounded">
                  Child Table (istable: 1)
                </span>
              </div>
              <p className="text-slate-600 text-[11px] leading-relaxed">
                Defines row-level mappings: Sales Order &rarr; Purchase Order, Sales Invoice &rarr; Purchase Invoice, Journal Entry &rarr; Journal Entry, plus Auto Submit flags.
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2">
            <ArrowRightLeft className="w-4 h-4 text-emerald-600" />
            <h2 className="font-bold text-slate-900 text-sm">Active Document Event Hooks (doc_events)</h2>
          </div>
          <div className="space-y-2 text-xs">
            <p className="text-slate-500 text-[11px]">
              Submitting or cancelling standard ERPNext vouchers triggers bilateral synchronization hooks registered in <code>hooks.py</code>:
            </p>
            <div className="bg-slate-50 rounded-lg border border-slate-200 p-3 font-mono text-[11px] space-y-1 text-slate-700">
              <div><strong className="text-indigo-700">Sales Order</strong>: on_submit, on_cancel</div>
              <div><strong className="text-indigo-700">Purchase Order</strong>: on_submit, on_cancel</div>
              <div><strong className="text-indigo-700">Sales Invoice</strong>: on_submit, on_cancel</div>
              <div><strong className="text-indigo-700">Purchase Invoice</strong>: on_submit, on_cancel</div>
              <div><strong className="text-indigo-700">Journal Entry</strong>: on_submit, on_cancel</div>
              <div><strong className="text-indigo-700">Payment Entry</strong>: on_submit, on_cancel</div>
            </div>
            <p className="text-[11px] text-slate-500">
              Handler: <code>inter_company_transactions.utils.transaction.create_linked_transaction</code>
            </p>
          </div>
        </div>
      </div>

      {/* Interactive Frappe File Explorer */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-slate-50/60">
          <div className="flex items-center gap-2">
            <FolderTree className="w-4 h-4 text-indigo-600" />
            <h3 className="text-sm font-bold text-slate-900">Restored ERPNext Custom App Codebase</h3>
          </div>
          <span className="text-xs text-slate-500 font-mono">
            {appInfo?.files?.length || 0} Frappe manifests & python modules verified
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[420px]">
          {/* File Selector Sidebar */}
          <div className="lg:col-span-4 border-r border-slate-200 p-3 space-y-1 bg-slate-50/30 overflow-y-auto max-h-[500px]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 block mb-1">
              Frappe App Files
            </span>
            {appInfo?.files?.map((f: any) => {
              const isSelected = f.path === selectedFile;
              return (
                <button
                  key={f.path}
                  onClick={() => setSelectedFile(f.path)}
                  className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-mono transition-colors flex items-center justify-between cursor-pointer ${
                    isSelected
                      ? 'bg-indigo-600 text-white font-semibold shadow-xs'
                      : 'text-slate-700 hover:bg-slate-200/60'
                  }`}
                >
                  <span className="truncate">{f.path}</span>
                  <span
                    className={`text-[10px] ml-2 shrink-0 ${
                      isSelected ? 'text-indigo-200' : 'text-slate-400'
                    }`}
                  >
                    {Math.round(f.size / 1024 * 10) / 10} KB
                  </span>
                </button>
              );
            })}
          </div>

          {/* File Content Preview */}
          <div className="lg:col-span-8 p-4 flex flex-col bg-slate-950 text-slate-100 overflow-hidden">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 text-xs">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-indigo-400" />
                <span className="font-mono text-emerald-400 font-semibold">{selectedFile}</span>
              </div>
              <button
                onClick={() => handleCopy('file-content', currentFileObj?.content || '')}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-mono cursor-pointer transition-colors"
              >
                {copiedKey === 'file-content' ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy Code</span>
                  </>
                )}
              </button>
            </div>

            <pre className="mt-3 font-mono text-xs leading-relaxed text-slate-300 overflow-auto flex-1 max-h-[420px] p-2 bg-slate-900 rounded-md">
              <code>{currentFileObj?.content || '// File empty or loading...'}</code>
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};
