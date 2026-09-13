import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { DashboardOverview } from './components/DashboardOverview';
import { TransactionMappingsTab } from './components/TransactionMappingsTab';
import { TransactionsHubTab } from './components/TransactionsHubTab';
import { WorkflowsTab } from './components/WorkflowsTab';
import { DateControlTab } from './components/DateControlTab';
import { RoleReplicationTab } from './components/RoleReplicationTab';
import { FrappeAppStructureTab } from './components/FrappeAppStructureTab';
import { NewTransactionModal } from './components/NewTransactionModal';
import { api } from './lib/api';
import type {
  Company,
  TransactionMapping,
  Transaction,
  WorkflowRule,
  ApprovalRequest,
  DateControlWhitelist,
  RoleReplication,
  SystemStats,
} from './types';
import { CheckCircle2, AlertCircle, X } from 'lucide-react';

export function App() {
  const [currentTab, setCurrentTab] = useState('frappe-app');
  const [selectedCompanyFilter, setSelectedCompanyFilter] = useState('ALL');
  const [isNewTxModalOpen, setIsNewTxModalOpen] = useState(false);

  // App state
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [mappings, setMappings] = useState<TransactionMapping[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowRule[]>([]);
  const [approvalRequests, setApprovalRequests] = useState<ApprovalRequest[]>([]);
  const [dateControls, setDateControls] = useState<DateControlWhitelist[]>([]);
  const [roleReplications, setRoleReplications] = useState<RoleReplication[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Toast notification
  const [toast, setToast] = useState<{ type: 'success' | 'error' | 'info'; title: string; message: string } | null>(null);

  const showToast = (title: string, message: string, type: 'success' | 'error' | 'info' = 'success') => {
    setToast({ title, message, type });
    setTimeout(() => {
      setToast(null);
    }, 6000);
  };

  // Initial load
  const loadAllData = async () => {
    try {
      setIsLoading(true);
      const [
        statsData,
        companiesData,
        mappingsData,
        transactionsData,
        workflowsData,
        approvalsData,
        dateControlsData,
        rolesData,
      ] = await Promise.all([
        api.getStats(),
        api.getCompanies(),
        api.getMappings(),
        api.getTransactions(),
        api.getWorkflows(),
        api.getApprovalRequests(),
        api.getDateControls(),
        api.getRoleReplications(),
      ]);

      setStats(statsData);
      setCompanies(companiesData);
      setMappings(mappingsData);
      setTransactions(transactionsData);
      setWorkflows(workflowsData);
      setApprovalRequests(approvalsData);
      setDateControls(dateControlsData);
      setRoleReplications(rolesData);
    } catch (err: any) {
      showToast('Error Loading Data', err.message || 'Could not connect to API server', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

  // Handlers for Mappings
  const handleToggleMapping = async (id: string) => {
    try {
      const updated = await api.toggleMapping(id);
      setMappings((prev) => prev.map((m) => (m.id === id ? updated : m)));
      const updatedStats = await api.getStats();
      setStats(updatedStats);
      showToast(
        updated.enabled ? 'Mapping Activated' : 'Mapping Deactivated',
        `${updated.name} is now ${updated.enabled ? 'active' : 'inactive'}.`
      );
    } catch (err: any) {
      showToast('Action Failed', err.message, 'error');
    }
  };

  const handleCreateMapping = async (mapping: Partial<TransactionMapping>) => {
    const created = await api.createMapping(mapping);
    setMappings((prev) => [created, ...prev]);
    const updatedStats = await api.getStats();
    setStats(updatedStats);
    showToast('Mapping Created', `Configured inter-company route [${created.id}].`);
  };

  const handleDeleteMapping = async (id: string) => {
    if (!window.confirm('Delete this mapping configuration?')) return;
    try {
      await api.deleteMapping(id);
      setMappings((prev) => prev.filter((m) => m.id !== id));
      const updatedStats = await api.getStats();
      setStats(updatedStats);
      showToast('Mapping Deleted', 'Inter-company rule removed.');
    } catch (err: any) {
      showToast('Delete Failed', err.message, 'error');
    }
  };

  // Handlers for Transactions
  const handleCreateTransaction = async (data: any) => {
    const result = await api.createTransaction(data);
    await loadAllData();
    if (result.linked) {
      showToast(
        'Inter-Company Pair Created',
        `Generated ${result.primary.docNumber} in ${result.primary.company} and automatically created mirrored ${result.linked.docNumber} in ${result.linked.company}!`,
        'success'
      );
    } else {
      showToast(
        'Transaction Posted',
        `Created ${result.primary.docNumber} in ${result.primary.company}.`,
        'info'
      );
    }
    if (result.workflowTriggered) {
      showToast(
        'Approval Workflow Initiated',
        `Document amount exceeds limit. Sent to executive sign-off queue.`,
        'info'
      );
    }
    return result;
  };

  const handleCancelTransaction = async (id: string) => {
    const result = await api.cancelTransaction(id);
    await loadAllData();
    if (result.cancelledLinkedDoc) {
      showToast(
        'Linked Cancellation Complete',
        `Cancelled ${result.cancelledDoc} and automatically cancelled counterpart ${result.cancelledLinkedDoc}!`,
        'info'
      );
    } else {
      showToast('Document Cancelled', `Cancelled ${result.cancelledDoc}.`, 'info');
    }
  };

  const handleSyncTransaction = async (id: string) => {
    const result = await api.syncTransaction(id);
    await loadAllData();
    showToast('Parity Synchronized', result.message, 'success');
  };

  // Handlers for Workflows
  const handleActionWorkflowRequest = async (
    id: string,
    action: 'Approved' | 'Rejected',
    comments: string
  ) => {
    const updated = await api.actionApprovalRequest(id, action, comments);
    await loadAllData();
    showToast(
      `Request ${action}`,
      `Recorded ${action} for ${updated.documentNumber} (${updated.status}).`,
      action === 'Approved' ? 'success' : 'info'
    );
  };

  // Handlers for Date Controls
  const handleCreateDateControl = async (data: Partial<DateControlWhitelist>) => {
    const created = await api.createDateControl(data);
    setDateControls((prev) => [created, ...prev]);
    showToast('Whitelist Created', `Backdate exception [${created.id}] granted to ${created.user}.`);
  };

  const handleDeleteDateControl = async (id: string) => {
    await api.deleteDateControl(id);
    setDateControls((prev) => prev.filter((d) => d.id !== id));
    showToast('Whitelist Removed', 'Date permission revoked.');
  };

  // Handlers for Role Replication
  const handleSyncRoleReplication = async (id: string) => {
    const updated = await api.syncRoleReplication(id);
    setRoleReplications((prev) => prev.map((r) => (r.id === id ? updated : r)));
    showToast('Roles Synchronized', `Synchronized ${updated.roles.length} roles to target entities.`);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 animate-in slide-in-from-bottom-5 duration-200">
          <div
            className={`max-w-md p-4 rounded-xl shadow-lg border flex items-start gap-3 ${
              toast.type === 'success'
                ? 'bg-emerald-900 text-white border-emerald-700'
                : toast.type === 'error'
                ? 'bg-rose-900 text-white border-rose-700'
                : 'bg-slate-900 text-white border-slate-700'
            }`}
          >
            {toast.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            )}
            <div className="flex-1 text-xs">
              <span className="font-bold block text-sm mb-0.5">{toast.title}</span>
              <p className="text-slate-200 leading-relaxed">{toast.message}</p>
            </div>
            <button
              onClick={() => setToast(null)}
              className="text-slate-400 hover:text-white cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Top Navigation */}
      <Navbar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        companies={companies}
        selectedCompany={selectedCompanyFilter}
        onCompanyChange={setSelectedCompanyFilter}
        onOpenNewTx={() => setIsNewTxModalOpen(true)}
        pendingApprovalsCount={approvalRequests.filter((r) => r.status === 'Pending').length}
      />

      {/* Main Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {isLoading ? (
          <div className="h-96 flex flex-col items-center justify-center text-slate-400 space-y-2">
            <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-xs font-semibold">Loading inter-company multi-entity ledger...</span>
          </div>
        ) : (
          <>
            {currentTab === 'frappe-app' && <FrappeAppStructureTab />}

            {currentTab === 'overview' && (
              <DashboardOverview
                stats={stats}
                companies={companies}
                mappings={mappings}
                recentTransactions={transactions}
                onNavigateTab={setCurrentTab}
                onOpenNewTx={() => setIsNewTxModalOpen(true)}
              />
            )}

            {currentTab === 'mappings' && (
              <TransactionMappingsTab
                mappings={mappings}
                companies={companies}
                onToggleMapping={handleToggleMapping}
                onCreateMapping={handleCreateMapping}
                onDeleteMapping={handleDeleteMapping}
              />
            )}

            {currentTab === 'transactions' && (
              <TransactionsHubTab
                transactions={transactions}
                companies={companies}
                selectedCompanyFilter={selectedCompanyFilter}
                onSelectCompanyFilter={setSelectedCompanyFilter}
                onCancelTransaction={handleCancelTransaction}
                onSyncTransaction={handleSyncTransaction}
                onOpenNewTx={() => setIsNewTxModalOpen(true)}
              />
            )}

            {currentTab === 'workflows' && (
              <WorkflowsTab
                workflows={workflows}
                approvalRequests={approvalRequests}
                onActionRequest={handleActionWorkflowRequest}
              />
            )}

            {currentTab === 'date-control' && (
              <DateControlTab
                dateControls={dateControls}
                companies={companies}
                onCreateDateControl={handleCreateDateControl}
                onDeleteDateControl={handleDeleteDateControl}
              />
            )}

            {currentTab === 'role-replication' && (
              <RoleReplicationTab
                roleReplications={roleReplications}
                onSyncRoleReplication={handleSyncRoleReplication}
              />
            )}
          </>
        )}
      </main>

      {/* New Transaction Modal */}
      {isNewTxModalOpen && (
        <NewTransactionModal
          companies={companies}
          mappings={mappings}
          onClose={() => setIsNewTxModalOpen(false)}
          onSubmit={handleCreateTransaction}
        />
      )}
    </div>
  );
}

export default App;
