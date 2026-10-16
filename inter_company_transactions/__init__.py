
__version__ = '1.0.0'

try:
    from inter_company_transactions.safe_eval_patch import apply_safe_eval_patch
    apply_safe_eval_patch()
except Exception:
    pass
