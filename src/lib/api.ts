import type {
  Company,
  TransactionMapping,
  Transaction,
  WorkflowRule,
  ApprovalRequest,
  DateControlWhitelist,
  RoleReplication,
  SystemStats,
} from '../types';

export const api = {
  async getStats(): Promise<SystemStats> {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
  },

  async getCompanies(): Promise<Company[]> {
    const res = await fetch('/api/companies');
    if (!res.ok) throw new Error('Failed to fetch companies');
    return res.json();
  },

  async getMappings(): Promise<TransactionMapping[]> {
    const res = await fetch('/api/mappings');
    if (!res.ok) throw new Error('Failed to fetch mappings');
    return res.json();
  },

  async createMapping(mapping: Partial<TransactionMapping>): Promise<TransactionMapping> {
    const res = await fetch('/api/mappings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(mapping),
    });
    if (!res.ok) throw new Error('Failed to create mapping');
    return res.json();
  },

  async toggleMapping(id: string): Promise<TransactionMapping> {
    const res = await fetch(`/api/mappings/${id}/toggle`, { method: 'PATCH' });
    if (!res.ok) throw new Error('Failed to toggle mapping');
    return res.json();
  },

  async deleteMapping(id: string): Promise<void> {
    const res = await fetch(`/api/mappings/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete mapping');
  },

  async getTransactions(params?: { company?: string; type?: string; status?: string }): Promise<Transaction[]> {
    const query = new URLSearchParams(params as Record<string, string>).toString();
    const res = await fetch(`/api/transactions?${query}`);
    if (!res.ok) throw new Error('Failed to fetch transactions');
    return res.json();
  },

  async createTransaction(data: any): Promise<{ primary: Transaction; linked: Transaction | null; workflowTriggered: boolean }> {
    const res = await fetch('/api/transactions/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ error: 'Creation failed' }));
      throw new Error(errData.error || 'Failed to create transaction');
    }
    return res.json();
  },

  async cancelTransaction(id: string): Promise<{ success: boolean; cancelledDoc: string; cancelledLinkedDoc: string | null }> {
    const res = await fetch(`/api/transactions/${id}/cancel`, { method: 'POST' });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ error: 'Cancellation failed' }));
      throw new Error(errData.error || 'Failed to cancel transaction');
    }
    return res.json();
  },

  async syncTransaction(id: string): Promise<any> {
    const res = await fetch(`/api/transactions/${id}/sync`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to sync transaction');
    return res.json();
  },

  async getWorkflows(): Promise<WorkflowRule[]> {
    const res = await fetch('/api/workflows');
    if (!res.ok) throw new Error('Failed to fetch workflows');
    return res.json();
  },

  async getApprovalRequests(): Promise<ApprovalRequest[]> {
    const res = await fetch('/api/approval-requests');
    if (!res.ok) throw new Error('Failed to fetch approval requests');
    return res.json();
  },

  async actionApprovalRequest(id: string, action: 'Approved' | 'Rejected', comments: string): Promise<ApprovalRequest> {
    const res = await fetch(`/api/approval-requests/${id}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, comments }),
    });
    if (!res.ok) throw new Error('Failed to update approval request');
    return res.json();
  },

  async getDateControls(): Promise<DateControlWhitelist[]> {
    const res = await fetch('/api/date-controls');
    if (!res.ok) throw new Error('Failed to fetch date controls');
    return res.json();
  },

  async createDateControl(data: Partial<DateControlWhitelist>): Promise<DateControlWhitelist> {
    const res = await fetch('/api/date-controls', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create date control');
    return res.json();
  },

  async deleteDateControl(id: string): Promise<void> {
    const res = await fetch(`/api/date-controls/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete date control');
  },

  async getRoleReplications(): Promise<RoleReplication[]> {
    const res = await fetch('/api/role-replications');
    if (!res.ok) throw new Error('Failed to fetch role replications');
    return res.json();
  },

  async syncRoleReplication(id: string): Promise<RoleReplication> {
    const res = await fetch(`/api/role-replications/${id}/sync`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to sync roles');
    return res.json();
  },

  async getFrappeAppInfo(): Promise<{
    appName: string;
    appTitle: string;
    appType: string;
    targetFramework: string;
    status: string;
    files: Array<{ path: string; exists: boolean; content: string; size: number }>;
  }> {
    const res = await fetch('/api/frappe-app');
    if (!res.ok) throw new Error('Failed to fetch Frappe app info');
    return res.json();
  },
};
