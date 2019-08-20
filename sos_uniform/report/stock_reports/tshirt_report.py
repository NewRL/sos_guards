import pdb
import time
from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import relativedelta
from pytz import timezone
import pytz, datetime
from dateutil import tz
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ReportTshirt(models.AbstractModel):
	_name = 'report.sos_uniform.report_tshirt'
	_description = 'SOS T-Shirt Report'
	
	def get_date_formate(self,sdate):
		ss = datetime.datetime.strptime(sdate,'%Y-%m-%d')
		return ss.strftime('%d %b %Y')
			
	@api.model
	def get_report_values(self, docids, data=None):
		date_from = data['form']['date_from'] and data['form']['date_from']
		date_to = data['form']['date_to'] and data['form']['date_to']
		
		new_demands = False
		
		new_demand_list = []
		new_demand_small_total = 0
		new_demand_medium_total = 0
		new_demand_large_total = 0
		new_demand_extra_large_total = 0
		new_demand_ee_large_total = 0
		
		#***** New Deployments *****#
		new_demands = self.env['sos.uniform.demand'].search([('date','>=',date_from),('date','<=',date_to),('dm_type','=','new_deployment')])
		
		if new_demands:
			new_demand_list = []
			for demand in new_demands: 
				dispatch_lines = demand.uniform_dispatch_line.filtered(lambda x: x.product_id.id in (278, 279, 280, 281,282))
				if dispatch_lines:
					for line in dispatch_lines:
						res=({
							'date': demand.date,
							'post': demand.post_id and demand.post_id.name or False,
							'center': demand.center_id and demand.center_id.name or False,
							'type': 'New Deployment',
							'demand_no' : demand.name,
							'small' : line.product_qty if line.product_id.id == 278 else '',
							'medium' : line.product_qty if line.product_id.id == 279 else '',
							'large' : line.product_qty if line.product_id.id == 280 else '',
							'extra_large' : line.product_qty if line.product_id.id == 281 else '',
							'ee_large' : line.product_qty if line.product_id.id == 282 else '',
						})
						new_demand_list.append(res)
						
						##Totals
						if line.product_id.id == 278:
							new_demand_small_total = new_demand_small_total + line.product_qty
						if line.product_id.id == 279:
							new_demand_medium_total = new_demand_medium_total + line.product_qty
						if line.product_id.id == 280:
							new_demand_large_total = new_demand_large_total + line.product_qty
						if line.product_id.id == 281:
							new_demand_extra_large_total = new_demand_extra_large_total + line.product_qty
						if line.product_id.id == 282:
							new_demand_ee_large_total = new_demand_ee_large_total + line.product_qty	
							
		
		
		#***** Complaints *****#
		complain_demands = False
		
		complain_demand_list = []
		complain_demand_small_total = 0
		complain_demand_medium_total = 0
		complain_demand_large_total = 0
		complain_demand_extra_large_total = 0
		complain_demand_ee_large_total = 0
		
		new_demands = self.env['sos.uniform.demand'].search([('date','>=',date_from),('date','<=',date_to),('dm_type','=','complain')])
		
		if complain_demands:
			complain_demand_list = []
			for demand in complain_demands: 
				dispatch_lines = demand.uniform_dispatch_line.filtered(lambda x: x.product_id.id in (278, 279, 280, 281,282))
				if dispatch_lines:
					for line in dispatch_lines:
						res=({
							'date': demand.date,
							'post': demand.post_id and demand.post_id.name or False,
							'center': demand.center_id and demand.center_id.name or False,
							'type': 'Complaint',
							'demand_no' : demand.name,
							'small' : line.product_qty if line.product_id.id == 278 else '',
							'medium' : line.product_qty if line.product_id.id == 279 else '',
							'large' : line.product_qty if line.product_id.id == 280 else '',
							'extra_large' : line.product_qty if line.product_id.id == 281 else '',
							'ee_large' : line.product_qty if line.product_id.id == 282 else '',
						})
						complain_demand_list.append(res)
						
						##Totals
						if line.product_id.id == 278:
							complain_demand_small_total = complain_demand_small_total + line.product_qty
						if line.product_id.id == 279:
							complain_demand_medium_total = complain_demand_medium_total + line.product_qty
						if line.product_id.id == 280:
							complain_demand_large_total = complain_demand_large_total + line.product_qty
						if line.product_id.id == 281:
							complain_demand_extra_large_total = complain_demand_extra_large_total + line.product_qty
						if line.product_id.id == 282:
							complain_demand_ee_large_total = complain_demand_ee_large_total + line.product_qty	
							
		
		#*****  Additional Guards *****#
		add_guard_demands = False
		
		add_guard_demand_list = []
		add_guard_demand_small_total = 0
		add_guard_demand_medium_total = 0
		add_guard_demand_large_total = 0
		add_guard_demand_extra_large_total = 0
		add_guard_demand_ee_large_total = 0
		
		add_guard_demands = self.env['sos.uniform.demand'].search([('date','>=',date_from),('date','<=',date_to),('dm_type','=','additional_guard')])
		
		if add_guard_demands:
			add_guard_demand_list = []
			for demand in add_guard_demands: 
				dispatch_lines = demand.uniform_dispatch_line.filtered(lambda x: x.product_id.id in (278, 279,280,281,282))
				if dispatch_lines:
					for line in dispatch_lines:
						res=({
							'date': demand.date,
							'post': demand.post_id and demand.post_id.name or False,
							'center': demand.center_id and demand.center_id.name or False,
							'type': 'Additional Guard',
							'demand_no' : demand.name,
							'small' : line.product_qty if line.product_id.id == 278 else '',
							'medium' : line.product_qty if line.product_id.id == 279 else '',
							'large' : line.product_qty if line.product_id.id == 280 else '',
							'extra_large' : line.product_qty if line.product_id.id == 281 else '',
							'ee_large' : line.product_qty if line.product_id.id == 282 else '',
						})
						add_guard_demand_list.append(res)
						
						##Totals
						if line.product_id.id == 278:
							add_guard_demand_small_total = add_guard_demand_small_total + line.product_qty
						if line.product_id.id == 279:
							add_guard_demand_medium_total = add_guard_demand_medium_total + line.product_qty
						if line.product_id.id == 280:
							add_guard_demand_large_total = add_guard_demand_large_total + line.product_qty
						if line.product_id.id == 281:
							add_guard_demand_extra_large_total = add_guard_demand_extra_large_total + line.product_qty
						if line.product_id.id == 282:
							add_guard_demand_ee_large_total = add_guard_demand_ee_large_total + line.product_qty												
		
		
		
		#*****  Replacement *****#
		replacement_demands = False
		
		replacement_demand_list = []
		replacement_demand_small_total = 0
		replacement_demand_medium_total = 0
		replacement_demand_large_total = 0
		replacement_demand_extra_large_total = 0
		replacement_demand_ee_large_total = 0
		
		replacement_demands = self.env['sos.uniform.demand'].search([('date','>=',date_from),('date','<=',date_to),('dm_type','=','replacement')])
		
		if replacement_demands:
			replacement_demand_list = []
			for demand in replacement_demands: 
				dispatch_lines = demand.uniform_dispatch_line.filtered(lambda x: x.product_id.id in (278, 279,280,281,282))
				if dispatch_lines:
					for line in dispatch_lines:
						res=({
							'date': demand.date,
							'post': demand.post_id and demand.post_id.name or False,
							'center': demand.center_id and demand.center_id.name or False,
							'type': 'Replacement',
							'demand_no' : demand.name,
							'small' : line.product_qty if line.product_id.id == 278 else '',
							'medium' : line.product_qty if line.product_id.id == 279 else '',
							'large' : line.product_qty if line.product_id.id == 280 else '',
							'extra_large' : line.product_qty if line.product_id.id == 281 else '',
							'ee_large' : line.product_qty if line.product_id.id == 282 else '',
						})
						replacement_demand_list.append(res)
						
						##Totals
						if line.product_id.id == 278:
							replacement_demand_small_total = replacement_demand_small_total + line.product_qty
						if line.product_id.id == 279:
							replacement_demand_medium_total = replacement_demand_medium_total + line.product_qty
						if line.product_id.id == 280:
							replacement_demand_large_total = replacement_demand_large_total + line.product_qty
						if line.product_id.id == 281:
							replacement_demand_extra_large_total = replacement_demand_extra_large_total + line.product_qty
						if line.product_id.id == 282:
							replacement_demand_ee_large_total = replacement_demand_ee_large_total + line.product_qty												
		
		
		
		report = self.env['ir.actions.report']._get_report_from_name('sos_uniform.report_tshirt')
		return {
			"doc_ids": self._ids,
			"doc_model": report.model,
			"time": time,
			"data": data['form'],
			"docs": self,
			'New_Demands' : new_demand_list,
			'New_Demand_Total': {'total_small': new_demand_small_total, 'total_medium' : new_demand_medium_total, 'total_large' : new_demand_large_total, 'total_extra_large' : new_demand_extra_large_total,'total_ee_large' : new_demand_ee_large_total},
			'Complain_Demands' : complain_demand_list,
			'Complain_Demand_Total': {'total_small': complain_demand_small_total, 'total_medium' : complain_demand_medium_total, 'total_large' : complain_demand_large_total, 'total_extra_large' : complain_demand_extra_large_total, 'total_ee_large' : complain_demand_ee_large_total},
			'Add_Guard_Demands' : add_guard_demand_list,
			'Add_Guard_Demand_Total': {'total_small': add_guard_demand_small_total, 'total_medium' : add_guard_demand_medium_total, 'total_large' : add_guard_demand_large_total, 'total_extra_large' : add_guard_demand_extra_large_total, 'total_ee_large' : add_guard_demand_ee_large_total},
			'Replacement_Demands' : replacement_demand_list,
			'Replacement_Demand_Total': {'total_small': replacement_demand_small_total, 'total_medium' : replacement_demand_medium_total, 'total_large' : replacement_demand_large_total, 'total_extra_large' : replacement_demand_extra_large_total, 'total_ee_large' : replacement_demand_ee_large_total},
			"get_date_formate" : self.get_date_formate,
		}
		
		
