from __future__ import unicode_literals
import frappe
from frappe import _

def execute():
	create_gst_accounts()
	update_fields_account_imports()
	update_fields_account_exports()
	update_fields_jv_capital_on_acquisitions()
	update_fields_gst_adjustments_pi()
	update_fields_gst_adjustments_si()
	update_fields_gst_adjustments_so_po_dn_pr_q_sq()

def create_gst_accounts():
	if not frappe.db.exists('Account', {'account_name': 'GST Adjustments'}):
		make_gst("GST Adjustments", 0)
	if not frappe.db.exists('Account', {'account_name': 'GST on Capital Acquisitions'}):
		make_gst("GST on Capital Acquisitions", 10)
	if not frappe.db.exists('Account', {'account_name': 'GST on Exports'}):
		make_gst("GST on Exports", 0)
	if not frappe.db.exists('Account', {'account_name': 'GST on Imports'}):
		make_gst("GST on Imports", 0)

def make_gst(account_name, tax_rate):
	gst = frappe.get_doc({
		"doctype": "Account",
		"account_name": account_name,
		"is_group": 0,
		"root_type": "Liability",
		"account_type": "Tax",
		"account_currency": "AUD",
		"company": "Industrial Automation Group Pty Ltd",
		"tax_rate": tax_rate,
		"report_type": "Balance Sheet",
		"parent": "ATO Liabilities - IAG",
		"parent_account": "ATO Liabilities - IAG",
		"group_or_ledger": "Ledger",
		"old_parent": "ATO Liabilities - IAG",
		"credit_limit": 0,
		"credit_days": 0,
		"show_in_tax_reports": 1
	})
	gst.insert(ignore_permissions=True)

# Supplier not from Australia
def update_fields_account_imports():
	suppliers_invoices = """(select `tabPurchase Invoice`.name as PINV
							from `tabPurchase Invoice` 
							left join tabSupplier on tabSupplier.name = `tabPurchase Invoice`.supplier
							where currency <> 'AUD')"""

	frappe.db.sql("""UPDATE `tabPurchase Taxes and Charges`
				  SET account_head = 'GST on Imports - IAG'
				  WHERE account_head like 'GST Paid - IAG'
				  AND parent in {suppliers_invoices}""".format(suppliers_invoices=suppliers_invoices),{}, as_dict=True)

	frappe.db.sql("""update `tabGL Entry`
				  set account = 'GST on Imports - IAG'
				  where account like 'GST Paid - IAG'
				  and voucher_no in {suppliers_invoices}""".format(suppliers_invoices=suppliers_invoices),{}, as_dict=True)

# Customer not from Australia
def update_fields_account_exports():
	customers_invoices = """(select `tabSales Invoice`.name as SINV
							from `tabSales Invoice` 
							left join tabCustomer on tabCustomer.name = `tabSales Invoice`.customer
							where tabCustomer.territory = 'Rest of the World')"""

	frappe.db.sql("""UPDATE `tabSales Taxes and Charges`
				  SET account_head = 'GST on Exports - IAG'
				  WHERE account_head like 'GST Collected - IAG'
				  AND parent in {customers_invoices}""".format(customers_invoices=customers_invoices),{}, as_dict=True)

	frappe.db.sql("""update `tabGL Entry`
				  set account = 'GST on Exports - IAG'
				  where account like 'GST Collected - IAG'
				  and voucher_no in {customers_invoices}""".format(customers_invoices=customers_invoices),{}, as_dict=True)

# GST on Capital Acquisitions
def update_fields_jv_capital_on_acquisitions():
	for d in frappe.db.sql("select parent from `tabJournal Entry Account` where account = 'Motor Vehicles GST paid - IAG'"):
		frappe.db.sql("update `tabJournal Entry Account` "
					  "set account = 'GST on Capital Acquisitions - IAG' "
					  "where account = 'GST Paid - IAG' "
					  "and parent = %s", d[0])

		frappe.db.sql("update `tabGL Entry` "
					  "set account = 'GST on Capital Acquisitions - IAG' "
					  "where account = 'GST Paid - IAG' "
					  "and voucher_no = %s", d[0])

