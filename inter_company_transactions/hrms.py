# File: your_app/hrms_hooks.py or similar
import frappe

def custom_fetch_fixed_allowances(salary_slip, method):
    employee = frappe.get_doc("Employee", salary_slip.employee)

    for comp in salary_slip.earnings:
        if comp.salary_component == "Fuel Allowance":
            comp.amount = employee.fuel_allowance or 0
        elif comp.salary_component == "SIM Allowance":
            comp.amount = employee.sim_allowance or 0
