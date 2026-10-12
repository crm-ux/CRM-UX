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
    attachment_file = fields.Binary(string='Attachment', attachment=True)

    # Employee Action & Reporting
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('complaint', 'Issue / Complaint'),
    ], string='Status', default='pending', required=True, tracking=True)

    completion_remarks = fields.Text(string='Work Completion Remarks', tracking=True)
    complaint_notes = fields.Text(string='Complaint / Issue Faced', tracking=True)

    # Permission flag for manager-level fields
    can_edit_manager_fields = fields.Boolean(
        string='Can Edit Manager Fields',
        compute='_compute_can_edit_manager_fields'
    )

    @api.depends('assigned_to_id', 'assigned_by_id')
    def _compute_can_edit_manager_fields(self):
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system') or current_user.id == 2
        for record in self:
            if is_admin:
                record.can_edit_manager_fields = True
                continue

            # If current user is the employee assigned to the task (not an admin)
            if record.assigned_to_id and record.assigned_to_id.id == current_user.id:
                record.can_edit_manager_fields = False
                continue

            # If current user is the assigner (manager)
            if record.assigned_by_id and record.assigned_by_id.id == current_user.id:
                record.can_edit_manager_fields = True
                continue

            # Check if assigned_to_id is in current user's subordinates hierarchy
            if record.assigned_to_id:
                subordinate_ids = current_user._get_all_subordinates().ids
                if record.assigned_to_id.id in subordinate_ids:
                    record.can_edit_manager_fields = True
                    continue

            # Check if current user is higher manager or has subordinates
            record.can_edit_manager_fields = current_user.check_can_assign_task()

    def write(self, vals):
        manager_fields = {'name', 'assigned_to_id', 'date_deadline', 'instructions', 'attachment_file', 'attachment_name'}
        if any(f in vals for f in manager_fields):
            current_user = self.env.user
            is_admin = current_user.has_group('base.group_system') or current_user.id == 2
            if not is_admin:
                for record in self:
                    if not record.can_edit_manager_fields:
                        from odoo.exceptions import UserError
                        raise UserError(_("You are not authorized to modify task instructions, title, or deadline. Only managers/administrators can change these details."))
        return super(CrmTaskManagement, self).write(vals)

    def action_preview_task_attachment(self):
        """Action button for Task Attachment preview."""
        return True

    @api.model
    def action_get_task_attachment_preview(self, res_id=None, raw_b64=None, filename=None, field_name='attachment_file'):
        """Extract preview content for Task Management attachments (delegates to universal parser)."""
        if res_id:
            rec = self.sudo().browse(int(res_id))
            if rec.exists():
                raw_b64 = rec.attachment_file or raw_b64
                filename = rec.attachment_name or filename

        return self.env['equipment.master'].action_get_invoice_preview_content(
            res_id=False, raw_b64=raw_b64, filename=filename
        )

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


