# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def workflow_approval_request_query(doctype, txt, searchfield, start, page_len, filters):
    """Custom query for Workflow Approval Request"""
    try:
        conditions = []
        values = []
        
        if txt:
            conditions.append("(document_name LIKE %s OR document_type LIKE %s)")
            values.extend([f"%{txt}%", f"%{txt}%"])
        
        if filters:
            if filters.get("status"):
                conditions.append("status = %s")
                values.append(filters["status"])
            
            if filters.get("workflow"):
                conditions.append("workflow = %s")
                values.append(filters["workflow"])
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT name, document_type, document_name, status, requested_by
            FROM `tabWorkflow Approval Request`
            WHERE {where_clause}
            ORDER BY creation DESC
            LIMIT %s OFFSET %s
        """
        
        values.extend([page_len, start])
        
        return frappe.db.sql(query, values)
        
    except Exception as e:
        frappe.log_error(f"Error in workflow approval request query: {str(e)}", "Query Error")
        return []