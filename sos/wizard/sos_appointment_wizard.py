import pdb
from odoo import tools
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class sos_appointmentdate_wizard(models.TransientModel):
	_name = 'sos.appointmentdate.wizard'
	_description = 'Appointment Date Wizard'
	
	appointmentdate = fields.Date('Appointment Date', readonly =False)
	cnic = fields.Char(string='CNIC')	
	
	
	@api.one
	@api.depends('cnic')	
	def _check_cnic(self):
		cnic_com = re.compile('^[0-9+]{5}-[0-9+]{7}-[0-9]{1}$')
		a = cnic_com.search(self.cnic)
		if a:
			return True
		else:	
			raise UserError(_("CNIC Format is Incorrect. Format Should like this 00000-0000000-0"))
		return True
		
	@api.one
	def change_appdate(self):
		## aamir=5 Access Only for Aamir
		## Zahid=10 Access Only for Zahid
		## Sami = 29 For Appointment change
		## Zegum = 83 For Appoinment change
		## Akamal = 39 For Cnic Change
		
		if self.env.user.id in (1,5,10,29,83,39):
			if self.appointmentdate:
				employee_id = self.env['hr.employee'].browse(self._context.get('active_id',False))
				old_appdate = employee_id.appointmentdate
				employee_id.appointmentdate = self.appointmentdate
			if self.cnic:
				employee_id = self.env['hr.employee'].browse(self._context.get('active_id',False))
				old_cnic = employee_id.cnic
				new_cnic = self.cnic
				employee_id.cnic = new_cnic	
		else:
			raise UserError(_('You are not Authorized to do this! Please Contact To Mr.Aamir Raza.'))			
		return {'type': 'ir.actions.act_window_close'}	 
	
