import React, { useState } from 'react';
import {
  Plus,
  ArrowRight,
  CheckCircle,
  XCircle,
  Trash2,
  Sliders,
  HelpCircle,
} from 'lucide-react';
import type { Company, TransactionMapping, TransactionType } from '../types';

interface TransactionMappingsTabProps {
  mappings: TransactionMapping[];
  companies: Company[];
  onToggleMapping: (id: string) => void;
  onCreateMapping: (mapping: Partial<TransactionMapping>) => Promise<void>;
  onDeleteMapping: (id: string) => void;
}

export const TransactionMappingsTab: React.FC<TransactionMappingsTabProps> = ({
  mappings,
  companies,
  onToggleMapping,
  onCreateMapping,
  onDeleteMapping,
}) => {
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [mainCompany, setMainCompany] = useState(companies[0]?.name || '');
  const [otherCompany, setOtherCompany] = useState(companies[1]?.name || '');
  const [mainType, setMainType] = useState<TransactionType>('Sales Order');
  const [otherType, setOtherType] = useState<TransactionType>('Purchase Order');
  const [mainParty, setMainParty] = useState('');
  const [otherParty, setOtherParty] = useState('');
  const [autoSubmit, setAutoSubmit] = useState(true);
  const [allowLinkedCancellation, setAllowLinkedCancellation] = useState(true);
  const [syncStatusUpdates, setSyncStatusUpdates] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const transactionTypes: TransactionType[] = [
    'Sales Order',
    'Purchase Order',
    'Sales Invoice',
    'Purchase Invoice',
    'Journal Entry',
    'Payment Entry',
  ];

  const handleMainTypeChange = (val: TransactionType) => {
    setMainType(val);
    // Auto suggest reverse mapping as in ERPNext
    if (val === 'Sales Order') setOtherType('Purchase Order');
    else if (val === 'Purchase Order') setOtherType('Sales Order');
    else if (val === 'Sales Invoice') setOtherType('Purchase Invoice');
    else if (val === 'Purchase Invoice') setOtherType('Sales Invoice');
    else if (val === 'Journal Entry') setOtherType('Journal Entry');
    else if (val === 'Payment Entry') setOtherType('Payment Entry');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mainCompany || !otherCompany || mainCompany === otherCompany) {
      alert('Source and Target companies must be different.');
      return;
    }

    setIsSubmitting(true);
    try {
      await onCreateMapping({
        name: name || `${mainCompany.split(' ')[0]} to ${otherCompany.split(' ')[0]} ${mainType}/${otherType} Pipeline`,
        mainCompany,
        otherCompany,
        mainTransactionType: mainType,
        otherTransactionType: otherType,
        mainParty: mainParty || `${otherCompany} (Mapped Entity)`,
        otherParty: otherParty || `${mainCompany} (Mapped Entity)`,
        autoSubmit,
        allowLinkedCancellation,
        syncStatusUpdates,
        enabled: true,
      });
      setShowModal(false);
      setName('');
      setMainParty('');
      setOtherParty('');
    } catch (err: any) {
      alert(err.message || 'Failed to create mapping');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <h1 className="text-base font-bold text-slate-900">Inter-Company Transaction Mappings</h1>
          <p className="text-xs text-slate-500">
            Define automated document generation and synchronization rules between corporate entities.
          </p>
        </div>
        <button
          id="btn-open-create-mapping-modal"
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>New Transaction Map</span>
        </button>
      </div>

      {/* Info Card explaining Frappe / ERPNext behavior */}
      <div className="bg-indigo-50/70 border border-indigo-200/80 rounded-xl p-4 text-xs text-indigo-950 flex items-start gap-3">
        <HelpCircle className="w-5 h-5 text-indigo-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold">How Inter-Company Mapping Works:</span>
          <p className="text-slate-700 leading-relaxed">
            When you create and post a transaction (such as a <strong>Sales Order</strong>) in Company A, ERPNext intercepts the submit event via hooks. It locates the matching active mapping rule and generates the corresponding mirror document (e.g. <strong>Purchase Order</strong>) in Company B, maintaining an immutable two-way cross-reference link.
          </p>
        </div>
      </div>

      {/* Mappings Cards */}
      <div className="grid grid-cols-1 gap-4">
        {mappings.map((mapping) => (
          <div
            key={mapping.id}
            className={`bg-white rounded-xl border p-5 transition-all shadow-xs ${
              mapping.enabled ? 'border-slate-200' : 'border-slate-200 bg-slate-50/50 opacity-80'
            }`}
          >
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div
                  className={`w-9 h-9 rounded-lg flex items-center justify-center font-mono font-bold text-xs ${
                    mapping.enabled ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-200 text-slate-600'
                  }`}
                >
                  {mapping.id}
                </div>
                <div>
                  <h2 className="text-sm font-bold text-slate-900">{mapping.name}</h2>
                  <p className="text-xs text-slate-500">{mapping.description || 'Configured intercompany route'}</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {/* Toggle Active */}
                <button
                  id={`toggle-mapping-${mapping.id}`}
                  onClick={() => onToggleMapping(mapping.id)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold cursor-pointer transition-colors ${
                    mapping.enabled
                      ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-200'
                  }`}
                >
                  {mapping.enabled ? (
                    <>
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Enabled</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-3.5 h-3.5 text-slate-400" />
                      <span>Disabled</span>
                    </>
                  )}
                </button>

                {/* Delete */}
                <button
                  id={`delete-mapping-${mapping.id}`}
                  onClick={() => onDeleteMapping(mapping.id)}
                  title="Delete Mapping"
                  className="p-1.5 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Pipeline Visualizer */}
            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 items-center gap-3 text-xs">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80">
                <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Source Company</span>
                <span className="font-bold text-slate-900 block">{mapping.mainCompany}</span>
                <div className="mt-2 flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-100 text-indigo-800">
                    {mapping.mainTransactionType}
                  </span>
                  <span className="text-[11px] text-slate-500">Party: {mapping.mainParty}</span>
                </div>
              </div>

              <div className="flex flex-col items-center justify-center text-center p-2">
                <div className="flex items-center gap-2 text-indigo-600 font-semibold mb-1">
                  <span className="text-xs">Automatic Generation</span>
                  <ArrowRight className="w-4 h-4" />
                </div>
                <div className="flex flex-wrap gap-1 justify-center">
                  <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-medium">
                    {mapping.autoSubmit ? 'Direct Submit' : 'Draft Mode'}
                  </span>
                  {mapping.allowLinkedCancellation && (
                    <span className="text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded font-medium">
                      Cancel Propagated
                    </span>
                  )}
                  {mapping.syncStatusUpdates && (
                    <span className="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-medium">
                      2-Way Synced
                    </span>
                  )}
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80">
                <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Target Company</span>
                <span className="font-bold text-slate-900 block">{mapping.otherCompany}</span>
                <div className="mt-2 flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800">
                    {mapping.otherTransactionType}
                  </span>
                  <span className="text-[11px] text-slate-500">Party: {mapping.otherParty}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* New Mapping Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-xl w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Sliders className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-sm">Create Inter-Company Transaction Map</h3>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none cursor-pointer"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Mapping Title (Optional)</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., US Sales to Europe Purchase Sync"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Source Company</label>
                  <select
                    value={mainCompany}
                    onChange={(e) => setMainCompany(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    {companies.map((c) => (
                      <option key={c.id} value={c.name}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Target Company</label>
                  <select
                    value={otherCompany}
                    onChange={(e) => setOtherCompany(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    {companies.map((c) => (
                      <option key={c.id} value={c.name}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Source Transaction Type</label>
                  <select
                    value={mainType}
                    onChange={(e) => handleMainTypeChange(e.target.value as TransactionType)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    {transactionTypes.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Target Transaction Type</label>
                  <select
                    value={otherType}
                    onChange={(e) => setOtherType(e.target.value as TransactionType)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    {transactionTypes.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Party in Source Company</label>
                  <input
                    type="text"
                    value={mainParty}
                    onChange={(e) => setMainParty(e.target.value)}
                    placeholder="e.g. Europe Subsidiary (Customer)"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Party in Target Company</label>
                  <input
                    type="text"
                    value={otherParty}
                    onChange={(e) => setOtherParty(e.target.value)}
                    placeholder="e.g. US HQ (Supplier)"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              {/* Toggles */}
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <label className="flex items-center gap-2 cursor-pointer font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={autoSubmit}
                    onChange={(e) => setAutoSubmit(e.target.checked)}
                    className="rounded text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>Auto Submit generated transaction immediately (skip draft state)</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={allowLinkedCancellation}
                    onChange={(e) => setAllowLinkedCancellation(e.target.checked)}
                    className="rounded text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>Linked Cancellation (cancelling source automatically cancels target)</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={syncStatusUpdates}
                    onChange={(e) => setSyncStatusUpdates(e.target.checked)}
                    className="rounded text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>Two-Way Status Synchronization</span>
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold cursor-pointer disabled:opacity-50"
                >
                  {isSubmitting ? 'Saving...' : 'Create Mapping'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
