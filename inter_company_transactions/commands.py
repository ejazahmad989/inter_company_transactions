import frappe
import json
import os

def execute():
    """Import doctypes for inter-company transactions"""
    app_path = frappe.get_app_path('inter_company_transactions')
    
    # List of doctypes to import
    doctypes = [
        'Inter Company Transaction Map',
        'Inter Company Transaction Mapping',
        'Intercompany Transaction Link',
        'Intercompany Transaction Type Mapping'
    ]
    
    for doctype in doctypes:
        try:
            # Convert doctype name to file path format
            file_name = doctype.lower().replace(' ', '_')
            json_file = os.path.join(
                app_path,
                'inter_company_transactions',
                'doctype',
                file_name,
                f'{file_name}.json'
            )
            
            if os.path.exists(json_file):
                with open(json_file, 'r') as f:
                    doc_data = json.load(f)
                
                # Create or update doctype
                if not frappe.db.exists('DocType', doctype):
                    doc = frappe.new_doc('DocType')
                    doc.update(doc_data)
                    doc.insert(ignore_permissions=True)
                    print(f'Created DocType: {doctype}')
                else:
                    doc = frappe.get_doc('DocType', doctype)
                    doc.update(doc_data)
                    doc.save(ignore_permissions=True)
                    print(f'Updated DocType: {doctype}')
                
                frappe.db.commit()
            else:
                print(f'JSON file not found for DocType: {doctype}')
        
        except Exception as e:
            print(f'Error importing DocType {doctype}: {str(e)}')