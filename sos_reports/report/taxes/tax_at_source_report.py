import pdb
import time
from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import relativedelta
from pytz import timezone
import pytz, datetime
from dateutil import tz
from openerp import api, fields, models, _
from openerp.exceptions import UserError


class TaxAtSourceReport(models.AbstractModel):
	_name = 'report.sos_reports.tax_at_source_report'
	
	def get_date_formate(self,sdate):
		ss = datetime.datetime.strptime(sdate,'%Y-%m-%d')
		return ss.strftime('%d %b %Y')

	@api.model
	def _get_report_values(self, docids, data=None):
		date_from = data['form']['date_from'] and data['form']['date_from']
		date_to = data['form']['date_to'] and data['form']['date_to']
		line_ids = []
		res = {}
		payments = False
		invoice_total = 0
		tax_total = 0

		payments = self.env['account.payment'].search([('payment_type','=','inbound'),('journal_id','=',30),('payment_date','>=',date_from),('payment_date','<=',date_to)])
		if payments:
			for payment in payments:
				invoice = payment.invoice_ids and payment.invoice_ids[0] or False
				tax_total = tax_total + payment.amount
				invoice_total = invoice_total + invoice.amount_total
				line = {
					'payment' : payment.name,
					'date' : payment.payment_date,
					'invoice' : invoice.number if invoice else '',
					'invoice_amount' : invoice.amount_total if invoice else 0,
					'invoice_month' : invoice.for_month if invoice else '',
					'project' : invoice.project_id.name if invoice else '',
					'tax_at_source' : payment.amount,
				}
				line_ids.append(line)
		res = line_ids
		report = self.env['ir.actions.report']._get_report_from_name('sos_reports.tax_at_source_report')
		docargs = {
			"doc_ids": self._ids,
			"doc_model": report.model,
			"time": time,
			"data": data['form'],
			"docs": self,
			"get_date_formate" : self.get_date_formate,
			'rep_data' : res,
			'tax_total' : tax_total,
			'invoice_total': invoice_total,
		}
		return docargs