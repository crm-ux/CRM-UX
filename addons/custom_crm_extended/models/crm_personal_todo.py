# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class CrmPersonalTodo(models.Model):
    _name = 'crm.personal.todo'
    _description = 'Personal Private To-Do'
    _order = 'priority desc, target_date asc, id desc'

    name = fields.Char(string='To-Do Title', required=True)
    user_id = fields.Many2one(
        'res.users', 
        string='Owner', 
        default=lambda self: self.env.user, 
        required=True, 
        readonly=True,
        index=True
    )
    
    target_date = fields.Date(string='Target Date')
    reminder_time = fields.Float(string='Reminder Time')
    reminder_datetime = fields.Datetime(string='Reminder Date & Time')
    reminder_sent = fields.Boolean(string='Reminder Sent', default=False)
    
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Priority', default='2')

    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('complaint', 'Issue / Hold'),
    ], string='Status', default='pending', required=True)

    notes = fields.Text(string='Personal Notes / Checklist')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'crm_personal_todo_ir_attachment_rel',
        'todo_id',
        'attachment_id',
        string='Attachments'
    )
    todo_attachment_ids = fields.One2many(
        'crm.personal.todo.attachment',
        'todo_id',
        string='To-Do Attachments'
    )

    is_overdue = fields.Boolean(string='Overdue', compute='_compute_is_overdue', store=False)

    @api.depends('target_date', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            if rec.target_date and rec.target_date < today and rec.state in ('pending', 'in_progress'):
                rec.is_overdue = True
            else:
                rec.is_overdue = False

    issue_reason = fields.Text(string='Issue / Blocker Details')

    def action_set_done(self):
        self.write({'state': 'done'})

    def action_set_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_set_pending(self):
        self.write({'state': 'pending'})

    def action_set_complaint(self):
        self.write({'state': 'complaint'})

    @api.model
    def check_todo_reminders_cron(self):
        """Dispatches real-time bus notifications to employees for their due personal to-dos."""
        now = fields.Datetime.now()
        due_todos = self.sudo().search([
            ('reminder_sent', '=', False),
            ('reminder_datetime', '!=', False),
            ('reminder_datetime', '<=', now),
            ('state', 'in', ('pending', 'in_progress')),
        ])
        for todo in due_todos:
            # Send notification via bus specifically to the owner
            channel = todo.user_id.partner_id
            if channel:
                self.env['bus.bus']._sendone(channel, 'crm.personal.todo/reminder', {
                    'title': _('Personal To-Do Reminder'),
                    'message': todo.name,
                    'todo_id': todo.id,
                })
            todo.write({'reminder_sent': True})
        return True


class CrmPersonalTodoAttachment(models.Model):
    _name = 'crm.personal.todo.attachment'
    _description = 'Personal To-Do Attachment'

    todo_id = fields.Many2one('crm.personal.todo', string='To-Do', ondelete='cascade')
    name = fields.Char(string='File Name')
    file = fields.Binary(string='File', attachment=True)

    def action_preview_file(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/crm.personal.todo.attachment/{self.id}/file/{self.name}?download=false',
            'target': 'new',
        }

    def action_download_file(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/crm.personal.todo.attachment/{self.id}/file/{self.name}?download=true',
            'target': 'self',
        }
