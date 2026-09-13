import React, { useState } from 'react';
import {
  GitMerge,
  Search,
  RefreshCw,
  Ban,
  Eye,
  ExternalLink,
  Calendar,
  Building,
  DollarSign,
  CheckCircle2,
  AlertTriangle,
  FileText,
} from 'lucide-react';
import type { Transaction, Company } from '../types';

interface TransactionsHubTabProps {
  transactions: Transaction[];
  companies: Company[];
  selectedCompanyFilter: string;
  onSelectCompanyFilter: (comp: string) => void;
  onCancelTransaction: (id: string) => Promise<void>;
  onSyncTransaction: (id: string) => Promise<void>;
  onOpenNewTx: () => void;
}

export const TransactionsHubTab: React.FC<TransactionsHubTabProps> = ({
  transactions,
  companies,
  selectedCompanyFilter,
  onSelectCompanyFilter,
  onCancelTransaction,
  onSyncTransaction,
  onOpenNewTx,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [inspectTx, setInspectTx] = useState<Transaction | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Filter transactions
  const filtered = transactions.filter((tx) => {
    if (selectedCompanyFilter !== 'ALL' && tx.company !== selectedCompanyFilter) return false;
    if (typeFilter !== 'ALL' && tx.transactionType !== typeFilter) return false;
    if (statusFilter !== 'ALL' && tx.status !== statusFilter) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      const matchDoc = tx.docNumber.toLowerCase().includes(q);
      const matchParty = tx.party.toLowerCase().includes(q);
      const matchLinked = tx.linkedDocNumber?.toLowerCase().includes(q);
      const matchCompany = tx.company.toLowerCase().includes(q);
      return matchDoc || matchParty || matchLinked || matchCompany;
    }
    return true;
  });

  const handleCancel = async (id: string) => {
    if (!window.confirm('Are you sure you want to cancel this transaction? If linked cancellation is enabled, the counterpart document in the linked company will also be automatically cancelled.')) {
      return;
    }
    setActionLoading(id);
    try {
      await onCancelTransaction(id);
    } catch (err: any) {
      alert(err.message || 'Cancellation failed');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSync = async (id: string) => {
    setActionLoading(id);
    try {
      await onSyncTransaction(id);
    } catch (err: any) {
      alert(err.message || 'Sync failed');
    } finally {
      setActionLoading(null);
    }
  };

  const getLinkedTx = (tx: Transaction) => {
    if (!tx.linkedTransactionId) return null;
    return transactions.find((t) => t.id === tx.linkedTransactionId);
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-base font-bold text-slate-900">Inter-Company Transactions Hub</h1>
            <p className="text-xs text-slate-500">
              Audit, trace, and synchronize documents paired across corporate entities.
            </p>
          </div>
          <button
            id="hub-new-transaction-btn"
            onClick={onOpenNewTx}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-colors cursor-pointer"
          >
            <GitMerge className="w-4 h-4" />
            <span>Post New Transaction</span>
          </button>
        </div>

        {/* Filters Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search doc#, party, linked..."
              className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Company Filter */}
          <div>
            <select
              aria-label="Filter by Company"
              value={selectedCompanyFilter}
              onChange={(e) => onSelectCompanyFilter(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500 font-medium text-slate-700"
            >
              <option value="ALL">All Companies</option>
              {companies.map((c) => (
                <option key={c.id} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Type Filter */}
          <div>
            <select
              aria-label="Filter by Transaction Type"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500 font-medium text-slate-700"
            >
              <option value="ALL">All Types</option>
              <option value="Sales Order">Sales Order</option>
              <option value="Purchase Order">Purchase Order</option>
              <option value="Sales Invoice">Sales Invoice</option>
              <option value="Purchase Invoice">Purchase Invoice</option>
              <option value="Journal Entry">Journal Entry</option>
              <option value="Payment Entry">Payment Entry</option>
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <select
              aria-label="Filter by Status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500 font-medium text-slate-700"
            >
              <option value="ALL">All Statuses</option>
              <option value="Submitted">Submitted</option>
              <option value="Draft">Draft</option>
              <option value="Pending Approval">Pending Approval</option>
              <option value="Cancelled">Cancelled</option>
            </select>
          </div>
        </div>
      </div>

      {/* Transactions List */}
      <div className="space-y-3">
        {filtered.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">
            <GitMerge className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-sm font-semibold text-slate-700">No transactions match your criteria</p>
            <p className="text-xs text-slate-400 mt-1">Try resetting your filters or post a new transaction.</p>
          </div>
        ) : (
          filtered.map((tx) => {
            const linked = getLinkedTx(tx);
            const isCancelled = tx.status === 'Cancelled';
            return (
              <div
                key={tx.id}
                className={`bg-white rounded-xl border p-4 shadow-xs transition-all ${
                  isCancelled ? 'border-rose-200 bg-rose-50/20' : 'border-slate-200 hover:border-indigo-200'
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  {/* Left doc info */}
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="font-mono font-bold text-sm text-slate-900">{tx.docNumber}</span>
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                        {tx.transactionType}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          tx.status === 'Submitted'
                            ? 'bg-emerald-100 text-emerald-800'
                            : tx.status === 'Pending Approval'
                            ? 'bg-amber-100 text-amber-800'
                            : tx.status === 'Cancelled'
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {tx.status}
                      </span>
                      {tx.requiresWorkflow && (
                        <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                          Workflow Rule
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-xs text-slate-500 flex-wrap">
                      <span className="flex items-center gap-1">
                        <Building className="w-3.5 h-3.5 text-slate-400" />
                        <strong className="text-slate-700">{tx.company}</strong>
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-slate-400" />
                        {tx.date}
                      </span>
                      <span>Party: {tx.party}</span>
                    </div>

                    {tx.notes && <p className="text-[11px] text-slate-400 italic">{tx.notes}</p>}
                  </div>

                  {/* Inter-Company Link Badge */}
                  <div className="lg:w-80 p-2.5 rounded-lg bg-slate-50 border border-slate-200/80 text-xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                      Inter-Company Linkage
                    </span>
                    {tx.linkedDocNumber ? (
                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-indigo-700 flex items-center gap-1">
                            <GitMerge className="w-3.5 h-3.5" />
                            {tx.linkedDocNumber}
                          </span>
                          <span
                            className={`text-[10px] font-semibold px-1.5 py-0.2 rounded ${
                              linked?.status === 'Cancelled'
                                ? 'bg-rose-100 text-rose-700'
                                : 'bg-emerald-100 text-emerald-700'
                            }`}
                          >
                            {linked?.status || 'Linked'}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600 truncate">
                          {tx.linkedCompany} ({tx.linkedTransactionType})
                        </p>
                      </div>
                    ) : (
                      <span className="text-slate-400 italic text-[11px]">Direct standalone document</span>
                    )}
                  </div>

                  {/* Amount & Actions */}
                  <div className="flex items-center justify-between lg:justify-end gap-3 shrink-0">
                    <div className="text-right">
                      <span className="text-xs text-slate-400 block">Total Value</span>
                      <span className="text-base font-bold text-slate-900">
                        ${tx.amount.toLocaleString()} {tx.currency}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => setInspectTx(tx)}
                        title="View Document Details"
                        className="p-2 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                      >
                        <Eye className="w-4 h-4" />
                      </button>

                      {tx.linkedTransactionId && !isCancelled && (
                        <button
                          onClick={() => handleSync(tx.id)}
                          disabled={actionLoading === tx.id}
                          title="Force Re-synchronization"
                          className="p-2 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                        >
                          <RefreshCw className={`w-4 h-4 ${actionLoading === tx.id ? 'animate-spin' : ''}`} />
                        </button>
                      )}

                      {!isCancelled && tx.status !== 'Pending Approval' && (
                        <button
                          onClick={() => handleCancel(tx.id)}
                          disabled={actionLoading === tx.id}
                          title="Linked Cancellation"
                          className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                        >
                          <Ban className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Inspect Document Modal (Side-by-Side Inter-Company Pair View) */}
      {inspectTx && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-3xl w-full p-6 animate-in fade-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-600" />
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">
                    Inter-Company Document Inspection
                  </h3>
                  <span className="text-xs text-slate-500 font-mono">{inspectTx.docNumber}</span>
                </div>
              </div>
              <button
                onClick={() => setInspectTx(null)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none cursor-pointer"
              >
                &times;
              </button>
            </div>

            {/* Side by Side Pair */}
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Primary Doc */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600">
                    Primary Voucher
                  </span>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      inspectTx.status === 'Submitted'
                        ? 'bg-emerald-100 text-emerald-800'
                        : inspectTx.status === 'Cancelled'
                        ? 'bg-rose-100 text-rose-800'
                        : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    {inspectTx.status}
                  </span>
                </div>
                <div className="text-xs space-y-1">
                  <div className="font-mono font-bold text-slate-900 text-sm">{inspectTx.docNumber}</div>
                  <div className="font-semibold text-slate-800">{inspectTx.company}</div>
                  <div className="text-slate-500">DocType: {inspectTx.transactionType}</div>
                  <div className="text-slate-500">Posting Date: {inspectTx.date}</div>
                  <div className="text-slate-500">Party: {inspectTx.party}</div>
                  <div className="font-bold text-slate-900 pt-1 text-sm">
                    ${inspectTx.amount.toLocaleString()} {inspectTx.currency}
                  </div>
                </div>
              </div>

              {/* Linked Doc */}
              {(() => {
                const linked = getLinkedTx(inspectTx);
                return linked ? (
                  <div className="p-4 rounded-xl bg-blue-50/50 border border-blue-200 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700">
                        Linked Counterpart Document
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          linked.status === 'Submitted'
                            ? 'bg-emerald-100 text-emerald-800'
                            : linked.status === 'Cancelled'
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-slate-200 text-slate-700'
                        }`}
                      >
                        {linked.status}
                      </span>
                    </div>
                    <div className="text-xs space-y-1">
                      <div className="font-mono font-bold text-slate-900 text-sm">{linked.docNumber}</div>
                      <div className="font-semibold text-slate-800">{linked.company}</div>
                      <div className="text-slate-500">DocType: {linked.transactionType}</div>
                      <div className="text-slate-500">Posting Date: {linked.date}</div>
                      <div className="text-slate-500">Party: {linked.party}</div>
                      <div className="font-bold text-slate-900 pt-1 text-sm">
                        ${linked.amount.toLocaleString()} {linked.currency}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-xl border border-dashed border-slate-200 flex flex-col items-center justify-center text-center text-slate-400 text-xs">
                    <AlertTriangle className="w-6 h-6 mb-1 text-amber-500" />
                    <span>No linked document associated.</span>
                  </div>
                );
              })()}
            </div>

            {/* Items Breakdown */}
            <div className="mt-5">
              <h4 className="text-xs font-bold text-slate-900 mb-2">Itemized Accounting Schedule</h4>
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-2 px-3">Item Code</th>
                      <th className="py-2 px-3">Description</th>
                      <th className="py-2 px-3 text-right">Qty</th>
                      <th className="py-2 px-3 text-right">Rate</th>
                      <th className="py-2 px-3 text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {inspectTx.items.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-3 px-3 text-center text-slate-400">
                          Direct GL entry / No sub-items
                        </td>
                      </tr>
                    ) : (
                      inspectTx.items.map((item) => (
                        <tr key={item.id}>
                          <td className="py-2 px-3 font-mono font-medium text-slate-800">{item.itemCode}</td>
                          <td className="py-2 px-3 text-slate-600">{item.description}</td>
                          <td className="py-2 px-3 text-right text-slate-700">{item.qty}</td>
                          <td className="py-2 px-3 text-right text-slate-700">${item.rate.toLocaleString()}</td>
                          <td className="py-2 px-3 text-right font-semibold text-slate-900">
                            ${item.amount.toLocaleString()}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-5 flex justify-end">
              <button
                onClick={() => setInspectTx(null)}
                className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
