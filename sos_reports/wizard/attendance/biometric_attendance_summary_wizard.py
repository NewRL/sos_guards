import time
import pdb
from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import relativedelta
from odoo import api, fields, models, _

class BiometricAttendanceSummaryWizard(models.TransientModel):
	_name = "biometric.attendance.summary.wizard"
	_description = "BioMetric Attendance Report"
	
	start_date = fields.Date("Date From",default=lambda *a: str(datetime.now() + relativedelta.relativedelta(day=1))[:10])
	end_date = fields.Date("Date To",default=lambda *a: str(datetime.now() + relativedelta.relativedelta(day=31))[:10])	
	employee_ids = fields.Many2many('hr.employee', string='Filter on Employee', help="""Only selected Employee will be printed. Leave empty to print all Employee.""")
	department_ids = fields.Many2many('hr.department', string='Filter on Department', help="""Only selected Department will be printed. Leave empty to print all Department.""")                           		
	project_ids = fields.Many2many('sos.project', string='Filter on Projects', help="""Only selected Projects will be printed. Leave empty to print all Projects.""")
	center_ids = fields.Many2many('sos.center', string='Filter on Centers', help="""Only selected Centers will be printed. Leave empty to print all Centers.""")
	generate_month_entries = fields.Boolean('Generate Month Entres', defaul=False)
	
	@api.multi
	def print_report(self):		
		self.ensure_one()
		[data] = self.read()
		datas = {
			'ids': [],
			'model': 'sos.guard.attendance1',
			'form': data
		}
		
		return self.env.ref('sos_reports.action_report_biometric_attendance_summary').with_context(landscape=True).report_action(self, data=datas, config=False)
