

from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
import random
import pdb
from odoo import tools
from datetime import datetime, timedelta
from openerp.tools.amount_to_text_en import english_number


class AttrDict(dict):
	"""A dictionary with attribute-style access. It maps attribute access to the real dictionary.  """
	def __init__(self, init={}):
		dict.__init__(self, init)

	def __getstate__(self):
		return self.__dict__.items()

	def __setstate__(self, items):
		for key, val in items:
			self.__dict__[key] = val

	def __repr__(self):
		return "%s(%s)" % (self.__class__.__name__, dict.__repr__(self))

	def __setitem__(self, key, value):
		return super(AttrDict, self).__setitem__(key, value)

	def __getitem__(self, name):
		item = super(AttrDict, self).__getitem__(name)
		return AttrDict(item) if type(item) == dict else item

	def __delitem__(self, name):
		return super(AttrDict, self).__delitem__(name)

	__getattr__ = __getitem__
	__setattr__ = __setitem__

	def copy(self):
		ch = AttrDict(self)
		return ch


class Parser(report_sxw.rml_parse):
	def __init__(self, cr, uid, name, context):
		super(Parser, self).__init__(cr, uid, name, context)
		
		self.localcontext.update({
			'get_serial': self.get_serial,
			'amount_in_word': self.amount_in_word,
			'get_projects': self.get_projects,	
			'get_arrear_line': self.get_arrear_line,
			'get_totals': self.get_totals,
		})
		self.totals = AttrDict({'serial':0})
		
	def amount_in_word(self, amount_total):
		
		number = '%.2f' % amount_total
		number = round(amount_total)
		units_name = 'PKR'
		list = str(number).split('.')
		start_word = english_number(int(list[0]))
		return ' '.join(filter(None, [start_word, units_name]))
		
		#return amount_to_text(amount_total,'en','PKR')
		
	def get_serial(self):
		self.totals.serial = self.totals.serial+1
		return self.totals.serial
		
	def get_arrear_line(self, partner_id):
		#arrear_obj = self.pool.get('arrear.invoice')
		#ids = arrear_obj.search(self.cr,self.uid,[('partner_id','=',partner_id),('state','=','done')])
		#arrears = arrear_obj.browse(self.cr,self.uid,ids)

		self.totals = AttrDict({'arrear':0})
		res = []
		#for arrear in arrears:
		#	res.append({
		#		'name': arrear.name,
		#		'residual': arrear.residual,				
		#	})
		#	self.totals.arrear += arrear.residual			
	
		return res
	
	def get_projects(self):
		proj_obj = self.pool.get('sos.project')
		projects = proj_obj.browse(self.cr,self.uid,[])
		res = []
		for project in projects:
			res[project.id]=project.name
		return res
	
	def get_totals(self,code):		
		return self.totals[code]
	
