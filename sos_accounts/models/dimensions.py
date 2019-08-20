import pdb
import time
import math
from datetime import date
from datetime import datetime
from datetime import timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from dateutil import relativedelta
from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api, _
from odoo import netsvc
from lxml import etree
from odoo.tools import config
from odoo.addons.analytic_structure.MetaAnalytic import MetaAnalytic


class SOSProject(models.Model, metaclass = MetaAnalytic):
	_name = 'sos.project'
	_inherit = 'sos.project'
	_bound_dimension_id = False

	_dimension = {
		'name': 'Project',
		'column': 'analytic_project_id',
		'ref_module': 'sos',
		'rel_code' : 'accountno',
		'rel_name' : 'accountno',		
	}
	
	
	
class SOSRegion(models.Model, metaclass = MetaAnalytic):
	_name = 'sos.region'
	_inherit = 'sos.region'

	_dimension = {
		'name': 'Region',
		'column': 'analytic_region_id',
		'ref_module': 'sos',
		'rel_code' : 'code',
		'rel_name' : 'code',		
	}


# Remark By Sarfraz, moved to the AARSOL ACCOUNTS dimensions.py

#class AccountBankStatementLine(models.Model):
#	_name = "account.bank.statement.line"
#	_inherit = "account.bank.statement.line"
#	__metaclass__ = MetaAnalytic
#	_analytic = True

	
#	@api.one
#	@api.depends('d_bin')
#	def _get_d_bin(self):
#		if self.d_bin:
#			self.H10_id = int(self.d_bin[0:1])
#			self.H9_id = int(self.d_bin[1:2])
#			self.H8_id = int(self.d_bin[2:3])
#			self.H7_id = int(self.d_bin[3:4])
#			self.H6_id = int(self.d_bin[4:5])
#			self.H5_id = int(self.d_bin[5:6])
#			self.H4_id = int(self.d_bin[6:7])
#			self.H3_id = int(self.d_bin[7:8])
#			self.H2_id = int(self.d_bin[8:9])
#			self.H1_id = int(self.d_bin[9:10])
#
#	d_bin = fields.Char("Binary Dimension")
#	H1_id = fields.Integer(compute='_get_d_bin')
#	H2_id = fields.Integer(compute='_get_d_bin')
#	H3_id = fields.Integer(compute='_get_d_bin')
#	H4_id = fields.Integer(compute='_get_d_bin')
#	H5_id = fields.Integer(compute='_get_d_bin')
#	H6_id = fields.Integer(compute='_get_d_bin')
#	H7_id = fields.Integer(compute='_get_d_bin')
#	H8_id = fields.Integer(compute='_get_d_bin')
#	H9_id = fields.Integer(compute='_get_d_bin')
#	H10_id = fields.Integer(compute='_get_d_bin')
#
#
#	def format_field_name(self, ordering, prefix='a', suffix='id'):
#		"""Return an analytic field's name from its slot, prefix and suffix."""
#		return '{pre}{n}_{suf}'.format(pre=prefix, n=ordering, suf=suffix)
#																					
#	@api.onchange('account_id')
#	def _onchange_account_id(self):		
#		if self.account_id:
#			dimensions = self.account_id.nd_ids
#			
#			structures = self.env['analytic.structure'].search([('nd_id','in',dimensions.ids)])
#			used = [int(structure.ordering) for structure in structures]
#			
#			number = 0
#			size = int(config.get_misc('analytic', 'analytic_size', 10))
#			for n in xrange(1, size + 1):
#				#src = self.format_field_name(n,'H','id')
#				if n in used:
#					src_data = 1
#					number += math.pow(2,n-1)
#				#else:
#				#	src_data = 0
#
#			self.d_bin = bin(int(number))[2:].zfill(10)		
#
#	def fast_counterpart_creation(self):
#		for st_line in self:
#			# Technical functionality to automatically reconcile by creating a new move line
#			vals = {
#				'name': st_line.name,
#				'debit': st_line.amount < 0 and -st_line.amount or 0.0,
#				'credit': st_line.amount > 0 and st_line.amount or 0.0,
#				'account_id': st_line.account_id.id,
#			}
#		
#			size = int(config.get_misc('analytic', 'analytic_size', 10))
#			for n in xrange(1, size + 1):
#				fld = self.format_field_name(n,'a','id')
#				vals.update({fld:eval('st_line.'+fld).id})
#			vals.update({'d_bin':st_line.d_bin})
#
#			st_line.process_reconciliation(new_aml_dicts=[vals])
#

