export type TransactionType =
  | 'Sales Order'
  | 'Purchase Order'
  | 'Sales Invoice'
  | 'Purchase Invoice'
  | 'Journal Entry'
  | 'Payment Entry';

export type TransactionStatus = 'Draft' | 'Submitted' | 'Cancelled' | 'Pending Approval';

export interface Company {
  id: string;
  name: string;
  code: string;
  country: string;
  currency: string;
  defaultCostCenter: string;
  isHolding: boolean;
}

export interface TransactionMapping {
  id: string;
  name: string;
  mainCompany: string;
  otherCompany: string;
  mainTransactionType: TransactionType;
  otherTransactionType: TransactionType;
  mainParty: string; // Customer or Supplier in main company
  otherParty: string; // Customer or Supplier in other company
  autoSubmit: boolean;
  allowLinkedCancellation: boolean;
  syncStatusUpdates: boolean;
  enabled: boolean;
  description?: string;
}

export interface TransactionItem {
  id: string;
  itemCode: string;
  description: string;
  qty: number;
  rate: number;
  amount: number;
}

export interface Transaction {
  id: string;
  docNumber: string;
  company: string;
  transactionType: TransactionType;
  date: string;
  party: string;
  amount: number;
  currency: string;
  status: TransactionStatus;
  linkedTransactionId?: string;
  linkedDocNumber?: string;
  linkedCompany?: string;
  linkedTransactionType?: TransactionType;
  items: TransactionItem[];
  notes?: string;
  createdAt: string;
  requiresWorkflow?: boolean;
}

export interface WorkflowRule {
  id: string;
  name: string;
  sourceCompany: string;
  targetCompany: string;
  documentType: TransactionType;
  minAmount: number;
  approvalLevels: number;
  approverRoles: string[];
  escalationHours: number;
  enabled: boolean;
}

export interface ApprovalActionLog {
  level: number;
  approver: string;
  action: 'Approved' | 'Rejected';
  date: string;
  comments: string;
}

export interface ApprovalRequest {
  id: string;
  workflowId: string;
  workflowName: string;
  transactionId: string;
  documentNumber: string;
  documentType: TransactionType;
  sourceCompany: string;
  targetCompany: string;
  amount: number;
  currency: string;
  requestedBy: string;
  currentLevel: number;
  requiredLevels: number;
  status: 'Pending' | 'Approved' | 'Rejected';
  history: ApprovalActionLog[];
  createdAt: string;
}

export interface DateControlWhitelist {
  id: string;
  company: string;
  user: string;
  documentType: string;
  allowedBackdateDays: number;
  allowedFutureDateDays: number;
  validFrom: string;
  validUpto: string;
  status: 'Active' | 'Expired' | 'Disabled';
}

export interface RoleReplication {
  id: string;
  sourceCompany: string;
  targetCompanies: string[];
  roles: string[];
  lastSynced: string;
  status: 'In Sync' | 'Pending Sync' | 'Failed';
  syncedUsersCount: number;
}

export interface SystemStats {
  totalTransactions: number;
  linkedTransactionsCount: number;
  activeMappingsCount: number;
  pendingApprovalsCount: number;
  totalVolumeUSD: number;
  syncedCompaniesCount: number;
}
