import express from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import { createServer as createViteServer } from 'vite';
import type {
  Company,
  TransactionMapping,
  Transaction,
  WorkflowRule,
  ApprovalRequest,
  DateControlWhitelist,
  RoleReplication,
  SystemStats,
  TransactionType,
} from './src/types';

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

// In-memory Database Store
const companies: Company[] = [
  {
    id: 'COMP-001',
    name: 'Apex Global Technologies Inc.',
    code: 'AGTI',
    country: 'United States',
    currency: 'USD',
    defaultCostCenter: 'HQ-Corporate-US',
    isHolding: true,
  },
  {
    id: 'COMP-002',
    name: 'Apex Europe B.V.',
    code: 'AEBV',
    country: 'Netherlands',
    currency: 'EUR',
    defaultCostCenter: 'Distribution-EU',
    isHolding: false,
  },
  {
    id: 'COMP-003',
    name: 'Apex Logistics Corp.',
    code: 'ALC',
    country: 'Singapore',
    currency: 'USD',
    defaultCostCenter: 'Logistics-APAC',
    isHolding: false,
  },
  {
    id: 'COMP-004',
    name: 'Apex Services Ltd.',
    code: 'ASL',
    country: 'United Kingdom',
    currency: 'GBP',
    defaultCostCenter: 'SharedServices-UK',
    isHolding: false,
  },
];

const mappings: TransactionMapping[] = [
  {
    id: 'MAP-001',
    name: 'Apex US to Europe Sales/Purchase Synchronization',
    mainCompany: 'Apex Global Technologies Inc.',
    otherCompany: 'Apex Europe B.V.',
    mainTransactionType: 'Sales Order',
    otherTransactionType: 'Purchase Order',
    mainParty: 'Apex Europe B.V. (Customer)',
    otherParty: 'Apex Global Technologies Inc. (Supplier)',
    autoSubmit: true,
    allowLinkedCancellation: true,
    syncStatusUpdates: true,
    enabled: true,
    description: 'Auto-generates mirrored Purchase Order in Europe when US submits a Sales Order',
  },
  {
    id: 'MAP-002',
    name: 'Apex Europe to US Billing',
    mainCompany: 'Apex Europe B.V.',
    otherCompany: 'Apex Global Technologies Inc.',
    mainTransactionType: 'Sales Invoice',
    otherTransactionType: 'Purchase Invoice',
    mainParty: 'Apex Global Technologies Inc. (Customer)',
    otherParty: 'Apex Europe B.V. (Supplier)',
    autoSubmit: false,
    allowLinkedCancellation: true,
    syncStatusUpdates: true,
    enabled: true,
    description: 'Generates draft Purchase Invoice in US when Europe bills for regional fulfillment',
  },
  {
    id: 'MAP-003',
    name: 'Inter-Company Treasury Settlements',
    mainCompany: 'Apex Global Technologies Inc.',
    otherCompany: 'Apex Logistics Corp.',
    mainTransactionType: 'Journal Entry',
    otherTransactionType: 'Journal Entry',
    mainParty: 'Apex Logistics Inter-Company Account',
    otherParty: 'Apex Global Holding Account',
    autoSubmit: true,
    allowLinkedCancellation: true,
    syncStatusUpdates: true,
    enabled: true,
    description: 'Reconciles mutual ledger settlements between US HQ and Singapore Logistics',
  },
  {
    id: 'MAP-004',
    name: 'Central Payment Reallocations',
    mainCompany: 'Apex Global Technologies Inc.',
    otherCompany: 'Apex Europe B.V.',
    mainTransactionType: 'Payment Entry',
    otherTransactionType: 'Payment Entry',
    mainParty: 'Apex Europe Clearing Bank',
    otherParty: 'Apex Global US Treasury',
    autoSubmit: true,
    allowLinkedCancellation: true,
    syncStatusUpdates: true,
    enabled: true,
    description: 'Replicates bank payment vouchers between US central treasury and European operations',
  },
];