class AccountAssetDepreciationLine(models.Model):
	_name = 'account.asset.depreciation.line'
	_inherit = 'account.asset.depreciation.line'

	@api.multi
	def create_move(self, post_move=True):
		created_moves = self.env['account.move']
		
		model_rec = self.env['ir.model'].search([('model','=','account.asset.depreciation.line')])
		auto_entries = self.env['auto.dimensions.entry'].search([('model_id','=',model_rec.id),('active','=',True)],order='sequence')

		for line in self:
			depreciation_date = self.env.context.get('depreciation_date') or line.depreciation_date or fields.Date.context_today(self)
			company_currency = line.asset_id.company_id.currency_id
			current_currency = line.asset_id.currency_id
			amount = current_currency.compute(line.amount, company_currency)
			sign = (line.asset_id.category_id.journal_id.type == 'purchase' or line.asset_id.category_id.journal_id.type == 'sale' and 1) or -1
			asset_name = line.asset_id.name + ' (%s/%s)' % (line.sequence, line.asset_id.method_number)
			reference = line.asset_id.code
			journal_id = line.asset_id.category_id.journal_id.id
			partner_id = line.asset_id.partner_id.id
			categ_type = line.asset_id.category_id.type
			debit_account = line.asset_id.category_id.account_asset_id.id
			credit_account = line.asset_id.category_id.account_depreciation_id.id
			
			move_line_1 = {
				'name': asset_name,
				'account_id': credit_account,
				'debit': 0.0,
				'credit': amount,
				'journal_id': journal_id,
				'partner_id': partner_id,
				'currency_id': company_currency != current_currency and current_currency.id or False,
				'amount_currency': company_currency != current_currency and - sign * line.amount or 0.0,
				'analytic_account_id': line.asset_id.category_id.account_analytic_id.id if categ_type == 'sale' else False,
				'date': depreciation_date,
			}
			number = 0
			for auto_entry in auto_entries:
				move_line_1.update({auto_entry.dst_col.name : eval(auto_entry.src_fnc)})
				ans = self.env['analytic.structure'].search([('model_name','=','account_move_line'),('nd_id','=',auto_entry.dimension_id.id)])	
				number += math.pow(2,int(ans.ordering)-1)			
			move_line_1.update({'d_bin' : bin(int(number))[2:].zfill(10)})
				
			move_line_2 = {
				'name': asset_name,
				'account_id': debit_account,
				'credit': 0.0,
				'debit': amount,
				'journal_id': journal_id,
				'partner_id': partner_id,
				'currency_id': company_currency != current_currency and current_currency.id or False,
				'amount_currency': company_currency != current_currency and sign * line.amount or 0.0,
				'analytic_account_id': line.asset_id.category_id.account_analytic_id.id if categ_type == 'purchase' else False,
				'date': depreciation_date,
			}
			number = 0
			for auto_entry in auto_entries:
				move_line_2.update({auto_entry.dst_col.name : eval(auto_entry.src_fnc)})				
				ans = self.env['analytic.structure'].search([('model_name','=','account_move_line'),('nd_id','=',auto_entry.dimension_id.id)])	
				number += math.pow(2,int(ans.ordering)-1)			
			move_line_2.update({'d_bin' : bin(int(number))[2:].zfill(10)})

			move_vals = {
				'ref': reference,
				'date': depreciation_date or False,
				'journal_id': line.asset_id.category_id.journal_id.id,
				'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
				'asset_id': line.asset_id.id,
				}
			move = self.env['account.move'].create(move_vals)
			line.write({'move_id': move.id, 'move_check': True})
			created_moves |= move

		if post_move and created_moves:
			created_moves.post()
		return [x.id for x in created_moves]









			
