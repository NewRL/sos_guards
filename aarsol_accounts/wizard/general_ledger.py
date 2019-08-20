
import time
import pdb
from datetime import date, datetime, timedelta
from dateutil import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

#SARFRAZ
#class AccountReportGeneralLedger(models.TransientModel):
#	_inherit = "account.report.general.ledger"
#
#	#dimension_ids = fields.Many2one('ledger.dimension.lines', string='Dimensions')
#	dimension_ids = fields.One2many('ledger.dimension.lines', 'ac_id',string='Dimensions')
#	dimension_group = fields.Many2one('analytic.dimension',string="Group by Dimension")
		
#	@api.multi
#	def pre_print_report(self, data):
#		data = super(AccountReportGeneralLedger,self).pre_print_report(data)
#		data['form'].update(self.read(['dimension_ids','dimension_group'])[0])
#		return data
        
	
        
class LedgerDimension(models.TransientModel):
	_name = "ledger.dimension"
	
	name = fields.Char('Description')	
	ac_lines = fields.One2many('ledger.dimension.lines','ac_id',string="Dimensions")   

class LedgerDimensionLines(models.TransientModel):
	_name = "ledger.dimension.lines"
	
	ac_id = fields.Many2one('account.report.general.ledger',string="Ledger Dimension")   
	nd_id = fields.Many2one('analytic.dimension',string="Dimension",required=True,)   
	code_id = fields.Many2one('analytic.code',string="Analytic Value",required=True,)   	
	
	
