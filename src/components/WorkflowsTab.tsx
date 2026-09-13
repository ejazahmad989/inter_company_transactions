import React, { useState } from 'react';
import {
  FileCheck,
  CheckCircle,
  XCircle,
  Clock,
  Shield,
  MessageSquare,
  AlertCircle,
  Building,
} from 'lucide-react';
import type { WorkflowRule, ApprovalRequest } from '../types';

interface WorkflowsTabProps {
  workflows: WorkflowRule[];
  approvalRequests: ApprovalRequest[];
  onActionRequest: (id: string, action: 'Approved' | 'Rejected', comments: string) => Promise<void>;
}

export const WorkflowsTab: React.FC<WorkflowsTabProps> = ({
  workflows,
  approvalRequests,
  onActionRequest,
}) => {
  const [selectedReq, setSelectedReq] = useState<ApprovalRequest | null>(null);
  const [actionType, setActionType] = useState<'Approved' | 'Rejected'>('Approved');
  const [comments, setComments] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const handleOpenAction = (req: ApprovalRequest, action: 'Approved' | 'Rejected') => {
    setSelectedReq(req);
    setActionType(action);
    setComments(action === 'Approved' ? 'Terms reviewed and approved.' : 'Rejected due to budget variance.');
  };

  const handleConfirmAction = async () => {
    if (!selectedReq) return;
    setIsProcessing(true);
    try {
      await onActionRequest(selectedReq.id, actionType, comments);
      setSelectedReq(null);
    } catch (err: any) {
      alert(err.message || 'Action failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const pendingRequests = approvalRequests.filter((r) => r.status === 'Pending');
  const resolvedRequests = approvalRequests.filter((r) => r.status !== 'Pending');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <h1 className="text-base font-bold text-slate-900">Inter-Company Multi-Level Approval Workflows</h1>
        <p className="text-xs text-slate-500">
          Governs high-value cross-border transactions requiring corporate treasury and executive controller sign-offs.
        </p>
      </div>

      {/* Workflow Rule Definitions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {workflows.map((wf) => (
          <div key={wf.id} className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-900 text-xs">{wf.name}</span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
                {wf.approvalLevels} Approval Tier{wf.approvalLevels > 1 ? 's' : ''}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
              <div>
                <span className="text-[10px] text-slate-400 block font-semibold">Source Route</span>
                <span className="font-medium text-slate-800">{wf.sourceCompany.split(' ')[0]} → {wf.targetCompany.split(' ')[0]}</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block font-semibold">Trigger Threshold</span>
                <span className="font-bold text-slate-900">&ge; ${wf.minAmount.toLocaleString()} USD</span>
              </div>
              <div className="col-span-2 pt-1 border-t border-slate-200/60">
                <span className="text-[10px] text-slate-400 block font-semibold">Authorized Signers</span>
                <span className="text-slate-700">{wf.approverRoles.join(', ')}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Approval Queue */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Clock className="w-4 h-4 text-amber-600" />
            <span>Pending Review Queue ({pendingRequests.length})</span>
          </h2>
        </div>

        {pendingRequests.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500">
            <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
            <p className="text-sm font-semibold text-slate-800">All workflow queues are clear</p>
            <p className="text-xs text-slate-400 mt-0.5">Transactions under threshold limits post immediately.</p>
          </div>
        ) : (
          pendingRequests.map((req) => (
            <div key={req.id} className="bg-white rounded-xl border border-amber-200 p-4 shadow-xs space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-xs text-slate-900">{req.id}</span>
                  <span className="text-xs font-bold text-indigo-700">{req.documentNumber}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                    Tier {req.currentLevel} of {req.requiredLevels} Pending
                  </span>
                </div>
                <span className="text-xs font-bold text-slate-900">
                  ${req.amount.toLocaleString()} {req.currency}
                </span>
              </div>

              <div className="text-xs text-slate-600 grid grid-cols-1 sm:grid-cols-3 gap-2">
                <div>
                  <span className="text-[10px] text-slate-400 block">Workflow</span>
                  <span className="font-medium text-slate-800">{req.workflowName}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block">Source & Target</span>
                  <span className="font-medium text-slate-800">{req.sourceCompany} &rarr; {req.targetCompany}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block">Initiated By</span>
                  <span className="text-slate-700">{req.requestedBy}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  onClick={() => handleOpenAction(req, 'Rejected')}
                  className="px-3 py-1.5 rounded-lg border border-rose-200 text-rose-700 hover:bg-rose-50 text-xs font-semibold cursor-pointer"
                >
                  Reject
                </button>
                <button
                  onClick={() => handleOpenAction(req, 'Approved')}
                  className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold cursor-pointer"
                >
                  Approve (Tier {req.currentLevel})
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* History Log */}
      {resolvedRequests.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Resolved Approval Audit History
          </h3>
          <div className="divide-y divide-slate-100">
            {resolvedRequests.map((req) => (
              <div key={req.id} className="py-3 text-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-slate-900">{req.documentNumber}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        req.status === 'Approved' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
                      }`}
                    >
                      {req.status}
                    </span>
                  </div>
                  <span className="font-semibold text-slate-900">${req.amount.toLocaleString()} {req.currency}</span>
                </div>
                <div className="space-y-1 pl-3 border-l-2 border-slate-200 text-[11px] text-slate-500">
                  {req.history.map((h, i) => (
                    <div key={i}>
                      Level {h.level} {h.action} by <strong className="text-slate-700">{h.approver}</strong> on {new Date(h.date).toLocaleDateString()} &mdash; <em>"{h.comments}"</em>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Confirmation Modal */}
      {selectedReq && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            <h3 className="font-bold text-slate-900 text-sm mb-1">
              Confirm {actionType === 'Approved' ? 'Approval' : 'Rejection'}
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Document: <span className="font-mono font-bold text-slate-800">{selectedReq.documentNumber}</span> (${selectedReq.amount.toLocaleString()} {selectedReq.currency})
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Audit Comments</label>
                <textarea
                  rows={3}
                  value={comments}
                  onChange={(e) => setComments(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSelectedReq(null)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmAction}
                  disabled={isProcessing}
                  className={`px-4 py-1.5 rounded-lg text-white font-semibold cursor-pointer disabled:opacity-50 ${
                    actionType === 'Approved' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'
                  }`}
                >
                  {isProcessing ? 'Recording...' : `Confirm ${actionType}`}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