let transactions: Transaction[] = [
  {
    id: 'TX-1001',
    docNumber: 'SO-2025-0841',
    company: 'Apex Global Technologies Inc.',
    transactionType: 'Sales Order',
    date: '2025-09-10',
    party: 'Apex Europe B.V. (Customer)',
    amount: 145000,
    currency: 'USD',
    status: 'Submitted',
    linkedTransactionId: 'TX-1002',
    linkedDocNumber: 'PO-2025-0329',
    linkedCompany: 'Apex Europe B.V.',
    linkedTransactionType: 'Purchase Order',
    items: [
      {
        id: 'ITM-1',
        itemCode: 'SRV-CLOUD-900',
        description: 'Enterprise Cloud Infrastructure Annual Allocation',
        qty: 1,
        rate: 95000,
        amount: 95000,
      },
      {
        id: 'ITM-2',
        itemCode: 'LIC-SEC-200',
        description: 'Global Security License Distribution EU Hub',
        qty: 50,
        rate: 1000,
        amount: 50000,
      },
    ],
    notes: 'Quarterly intercompany shared software licensing allocation',
    createdAt: new Date(Date.now() - 3600000 * 48).toISOString(),
  },
  {
    id: 'TX-1002',
    docNumber: 'PO-2025-0329',
    company: 'Apex Europe B.V.',
    transactionType: 'Purchase Order',
    date: '2025-09-10',
    party: 'Apex Global Technologies Inc. (Supplier)',
    amount: 145000,
    currency: 'USD',
    status: 'Submitted',
    linkedTransactionId: 'TX-1001',
    linkedDocNumber: 'SO-2025-0841',
    linkedCompany: 'Apex Global Technologies Inc.',
    linkedTransactionType: 'Sales Order',
    items: [
      {
        id: 'ITM-1',
        itemCode: 'SRV-CLOUD-900',
        description: 'Enterprise Cloud Infrastructure Annual Allocation',
        qty: 1,
        rate: 95000,
        amount: 95000,
      },
      {
        id: 'ITM-2',
        itemCode: 'LIC-SEC-200',
        description: 'Global Security License Distribution EU Hub',
        qty: 50,
        rate: 1000,
        amount: 50000,
      },
    ],
    notes: 'Auto-created via Inter-Company Map MAP-001 from SO-2025-0841',
    createdAt: new Date(Date.now() - 3600000 * 48).toISOString(),
  },
  {
    id: 'TX-1003',
    docNumber: 'JE-2025-0112',
    company: 'Apex Global Technologies Inc.',
    transactionType: 'Journal Entry',
    date: '2025-09-12',
    party: 'Apex Logistics Inter-Company Account',
    amount: 68500,
    currency: 'USD',
    status: 'Submitted',
    linkedTransactionId: 'TX-1004',
    linkedDocNumber: 'JE-2025-0098',
    linkedCompany: 'Apex Logistics Corp.',
    linkedTransactionType: 'Journal Entry',
    items: [
      {
        id: 'ITM-3',
        itemCode: 'FRT-AIR-EXP',
        description: 'Air Freight Reimbursement SG to US West Coast',
        qty: 1,
        rate: 68500,
        amount: 68500,
      },
    ],
    notes: 'Q3 Intercompany logistics reconciliation',
    createdAt: new Date(Date.now() - 3600000 * 18).toISOString(),
  },
  {
    id: 'TX-1004',
    docNumber: 'JE-2025-0098',
    company: 'Apex Logistics Corp.',
    transactionType: 'Journal Entry',
    date: '2025-09-12',
    party: 'Apex Global Holding Account',
    amount: 68500,
    currency: 'USD',
    status: 'Submitted',
    linkedTransactionId: 'TX-1003',
    linkedDocNumber: 'JE-2025-0112',
    linkedCompany: 'Apex Global Technologies Inc.',
    linkedTransactionType: 'Journal Entry',
    items: [
      {
        id: 'ITM-3',
        itemCode: 'FRT-AIR-EXP',
        description: 'Air Freight Reimbursement SG to US West Coast',
        qty: 1,
        rate: 68500,
        amount: 68500,
      },
    ],
    notes: 'Auto-reconciled intercompany journal',
    createdAt: new Date(Date.now() - 3600000 * 18).toISOString(),
  },
];

