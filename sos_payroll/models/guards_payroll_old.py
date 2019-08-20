
import time
import pdb
from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import relativedelta
from openerp.tools import float_compare, float_is_zero
from openerp import netsvc
from openerp.osv import fields, osv
from openerp import tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

from openerp.tools.safe_eval import safe_eval as eval

class one2many_mod2(fields.one2many):

	def get(self, cr, obj, ids, name, user=None, offset=0, context=None, values=None):
		if context is None:
			context = {}
		if not values:
			values = {}
		res = {}
		for id in ids:
			res[id] = []
		ids2 = obj.pool.get(self._obj).search(cr, user, [(self._fields_id,'in',ids), ('appears_on_payslip', '=', True)], limit=self._limit)
		for r in obj.pool.get(self._obj)._read(cr, user, ids2, [self._fields_id], context=context, load='_classic_write'):
			res[r[self._fields_id]].append( r['id'] )
		return res

        
class guards_payslip(osv.osv):
	_name = 'guards.payslip'
	_inherit = 'guards.payslip'

	_track = {
		'state': {
			'sos.mt_guard_payslip': lambda self, cr, uid, obj, ctx=None: True,
		},
		'total': {
			'sos.mt_guard_payslip': lambda self, cr, uid, obj, ctx=None: True,
		},		
	}
	
	
	def _get_payslips(self,cr,uid,ids,context=None):
		att={}
		for r in self.pool.get('guards.payslip.line').browse(cr,uid,ids,context=context):
			att[r.slip_id.id] = True
		slip_ids = []
		if att:
			slip_ids = self.pool.get('guards.payslip').search(cr,uid,[('id','=',att.keys())],context=context)
		return slip_ids
	
	def create(self, cr, uid, vals, context=None):
		if context is None:
			context = {}
		pdb.set_trace()		
		if 'journal_id' in context:
			vals.update({'journal_id': context.get('journal_id')})
		
		slip_id = super(guards_payslip, self).create(cr, uid, vals, context=context)
		#self.pool.get('hr.employee').write(cr, uid,vals['employee_id'],{'att_draft':False}, context=context)
		
		att_ids = []
		if vals['attendance_line_ids']:
			att_lines = vals['attendance_line_ids']
			for line in att_lines:
				if isinstance(line, (int, long)):
					att_ids.append(line)
				else:
					att_ids.append(line[1])
			att_ids = list(set(att_ids))			
			self.pool.get('sos.guard.attendance').write(cr,uid,att_ids,{'state':'counted','slip_id':slip_id},context=context)		
		return slip_id
	
	def write(self, cr, uid, ids, vals, context=None):
		if context is None:
			context = {}
		if not ids:
			return True
		if isinstance(ids, (int, long)):
			ids = [ids]

		att_ids = []
		if 'attendance_line_ids' in vals:
			att_lines = vals['attendance_line_ids']
			for line in att_lines:
				if isinstance(line, (int, long)):
					att_ids.append(line)
				else:
					att_ids.append(line[1])
			att_ids = list(set(att_ids))	
			self.pool.get('sos.guard.attendance').write(cr,uid,att_ids,{'state':'counted'},context=context)
			
		return super(guards_payslip, self).write(cr, uid, ids, vals, context=context)
		
	def _check_dates(self, cr, uid, ids, context=None):
		for payslip in self.browse(cr, uid, ids, context=context):
			if payslip.date_from > payslip.date_to:
				return False
		return True

	_constraints = [(_check_dates, "Payslip 'Date From' must be before 'Date To'.", ['date_from', 'date_to'])]

	def copy(self, cr, uid, id, default=None, context=None):
		if not default:
			default = {}
		company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
		default.update({
			'line_ids': [],
			'company_id': company_id,
			'number': '',
			'move_id': False,
			'payslip_run_id': False,
			'paid': False,
			'advice_id' : False,
		})
		return super(guards_payslip, self).copy(cr, uid, id, default, context=context)

	def guards_cancel_sheet(self, cr, uid, ids, context=None):
		return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

	def guards_process_sheet(self, cr, uid, ids, context=None):
		move_pool = self.pool.get('account.move')
		move_line_pool = self.pool.get('account.move.line')
		att_pool = self.pool.get('sos.guard.attendance')
		arr_pool = self.pool.get('guards.arrears')
		precision = self.pool.get('decimal.precision').precision_get(cr, uid, 'Payroll')
		
		for slip in self.browse(cr, uid, ids, context=context):
			line_ids = []
			debit_sum = 0.0
			credit_sum = 0.0
			
			date_accounting = slip.date_to
	
			if slip.move_id:
				continue
			
			if slip.state == 'done':
				continue
				
			default_emp_id = slip.employee_id.id
			name = _('Payslip of %s') % (slip.employee_id.name)
			move = {
				'narration': name,
				'date': date_accounting,
				'ref': slip.number,
				'journal_id': slip.journal_id.id,				
			}
			
			#to_reconsile = []
			for line in slip.line_ids:
				amt = slip.credit_note and -line.total or line.total
				if float_is_zero(amt, precision_digits=precision):
					continue
				emp_id = line.salary_rule_id.register_id.partner_id and line.salary_rule_id.register_id.partner_id.id or default_emp_id
				debit_account_id = line.salary_rule_id.account_debit.id
				credit_account_id = line.salary_rule_id.account_credit.id
				partner_id = line.post_id.partner_id.id if line.salary_rule_id.code == 'BASIC' else False
				
				if debit_account_id:
					debit_line = (0, 0, {
						'name': line.slip_id.name,
						'date': date_accounting,
						'post_id': line.post_id and line.post_id.id or False,
						#'project_id': line.post_id and line.post_id.project_id.id or False,
						#'center_id': line.post_id and line.post_id.center_id.id or False,
						#'emp_id': emp_id,
						'account_id': debit_account_id,						
						'journal_id': slip.journal_id.id,
						'debit': abs(amt), #amt > 0.0 and amt or 0.0,
						'credit': 0.0, #amt < 0.0 and -amt or 0.0,
						'analytic_account_id': line.salary_rule_id.analytic_account_id and line.salary_rule_id.analytic_account_id.id or False,
						'tax_line_id': line.salary_rule_id.account_tax_id and line.salary_rule_id.account_tax_id.id or False,						
						'invoice_id': line.move_line_id and line.move_line_id.invoice_id.id or False,
						'partner_id': partner_id,
					})
					line_ids.append(debit_line)
					debit_sum += debit_line[2]['debit'] - debit_line[2]['credit']
				
				if credit_account_id:
					credit_line = (0, 0, {
						'name': line.slip_id.name,
						'date': date_accounting,
						'post_id': line.post_id and line.post_id.id or False,
						#'project_id': line.post_id and line.post_id.project_id.id or False,
						#'center_id': line.post_id and line.post_id.center_id.id or False,
						#'emp_id': emp_id,
						'account_id': credit_account_id,						
						'journal_id': slip.journal_id.id,
						'debit': 0.0, #amt < 0.0 and -amt or 0.0,
						'credit': abs(amt), #amt > 0.0 and amt or 0.0,
						'analytic_account_id': line.salary_rule_id.analytic_account_id and line.salary_rule_id.analytic_account_id.id or False,
						'tax_line_id': line.salary_rule_id.account_tax_id and line.salary_rule_id.account_tax_id.id or False,
						'invoice_id': line.move_line_id and line.move_line_id.invoice_id.id or False,
						'partner_id': partner_id,						
					})
					line_ids.append(credit_line)
					credit_sum += credit_line[2]['credit'] - credit_line[2]['debit']
				#if line.move_line_id:
				#	to_reconsile.append(line.move_line_id.id)
		
			if debit_sum > credit_sum:
				acc_id = slip.journal_id.default_credit_account_id.id
				if not acc_id:
					raise osv.except_osv(_('Configuration Error!'),_('The Expense Journal "%s" has not properly configured the Credit Account!')%(slip.journal_id.name))
				adjust_credit = (0, 0, {
					'name': _('Adjustment Entry'),
					'date': date_accounting,
					'partner_id': False,
					'account_id': acc_id,
					'journal_id': slip.journal_id.id,
					'debit': 0.0,
					'credit': debit_sum - credit_sum,
				})
				line_ids.append(adjust_credit)
			elif debit_sum < credit_sum:
				acc_id = slip.journal_id.default_debit_account_id.id
				if not acc_id:
					raise osv.except_osv(_('Configuration Error!'),_('The Expense Journal "%s" has not properly configured the Debit Account!')%(slip.journal_id.name))
				adjust_debit = (0, 0, {
					'name': _('Adjustment Entry'),
					'date': date_accounting,
					'partner_id': False,
					'account_id': acc_id,
					'journal_id': slip.journal_id.id,
					'debit': credit_sum - debit_sum,
					'credit': 0.0,
				})
				line_ids.append(adjust_debit)
			move.update({'line_ids': line_ids})
			
			move_id = move_pool.create(cr, uid, move, context=context)
			
			#move_ids = move_line_pool.search(cr, uid, [('move_id','=',move_id),('invoice_id','<>',False),('account_id.type','in',('payable','receivable'))], context=context)
			#for moveid in move_ids:
			#	to_reconsile.append(moveid)
			
			self.write(cr, uid, [slip.id], {'move_id': move_id}, context=context)
			#if slip.journal_id.entry_posted:
			move_pool.post(cr, uid, [move_id], context=context)				
			
			att_ids = att_pool.search(cr, uid, [('slip_id','=',slip.id)], context=context)
			att_pool.write(cr,1,att_ids,{'state':'done'},context=context)
			
			arr_ids = arr_pool.search(cr, uid, [('employee_id','=',slip.employee_id.id)], context=context)
			arr_pool.write(cr,1,arr_ids,{'state':'done','slip_id':slip.id},context=context)
			
			#if len(to_reconsile) >= 2:
			#	reconcile = move_line_pool.reconcile_partial(cr, uid, to_reconsile)
			
		return self.write(cr, uid, ids, {'paid': True, 'state': 'done'}, context=context)

	def guards_verify_sheet(self, cr, uid, ids, context=None):		
		self.compute_sheet(cr, uid, ids, context)
		self.guards_process_sheet(cr, uid, ids, context)
		#return self.write(cr, uid, ids, {'state': 'verify'}, context=context)

