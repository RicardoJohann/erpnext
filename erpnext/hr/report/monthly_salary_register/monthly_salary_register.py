# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from frappe import _
from datetime import datetime

def execute(filters=None):
	if not filters: filters = {}
	validate_date_range(filters)
	salary_slips = get_salary_slips(filters)
	columns, earning_types, ded_types = get_columns(salary_slips)
	ss_earning_map = get_ss_earning_map(salary_slips)
	ss_ded_map = get_ss_ded_map(salary_slips)


	data = []
	for ss in salary_slips:
		row = [ss.name, ss.employee, ss.employee_name, ss.branch, ss.department, ss.designation,
			ss.company, ss.start_date, ss.end_date, ss.posting_date, ss.leave_withut_pay, ss.payment_days]

		for e in earning_types:
			row.append(ss_earning_map.get(ss.name, {}).get(e))

		row += [ss.gross_pay]

		for d in ded_types:
			row.append(ss_ded_map.get(ss.name, {}).get(d))

		row += [ss.total_deduction, ss.net_pay]

		data.append(row)

	return columns, data

def validate_date_range(filters):
	dates = filters.date_range.split(" ")
	if dates:
		filters.from_date = datetime.strptime(dates[0], '%d-%m-%Y').strftime('%Y-%m-%d')
		filters.to_date = datetime.strptime(dates[2], '%d-%m-%Y').strftime('%Y-%m-%d')
		del filters["date_range"]

def get_columns(salary_slips):
	columns = [
		_("Salary Slip ID") + ":Link/Salary Slip:150",_("Employee") + ":Link/Employee:120", _("Employee Name") + "::140",
		_("Branch") + ":Link/Branch:120", _("Department") + ":Link/Department:120", _("Designation") + ":Link/Designation:120",
		_("Company") + ":Link/Company:120", _("Start Date") + ":Date:80", _("End Date") + ":Date:80", _("Posting Date") + ":Date:85",
		_("Leave Without Pay") + ":Float:130", _("Payment Days") + ":Float:120"
	]

	salary_components = {_("Earning"): [], _("Deduction"): []}

	for component in frappe.db.sql("""select distinct sd.salary_component, sc.type
		from `tabSalary Detail` sd, `tabSalary Component` sc
		where sc.name=sd.salary_component and sd.amount != 0 and sd.parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1):
		salary_components[_(component.type)].append(component.salary_component)

	columns = columns + [(e + ":Currency:120") for e in salary_components[_("Earning")]] + \
		[_("Gross Pay") + ":Currency:120"] + [(d + ":Currency:120") for d in salary_components[_("Deduction")]] + \
		[_("Total Deduction") + ":Currency:120", _("Net Pay") + ":Currency:120"]

	return columns, salary_components[_("Earning")], salary_components[_("Deduction")]

def get_salary_slips(filters):
	conditions, filters = get_conditions(filters)
	salary_slips = frappe.db.sql("""select * from `tabSalary Slip` where docstatus = 1 %s
		order by employee""" % conditions, filters, as_dict=1)

	if not salary_slips:
		frappe.throw(_("No salary slip found between {0} and {1}").format(
			datetime.strptime(filters.from_date, '%Y-%m-%d').strftime('%d-%m-%Y'),
			datetime.strptime(filters.to_date, '%Y-%m-%d').strftime('%d-%m-%Y')))
	return salary_slips

def get_conditions(filters):
	conditions = ""
	if filters.from_date:
		if filters.by == "Salary Slip":
			conditions += " and start_date >= %(from_date)s"
			conditions += " and end_date <= %(to_date)s"
		else: # Posting_Date
			conditions += " and posting_date between %(from_date)s and %(to_date)s"
	if filters.get("company"): conditions += " and company = %(company)s"
	if filters.get("employee"): conditions += " and employee = %(employee)s"

	return conditions, filters

def get_ss_earning_map(salary_slips):
	ss_earnings = frappe.db.sql("""select parent, salary_component, amount
		from `tabSalary Detail` where parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)

	ss_earning_map = {}
	for d in ss_earnings:
		ss_earning_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, [])
		ss_earning_map[d.parent][d.salary_component] = flt(d.amount)

	return ss_earning_map

def get_ss_ded_map(salary_slips):
	ss_deductions = frappe.db.sql("""select parent, salary_component, amount
		from `tabSalary Detail` where parent in (%s)""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)

	ss_ded_map = {}
	for d in ss_deductions:
		ss_ded_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, [])
		ss_ded_map[d.parent][d.salary_component] = flt(d.amount)

	return ss_ded_map