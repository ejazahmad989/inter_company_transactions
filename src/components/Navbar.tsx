import React from 'react';
import {
  ArrowLeftRight,
  GitMerge,
  FileCheck,
  CalendarClock,
  ShieldCheck,
  LayoutDashboard,
  Plus,
  Building2,
  Boxes,
} from 'lucide-react';
import type { Company } from '../types';

interface NavbarProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  companies: Company[];
  selectedCompany: string;
  onCompanyChange: (company: string) => void;
  onOpenNewTx: () => void;
  pendingApprovalsCount: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onTabChange,
  companies,
  selectedCompany,
  onCompanyChange,
  onOpenNewTx,
  pendingApprovalsCount,
}) => {
  const tabs = [
    { id: 'frappe-app', label: 'ERPNext App (Rollback)', icon: Boxes },
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'mappings', label: 'Transaction Mappings', icon: ArrowLeftRight },
    { id: 'transactions', label: 'Transactions Hub', icon: GitMerge },
    {
      id: 'workflows',
      label: 'Approvals Queue',
      icon: FileCheck,
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined,
    },
    { id: 'date-control', label: 'Date Control', icon: CalendarClock },
    { id: 'role-replication', label: 'Role Replication', icon: ShieldCheck },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand & Context */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs">
                <ArrowLeftRight className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-slate-900 text-lg tracking-tight">
                    Inter-Company
                  </span>
                  <span className="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                    ERPNext Suite
                  </span>
                </div>
                <p className="text-xs text-slate-500">Multi-Entity Synchronization & Controls</p>
              </div>
            </div>

            {/* Company Context Filter */}
            <div className="hidden lg:flex items-center gap-2 pl-4 border-l border-slate-200">
              <Building2 className="w-4 h-4 text-slate-400" />
              <select
                id="company-context-select"
                aria-label="Filter by Company"
                value={selectedCompany}
                onChange={(e) => onCompanyChange(e.target.value)}
                className="text-xs font-medium text-slate-700 bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              >
                <option value="ALL">All Consolidated Entities</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.name}>
                    {c.name} ({c.code})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              id="new-transaction-nav-btn"
              onClick={onOpenNewTx}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-xs transition-colors cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Create Transaction</span>
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav className="flex space-x-1 overflow-x-auto py-2 border-t border-slate-100 scrollbar-none">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                id={`tab-btn-${tab.id}`}
                onClick={() => onTabChange(tab.id)}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md whitespace-nowrap transition-colors cursor-pointer ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
                {tab.badge !== undefined && (
                  <span className="ml-1 px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-amber-500 text-white">
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};
