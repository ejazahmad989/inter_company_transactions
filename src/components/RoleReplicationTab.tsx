import React, { useState } from 'react';
import { ShieldCheck, RefreshCw, Users, Building2, CheckCircle2, HelpCircle } from 'lucide-react';
import type { RoleReplication } from '../types';

interface RoleReplicationTabProps {
  roleReplications: RoleReplication[];
  onSyncRoleReplication: (id: string) => Promise<void>;
}

export const RoleReplicationTab: React.FC<RoleReplicationTabProps> = ({
  roleReplications,
  onSyncRoleReplication,
}) => {
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const handleSync = async (id: string) => {
    setSyncingId(id);
    try {
      await onSyncRoleReplication(id);
    } catch (err: any) {
      alert(err.message || 'Sync failed');
    } finally {
      setSyncingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <h1 className="text-base font-bold text-slate-900">Inter-Company Role Replication</h1>
        <p className="text-xs text-slate-500">
          Propagate accounting, auditing, and procurement permissions across sister corporations automatically.
        </p>
      </div>

      {/* Explainer */}
      <div className="bg-blue-50/70 border border-blue-200 rounded-xl p-4 text-xs text-blue-950 flex items-start gap-3">
        <HelpCircle className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold">ERPNext Role Replication Engine:</span>
          <p className="text-slate-700 leading-relaxed">
            In complex group structures, managing identical permissions across multiple corporate site instances is error-prone. Role Replication ensures designated roles (like <em>Intercompany Auditor</em> or <em>Compliance Officer</em>) are automatically mirrored and synchronized with target subsidiaries.
          </p>
        </div>
      </div>

      {/* Rules list */}
      <div className="space-y-4">
        {roleReplications.map((rr) => (
          <div key={rr.id} className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-700 flex items-center justify-center font-bold text-xs">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <span className="font-mono font-bold text-xs text-slate-900">{rr.id}</span>
                  <div className="text-xs font-semibold text-slate-800">
                    Source: <strong className="text-indigo-700">{rr.sourceCompany}</strong>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {rr.status}
                </span>

                <button
                  id={`sync-roles-btn-${rr.id}`}
                  onClick={() => handleSync(rr.id)}
                  disabled={syncingId === rr.id}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${syncingId === rr.id ? 'animate-spin' : ''}`} />
                  <span>{syncingId === rr.id ? 'Syncing...' : 'Sync Roles Now'}</span>
                </button>
              </div>
            </div>

            {/* Target Entities & Roles */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-2">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">
                  Replicated Roles
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {rr.roles.map((role, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 rounded bg-white text-slate-800 border border-slate-200 font-medium"
                    >
                      {role}
                    </span>
                  ))}
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-2">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">
                  Target Subsidiary Entities
                </span>
                <div className="space-y-1">
                  {rr.targetCompanies.map((tc, idx) => (
                    <div key={idx} className="flex items-center gap-1.5 text-slate-700">
                      <Building2 className="w-3.5 h-3.5 text-slate-400" />
                      <span>{tc}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-2 border-t border-slate-100">
              <span className="flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-slate-400" />
                {rr.syncedUsersCount} active users mapped across subsidiaries
              </span>
              <span>Last Synchronized: {new Date(rr.lastSynced).toLocaleString()}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