const workflows: WorkflowRule[] = [
  {
    id: 'WF-001',
    name: 'High-Value Inter-Company Sales Order Approval',
    sourceCompany: 'Apex Global Technologies Inc.',
    targetCompany: 'Apex Europe B.V.',
    documentType: 'Sales Order',
    minAmount: 100000,
    approvalLevels: 2,
    approverRoles: ['Financial Controller', 'VP Finance'],
    escalationHours: 48,
    enabled: true,
  },
  {
    id: 'WF-002',
    name: 'Intercompany Journal Entry Audit',
    sourceCompany: 'Apex Global Technologies Inc.',
    targetCompany: 'Apex Logistics Corp.',
    documentType: 'Journal Entry',
    minAmount: 50000,
    approvalLevels: 1,
    approverRoles: ['Chief Accountant'],
    escalationHours: 24,
    enabled: true,
  },
];

let approvalRequests: ApprovalRequest[] = [
  {
    id: 'REQ-501',
    workflowId: 'WF-001',
    workflowName: 'High-Value Inter-Company Sales Order Approval',
    transactionId: 'TX-1001',
    documentNumber: 'SO-2025-0841',
    documentType: 'Sales Order',
    sourceCompany: 'Apex Global Technologies Inc.',
    targetCompany: 'Apex Europe B.V.',
    amount: 145000,
    currency: 'USD',
    requestedBy: 'administrator@apexglobal.com',
    currentLevel: 2,
    requiredLevels: 2,
    status: 'Approved',
    history: [
      {
        level: 1,
        approver: 'controller@apexglobal.com',
        action: 'Approved',
        date: new Date(Date.now() - 3600000 * 40).toISOString(),
        comments: 'Verified pricing matrix and cross-border customs terms.',
      },
      {
        level: 2,
        approver: 'vpfinance@apexglobal.com',
        action: 'Approved',
        date: new Date(Date.now() - 3600000 * 36).toISOString(),
        comments: 'Final executive sign-off granted.',
      },
    ],
    createdAt: new Date(Date.now() - 3600000 * 48).toISOString(),
  },
];

let dateControlWhitelists: DateControlWhitelist[] = [
  {
    id: 'DCW-001',
    company: 'Apex Global Technologies Inc.',
    user: 'finance.lead@apexglobal.com',
    documentType: 'Sales Order',
    allowedBackdateDays: 30,
    allowedFutureDateDays: 14,
    validFrom: '2025-01-01',
    validUpto: '2025-12-31',
    status: 'Active',
  },
  {
    id: 'DCW-002',
    company: 'Apex Europe B.V.',
    user: 'auditor@apexeurope.nl',
    documentType: 'Journal Entry',
    allowedBackdateDays: 60,
    allowedFutureDateDays: 7,
    validFrom: '2025-01-01',
    validUpto: '2025-12-31',
    status: 'Active',
  },
  {
    id: 'DCW-003',
    company: 'Apex Logistics Corp.',
    user: 'ops.manager@apexlogistics.sg',
    documentType: 'Purchase Order',
    allowedBackdateDays: 15,
    allowedFutureDateDays: 30,
    validFrom: '2025-06-01',
    validUpto: '2025-09-30',
    status: 'Active',
  },
];