# GST Adjustments - Purchase Invoice
def update_fields_gst_adjustments_pi():
	inv_not_combined = ""
	for x in frappe.db.sql("""select voucher_no, account
							from `tabGL Entry` t1
							where account = 'GST Paid - IAG'
							and (credit > 0.0 and debit = 0.0)
							and voucher_no in (
								SELECT parent
								FROM `tabPurchase Taxes and Charges`
								WHERE description LIKE '%GST%tment%'
											AND parent LIKE 'PINV-%'
											AND `tabPurchase Taxes and Charges`.docstatus = 1)
							and (select count(account) from `tabGL Entry` where account = 'GST Paid - IAG'
								and voucher_no = t1.voucher_no) > 1"""):
		inv_not_combined += "'" + x[0] + "',"
	if inv_not_combined != "":
		inv_not_combined = " (" + inv_not_combined[:len(inv_not_combined)-1] + ") "

	for p in frappe.db.sql("""select name, parent, tax_amount_after_discount_amount, docstatus, add_deduct_tax
								from `tabPurchase Taxes and Charges`
								where description like '%Adjustment%'
								and description not LIKE '%Cash%tment%'
								and parent like 'PINV-%'"""):

		frappe.db.sql("""update `tabPurchase Taxes and Charges`
							set account_head = 'GST Adjustments - IAG'
							where name = %s""", p[0]) #name

		if p[3] == 1: #docstatus
			gle = frappe.db.sql("""select name,docstatus,account,fiscal_year,company,is_opening,against,voucher_type,credit,
					is_advance,debit,remarks,posting_date,cost_center,voucher_no,debit_in_account_currency,account_currency,
					credit_in_account_currency,aging_date
					from `tabGL Entry`
					where voucher_no = %s
					and account = 'GST Paid - IAG'""", p[1]) #parent

			debit = 0.0
			debit_in_account_currency = 0.0
			credit = 0.0
			credit_in_account_currency = 0.0
			debit_gle = 0.0
			debit_in_account_currency_gle = 0.0
			credit_gle = 0.0
			credit_in_account_currency_gle = 0.0

			if p[2] < 0.0:  # tax_amount_after_discount_amount
				if gle[0][15] >= 0.0: # Debit in account currency
					debit = gle[0][10] + abs(p[2])
					debit_in_account_currency = gle[0][15] + abs(p[2])
					credit_gle = abs(p[2])
					credit_in_account_currency_gle = abs(p[2])
					if p[1] in inv_not_combined and len(gle) > 1: # pinv 290 2493 and 314-2
						if gle[1][8] > 0.0: # Credit
							credit = abs(p[2])
							credit_in_account_currency = abs(p[2])
				else:
					debit = gle[0][10] + abs(p[2])
					debit_in_account_currency = gle[0][15] + abs(p[2])
					debit_gle = abs(p[2])
					debit_in_account_currency_gle = abs(p[2])
			else:
				if gle[0][15] < 0.0: # Debit in account currency
					debit = gle[0][10] - abs(p[2])
					debit_in_account_currency = gle[0][15] - abs(p[2])
					credit_gle = abs(p[2])
					credit_in_account_currency_gle = abs(p[2])
				else:
					if gle[0][10] != 0: # Debit
						if gle[0][8] != 0.0: # Credit
							temp = p[1]
							debit = gle[0][10]
							debit_in_account_currency = gle[0][15]
							if p[4] == 'Add':
								debit_gle = abs(p[2])
								debit_in_account_currency_gle = abs(p[2])
							else:   # 'Deduct':
								credit_gle = abs(p[2])
								credit_in_account_currency_gle = abs(p[2])
						else:
							if p[4] == 'Add':
								debit = gle[0][10] - abs(p[2])
								debit_in_account_currency = gle[0][15] - abs(p[2])
								debit_gle = abs(p[2])
								debit_in_account_currency_gle = abs(p[2])
							else:    # 'Deduct':
								credit_gle = abs(p[2])
								credit_in_account_currency_gle = abs(p[2])
								debit = gle[0][10]  # - abs(p[2])
								debit_in_account_currency = gle[0][15]  # - abs(p[2])
					else:
						if gle[0][8] > 0.0: # Credit
							credit = gle[0][8] + abs(p[2])
							credit_in_account_currency = gle[0][17] + abs(p[2])
							debit_gle = abs(p[2])
							debit_in_account_currency_gle = abs(p[2])
						else:
							credit = gle[0][8] + abs(p[2])
							credit_in_account_currency = gle[0][17] + abs(p[2])
							debit_gle = abs(p[2])
							debit_in_account_currency_gle = abs(p[2])

			if p[1] not in inv_not_combined:
				frappe.db.sql("""update `tabGL Entry`
					set debit = {0}, debit_in_account_currency = {1},
					credit = {2}, credit_in_account_currency = {3}
					where name = '{4}'""".format(debit, debit_in_account_currency, credit, credit_in_account_currency, gle[0][0]))

				make_gl_entry = frappe.get_doc({
					"doctype": "GL Entry",
					"name": gle[0][0],
					"docstatus": gle[0][1],
					"account": 'GST Adjustments - IAG',
					"fiscal_year": gle[0][3],
					"company": gle[0][4],
					"is_opening": gle[0][5],
					"against": gle[0][6],
					"voucher_type": gle[0][7],
					"credit": credit_gle,
					"is_advance": gle[0][9],
					"debit": debit_gle,
					"remarks": gle[0][11],
					"posting_date": gle[0][12],
					"cost_center": gle[0][13],
					"voucher_no": gle[0][14],
					"debit_in_account_currency": debit_in_account_currency_gle,
					"account_currency": gle[0][16],
					"credit_in_account_currency": credit_in_account_currency_gle,
					"aging_date": gle[0][18]
				})

				make_gl_entry.insert(ignore_permissions=True)
			else:
				frappe.db.sql("""update `tabGL Entry`
								set account = 'GST Adjustments - IAG',
								debit = {0}, debit_in_account_currency = {1},
								credit = {2}, credit_in_account_currency = {3}
								where account = 'GST Paid - IAG'
								and credit > 0.0
								and voucher_no = '{4}'""".format(debit_gle, debit_in_account_currency_gle, credit_gle, credit_in_account_currency_gle, p[1]))

