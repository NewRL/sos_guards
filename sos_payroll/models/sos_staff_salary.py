import pdb
import babel
import math
import calendar
import time
from dateutil.relativedelta import relativedelta
from pytz import common_timezones, timezone, utc
from datetime import date,datetime, timedelta
from odoo.tools import float_compare, float_is_zero
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import odoo.netsvc
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as OE_DFORMAT
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as OE_DTFORMAT
from odoo.tools.translate import _
from odoo import tools
import odoo.addons.decimal_precision as dp
from odoo.osv import expression

class hr_employee(models.Model):
	_name = 'hr.employee'
	_inherit = 'hr.employee'

	@api.model	
	def name_search(self, name, args=None, operator='ilike', limit=100):
		args = args or []
		domain = []
		if name:
			domain = ['|',('code', '=ilike', name + '%'),('name', operator, name)]			
			if operator in expression.NEGATIVE_TERM_OPERATORS:
				domain = ['&'] + domain
		emps = self.search(domain + args, limit=limit)
		return emps.name_get()
	
	## Column ##
	status = fields.Selection([('new', 'New-Hire'),('onboarding', 'On-Boarding'),('active', 'Active'),('pending_inactive', 'Pending Deactivation'),('inactive', 'Inactive'),('reactivated', 'Re-Activated'),('terminated', 'Terminated'),],default='new',string='Status',readonly=True,)		