let roleReplications: RoleReplication[] = [
  {
    id: 'RR-001',
    sourceCompany: 'Apex Global Technologies Inc.',
    targetCompanies: ['Apex Europe B.V.', 'Apex Logistics Corp.', 'Apex Services Ltd.'],
    roles: ['Intercompany Auditor', 'Accounts Manager', 'Compliance Officer'],
    lastSynced: new Date(Date.now() - 3600000 * 12).toISOString(),
    status: 'In Sync',
    syncedUsersCount: 18,
  },
  {
    id: 'RR-002',
    sourceCompany: 'Apex Europe B.V.',
    targetCompanies: ['Apex Services Ltd.'],
    roles: ['Regional Procurement Officer'],
    lastSynced: new Date(Date.now() - 3600000 * 72).toISOString(),
    status: 'In Sync',
    syncedUsersCount: 6,
  },
];

// Helper: Reverse mapping lookup
function getReverseTransactionType(type: TransactionType): TransactionType {
  switch (type) {
    case 'Sales Order':
      return 'Purchase Order';
    case 'Purchase Order':
      return 'Sales Order';
    case 'Sales Invoice':
      return 'Purchase Invoice';
    case 'Purchase Invoice':
      return 'Sales Invoice';
    case 'Journal Entry':
      return 'Journal Entry';
    case 'Payment Entry':
      return 'Payment Entry';
  }
}

// ---------------- API ROUTES ----------------

// System Statistics
app.get('/api/stats', (req, res) => {
  const totalVolumeUSD = transactions
    .filter((t) => t.status !== 'Cancelled')
    .reduce((acc, curr) => acc + curr.amount, 0);

  const stats: SystemStats = {
    totalTransactions: transactions.length,
    linkedTransactionsCount: transactions.filter((t) => !!t.linkedTransactionId).length,
    activeMappingsCount: mappings.filter((m) => m.enabled).length,
    pendingApprovalsCount: approvalRequests.filter((r) => r.status === 'Pending').length,
    totalVolumeUSD,
    syncedCompaniesCount: companies.length,
  };
  res.json(stats);
});

// Companies
app.get('/api/companies', (req, res) => {
  res.json(companies);
});

// Mappings
app.get('/api/mappings', (req, res) => {
  res.json(mappings);
});

app.post('/api/mappings', (req, res) => {
  const newMapping: TransactionMapping = {
    id: `MAP-${String(mappings.length + 1).padStart(3, '0')}`,
    ...req.body,
  };
  mappings.unshift(newMapping);
  res.status(201).json(newMapping);
});

app.patch('/api/mappings/:id/toggle', (req, res) => {
  const mapping = mappings.find((m) => m.id === req.params.id);
  if (!mapping) {
    return res.status(404).json({ error: 'Mapping not found' });
  }
  mapping.enabled = !mapping.enabled;
  res.json(mapping);
});

app.delete('/api/mappings/:id', (req, res) => {
  const index = mappings.findIndex((m) => m.id === req.params.id);
  if (index === -1) {
    return res.status(404).json({ error: 'Mapping not found' });
  }
  mappings.splice(index, 1);
  res.json({ success: true });
});

// Transactions
app.get('/api/transactions', (req, res) => {
  const { company, type, status } = req.query;
  let result = [...transactions];
  if (company) {
    result = result.filter((t) => t.company === company);
  }
  if (type) {
    result = result.filter((t) => t.transactionType === type);
  }
  if (status) {
    result = result.filter((t) => t.status === status);
  }
  res.json(result);
});

app.get('/api/transactions/:id', (req, res) => {
  const tx = transactions.find((t) => t.id === req.params.id);
  if (!tx) return res.status(404).json({ error: 'Transaction not found' });
  res.json(tx);
});

