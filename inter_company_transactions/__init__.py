# -*- coding: utf-8 -*-
from __future__ import unicode_literals

__version__ = '0.0.1'

try:
    from inter_company_transactions.safe_eval_patch import apply_safe_eval_patch
    apply_safe_eval_patch()
except Exception:
    pass