#	def refund_sheet(self, cr, uid, ids, context=None):
#		mod_obj = self.pool.get('ir.model.data')
#		wf_service = netsvc.LocalService("workflow")
#		for payslip in self.browse(cr, uid, ids, context=context):
#			id_copy = self.copy(cr, uid, payslip.id, {'credit_note': True, 'name': _('Refund: ')+payslip.name}, context=context)
#			self.compute_sheet(cr, uid, [id_copy], context=context)
#			wf_service.trg_validate(uid, 'hr.payslip', id_copy, 'hr_verify_sheet', cr)
#			wf_service.trg_validate(uid, 'hr.payslip', id_copy, 'process_sheet', cr)
#
#		form_id = mod_obj.get_object_reference(cr, uid, 'hr_payroll', 'view_hr_payslip_form')
#		form_res = form_id and form_id[1] or False
#		tree_id = mod_obj.get_object_reference(cr, uid, 'hr_payroll', 'view_hr_payslip_tree')
#		tree_res = tree_id and tree_id[1] or False
#		return {
#			'name':_("Refund Payslip"),
#			'view_mode': 'tree, form',
#			'view_id': False,
#			'view_type': 'form',
#			'res_model': 'hr.payslip',
#			'type': 'ir.actions.act_window',
#			'nodestroy': True,
#			'target': 'current',
#			'domain': "[('id', 'in', %s)]" % [id_copy],
#			'views': [(tree_res, 'tree'), (form_res, 'form')],
#			'context': {}
#		}

	def check_done(self, cr, uid, ids, context=None):
		return True

	def unlink(self, cr, uid, ids, context=None):
		for payslip in self.browse(cr, uid, ids, context=context):
			if payslip.state not in  ['draft','cancel']:
				raise osv.except_osv(_('Warning!'),_('You cannot delete a payslip which is not draft or cancelled!'))
		return super(guards_payslip, self).unlink(cr, uid, ids, context)

	#TODO move this function into guards_contract module, on hr.guard object
	def get_contract(self, cr, uid, employee, date_from, date_to, context=None):
		contract_obj = self.pool.get('guards.contract')
		clause = []
		#a contract is valid if it ends between the given dates
		clause_1 = ['&',('date_end', '<=', date_to),('date_end','>=', date_from)]
		#OR if it starts between the given dates
		clause_2 = ['&',('date_start', '<=', date_to),('date_start','>=', date_from)]
		#OR if it starts before the date_from and finish after the date_end (or never finish)
		clause_3 = [('date_start','<=', date_from),'|',('date_end', '=', False),('date_end','>=', date_to)]
		#clause_final =  [('employee_id', '=', employee.id),'|','|'] + clause_1 + clause_2 + clause_3
		clause_final =  ['|','|'] + clause_1 + clause_2 + clause_3
		contract_ids = contract_obj.search(cr, uid, clause_final, context=context)
		return contract_ids

	def compute_sheet(self, cr, uid, ids, context=None):
		
		slip_line_pool = self.pool.get('guards.payslip.line')
		sequence_obj = self.pool.get('ir.sequence')
		for payslip in self.browse(cr, uid, ids, context=context):
			number = payslip.number or sequence_obj.next_by_code(cr, uid, 'salary.slip')
			#delete old payslip lines
			old_slipline_ids = slip_line_pool.search(cr, uid, [('slip_id', '=', payslip.id)], context=context)
			if old_slipline_ids:
				slip_line_pool.unlink(cr, uid, old_slipline_ids, context=context)
			if payslip.contract_id:
				#set the list of contract for which the rules have to be applied
				contract_ids = [payslip.contract_id.id]
			else:
				#if we don't give the contract, then the rules to apply should be for all current contracts of the employee
				contract_ids = self.get_contract(cr, uid, payslip.employee_id, payslip.date_from, payslip.date_to, context=context)
			lines = [(0,0,line) for line in self.pool.get('guards.payslip').get_payslip_lines(cr, uid, payslip.employee_id,contract_ids, payslip.id, context=context)]
			self.write(cr, uid, [payslip.id], {'line_ids': lines, 'number': number,}, context=context)
		return True

	
	def get_attendance_lines(self, cr, uid, ids, employee, date_from, date_to, paidon, slips, exclude_project_ids, context=None):		
		att_line_pool = self.pool.get('sos.guard.attendance')
		pending_pool = self.pool.get('project.salary.pending')
		if not employee:
			return False		
				
		set2 = []
		res = []
		# '|',('slip_id','=',False),('slip_id','in',slips)
		if exclude_project_ids:
			set2 = list(set(set2) | set(att_line_pool.search(cr, uid, [('paidon','=',paidon), ('name', '>=', date_from), ('name', '<=', date_to), ('employee_id', '=', employee.id),
				('project_id', 'not in', exclude_project_ids.ids),'|',('state','=','counted'),('slip_id','in',slips)], context=context)))	
		
		att_ids = att_line_pool.search(cr, uid, [('paidon','=',paidon), ('name', '>=', date_from), ('name', '<=', date_to), 
			('employee_id', '=', employee.id),'|',('slip_id','=',False),('slip_id','in',slips)], context=context)
		att_ids = list(set(att_ids) - set(set2))
		
		for att_id in att_ids:
			att = att_line_pool.browse(cr, uid, att_id, context=context)
			atts = {
				'name' : att.name,
				'center_id' : att.center_id.id,
				'post_id' : att.post_id.id,
				'employee_id' : att.employee_id.id,
				'action' : att.action,
				'action_desc' : att.action_desc,
				'state' : att.state,
				'paidon' : att.paidon,
				'slip_id' : att.slip_id.id,
				'project_id' : att.project_id.id or False,
			}
			res +=[atts]	
		
		return res
	
	def get_worked_day_lines(self, cr, uid, ids, employee_id, paidon, contract_id, date_from, date_to, exclude_project_ids, context=None):
		"""
		@param contract_ids: list of contract id
		@return: returns a list of dict containing the input that should be applied for the given contract between date_from and date_to
		"""

		def was_on_leave(employee_id, datetime_day, context=None):
			res = False
			day = datetime_day.strftime("%Y-%m-%d")
			holiday_ids = self.pool.get('hr.holidays').search(cr, uid, [('state','=','validate'),('employee_id','=',employee_id),('type','=','remove'),('date_from','<=',day),('date_to','>=',day)])
			if holiday_ids:
				res = self.pool.get('hr.holidays').browse(cr, uid, holiday_ids, context=context)[0].holiday_status_id.name
			return res
		
		def pending_salary(project_id, day, context=None):
			res = False
			#day = datetime_day.strftime("%Y-%m-%d")
			pending_ids = self.pool.get('project.salary.pending').search(cr, uid, [('project_id','=',project_id),('state','=','block'),('date_from','<=',day),('date_to','>=',day)])
			if pending_ids:
				res = True
			return res
			
		if ids:
			att_obj = self.pool.get('sos.guard.attendance')
			att_ids = att_obj.search(cr, uid, [('slip_id','=',ids[0])])
			#if att_ids:
			#	att_obj.write(cr,uid,att_ids,{'state':'draft'},context=context)
		
		result_dict = {}		
		seq = 1
		day_from = datetime.strptime(date_from,"%Y-%m-%d")
		day_to = datetime.strptime(date_to,"%Y-%m-%d")
		nb_of_days = (day_to - day_from).days + 1
		
		if exclude_project_ids:
			duty_ids = self.pool.get('sos.guard.attendance').search(cr, uid, [('employee_id','=',employee_id.id),('name', '>=', date_from),('name','<=',date_to),
				('project_id', 'not in', exclude_project_ids.ids),('paidon','=',paidon),'|',('slip_id','=',False),('slip_id','in',ids)])
		else:
			duty_ids = self.pool.get('sos.guard.attendance').search(cr, uid, [('employee_id','=',employee_id.id),('name', '>=', date_from),('name','<=',date_to),
				('paidon','=',paidon),'|',('slip_id','=',False),('slip_id','in',ids)])

		for duty in self.pool.get('sos.guard.attendance').browse(cr, uid, duty_ids, context=context):
			if duty.action  == 'absent':
				continue
			if duty.action in ('present','double'):
				duty_type='regular'
			else:
				duty_type='extra'
				
			#is_pending = pending_salary(duty.project_id.id, duty.name, context=context)
			
			#if not is_pending:
			code = str(duty.post_id.id) + '_' + duty_type

			if not code in result_dict:
				inv = self.pool.get('account.move.line').search(cr,uid,[('post_id', '=', duty.post_id.id),('journal_id','=',1)], order="id desc", limit=1, context=context)
				result_dict[code] = {
					'post_id': duty.post_id.id,
					'project_id': duty.project_id.id,
					'center_id': duty.center_id.id,
					'employee_id': employee_id.id,
					'sequence': seq,
					'code': duty_type,
					'number_of_days': 0.0,
					'total_days': nb_of_days,
					'contract_id': contract_id,
					'move_line_id': (paidon and inv and inv[0] ) or False,
				}				
				seq += 1
			if duty.action in ('present','extra'):
				result_dict[code]['number_of_days'] += 1.0
			if duty.action in ('double','extra_double'):
				result_dict[code]['number_of_days'] += 2.0
				
		result = [value for code, value in result_dict.items()]	
		
		abl_incentive = False
		abl_incentive_amt = 0
		abl_days = sum([line['number_of_days'] for line in result if line['project_id'] == 26])
		if abl_days > 0:
			abl_incentive = True
		
		# For pose Wise Calculation	
		#	for line in result:
		#		if line['project_id'] == 26:
		#			incentive_invoice = self.pool.get('account.invoice').search(cr,uid,[('incentive','=',True),('post_id','=',line['post_id']),('date_invoice','>=',date_from),('date_invoice','<=',date_to)],context=context)																																																																									
		#			if incentive_invoice:
		#				incentive_rec = self.pool.get('account.invoice').browse(cr,uid,incentive_invoice, context=context)
		#				days = 0
		#				duty_ids = self.pool.get('sos.guard.attendance').search(cr, uid, [('name', '>=', date_from),('name','<=',date_to),('post_id','=',line['post_id'])],context=context)
		#				for duty in self.pool.get('sos.guard.attendance').browse(cr, uid, duty_ids, context=context):
		#					if duty.action in ('present','extra'):
		#						days += 1.0
		#					if duty.action in ('double','extra_double'):
		#						days += 2.0	
		#				abl_incentive_amt += ((incentive_rec.amount_untaxed * 1.00) / days) * line['number_of_days']
		
		# For Over all calculation 2300 % 31=74.193 for month of June 2016
		#	abl_incentive_amt += 76.667 * abl_days

		return result,abl_incentive,abl_incentive_amt

	def get_inputs(self, cr, uid, contract_ids, date_from, date_to, employee, context=None):
		res = []
		contract_obj = self.pool.get('guards.contract')
		rule_obj = self.pool.get('hr.salary.rule')
		arrears_obj = self.pool.get('guards.arrears')
		
		structure_ids = contract_obj.get_all_structures(cr, uid, contract_ids, context=context)
		rule_ids = self.pool.get('hr.payroll.structure').get_all_rules(cr, uid, structure_ids, context=context)
		sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]
			
		for contract in contract_obj.browse(cr, uid, contract_ids, context=context):
			for rule in rule_obj.browse(cr, uid, sorted_rule_ids, context=context):
				if rule.input_ids:					
					for input in rule.input_ids:
						arr_amt = ''
						arr_id = arrears_obj.search(cr, uid, [('employee_id', '=', employee.id),('name', '=', input.code),('date', '>=', date_from),('date', '<=', date_to),('state', '=', 'confirm')], context=context)
						if arr_id:
							arr_amt = arrears_obj.browse(cr, uid,arr_id)[0].amount	 
						inputs = {
							'name': input.name,
							'code': input.code,
							'contract_id': contract.id,
							'amount': arr_amt or 0,
							'sequence': 10,
						}
						res += [inputs]		
		return res

	def get_payslip_lines(self, cr, uid, employee_id, contract_ids, payslip_id, context):
		def _sum_salary_rule_category(localdict, category, amount):
			if category.parent_id:
				localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
			localdict['categories'].dict[category.code] = category.code in localdict['categories'].dict and localdict['categories'].dict[category.code] + amount or amount
			return localdict

		class BrowsableObject(object):
			def __init__(self, pool, cr, uid, employee_id, dict):
				self.pool = pool
				self.cr = cr
				self.uid = uid
				self.employee_id = employee_id
				self.dict = dict

			def __getattr__(self, attr):
				return attr in self.dict and self.dict.__getitem__(attr) or 0.0

		class InputLine(BrowsableObject):
			"""a class that will be used into the python code, mainly for usability purposes"""
			def sum(self, code, from_date, to_date=None):
				if to_date is None:
					to_date = datetime.now().strftime('%Y-%m-%d')
				result = 0.0
				self.cr.execute("SELECT sum(amount) as sum\
					FROM guards_payslip as hp, hr_payslip_input as pi \
					WHERE hp.employee_id = %s AND hp.state = 'done' \
					AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
					(self.employee_id, from_date, to_date, code))
				res = self.cr.fetchone()[0]
				return res or 0.0

		class WorkedDays(BrowsableObject):
			"""a class that will be used into the python code, mainly for usability purposes"""
			def _sum(self, code, from_date, to_date=None):
				if to_date is None:
					to_date = datetime.now().strftime('%Y-%m-%d')
				result = 0.0
				self.cr.execute("SELECT sum(number_of_days) as number_of_days, sum(number_of_hours) as number_of_hours\
					FROM guards_payslip as hp, guards_payslip_worked_days as pi \
					WHERE hp.employee_id = %s AND hp.state = 'done'\
					AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
					(self.employee_id, from_date, to_date, code))
				return self.cr.fetchone()

			def sum(self, code, from_date, to_date=None):
				res = self._sum(code, from_date, to_date)
				return res and res[0] or 0.0

			def sum_hours(self, code, from_date, to_date=None):
				res = self._sum(code, from_date, to_date)
				return res and res[1] or 0.0

		class Payslips(BrowsableObject):
			"""a class that will be used into the python code, mainly for usability purposes"""

			def sum(self, code, from_date, to_date=None):
				if to_date is None:
					to_date = datetime.now().strftime('%Y-%m-%d')
				self.cr.execute("SELECT sum(case when hp.credit_note = False then (pl.total) else (-pl.total) end)\
					FROM guards_payslip as hp, guards_payslip_line as pl \
					WHERE hp.employee_id = %s AND hp.state = 'done' \
					AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pl.slip_id AND pl.code = %s",
					(self.employee_id, from_date, to_date, code))
				res = self.cr.fetchone()
				return res and res[0] or 0.0

		#we keep a dict with the result because a value can be overwritten by another rule with the same code
		result_dict = {}
		rules = {}
		categories_dict = {}
		blacklist = []
		payslip_obj = self.pool.get('guards.payslip')
		inputs_obj = self.pool.get('guards.payslip.worked_days')
		obj_rule = self.pool.get('hr.salary.rule')
		payslip = payslip_obj.browse(cr, uid, payslip_id, context=context)
		worked_days = {}
		
		for worked_days_line in payslip.worked_days_line_ids:
			worked_days['seq'+str(worked_days_line.sequence)] = worked_days_line
		
		inputs = {}
		for input_line in payslip.input_line_ids:
			inputs[input_line.code] = input_line
		
		counter = 1    
		categories_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, categories_dict)
		input_obj = InputLine(self.pool, cr, uid, payslip.employee_id.id, inputs)
		worked_days_obj = WorkedDays(self.pool, cr, uid, payslip.employee_id.id, worked_days)
		payslip_obj = Payslips(self.pool, cr, uid, payslip.employee_id.id, payslip)
		rules_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, rules)

		localdict = {'categories': categories_obj, 'rules': rules_obj, 'payslip': payslip_obj, 'worked_days': worked_days_obj, 'inputs': input_obj,'counter': counter}
		#localdict = {'categories': categories_obj, 'rules': rules_obj, 'payslip': payslip_obj, 'worked_days': worked_days_obj,'counter': counter}
		#get the ids of the structures on the contracts and their parent id as well
		structure_ids = self.pool.get('guards.contract').get_all_structures(cr, uid, contract_ids, context=context)
		#get the rules of the structure and thier children
		rule_ids = self.pool.get('hr.payroll.structure').get_all_rules(cr, uid, structure_ids, context=context)
		#run the rules by sequence
		sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]

		for contract in self.pool.get('guards.contract').browse(cr, uid, contract_ids, context=context):
			employee = employee_id
			localdict.update({'employee': employee, 'contract': contract})
			for rule in obj_rule.browse(cr, uid, sorted_rule_ids, context=context):
				if rule.is_loop:					
					while counter <= len(worked_days):
						key = rule.code + '-' + str(contract.id) + '-' + str(counter)
						localdict['result'] = None
						localdict['result_qty'] = 1.0
						#check if the rule can be applied
						if obj_rule.satisfy_condition(cr, uid, rule.id, localdict, context=context) and rule.id not in blacklist:
							#compute the amount of the rule
							
							amount, qty, rate = obj_rule.compute_rule(cr, uid, rule.id, localdict, context=context)
							#check if there is already a rule computed with that code
							previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
							#set/overwrite the amount computed for this rule in the localdict
							
							tot_rule = previous_amount + amount * qty 
							localdict[rule.code] = tot_rule
							rules[rule.code] = rule
							#sum the amount for its salary category
							localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
							#create/overwrite the rule in the temporary results
							
							result_dict[key] = {
								'salary_rule_id': rule.id,
								'contract_id': contract.id,
								'name': rule.name,
								'code': rule.code,
								'category_id': rule.category_id.id,
								'sequence': rule.sequence,
								'appears_on_payslip': rule.appears_on_payslip,
								'condition_select': rule.condition_select,
								'condition_python': rule.condition_python,
								'condition_range': rule.condition_range,
								'condition_range_min': rule.condition_range_min,
								'condition_range_max': rule.condition_range_max,
								'amount_select': rule.amount_select,
								'amount_fix': rule.amount_fix,
								'amount_python_compute': rule.amount_python_compute,
								'amount_percentage': rule.amount_percentage,
								'amount_percentage_base': rule.amount_percentage_base,
								'register_id': rule.register_id.id,
								'amount': amount,
								'employee_id': payslip.employee_id.id,
								'quantity': qty,
								'rate': rate,
								'post_id': worked_days['seq'+str(counter)].post_id.id,
								'move_line_id': worked_days['seq'+str(counter)].move_line_id and worked_days['seq'+str(counter)].move_line_id.id,
							}
							counter += 1
							localdict['counter'] = counter
						else:
							#blacklist this rule and its children
							blacklist += [id for id, seq in self.pool.get('hr.salary.rule')._recursive_search_of_rules(cr, uid, [rule], context=context)]
				else:
					key = rule.code + '-' + str(contract.id)
					localdict['result'] = None
					localdict['result_qty'] = 1.0
					localdict['result_rate'] = None
					#check if the rule can be applied
					if obj_rule.satisfy_condition(cr, uid, rule.id, localdict, context=context) and rule.id not in blacklist:
						#compute the amount of the rule
						
						amount, qty, rate = obj_rule.compute_rule(cr, uid, rule.id, localdict, context=context)
						#check if there is already a rule computed with that code
						previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
						#set/overwrite the amount computed for this rule in the localdict
						
						tot_rule = amount * qty * rate / 100.0
						localdict[rule.code] = tot_rule
						rules[rule.code] = rule
						#sum the amount for its salary category
						localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
						#create/overwrite the rule in the temporary results
					
						result_dict[key] = {
							'salary_rule_id': rule.id,
							'contract_id': contract.id,
							'name': rule.name,
							'code': rule.code,
							'category_id': rule.category_id.id,
							'sequence': rule.sequence,
							'appears_on_payslip': rule.appears_on_payslip,
							'condition_select': rule.condition_select,
							'condition_python': rule.condition_python,
							'condition_range': rule.condition_range,
							'condition_range_min': rule.condition_range_min,
							'condition_range_max': rule.condition_range_max,
							'amount_select': rule.amount_select,
							'amount_fix': rule.amount_fix,
							'amount_python_compute': rule.amount_python_compute,
							'amount_percentage': rule.amount_percentage,
							'amount_percentage_base': rule.amount_percentage_base,
							'register_id': rule.register_id.id,
							'amount': amount,
							'employee_id': payslip.employee_id.id,
							'post_id': payslip.employee_id.current_post_id.id,
							'quantity': qty,
							'rate': rate,
					
						}
					
					else:
						#blacklist this rule and its children
						blacklist += [id for id, seq in self.pool.get('hr.salary.rule')._recursive_search_of_rules(cr, uid, [rule], context=context)]

		result = [value for code, value in result_dict.items()]
		return result

	def update_slip(self, cr, uid, ids, date_from, date_to, employee_id=False, paidon=False, contract_id=False, context=None):		
			
		empolyee_obj = self.pool.get('hr.employee')
		worked_days_obj = self.pool.get('guards.payslip.worked_days')
		
		if context is None:
			context = {}
	
		old_worked_days_ids = ids and worked_days_obj.search(cr, uid, [('payslip_id', '=', ids[0])], context=context) or False
		if old_worked_days_ids:
			sql = "delete from guards_payslip_worked_days where id in %s"
			cr.execute(sql, (tuple(old_worked_days_ids),))
				
		
		employee_id = empolyee_obj.browse(cr, uid, employee_id, context=context)
		
		worked_days_line_ids = self.get_worked_day_lines(cr, uid, ids, employee_id, paidon, contract_id, date_from, date_to, context=context)
		#attendance_line_ids = self.get_attendance_lines(cr, uid, ids, employee_id, date_from, date_to, paidon, ids, context=context)
		
		for item in worked_days_line_ids:
			item.update({'payslip_id':ids[0]})
			worked_days_obj.create(cr,uid,item,context=context)

	def on_change_employee_id(self, cr, uid, ids, date_from, date_to, employee_id=False, paidon=False, contract_id=False, exclude_project_ids= False, context=None):		
		
		empolyee_obj = self.pool.get('hr.employee')
		contract_obj = self.pool.get('guards.contract')
		worked_days_obj = self.pool.get('guards.payslip.worked_days')
		input_obj = self.pool.get('guards.payslip.input')

		if context is None:
			context = {}
			
		#delete old worked days lines
		old_worked_days_ids = ids and worked_days_obj.search(cr, uid, [('payslip_id', '=', ids[0])], context=context) or False
		if old_worked_days_ids:
			
			sql = "delete from guards_payslip_worked_days where id in %s"
			cr.execute(sql, (tuple(old_worked_days_ids),))
		#	worked_days_obj.unlink(cr, uid, old_worked_days_ids, context=context)

		#delete old input lines
		old_input_ids = ids and input_obj.search(cr, uid, [('payslip_id', '=', ids[0])], context=context) or False
		if old_input_ids:
			sql = "delete from guards_payslip_input where id in %s"
			cr.execute(sql, (tuple(old_input_ids),))
		#	input_obj.unlink(cr, uid, old_input_ids, context=context)

		
		#defaults
		res = {'value':{
				'line_ids':[],
				'input_line_ids': [],
				'worked_days_line_ids': [],
				#'details_by_salary_head':[], TODO put me back
				'name':'',
				'contract_id': False,
				'struct_id': False,
				'bank': False,
				'bankacctitle': False,
				'bankacc': False,
				'accowner': False,
				'paidon': paidon,
				}
		}
		if (not employee_id) or (not date_from) or (not date_to):
			return res
		ttyme = datetime.fromtimestamp(time.mktime(time.strptime(date_from, "%Y-%m-%d")))
		employee = empolyee_obj.browse(cr, uid, employee_id, context=context)
				
		res['value'].update({
			'name': _('Salary Slip of %s for %s') % (employee.name, tools.ustr(ttyme.strftime('%B-%Y'))),
			'company_id': employee.company_id.id,
			'bank': employee.bank_id.id,
			'bankacctitle': employee.bankacctitle,
			'bankacc': employee.bankacc,
			'accowner': employee.accowner,
			'paidon': paidon,
			'post_id': employee.current_post_id.id,
			'project_id': employee.current_post_id.project_id.id,
			'center_id': employee.current_post_id.center_id.id,
		})
		
		if contract_id:
			contract_ids = [contract_id]
		else:	
			contract_ids = [employee.guard_contract_id.id]	
		contract_record = contract_obj.browse(cr, uid, contract_ids, context=context)[0]
		res['value'].update({
			'contract_id': contract_record and contract_record.id or False
		})
		
		struct_record = contract_record and contract_record.struct_id or False
		if not struct_record:
			return res
		res['value'].update({
			'struct_id': struct_record.id,
		})
		
		#computation of the salary input
		worked_days_line_ids,abl_incentive,abl_incentive_amt = self.get_worked_day_lines(cr, uid, ids, employee, paidon, contract_record.id, date_from, date_to, exclude_project_ids, context=context)
		attendance_line_ids = self.get_attendance_lines(cr, uid, ids, employee, date_from, date_to, paidon, ids, exclude_project_ids, context=context)
		input_line_ids = self.get_inputs(cr, uid, contract_ids, date_from, date_to, employee, context=context)		
					
		res['value'].update({
			'worked_days_line_ids': worked_days_line_ids,
			'input_line_ids': input_line_ids,
			'attendance_line_ids': attendance_line_ids,
			'abl_incentive': abl_incentive,
			'abl_incentive_amt': abl_incentive_amt,
		})
		
		return res

	def on_change_contract_id(self, cr, uid, ids, date_from, date_to, employee_id=False, paidon=False, contract_id=False, context=None):
		
		#TODO it seems to be the mess in the onchanges, we should have onchange_employee => onchange_contract => doing all the things
		if context is None:
			context = {}		
		contract_obj = self.pool.get('guards.contract')
		res = self.on_change_employee_id(cr, uid, ids, date_from=date_from, date_to=date_to, employee_id=employee_id, paidon=paidon, contract_id=contract_id, context=context)
		journal_id = contract_id and contract_obj.browse(cr, uid, contract_id, context=context).journal_id.id or False
		res['value'].update({'journal_id': journal_id, 'line_ids': [],})
		
		context = dict(context)
		context.update({'contract': True})
		if not contract_id:
			res['value'].update({'struct_id': False})
		
		return res
		
	#store = {				
	#		'guards.payslip': (lambda self,cr,uid,ids,c=None: ids, ['line_ids','state','note'], 10),				
	#		'guards.payslip.line': (_get_payslips,None,10),
	#	}),
	#	'company_id': lambda self, cr, uid, context: self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,