// Create Transaction with Inter-Company Generation
app.post('/api/transactions/create', (req, res) => {
  const {
    company,
    transactionType,
    date,
    party,
    amount,
    currency,
    items,
    notes,
    submitImmediately,
    userEmail = 'user@apexglobal.com',
  } = req.body;

  // 1. Date Control Validation
  const txDate = new Date(date);
  const today = new Date();
  const diffDays = Math.round((today.getTime() - txDate.getTime()) / (1000 * 3600 * 24));

  if (diffDays > 3) {
    // Check whitelist
    const whitelist = dateControlWhitelists.find(
      (w) =>
        w.company === company &&
        w.status === 'Active' &&
        (w.documentType === 'All' || w.documentType === transactionType) &&
        diffDays <= w.allowedBackdateDays
    );

    if (!whitelist) {
      return res.status(403).json({
        error: `Date Control Violation: Transaction date ${date} is backdated by ${diffDays} days. No active backdate permission exists for ${company}.`,
      });
    }
  }

  // 2. Find applicable Inter-Company Mapping
  const applicableMapping = mappings.find(
    (m) =>
      m.enabled &&
      m.mainCompany === company &&
      m.mainTransactionType === transactionType
  );

  const prefixMap: Record<TransactionType, string> = {
    'Sales Order': 'SO',
    'Purchase Order': 'PO',
    'Sales Invoice': 'SI',
    'Purchase Invoice': 'PI',
    'Journal Entry': 'JE',
    'Payment Entry': 'PE',
  };

  const currentYear = new Date().getFullYear();
  const nextSeq = transactions.length + 1;
  const primaryDocNumber = `${prefixMap[transactionType as TransactionType] || 'DOC'}-${currentYear}-${String(nextSeq).padStart(4, '0')}`;
  const primaryId = `TX-${1000 + nextSeq}`;

  // 3. Check Workflow Rule requirement
  const applicableWorkflow = workflows.find(
    (w) =>
      w.enabled &&
      w.sourceCompany === company &&
      w.documentType === transactionType &&
      amount >= w.minAmount
  );

  const initialStatus = applicableWorkflow
    ? 'Pending Approval'
    : submitImmediately || (applicableMapping?.autoSubmit ?? false)
    ? 'Submitted'
    : 'Draft';

  let linkedTx: Transaction | undefined;

  // 4. Create Linked Transaction if mapping exists
  if (applicableMapping) {
    const linkedSeq = nextSeq + 1;
    const linkedType = applicableMapping.otherTransactionType;
    const linkedDocNumber = `${prefixMap[linkedType] || 'DOC'}-${currentYear}-${String(linkedSeq).padStart(4, '0')}`;
    const linkedId = `TX-${1000 + linkedSeq}`;

    linkedTx = {
      id: linkedId,
      docNumber: linkedDocNumber,
      company: applicableMapping.otherCompany,
      transactionType: linkedType,
      date,
      party: applicableMapping.otherParty || company,
      amount,
      currency,
      status: initialStatus,
      linkedTransactionId: primaryId,
      linkedDocNumber: primaryDocNumber,
      linkedCompany: company,
      linkedTransactionType: transactionType,
      items: items || [],
      notes: `Auto-generated via Inter-Company Map [${applicableMapping.id}] linked to ${primaryDocNumber}`,
      createdAt: new Date().toISOString(),
    };
  }

  const primaryTx: Transaction = {
    id: primaryId,
    docNumber: primaryDocNumber,
    company,
    transactionType,
    date,
    party,
    amount,
    currency,
    status: initialStatus,
    linkedTransactionId: linkedTx?.id,
    linkedDocNumber: linkedTx?.docNumber,
    linkedCompany: linkedTx?.company,
    linkedTransactionType: linkedTx?.transactionType,
    items: items || [],
    notes,
    createdAt: new Date().toISOString(),
    requiresWorkflow: !!applicableWorkflow,
  };

  transactions.unshift(primaryTx);
  if (linkedTx) {
    transactions.unshift(linkedTx);
  }

  // 5. Create Approval Request if workflow triggered
  if (applicableWorkflow) {
    const approvalReq: ApprovalRequest = {
      id: `REQ-${approvalRequests.length + 501}`,
      workflowId: applicableWorkflow.id,
      workflowName: applicableWorkflow.name,
      transactionId: primaryId,
      documentNumber: primaryDocNumber,
      documentType: transactionType,
      sourceCompany: company,
      targetCompany: applicableMapping?.otherCompany || 'External',
      amount,
      currency,
      requestedBy: userEmail,
      currentLevel: 1,
      requiredLevels: applicableWorkflow.approvalLevels,
      status: 'Pending',
      history: [],
      createdAt: new Date().toISOString(),
    };
    approvalRequests.unshift(approvalReq);
  }

  res.status(201).json({
    primary: primaryTx,
    linked: linkedTx || null,
    workflowTriggered: !!applicableWorkflow,
  });
});

