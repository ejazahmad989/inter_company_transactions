import frappe


def get_notification_config():
    """Get notification configuration for Inter Company Transactions"""
    return {
        "for_doctype": {
            "Inter Company Error Log": {
                "status": "status"
            },
            "Inter Company Dispute": {
                "status": "status"
            }
        }
    }
