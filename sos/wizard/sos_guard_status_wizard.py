import pdb
from odoo import tools
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class sos_guard_status_wizard(models.TransientModel):
	_name = 'sos.guard.status.wizard'
	_description = 'This Will update the Guard Status in Different States'
	
		
	status = fields.Selection( [('draft','Draft'),('done','Done'), ('hr_review','Hr Review'), ('mi_review','MI Review'),('complete','Complete')],'Status')
	
	@api.one
	def guard_status(self):
		## user zahid = 10, aamir=5 Access Only for Zahid, zegum = 83
		
		#if self.env.user.id in (1,5,10,83) :
		employee_id = self.env['hr.employee'].browse(self._context.get('active_id',False))
		current_status = employee_id.profile_status
		employee_id.profile_status = self.status
		
		#else:
		#	raise UserError(_('You are not Authorized to do this! Please Contact To Mr.Zahid'))			
		return {'type': 'ir.actions.act_window_close'}	 
	
