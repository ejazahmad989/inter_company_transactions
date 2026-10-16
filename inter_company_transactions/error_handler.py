import frappe


def handle_error(error):
    """Handle application errors"""
    try:
        frappe.log_error(
            f"Application Error: {error!s}\nUser: {frappe.session.user}\nURL: {frappe.request.url if frappe.request else 'N/A'}",
            "Inter Company Transactions Error"
        )
        if is_critical_error(error):
            send_error_notification(error)
    except Exception as e:
        frappe.log_error(f"Error in error handler: {e!s}", "Error Handler")

def is_critical_error(error):
    """Check if error is critical"""
    critical_keywords = [
        "database",
        "connection",
        "permission",
        "inter_company"
    ]
    error_str = str(error).lower()
    return any(keyword in error_str for keyword in critical_keywords)

def send_error_notification(error):
    """Send error notification to administrators"""
    try:
        administrators = frappe.get_all(
            "Has Role",
            filters={"role": "System Manager"},
            fields=["parent"]
        )
        for admin in administrators:
            frappe.sendmail(
                recipients=[admin.parent],
                subject="Critical Error in Inter Company Transactions",
                message=f"A critical error occurred: {error!s}",
                reference_doctype="Error Log",
                reference_name=frappe.utils.now()
            )
    except Exception as e:
        frappe.log_error(f"Error sending error notification: {e!s}", "Error Notification")