class guards_arrears(osv.osv):		
	_name = "guards.arrears"
		
	_columns = {
		'employee_id': fields.many2one('hr.employee', 'Guard', required=True),
		'center_id': fields.many2one('sos.center', string='Center', required=True, readonly=False, ondelete='restrict'),
		'amount': fields.float(string='Amount', required=True),
		'description': fields.text('Description'),
		'date': fields.date('Period', required=True),		
		'name': fields.selection([('BNS','Bonus of Employee'),('ADV','Advance against Salary'),('ARS','Arrear'),('FINE','Fine Deduction'),('GLD','Guard Loan Deduction'),('GSD','Guard Security Deduction'),],'Category', required=True),
		'state': fields.selection([('draft','Draft'),('confirm','Confirm'),('done','Paid'),('cancel','Cancelled'),],'Status'),
		'slip_id':fields.many2one('guards.payslip', 'Pay Slip', ondelete='cascade'),
		}
	_defaults = {
		'state': 'draft',
		}
	
	def arrears_validate(self, cr, uid, ids, context=None):		
		if context is None:
			context = {}		
		self.write(cr, uid, ids, {'state':'confirm'}, context=context)
		return True    
	
	def arrears_cancel(self, cr, uid, ids, context=None):			
		if context is None:
			context = {}		
		self.write(cr, uid, ids, {'state':'cancel'}, context=context)
		return True 
		
	def arrear_approve(self, cr, uid, ids, context=None):
		if context is None:
			context = {}		
		self.write(cr,uid,ids,{'state':'confirm'},context=context)
		return True 						
		