// Linked Cancellation
app.post('/api/transactions/:id/cancel', (req, res) => {
  const tx = transactions.find((t) => t.id === req.params.id);
  if (!tx) return res.status(404).json({ error: 'Transaction not found' });

  if (tx.status === 'Cancelled') {
    return res.status(400).json({ error: 'Transaction is already cancelled' });
  }

  tx.status = 'Cancelled';
  let cancelledLinkedDoc = null;

  // Check if linked transaction exists
  if (tx.linkedTransactionId) {
    const linkedTx = transactions.find((t) => t.id === tx.linkedTransactionId);
    if (linkedTx && linkedTx.status !== 'Cancelled') {
      linkedTx.status = 'Cancelled';
      linkedTx.notes = `${linkedTx.notes || ''} [Cancelled automatically via linked cancellation from ${tx.docNumber}]`;
      cancelledLinkedDoc = linkedTx.docNumber;
    }
  }

  res.json({
    success: true,
    cancelledDoc: tx.docNumber,
    cancelledLinkedDoc,
  });
});

// Force Sync between linked documents
app.post('/api/transactions/:id/sync', (req, res) => {
  const tx = transactions.find((t) => t.id === req.params.id);
  if (!tx || !tx.linkedTransactionId) {
    return res.status(404).json({ error: 'Linked transaction not found' });
  }

  const linked = transactions.find((t) => t.id === tx.linkedTransactionId);
  if (!linked) {
    return res.status(404).json({ error: 'Corresponding document not found' });
  }

  // Sync amount and items from master
  linked.amount = tx.amount;
  linked.items = JSON.parse(JSON.stringify(tx.items));
  linked.notes = `${linked.notes || ''} [Synchronized on ${new Date().toLocaleTimeString()}]`;

  res.json({
    success: true,
    message: `Synchronized ${tx.docNumber} with ${linked.docNumber}`,
    syncedTransaction: linked,
  });
});

// Workflows & Approvals
app.get('/api/workflows', (req, res) => {
  res.json(workflows);
});

app.get('/api/approval-requests', (req, res) => {
  res.json(approvalRequests);
});

app.post('/api/approval-requests/:id/action', (req, res) => {
  const { action, comments, approver = 'financial.controller@apexglobal.com' } = req.body;
  const request = approvalRequests.find((r) => r.id === req.params.id);
  if (!request) return res.status(404).json({ error: 'Approval request not found' });

  if (request.status !== 'Pending') {
    return res.status(400).json({ error: `Request is already ${request.status}` });
  }

  request.history.push({
    level: request.currentLevel,
    approver,
    action,
    date: new Date().toISOString(),
    comments: comments || (action === 'Approved' ? 'Standard approval.' : 'Rejected per policy.'),
  });

  if (action === 'Rejected') {
    request.status = 'Rejected';
    // Update transactions to Draft or Cancelled
    const primaryTx = transactions.find((t) => t.id === request.transactionId);
    if (primaryTx) primaryTx.status = 'Cancelled';
    if (primaryTx?.linkedTransactionId) {
      const linked = transactions.find((t) => t.id === primaryTx.linkedTransactionId);
      if (linked) linked.status = 'Cancelled';
    }
  } else if (action === 'Approved') {
    if (request.currentLevel < request.requiredLevels) {
      request.currentLevel += 1;
    } else {
      request.status = 'Approved';
      // Promote transactions to Submitted!
      const primaryTx = transactions.find((t) => t.id === request.transactionId);
      if (primaryTx) primaryTx.status = 'Submitted';
      if (primaryTx?.linkedTransactionId) {
        const linked = transactions.find((t) => t.id === primaryTx.linkedTransactionId);
        if (linked) linked.status = 'Submitted';
      }
    }
  }

  res.json(request);
});