# GST Adjustments - Sales Invoice
def update_fields_gst_adjustments_si():
	inv_not_combined = ""
	for x in frappe.db.sql("""select voucher_no
							from `tabGL Entry` 
							where account = 'GST Collected - IAG'
							and debit > 0.0
							and voucher_no in (
								SELECT parent
								FROM `tabSales Taxes and Charges`
								WHERE description LIKE '%GST%tment%'
											AND parent LIKE 'SINV-%'
											AND `tabSales Taxes and Charges`.docstatus = 1
							)"""):
		inv_not_combined += "'" + x[0] + "',"
	if inv_not_combined != "":
		inv_not_combined = " (" + inv_not_combined[:len(inv_not_combined)-1] + ") "

	for p in frappe.db.sql("""select name, parent, tax_amount_after_discount_amount, docstatus
								from `tabSales Taxes and Charges`
								where description like '%GST%tment%'
								and parent like 'SINV-%'"""):

		frappe.db.sql("""update `tabSales Taxes and Charges`
							set account_head = 'GST Adjustments - IAG'
							where name = %s""", p[0]) #name

		if p[3] == 1: #docstatus
			gle = frappe.db.sql("""select name,docstatus,account,fiscal_year,company,is_opening,against,voucher_type,credit,
					is_advance,debit,remarks,posting_date,cost_center,voucher_no,debit_in_account_currency,account_currency,
					credit_in_account_currency,aging_date
					from `tabGL Entry` 
					where voucher_no = %s
					and account = 'GST Collected - IAG'""", p[1]) #parent

			debit = 0.0
			debit_in_account_currency = 0.0
			#credit = 0.0
			#credit_in_account_currency = 0.0
			debit_gle = 0.0
			debit_in_account_currency_gle = 0.0
			credit_gle = 0.0
			credit_in_account_currency_gle = 0.0

			if p[2] < 0.0: #tax_amount_after_discount_amount
				if gle[0][15] >= 0.0:
					credit = gle[0][8] + abs(p[2]) #credit
					credit_in_account_currency = gle[0][17] + abs(p[2]) #credit_in_account_currency
					debit_gle = abs(p[2])
					debit_in_account_currency_gle = abs(p[2])
				else:
					credit = gle[0][8] + abs(p[2])  # credit
					credit_in_account_currency = gle[0][17] + abs(p[2])  # credit_in_account_currency
					credit_gle = abs(p[2])
					credit_in_account_currency_gle = abs(p[2])
			else:
				if gle[0][15] < 0.0:
					credit = gle[0][8] - abs(p[2])  # credit
					credit_in_account_currency = gle[0][17] - abs(p[2])  # credit_in_account_currency
					debit_gle = abs(p[2])
					debit_in_account_currency_gle = abs(p[2])
				else:
					credit = gle[0][8] - abs(p[2])  # credit
					credit_in_account_currency = gle[0][17] - abs(p[2])  # credit_in_account_currency
					credit_gle = abs(p[2])
					credit_in_account_currency_gle = abs(p[2])

			if p[1] not in inv_not_combined:
				frappe.db.sql("""update `tabGL Entry`
								set debit = {0}, debit_in_account_currency = {1},
								credit = {2}, credit_in_account_currency = {3}
								where name = '{4}'""".format(debit, debit_in_account_currency, credit, credit_in_account_currency,
				                                             gle[0][0]))

				make_gl_entry = frappe.get_doc({
					"doctype": "GL Entry",
					"name": gle[0][0],
					"docstatus": gle[0][1],
					"account": 'GST Adjustments - IAG',
					"fiscal_year": gle[0][3],
					"company": gle[0][4],
					"is_opening": gle[0][5],
					"against": gle[0][6],
					"voucher_type": gle[0][7],
					"credit": credit_gle,
					"is_advance": gle[0][9],
					"debit": debit_gle,
					"remarks": gle[0][11],
					"posting_date": gle[0][12],
					"cost_center": gle[0][13],
					"voucher_no": gle[0][14],
					"debit_in_account_currency": debit_in_account_currency_gle,
					"account_currency": gle[0][16],
					"credit_in_account_currency": credit_in_account_currency_gle,
					"aging_date": gle[0][18]
				})

				make_gl_entry.insert(ignore_permissions=True)
			else:
				frappe.db.sql("""update `tabGL Entry`
								set account = 'GST Adjustments - IAG',
								debit = {0}, debit_in_account_currency = {1},
								credit = {2}, credit_in_account_currency = {3}
								where account = 'GST Collected - IAG'
								and debit > 0.0
								and voucher_no = '{4}'""".format(debit_gle, debit_in_account_currency_gle, credit_in_account_currency_gle, credit_in_account_currency_gle, p[1]))
#########################
# GST Adjustments:      #
# - Sales Order         #
# - Purchase Order      #
# - Delivery Note       #
# - Purchase Receipt    #
# - Quotation           #
# - Supplier Quotation  #
#########################
def update_fields_gst_adjustments_so_po_dn_pr_q_sq():
	frappe.db.sql("""update `tabPurchase Taxes and Charges`
					set account_head = 'GST Adjustments - IAG'
					where description like '%Adjustment%'
					and parent not like 'PINV-%'""")

	frappe.db.sql("""update `tabSales Taxes and Charges`
					set account_head = 'GST Adjustments - IAG'
					where description like '%Adjustment%'
					and parent not like 'SINV-%'""")