# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def get_reverse_mapping():
    """Get reverse mapping for transaction types"""
    return {
        "Sales Order": "Purchase Order",
        "Purchase Order": "Sales Order",
        "Journal Entry": "Journal Entry",
        "Payment Entry": "Payment Entry"
    }

def get_valid_mappings():
    """Get valid transaction type mappings"""
    return {
        "Sales Order": ["Purchase Order"],
        "Purchase Order": ["Sales Order"],
        "Journal Entry": ["Journal Entry"],
        "Payment Entry": ["Payment Entry"]
    }

def is_valid_mapping(source_type, target_type):
    """Check if mapping is valid"""
    valid_mappings = get_valid_mappings()
    return target_type in valid_mappings.get(source_type, [])