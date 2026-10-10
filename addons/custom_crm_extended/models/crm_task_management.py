# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class CrmTaskManagement(models.Model):
    _name = 'crm.task.management'
    _description = 'Task Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_assigned desc, id desc'

    name = fields.Char(string='Task Title', required=True, tracking=True)
    assigned_to_id = fields.Many2one('res.users', string='Assigned Employee', required=True, tracking=True)
    assigned_by_id = fields.Many2one('res.users', string='Assigned By (Manager/Owner)', default=lambda self: self.env.user, readonly=True, tracking=True)
    date_assigned = fields.Datetime(string='Assigned Date', default=fields.Datetime.now, readonly=True, tracking=True)
    date_deadline = fields.Date(string='Deadline', tracking=True)
    
    # Manager Instructions
    instructions = fields.Text(string='Work Details / Instructions')
    attachment_name = fields.Char(string='Attachment Name')
    attachment_file = fields.Binary(string='Attachment (Drawings, PO, PDF)', attachment=True)

    # Employee Action & Reporting
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('complaint', 'Issue / Complaint'),
    ], string='Status', default='pending', required=True, tracking=True)

    completion_remarks = fields.Text(string='Work Completion Remarks', tracking=True)
    complaint_notes = fields.Text(string='Complaint / Issue Faced', tracking=True)

    # Security domain rule helper
    def check_user_can_create(self):
        u = self.env.user
        if u.has_group('base.group_system') or u.id == 2:
            return True
        # Check if user is a manager (has subordinates)
        has_sub_users = bool(self.env['res.users'].sudo().search_count([('crm_manager_id', '=', u.id), ('id', '!=', u.id)]))
        if has_sub_users:
            return True
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', u.id)], limit=1)
        if emp and bool(self.env['hr.employee'].sudo().search_count([('parent_id', '=', emp.id), ('id', '!=', emp.id)])):
            return True
        return False
