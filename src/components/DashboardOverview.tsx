import React from 'react';
import {
  GitMerge,
  ArrowRight,
  ShieldCheck,
  CalendarCheck,
  Building,
  CheckCircle2,
  Clock,
  ArrowLeftRight,
  PlusCircle,
  FileSpreadsheet,
} from 'lucide-react';
import type { SystemStats, Company, TransactionMapping, Transaction } from '../types';

interface DashboardOverviewProps {
  stats: SystemStats | null;
  companies: Company[];
  mappings: TransactionMapping[];
  recentTransactions: Transaction[];
  onNavigateTab: (tab: string) => void;
  onOpenNewTx: () => void;
}

export const DashboardOverview: React.FC<DashboardOverviewProps> = ({
  stats,
  companies,
  mappings,
  recentTransactions,
  onNavigateTab,
  onOpenNewTx,
}) => {
  return (
    <div className="space-y-6">
      {/* Top Banner with Quick Actions */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-xl p-6 text-white shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-400/30 mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            Automated Parity Active
          </span>
          <h1 className="text-xl font-bold tracking-tight">Inter-Company Multi-Entity Automation</h1>
          <p className="text-sm text-slate-300 max-w-2xl mt-1">
            Synchronize sales orders, purchase vouchers, invoices, and journal entries seamlessly across {companies.length} corporate legal entities with strict date validation and multi-tier approval workflows.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            id="overview-new-tx-btn"
            onClick={onOpenNewTx}
            className="inline-flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg bg-indigo-500 hover:bg-indigo-400 text-white shadow-xs transition-colors cursor-pointer"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Simulate Inter-Company Post</span>
          </button>
          <button
            id="overview-view-mappings-btn"
            onClick={() => onNavigateTab('mappings')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2.5 text-xs font-medium rounded-lg bg-white/10 hover:bg-white/15 text-white border border-white/10 transition-colors cursor-pointer"
          >
            <span>View Mappings</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Active Mappings</span>
            <span className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <ArrowLeftRight className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-slate-900">{stats?.activeMappingsCount ?? 0}</span>
            <span className="text-xs text-slate-500 ml-2">rule sets</span>
          </div>
          <p className="text-[11px] text-emerald-600 mt-2 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            100% two-way bidirectional
          </p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Linked Transactions</span>
            <span className="p-2 rounded-lg bg-blue-50 text-blue-600">
              <GitMerge className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-slate-900">{stats?.linkedTransactionsCount ?? 0}</span>
            <span className="text-xs text-slate-500 ml-2">of {stats?.totalTransactions ?? 0} total</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-2">
            Auto-generated cross-entity pairs
          </p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Pending Approvals</span>
            <span className="p-2 rounded-lg bg-amber-50 text-amber-600">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-slate-900">{stats?.pendingApprovalsCount ?? 0}</span>
            <span className="text-xs text-slate-500 ml-2">awaiting sign-off</span>
          </div>
          <p className="text-[11px] text-amber-600 mt-2">
            Exceeding workflow amount limit
          </p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Consolidated Intercompany Volume</span>
            <span className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
              <FileSpreadsheet className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-slate-900">
              ${(stats?.totalVolumeUSD ?? 0).toLocaleString()}
            </span>
            <span className="text-xs text-slate-500 ml-2">USD</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-2">
            Eliminates intercompany double-entry
          </p>
        </div>
      </div>

      {/* Network Topology & Active Mappings */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Entity Topology */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Active Inter-Company Linkage Matrix</h2>
              <p className="text-xs text-slate-500">Configured transaction pipelines between corporate entities</p>
            </div>
            <button
              onClick={() => onNavigateTab('mappings')}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1 cursor-pointer"
            >
              Configure <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="space-y-3">
            {mappings.map((m) => (
              <div
                key={m.id}
                className="p-3.5 rounded-lg border border-slate-200 hover:border-indigo-200 transition-colors bg-slate-50/50"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900">{m.name}</span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      m.enabled
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    {m.enabled ? 'Active Pipeline' : 'Disabled'}
                  </span>
                </div>

                <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 items-center gap-2 text-xs">
                  {/* Source */}
                  <div className="bg-white p-2.5 rounded-md border border-slate-200">
                    <span className="text-[10px] text-slate-500 uppercase font-semibold block">Source Entity</span>
                    <span className="font-semibold text-slate-900 block truncate">{m.mainCompany}</span>
                    <span className="inline-block mt-1 text-[11px] font-medium text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded">
                      {m.mainTransactionType}
                    </span>
                  </div>

                  {/* Flow Arrow */}
                  <div className="flex flex-col items-center justify-center text-slate-400 py-1">
                    <div className="flex items-center gap-1">
                      <span className="text-[10px] text-indigo-600 font-semibold">Auto-mirrors</span>
                      <ArrowRight className="w-4 h-4 text-indigo-600" />
                    </div>
                    <span className="text-[10px] text-slate-500">
                      {m.autoSubmit ? 'Direct Submit' : 'Save as Draft'}
                    </span>
                  </div>

                  {/* Target */}
                  <div className="bg-white p-2.5 rounded-md border border-slate-200">
                    <span className="text-[10px] text-slate-500 uppercase font-semibold block">Target Entity</span>
                    <span className="font-semibold text-slate-900 block truncate">{m.otherCompany}</span>
                    <span className="inline-block mt-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
                      {m.otherTransactionType}
                    </span>
                  </div>
                </div>

                <div className="mt-2.5 flex items-center justify-between text-[11px] text-slate-500 border-t border-slate-200/60 pt-2">
                  <span>Linked Party: <strong className="text-slate-700">{m.mainParty}</strong></span>
                  <span className="flex items-center gap-1.5">
                    {m.allowLinkedCancellation && (
                      <span className="text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                        ✓ Linked Cancellation
                      </span>
                    )}
                    {m.syncStatusUpdates && (
                      <span className="text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                        ✓ 2-Way Sync
                      </span>
                    )}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Corporate Legal Entities */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
            <h2 className="text-sm font-bold text-slate-900 mb-1">Registered Companies</h2>
            <p className="text-xs text-slate-500 mb-3">Multi-company ERP setup</p>

            <div className="space-y-2.5">
              {companies.map((c) => (
                <div key={c.id} className="p-2.5 rounded-lg border border-slate-100 bg-slate-50 flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-md bg-white border border-slate-200 flex items-center justify-center text-slate-700 font-bold text-xs">
                      {c.code}
                    </div>
                    <div>
                      <span className="text-xs font-semibold text-slate-900 block truncate max-w-[140px]">
                        {c.name}
                      </span>
                      <span className="text-[10px] text-slate-500">{c.country} • {c.currency}</span>
                    </div>
                  </div>
                  {c.isHolding ? (
                    <span className="text-[10px] font-bold text-indigo-700 bg-indigo-100 px-2 py-0.5 rounded-full">
                      Parent HQ
                    </span>
                  ) : (
                    <span className="text-[10px] font-medium text-slate-600 bg-slate-200 px-2 py-0.5 rounded-full">
                      Subsidiary
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* ERP Control Systems Status */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
            <h2 className="text-sm font-bold text-slate-900 mb-2">Policy Enforcement</h2>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <CalendarCheck className="w-4 h-4 text-emerald-600" />
                  Date Control Hooks
                </span>
                <span className="text-emerald-700 font-semibold text-[11px] bg-emerald-50 px-2 py-0.5 rounded">
                  Enforced
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  Role Replication
                </span>
                <span className="text-emerald-700 font-semibold text-[11px] bg-emerald-50 px-2 py-0.5 rounded">
                  In Sync
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <Building className="w-4 h-4 text-indigo-600" />
                  Cross-Entity Tax & FX
                </span>
                <span className="text-indigo-700 font-semibold text-[11px] bg-indigo-50 px-2 py-0.5 rounded">
                  Active
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Recent Inter-Company Transactions</h2>
            <p className="text-xs text-slate-500">Live feed of transactions generated or linked across companies</p>
          </div>
          <button
            onClick={() => onNavigateTab('transactions')}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1 cursor-pointer"
          >
            All Transactions <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 text-slate-700 uppercase font-semibold text-[10px] border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3">Document #</th>
                <th className="py-2.5 px-3">Company</th>
                <th className="py-2.5 px-3">Type</th>
                <th className="py-2.5 px-3">Linked Document</th>
                <th className="py-2.5 px-3">Amount</th>
                <th className="py-2.5 px-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recentTransactions.slice(0, 5).map((tx) => (
                <tr key={tx.id} className="hover:bg-slate-50 transition-colors">
                  <td className="py-2.5 px-3 font-mono font-bold text-slate-900">{tx.docNumber}</td>
                  <td className="py-2.5 px-3 font-medium text-slate-800">{tx.company}</td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700">
                      {tx.transactionType}
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    {tx.linkedDocNumber ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-mono text-[11px] font-medium">
                        <GitMerge className="w-3 h-3" />
                        {tx.linkedDocNumber} ({tx.linkedCompany})
                      </span>
                    ) : (
                      <span className="text-slate-400 italic">None</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-slate-900">
                    ${tx.amount.toLocaleString()} {tx.currency}
                  </td>
                  <td className="py-2.5 px-3">
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