guards_arrears()

class project_salary_pending(osv.osv):		
	_name = "project.salary.pending"
		
	_columns = {
		'project_id': fields.many2one('sos.project', string='Poject', required=True, readonly=False, ondelete='restrict'),
		'name': fields.text('Description'),
		'date_from': fields.date('Date From', readonly=True, states={'block': [('readonly', False)]}, required=True),
		'date_to': fields.date('Date To', readonly=True, states={'block': [('readonly', False)]}, required=True),
		'state': fields.selection([('draft','Draft'),('block','Block'),('open','Open')],'Status'),		
		}
	_defaults = {
		'state': 'draft',
		}
	
	def pending_open(self, cr, uid, ids, context=None):		
		pending_pool = self.pool.get('project.salary.pending')		
		if context is None:
			context = {}		
		self.write(cr, uid, ids, {'state':'open'}, context=context)
		for rec in pending_pool.browse(cr,uid,ids):
			sql="""select distinct employee_id from sos_guard_attendance where project_id = %s and name >= %s and name <= %s"""
			cr.execute(sql,(rec.project_id.id,rec.date_from,rec.date_to))		
			res= cr.dictfetchall()
			for emp in res:
				self.pool.get('hr.guard')._check_draft_attendance(cr,uid,emp['employee_id'],context=context)			
				
		return True    
	
	def pending_block(self, cr, uid, ids, context=None):		
		pending_pool = self.pool.get('project.salary.pending')
		if context is None:
			context = {}		
		self.write(cr, uid, ids, {'state':'block'}, context=context)
			
		for rec in pending_pool.browse(cr,uid,ids):
			sql="""select distinct employee_id from sos_guard_attendance where project_id = %s and name >= %s and name <= %s"""
			cr.execute(sql,(rec.project_id.id,rec.date_from,rec.date_to))		
			res= cr.dictfetchall()
			for emp in res:
				self.pool.get('hr.guard')._check_draft_attendance(cr,uid,emp['employee_id'],context=context)			
		
		return True    
	
project_salary_pending()