// Date Control Whitelists
app.get('/api/date-controls', (req, res) => {
  res.json(dateControlWhitelists);
});

app.post('/api/date-controls', (req, res) => {
  const newEntry: DateControlWhitelist = {
    id: `DCW-${String(dateControlWhitelists.length + 1).padStart(3, '0')}`,
    ...req.body,
    status: 'Active',
  };
  dateControlWhitelists.unshift(newEntry);
  res.status(201).json(newEntry);
});

app.delete('/api/date-controls/:id', (req, res) => {
  const index = dateControlWhitelists.findIndex((d) => d.id === req.params.id);
  if (index === -1) return res.status(404).json({ error: 'Entry not found' });
  dateControlWhitelists.splice(index, 1);
  res.json({ success: true });
});

// Role Replications
app.get('/api/role-replications', (req, res) => {
  res.json(roleReplications);
});

app.post('/api/role-replications/:id/sync', (req, res) => {
  const replication = roleReplications.find((r) => r.id === req.params.id);
  if (!replication) return res.status(404).json({ error: 'Replication rule not found' });

  replication.lastSynced = new Date().toISOString();
  replication.status = 'In Sync';
  replication.syncedUsersCount += Math.floor(Math.random() * 3);

  res.json(replication);
});

// ERPNext / Frappe Custom App Inspect Endpoint
app.get('/api/frappe-app', (req, res) => {
  const rootDir = process.cwd();
  const filePaths = [
    'hooks.py',
    'setup.py',
    'pyproject.toml',
    'requirements.txt',
    'MANIFEST.in',
    'custom_fields.json',
    'INSTALLATION.md',
    'README.md',
    'USER_GUIDE.md',
    'inter_company_transactions/hooks.py',
    'inter_company_transactions/modules.txt',
    'inter_company_transactions/utils/transaction.py',
    'inter_company_transactions/doctype/inter_company_transaction_map/inter_company_transaction_map.json',
    'inter_company_transactions/doctype/inter_company_transaction_map/inter_company_transaction_map.py',
    'inter_company_transactions/doctype/inter_company_transaction_map/inter_company_transaction_map.js',
    'inter_company_transactions/doctype/inter_company_transaction_mapping/inter_company_transaction_mapping.json',
    'inter_company_transactions/doctype/inter_company_transaction_mapping/inter_company_transaction_mapping.py'
  ];

  const files = filePaths.map((relPath) => {
    const fullPath = path.join(rootDir, relPath);
    const exists = fs.existsSync(fullPath);
    let content = '';
    if (exists) {
      try {
        content = fs.readFileSync(fullPath, 'utf8');
      } catch (e) {
        content = '// error reading file';
      }
    }
    return {
      path: relPath,
      exists,
      content,
      size: exists ? fs.statSync(fullPath).size : 0,
    };
  });

  res.json({
    appName: 'inter_company_transactions',
    appTitle: 'Inter Company Transactions',
    appType: 'ERPNext / Frappe Custom App',
    targetFramework: 'Frappe v14 / v15',
    status: 'Restored & Active on Disk',
    files,
  });
});

// ---------------- VITE MIDDLEWARE & STATIC SERVING ----------------

async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[Inter-Company Transactions] Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
