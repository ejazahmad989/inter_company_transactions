import React, { useState } from 'react';
import {
  GitMerge,
  ArrowRight,
  Plus,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Calendar,
} from 'lucide-react';
import type { Company, TransactionMapping, TransactionType, TransactionItem } from '../types';

interface NewTransactionModalProps {
  companies: Company[];
  mappings: TransactionMapping[];
  onClose: () => void;
  onSubmit: (data: any) => Promise<any>;
}

export const NewTransactionModal: React.FC<NewTransactionModalProps> = ({
  companies,
  mappings,
  onClose,
  onSubmit,
}) => {
  const [company, setCompany] = useState(companies[0]?.name || '');
  const [transactionType, setTransactionType] = useState<TransactionType>('Sales Order');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [party, setParty] = useState('Apex Europe B.V. (Customer)');
  const [notes, setNotes] = useState('Cross-entity service delivery agreement');
  const [submitImmediately, setSubmitImmediately] = useState(true);
  const [items, setItems] = useState<TransactionItem[]>([
    {
      id: '1',
      itemCode: 'PRD-SRV-101',
      description: 'Enterprise API Gateway & Cross-Border Routing',
      qty: 1,
      rate: 35000,
      amount: 35000,
    },
  ]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Check matching mapping
  const matchedMapping = mappings.find(
    (m) => m.enabled && m.mainCompany === company && m.mainTransactionType === transactionType
  );

  const calculateTotal = () => {
    return items.reduce((sum, item) => sum + (item.qty * item.rate), 0);
  };

  const handleAddItem = () => {
    setItems([
      ...items,
      {
        id: String(Date.now()),
        itemCode: 'NEW-ITEM',
        description: 'Intercompany Service Item',
        qty: 1,
        rate: 10000,
        amount: 10000,
      },
    ]);
  };

  const handleUpdateItem = (id: string, field: 'qty' | 'rate' | 'description' | 'itemCode', value: any) => {
    setItems(
      items.map((item) => {
        if (item.id !== id) return item;
        const updated = { ...item, [field]: value };
        if (field === 'qty' || field === 'rate') {
          const q = field === 'qty' ? Number(value) : item.qty;
          const r = field === 'rate' ? Number(value) : item.rate;
          updated.amount = q * r;
        }
        return updated;
      })
    );
  };

  const handleRemoveItem = (id: string) => {
    if (items.length <= 1) return;
    setItems(items.filter((i) => i.id !== id));
  };

  // Check backdating status
  const today = new Date();
  const txDate = new Date(date);
  const diffDays = Math.round((today.getTime() - txDate.getTime()) / (1000 * 3600 * 24));
  const isBackdated = diffDays > 3;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsSubmitting(true);
    try {
      await onSubmit({
        company,
        transactionType,
        date,
        party: party || 'Inter-Company Counterparty',
        amount: calculateTotal(),
        currency: 'USD',
        items,
        notes,
        submitImmediately,
      });
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Transaction submission failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-2xl w-full p-6 animate-in fade-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <GitMerge className="w-5 h-5 text-indigo-600" />
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Post Inter-Company Transaction</h3>
              <p className="text-xs text-slate-500">
                Creates the source document and triggers automated linked mirror creation
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 text-lg leading-none cursor-pointer"
          >
            &times;
          </button>
        </div>

        {errorMsg && (
          <div className="mt-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
          {/* Company & Type */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Source Company</label>
              <select
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500 font-medium"
              >
                {companies.map((c) => (
                  <option key={c.id} value={c.name}>
                    {c.name} ({c.currency})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Transaction Type</label>
              <select
                value={transactionType}
                onChange={(e) => setTransactionType(e.target.value as TransactionType)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500 font-medium"
              >
                <option value="Sales Order">Sales Order</option>
                <option value="Purchase Order">Purchase Order</option>
                <option value="Sales Invoice">Sales Invoice</option>
                <option value="Purchase Invoice">Purchase Invoice</option>
                <option value="Journal Entry">Journal Entry</option>
                <option value="Payment Entry">Payment Entry</option>
              </select>
            </div>
          </div>

          {/* Real-Time Mapping Prediction Banner */}
          {matchedMapping ? (
            <div className="p-3 rounded-lg bg-indigo-50/80 border border-indigo-200 flex items-center justify-between text-indigo-950">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-indigo-600 shrink-0" />
                <span>
                  <strong>Active Mapping Found:</strong> Submitting will automatically generate a{' '}
                  <strong className="text-indigo-700">{matchedMapping.otherTransactionType}</strong> in{' '}
                  <strong>{matchedMapping.otherCompany}</strong>.
                </span>
              </div>
              <span className="text-[10px] bg-indigo-200/60 font-semibold px-2 py-0.5 rounded text-indigo-800 shrink-0">
                {matchedMapping.autoSubmit ? 'Direct Submit' : 'Draft Mode'}
              </span>
            </div>
          ) : (
            <div className="p-3 rounded-lg bg-slate-100 border border-slate-200 text-slate-600 text-[11px]">
              ℹ No active mapping configured for {transactionType} from {company}. This will post as an unlinked internal voucher.
            </div>
          )}

          {/* Date & Party */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="font-semibold text-slate-700">Posting Date</label>
                {isBackdated && (
                  <span className="text-[10px] text-amber-700 font-semibold bg-amber-50 px-1.5 py-0.2 rounded">
                    Backdated ({diffDays}d) - Subject to Date Control
                  </span>
                )}
              </div>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Party / Account</label>
              <input
                type="text"
                value={party}
                onChange={(e) => setParty(e.target.value)}
                placeholder="e.g. Apex Europe B.V. (Customer)"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Item Lines */}
          <div className="space-y-2 pt-2 border-t border-slate-100">
            <div className="flex items-center justify-between">
              <label className="font-semibold text-slate-700">Line Items & Allocation</label>
              <button
                type="button"
                onClick={handleAddItem}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-700 cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" /> Add Row
              </button>
            </div>

            <div className="space-y-2">
              {items.map((item) => (
                <div key={item.id} className="grid grid-cols-12 gap-2 items-center bg-slate-50 p-2 rounded-lg border border-slate-200">
                  <div className="col-span-3">
                    <input
                      type="text"
                      value={item.itemCode}
                      onChange={(e) => handleUpdateItem(item.id, 'itemCode', e.target.value)}
                      placeholder="Code"
                      className="w-full px-2 py-1 bg-white border border-slate-300 rounded font-mono text-xs"
                    />
                  </div>
                  <div className="col-span-4">
                    <input
                      type="text"
                      value={item.description}
                      onChange={(e) => handleUpdateItem(item.id, 'description', e.target.value)}
                      placeholder="Description"
                      className="w-full px-2 py-1 bg-white border border-slate-300 rounded text-xs"
                    />
                  </div>
                  <div className="col-span-2">
                    <input
                      type="number"
                      value={item.qty}
                      onChange={(e) => handleUpdateItem(item.id, 'qty', e.target.value)}
                      placeholder="Qty"
                      className="w-full px-2 py-1 bg-white border border-slate-300 rounded text-xs text-right"
                    />
                  </div>
                  <div className="col-span-2">
                    <input
                      type="number"
                      value={item.rate}
                      onChange={(e) => handleUpdateItem(item.id, 'rate', e.target.value)}
                      placeholder="Rate"
                      className="w-full px-2 py-1 bg-white border border-slate-300 rounded text-xs text-right"
                    />
                  </div>
                  <div className="col-span-1 text-center">
                    <button
                      type="button"
                      onClick={() => handleRemoveItem(item.id)}
                      className="text-slate-400 hover:text-rose-600 cursor-pointer"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-2">
              <div className="text-right">
                <span className="text-xs text-slate-500 mr-3">Consolidated Total:</span>
                <span className="text-base font-bold text-slate-900">
                  ${calculateTotal().toLocaleString()} USD
                </span>
              </div>
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Memo / Intercompany Notes</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Q3 Shared services cross-billing"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Submit Action */}
          <div className="flex items-center justify-between pt-4 border-t border-slate-100">
            <label className="flex items-center gap-2 cursor-pointer font-medium text-slate-700">
              <input
                type="checkbox"
                checked={submitImmediately}
                onChange={(e) => setSubmitImmediately(e.target.checked)}
                className="rounded text-indigo-600 focus:ring-indigo-500"
              />
              <span>Submit voucher immediately (triggers workflow if &ge; $100k)</span>
            </label>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg shadow-xs cursor-pointer disabled:opacity-50"
              >
                {isSubmitting ? 'Posting...' : 'Post Transaction'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
