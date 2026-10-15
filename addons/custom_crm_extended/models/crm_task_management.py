# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class CrmTaskManagement(models.Model):
    _name = 'crm.task.management'
    _description = 'Task Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_deadline asc, id desc'

    name = fields.Char(string='Task Title', required=True, tracking=True)
    assigned_to_id = fields.Many2one('res.users', string='Assigned Employee', required=True, tracking=True)
    assigned_by_id = fields.Many2one('res.users', string='Assigned By', default=lambda self: self.env.user, readonly=True, tracking=True)
    date_assigned = fields.Datetime(string='Assigned Date', default=fields.Datetime.now, readonly=True, tracking=True)
    date_deadline = fields.Date(string='Deadline / Target Date', tracking=True)

    # Optional Multi-Company Scope
    company_id = fields.Many2one('res.company', string='Company', tracking=True)

    # Entity Linking (Optional)
    related_model = fields.Selection([
        ('crm.lead', 'Lead / Opportunity'),
        ('sale.order', 'Quotation / Sale Order'),
        ('res.partner', 'Customer / Contact'),
        ('equipment.master', 'Equipment Master'),
        ('service.ticket', 'Service Ticket'),
        ('amc.contract', 'AMC Contract'),
    ], string='Related Entity', tracking=True)
    related_res_id = fields.Integer(string='Related Record ID', tracking=True)
    related_record_display = fields.Char(string='Related Record', compute='_compute_related_record_display', store=True)

    # Specific Many2ones for clean UI selection
    lead_id = fields.Many2one('crm.lead', string='Linked Lead')
    order_id = fields.Many2one('sale.order', string='Linked Quotation')
    partner_id = fields.Many2one('res.partner', string='Linked Customer')
    equipment_id = fields.Many2one('equipment.master', string='Linked Equipment')
    ticket_id = fields.Many2one('service.ticket', string='Linked Service Ticket')
    amc_id = fields.Many2one('amc.contract', string='Linked AMC Contract')

    # Recurrence
    is_recurring = fields.Boolean(string='Recurring Task', default=False, tracking=True)
    recurrence_period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], string='Repeat Every', default='monthly', tracking=True)
    recurrence_end_date = fields.Date(string='Repeat Until', tracking=True)

    # Sequential Task Delivery (Unlocks for employee only when prior task is Done)
    is_unlocked = fields.Boolean(string='Is Active / Unlocked', default=True, tracking=True)

    # Work Instructions & Attachment
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

    # Permission flag for assigner/manager-level fields
    can_edit_manager_fields = fields.Boolean(
        string='Can Edit Assigner Fields',
        compute='_compute_can_edit_manager_fields'
    )

    @api.depends('related_model', 'lead_id', 'order_id', 'partner_id', 'equipment_id', 'ticket_id', 'amc_id')
    def _compute_related_record_display(self):
        for rec in self:
            label = ''
            if rec.related_model == 'crm.lead' and rec.lead_id:
                label = rec.lead_id.name or f"Lead #{rec.lead_id.id}"
                rec.related_res_id = rec.lead_id.id
            elif rec.related_model == 'sale.order' and rec.order_id:
                label = rec.order_id.name or f"Quote #{rec.order_id.id}"
                rec.related_res_id = rec.order_id.id
            elif rec.related_model == 'res.partner' and rec.partner_id:
                label = rec.partner_id.display_name or rec.partner_id.name or f"Customer #{rec.partner_id.id}"
                rec.related_res_id = rec.partner_id.id
            elif rec.related_model == 'equipment.master' and rec.equipment_id:
                label = f"{rec.equipment_id.equipment_id or ''} {rec.equipment_id.name.name if rec.equipment_id.name else ''}".strip()
                rec.related_res_id = rec.equipment_id.id
            elif rec.related_model == 'service.ticket' and rec.ticket_id:
                label = rec.ticket_id.ticket_id or f"Ticket #{rec.ticket_id.id}"
                rec.related_res_id = rec.ticket_id.id
            elif rec.related_model == 'amc.contract' and rec.amc_id:
                label = rec.amc_id.contract_id or f"AMC #{rec.amc_id.id}"
                rec.related_res_id = rec.amc_id.id
            rec.related_record_display = label

    @api.onchange('related_model')
    def _onchange_related_model(self):
        # Clear fields when entity type changes
        self.lead_id = False
        self.order_id = False
        self.partner_id = False
        self.equipment_id = False
        self.ticket_id = False
        self.amc_id = False
        self.related_res_id = 0

    @api.depends('assigned_to_id', 'assigned_by_id')
    def _compute_can_edit_manager_fields(self):
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system') or current_user.id == 2
        for record in self:
            if is_admin:
                record.can_edit_manager_fields = True
                continue
            # The person who assigned the task can always edit the instructions/deadline
            if record.assigned_by_id and record.assigned_by_id.id == current_user.id:
                record.can_edit_manager_fields = True
                continue
            # If current user is the assignee, they cannot edit instructions/deadline
            if record.assigned_to_id and record.assigned_to_id.id == current_user.id:
                record.can_edit_manager_fields = False
                continue
            # Managers above assignee can also edit
            subordinates = current_user._get_all_subordinates().ids if hasattr(current_user, '_get_all_subordinates') else []
            record.can_edit_manager_fields = bool(record.assigned_to_id and record.assigned_to_id.id in subordinates)

    def write(self, vals):
        manager_fields = {'name', 'assigned_to_id', 'date_deadline', 'instructions', 'attachment_file', 'attachment_name', 'related_model'}
        if any(f in vals for f in manager_fields):
            current_user = self.env.user
            is_admin = current_user.has_group('base.group_system') or current_user.id == 2
            if not is_admin:
                for record in self:
                    if not record.can_edit_manager_fields:
                        raise UserError(_("You are not authorized to modify task instructions, title, or deadline. Only the task assigner can change these details."))

        res = super(CrmTaskManagement, self).write(vals)

        # Handle Sequential Task Unlock and Recurrence on completion
        if 'state' in vals and vals['state'] == 'done':
            for rec in self:
                # 1. Unlock next pending task for this assignee if any was queued
                next_task = self.search([
                    ('assigned_to_id', '=', rec.assigned_to_id.id),
                    ('state', '=', 'pending'),
                    ('is_unlocked', '=', False),
                    ('id', '!=', rec.id)
                ], order='date_deadline asc, id asc', limit=1)
                if next_task:
                    next_task.write({'is_unlocked': True})

                # 2. If recurring task is marked done, generate next cycle
                if rec.is_recurring and rec.date_deadline:
                    next_deadline = rec.date_deadline
                    if rec.recurrence_period == 'daily':
                        next_deadline += relativedelta(days=1)
                    elif rec.recurrence_period == 'weekly':
                        next_deadline += relativedelta(weeks=1)
                    elif rec.recurrence_period == 'monthly':
                        next_deadline += relativedelta(months=1)
                    elif rec.recurrence_period == 'yearly':
                        next_deadline += relativedelta(years=1)

                    if not rec.recurrence_end_date or next_deadline <= rec.recurrence_end_date:
                        self.copy({
                            'state': 'pending',
                            'date_assigned': fields.Datetime.now(),
                            'date_deadline': next_deadline,
                            'completion_remarks': False,
                            'complaint_notes': False,
                            'is_unlocked': True,
                        })

        return res

    def action_open_related_record(self):
        """1-Click Smart Button to directly open the linked Lead, Quote, Equipment, Customer, etc."""
        self.ensure_one()
        model = self.related_model
        res_id = self.related_res_id
        if not model or not res_id:
            raise UserError(_("No related record is linked to this task."))

        view_type = 'form'
        action_name = self.related_record_display or "Linked Record"
        return {
            'type': 'ir.actions.act_window',
            'name': action_name,
            'res_model': model,
            'res_id': res_id,
            'views': [(False, view_type)],
            'target': 'current',
        }

    def action_preview_task_attachment(self):
        return True

    @api.model
    def action_get_task_attachment_preview(self, res_id=None, raw_b64=None, filename=None, field_name='attachment_file'):
        if res_id:
            rec = self.sudo().browse(int(res_id))
            if rec.exists():
                raw_b64 = rec.attachment_file or raw_b64
                filename = rec.attachment_name or filename

        return self.env['equipment.master'].action_get_invoice_preview_content(
            res_id=False, raw_b64=raw_b64, filename=filename
        )