class hr_payslip(models.Model):
	_inherit = 'hr.payslip'

	@api.model
	def _default_journal(self):
		company_id = self._context.get('company_id', self.env.user.company_id.id)
		domain = [
			('code', '=', 'SAL'),
			('company_id', '=', company_id),
		]
		return self.env['account.journal'].search(domain, limit=1)


	journal_id = fields.Many2one('account.journal', 'Salary Journal',states={'draft': [('readonly', False)]}, readonly=True, required=True,default=_default_journal)
	
	@api.onchange('employee_id', 'date_from','date_to')
	def onchange_employee(self):
		if (not self.employee_id) or (not self.date_from) or (not self.date_to):
			return
			
		employee_id = self.employee_id
		date_from = self.date_from
		date_to = self.date_to

		# pdb.set_trace()
		# ttyme = datetime.fromtimestamp(time.mktime(time.strptime(date_to, "%Y-%m-%d")))
		self.name = _('Salary Slip of %s for %s') % (employee_id.name, tools.ustr(date_to.strftime('%B-%Y')))
		self.company_id = employee_id.company_id

		if not self.env.context.get('contract') or not self.contract_id:
			contract_ids = self.get_contract(employee_id, date_from, date_to)
			if not contract_ids:
				return
			self.contract_id = self.contract_id.browse(contract_ids[0])

		if not self.contract_id.struct_id:
			return

		self.struct_id = self.contract_id.struct_id
		if self.contract_id.journal_id:
			self.journal_id = self.contract_id.journal_id

		#computation of the salary input
		#worked_days_line_ids = self.get_worked_day_lines(contract_ids, date_from, date_to)
		worked_days_line_ids = self.get_worked_day_lines_monthly_attendance(contract_ids, date_from, date_to)
		worked_days_lines = self.worked_days_line_ids.browse([])
		for r in worked_days_line_ids:
			worked_days_lines += worked_days_lines.new(r)
		self.worked_days_line_ids = worked_days_lines

		input_line_ids = self.get_inputs(contract_ids, date_from, date_to)
		input_lines = self.input_line_ids.browse([])
		for r in input_line_ids:
			input_lines += input_lines.new(r)
		self.input_line_ids = input_lines
		return 

	@api.multi
	def compute_sheet(self):
		arrears_obj = self.env['hr.salary.inputs']
		att_obj = self.env['hr.employee.month.attendance']
		slip_line_pool = self.env['hr.payslip.line']
		
		for payslip in self:
			ttyme = datetime.fromtimestamp(time.mktime(time.strptime(payslip.date_from, "%Y-%m-%d")))
			number = _('Slip-%s-%s') % (tools.ustr(ttyme.strftime('%y%m')),payslip.employee_id.code)
		
			old_slipline_ids = slip_line_pool.search([('slip_id', '=', payslip.id)])
			if old_slipline_ids:
				old_slipline_ids.unlink()
			if payslip.contract_id:
				contract_ids = [payslip.contract_id.id]
			else:
				#if we don't give the contract, then the rules to apply should be for all current contracts of the employee
				contract_ids = self.get_contract(payslip.employee_id, payslip.date_from, payslip.date_to)
			
			arr_ids = arrears_obj.search([('employee_id', '=', payslip.employee_id.id),('date', '>=', payslip.date_from),('date', '<=', payslip.date_to),('state', '=', 'confirm')])
			##Handling Staff Loan
			if arr_ids:
				for arr_id in arr_ids:
					arr_id = arrears_obj.browse(arr_id)
					if arr_id.name == 'LOAN' and arr_id.loan_line:
						arr_id.loan_line.paid = True
						
				arr_ids.write({'state':'done','slip_id':payslip.id})
 			
			att_ids = att_obj.search([('employee_id', '=', payslip.employee_id.id),('date', '>=', payslip.date_from),('date', '<=', payslip.date_to)])
			if att_ids:
				att_ids.write({'state':'done','slip_id':payslip.id})
			
			lines = [(0,0,line) for line in self.get_payslip_lines(contract_ids, payslip.id)]
			payslip.write({'line_ids': lines, 'number': number,})
		return True

	@api.model
	def get_inputs(self,contract_ids, date_from, date_to):
		res = []
		contract_obj = self.env['hr.contract']
		rule_obj = self.env['hr.salary.rule']
		arrears_obj = self.env['hr.salary.inputs']
		
		structure_ids = contract_ids.get_all_structures()
		rule_ids = self.env['hr.payroll.structure'].browse(structure_ids).get_all_rules()
		sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]
		
		
		for contract in contract_ids:
			for rule in rule_obj.browse(sorted_rule_ids):
				if rule.input_ids:
					for input in rule.input_ids:
						arr_amt = ''
						arr_ids = arrears_obj.search([('employee_id', '=', contract.employee_id.id),('name', '=', input.code),('date', '>=', date_from),('date', '<=', date_to),('state', '=', 'confirm')])
						if arr_ids:
							arr_amt = 0
							for arr_id in arr_ids:
								arr_amt += arr_id.amount
							#arrears_obj.write(cr, uid,arr_id,{'slip_id': self})
						inputs = {
							'name': input.name,
							'code': input.code,
							'contract_id': contract.id,
							'amount': arr_amt or 0,
						}
						res += [inputs]
		return res

	#@api.multi
	def process_sheet(self):
		
		move_pool = self.env['account.move']
		hr_payslip_line_pool = self.env['hr.payslip.line']
		precision = self.env['decimal.precision'].precision_get('Payroll')
		timenow = time.strftime('%Y-%m-%d')

		model_rec = self.env['ir.model'].search([('model','=','hr.payslip.line')])
		auto_entries = self.env['auto.dimensions.entry'].search([('model_id','=',model_rec.id),('active','=',True)],order='sequence')
	
		for slip in self:
			line_ids = []
			debit_sum = 0.0
			credit_sum = 0.0
			date = timenow
			credit_combine_entry = 0
			
			company_id = slip.company_id.id

			name = _('Being Charge of Salary %s') % (slip.number)
			move = {
				'narration': name,
				'ref': slip.number,
				'journal_id': slip.journal_id.id,
				'company_id': company_id,
				'date': date,
			}
			for line in slip.details_by_salary_rule_category:
				#amt = slip.credit_note and -line.total or line.total
				amt = abs(slip.credit_note and -line.total or line.total)
				if float_is_zero(amt, precision_digits=precision):
					continue

				#company_id = line.company_id.id
				debit_account_id = line.salary_rule_id.account_debit.id
				credit_account_id = line.salary_rule_id.account_credit.id


				#if flag:
				if debit_account_id:
					debit_line = (0, 0, {
						'name': _('Charging of Salary %s') % (slip.number),
						'company_id': company_id,
						'partner_id': hr_payslip_line_pool._get_partner_id(line, credit_account=False),
						'account_id': debit_account_id,
						'journal_id': slip.journal_id.id,
						'date': date,
						'debit': amt > 0.0 and amt or 0.0,
						'credit': amt < 0.0 and -amt or 0.0,
						'analytic_account_id': line.salary_rule_id.analytic_account_id and line.salary_rule_id.analytic_account_id.id or False,
						'tax_line_id': line.salary_rule_id.account_tax_id and line.salary_rule_id.account_tax_id.id or False,
					})
					line_ids.append(debit_line)
					debit_sum += debit_line[2]['debit'] - debit_line[2]['credit']

																																											
				if credit_account_id:
					credit_line = (0, 0, {
						'name': _('%s %s') % (line.name,slip.number),
						'company_id': company_id,
						'partner_id': hr_payslip_line_pool._get_partner_id(line, credit_account=True),
						'account_id': credit_account_id,
						'journal_id': slip.journal_id.id,
						'date': date,
						'debit': amt < 0.0 and -amt or 0.0,
						'credit': amt > 0.0 and amt or 0.0,
						'analytic_account_id': line.salary_rule_id.analytic_account_id and line.salary_rule_id.analytic_account_id.id or False,
						'tax_line_id': line.salary_rule_id.account_tax_id and line.salary_rule_id.account_tax_id.id or False,
					})
					
					line_ids.append(credit_line)
					credit_sum += credit_line[2]['credit'] - credit_line[2]['debit']
				
			for move_line in line_ids:
				number = 0
				nd_ids = eval("self.env['account.account'].browse(move_line[2].get('account_id')).nd_ids")
				if nd_ids:
					for auto_entry in auto_entries:
						if auto_entry.dimension_id in nd_ids:
							if auto_entry.src_fnc:
								move_line[2].update({auto_entry.dst_col.name : eval(auto_entry.src_fnc)})
							else:
								move_line[2].update({auto_entry.dst_col.name : eval('self.'+auto_entry.src_col.name).id})
	
							ans = self.env['analytic.structure'].search([('model_name','=','account_move_line'),('nd_id','=',auto_entry.dimension_id.id)])	
							number += math.pow(2,int(ans.ordering)-1)			
					move_line[2].update({'d_bin' : bin(int(number))[2:].zfill(10)})
		
			move.update({'line_ids': line_ids})
			move = move_pool.create(move)
			self.write({'move_id': move.id, 'date' : date,'state': 'done'})

