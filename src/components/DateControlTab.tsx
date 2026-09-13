import React, { useState } from 'react';
import {
  CalendarClock,
  ShieldCheck,
  AlertOctagon,
  CheckCircle2,
  Plus,
  Trash2,
  HelpCircle,
} from 'lucide-react';
import type { Company, DateControlWhitelist } from '../types';

interface DateControlTabProps {
  dateControls: DateControlWhitelist[];
  companies: Company[];
  onCreateDateControl: (data: Partial<DateControlWhitelist>) => Promise<void>;
  onDeleteDateControl: (id: string) => Promise<void>;
}

export const DateControlTab: React.FC<DateControlTabProps> = ({
  dateControls,
  companies,
  onCreateDateControl,
  onDeleteDateControl,
}) => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [company, setCompany] = useState(companies[0]?.name || '');
  const [user, setUser] = useState('');
  const [documentType, setDocumentType] = useState('All');
  const [allowedBackdateDays, setAllowedBackdateDays] = useState(30);
  const [allowedFutureDateDays, setAllowedFutureDateDays] = useState(14);
  const [validFrom, setValidFrom] = useState('2025-01-01');
  const [validUpto, setValidUpto] = useState('2025-12-31');

  // Sandbox Validator state
  const [testCompany, setTestCompany] = useState(companies[0]?.name || '');
  const [testDate, setTestDate] = useState(new Date().toISOString().split('T')[0]);
  const [testUser, setTestUser] = useState('finance.lead@apexglobal.com');
  const [testResult, setTestResult] = useState<{ allowed: boolean; message: string } | null>(null);

  const handleTestValidate = () => {
    const today = new Date();
    const targetDate = new Date(testDate);
    const diffDays = Math.round((today.getTime() - targetDate.getTime()) / (1000 * 3600 * 24));

    if (diffDays <= 3 && diffDays >= -7) {
      setTestResult({
        allowed: true,
        message: `Standard posting policy allowed (${diffDays >= 0 ? `${diffDays} days backdated` : `${Math.abs(diffDays)} days future`}). Within default 3-day grace window.`,
      });
      return;
    }

    if (diffDays > 3) {
      const match = dateControls.find(
        (dc) =>
          dc.company === testCompany &&
          dc.status === 'Active' &&
          (dc.user === testUser || dc.user === 'All Users') &&
          diffDays <= dc.allowedBackdateDays
      );

      if (match) {
        setTestResult({
          allowed: true,
          message: `Backdating Approved! Transaction is backdated by ${diffDays} days, covered by active Whitelist [${match.id}] (allows up to ${match.allowedBackdateDays} days for ${match.user}).`,
        });
      } else {
        setTestResult({
          allowed: false,
          message: `Posting Blocked! Transaction is backdated by ${diffDays} days. Default limit is 3 days, and no active whitelist grant was found for ${testCompany} and user ${testUser}.`,
        });
      }
    } else {
      setTestResult({
        allowed: false,
        message: `Future date exceeds standard posting window (${Math.abs(diffDays)} days in advance).`,
      });
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) {
      alert('Please specify a user email or "All Users"');
      return;
    }
    await onCreateDateControl({
      company,
      user,
      documentType,
      allowedBackdateDays: Number(allowedBackdateDays),
      allowedFutureDateDays: Number(allowedFutureDateDays),
      validFrom,
      validUpto,
      status: 'Active',
    });
    setShowAddModal(false);
    setUser('');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <h1 className="text-base font-bold text-slate-900">Inter-Company Date Control & Whitelisting</h1>
          <p className="text-xs text-slate-500">
            Prevents fiscal period distortion by enforcing strict backdate and future posting limits across legal entities.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>New Whitelist Exception</span>
        </button>
      </div>

      {/* Date Policy Explainer */}
      <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-4 text-xs text-amber-950 flex items-start gap-3">
        <HelpCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold">ERPNext Date Validator Hook:</span>
          <p className="text-slate-700 leading-relaxed">
            Standard transactions are restricted to posting dates within <strong>3 days</strong> of the current date. For retrospective intercompany reconciliations, fiscal period audit corrections, or cross-border shipping lags, explicit <strong>Backdate Whitelist Permissions</strong> can be provisioned by entity and role.
          </p>
        </div>
      </div>

      {/* Interactive Date Validator Sandbox */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="flex items-center gap-2 mb-3">
          <CalendarClock className="w-4 h-4 text-indigo-600" />
          <h2 className="text-sm font-bold text-slate-900">Live Date Validator Sandbox</h2>
        </div>
        <p className="text-xs text-slate-500 mb-4">
          Test any transaction posting date to verify if it passes company policy or triggers an unauthorized backdating block.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs mb-4">
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Company Entity</label>
            <select
              value={testCompany}
              onChange={(e) => setTestCompany(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-slate-50 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            >
              {companies.map((c) => (
                <option key={c.id} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Test Posting Date</label>
            <input
              type="date"
              value={testDate}
              onChange={(e) => setTestDate(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-slate-50 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">User Identity</label>
            <input
              type="email"
              value={testUser}
              onChange={(e) => setTestUser(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-slate-50 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <button
          onClick={handleTestValidate}
          className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold cursor-pointer"
        >
          Run Date Control Hook
        </button>

        {testResult && (
          <div
            className={`mt-4 p-3.5 rounded-lg border text-xs flex items-start gap-2.5 ${
              testResult.allowed
                ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                : 'bg-rose-50 border-rose-200 text-rose-900'
            }`}
          >
            {testResult.allowed ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <AlertOctagon className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            )}
            <div>
              <span className="font-bold block mb-0.5">
                {testResult.allowed ? 'Policy Compliant' : 'Date Control Violation Detected'}
              </span>
              <p className="text-slate-700">{testResult.message}</p>
            </div>
          </div>
        )}
      </div>

      {/* Whitelist Rules Table */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <h2 className="text-sm font-bold text-slate-900 mb-3">Active Backdate Whitelists</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 text-slate-700 uppercase font-semibold text-[10px] border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3">Rule ID</th>
                <th className="py-2.5 px-3">Company</th>
                <th className="py-2.5 px-3">Authorized User</th>
                <th className="py-2.5 px-3">Document Type</th>
                <th className="py-2.5 px-3">Allowed Backdate</th>
                <th className="py-2.5 px-3">Validity Period</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {dateControls.map((dc) => (
                <tr key={dc.id} className="hover:bg-slate-50 transition-colors">
                  <td className="py-2.5 px-3 font-mono font-bold text-slate-900">{dc.id}</td>
                  <td className="py-2.5 px-3 font-medium text-slate-800">{dc.company}</td>
                  <td className="py-2.5 px-3 text-slate-700">{dc.user}</td>
                  <td className="py-2.5 px-3">
                    <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-[11px]">
                      {dc.documentType}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-slate-900">
                    Up to {dc.allowedBackdateDays} days
                  </td>
                  <td className="py-2.5 px-3 text-slate-500">
                    {dc.validFrom} to {dc.validUpto}
                  </td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                      {dc.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <button
                      onClick={() => onDeleteDateControl(dc.id)}
                      className="text-slate-400 hover:text-rose-600 p-1 rounded transition-colors cursor-pointer"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* New Whitelist Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            <h3 className="font-bold text-slate-900 text-sm mb-3">Add Backdate Whitelist Permission</h3>
            <form onSubmit={handleCreate} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Company</label>
                <select
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
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
                <label className="block font-semibold text-slate-700 mb-1">User Email or "All Users"</label>
                <input
                  type="text"
                  value={user}
                  onChange={(e) => setUser(e.target.value)}
                  placeholder="e.g. auditor@company.com"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Document Type</label>
                <select
                  value={documentType}
                  onChange={(e) => setDocumentType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="All">All Transactions</option>
                  <option value="Sales Order">Sales Order</option>
                  <option value="Purchase Order">Purchase Order</option>
                  <option value="Sales Invoice">Sales Invoice</option>
                  <option value="Purchase Invoice">Purchase Invoice</option>
                  <option value="Journal Entry">Journal Entry</option>
                  <option value="Payment Entry">Payment Entry</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Allowed Backdate Days</label>
                  <input
                    type="number"
                    value={allowedBackdateDays}
                    onChange={(e) => setAllowedBackdateDays(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Future Days</label>
                  <input
                    type="number"
                    value={allowedFutureDateDays}
                    onChange={(e) => setAllowedFutureDateDays(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Valid From</label>
                  <input
                    type="date"
                    value={validFrom}
                    onChange={(e) => setValidFrom(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Valid Upto</label>
                  <input
                    type="date"
                    value={validUpto}
                    onChange={(e) => setValidUpto(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold cursor-pointer"
                >
                  Save Whitelist
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
