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

    # Recurrence & Series Tracking
    is_recurring = fields.Boolean(string='Recurring Task', default=False, tracking=True)
    recurrence_period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], string='Repeat Every', default='monthly', tracking=True)
    recurrence_end_date = fields.Date(string='Repeat Until', tracking=True)
    recurring_group_id = fields.Char(string='Recurring Series Group ID', index=True)

    # Sequential Task Delivery (Unlocks for employee only when prior task is Done)
    is_unlocked = fields.Boolean(string='Is Active / Unlocked', default=True, tracking=True)

    # Work Instructions & Attachments (Supports 1 or N bulk attachments)
    instructions = fields.Text(string='Work Details / Instructions')
    attachment_name = fields.Char(string='Attachment Name')
    attachment_file = fields.Binary(string='Attachment', attachment=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'crm_task_management_ir_attachment_rel',
        'task_id',
        'attachment_id',
        string='Attachments'
    )
    task_attachment_ids = fields.One2many(
        'crm.task.attachment',
        'task_id',
        string='Task Attachments'
    )

    # Employee Action & Reporting
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('complaint', 'Issue / Complaint'),
    ], string='Status', default='pending', required=True, tracking=True)

    completion_remarks = fields.Html(string='Work Completion Remarks', sanitize=False)
    complaint_notes = fields.Text(string='Complaint / Issue Faced', tracking=True)

    # Color index for Calendar Event strip matching exact status:
    # 1: Amber / Gold (Pending)
    # 2: Vibrant Blue (In Progress)
    # 10: Emerald Green (Done)
    # 9: Crimson Red (Issue / Complaint)
    task_color = fields.Integer(string='Task Color', compute='_compute_task_color', store=True)

    @api.depends('state')
    def _compute_task_color(self):
        color_map = {
            'pending': 1,      # Amber / Gold
            'in_progress': 2,  # Vibrant Blue
            'done': 10,        # Emerald Green
            'complaint': 9,    # Crimson Red
        }
        for rec in self:
            rec.task_color = color_map.get(rec.state, 1)

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
        is_admin = current_user.has_group('base.group_system') or current_user.has_group('base.group_erp_manager') or current_user.id in (1, 2)
        for record in self:
            if is_admin:
                record.can_edit_manager_fields = True
                continue
            # The person who assigned the task can always edit
            if record.assigned_by_id and record.assigned_by_id.id == current_user.id:
                record.can_edit_manager_fields = True
                continue
            # Senior managers/supervisors of the assignee can edit
            subordinates = current_user._get_all_subordinates().ids if hasattr(current_user, '_get_all_subordinates') else []
            if record.assigned_to_id and record.assigned_to_id.id in subordinates:
                record.can_edit_manager_fields = True
                continue
            # Assigned employee CANNOT change deadline or task instructions
            record.can_edit_manager_fields = False

    def write(self, vals):
        manager_fields = {'name', 'assigned_to_id', 'date_deadline', 'instructions', 'attachment_file', 'attachment_name', 'attachment_ids', 'task_attachment_ids', 'related_model'}
        if any(f in vals for f in manager_fields):
            current_user = self.env.user
            is_admin = current_user.has_group('base.group_system') or current_user.has_group('base.group_erp_manager') or current_user.id in (1, 2)
            if not is_admin:
                for record in self:
                    if not record.can_edit_manager_fields:
                        raise UserError(_("You are not authorized to modify task instructions, title, or deadline. Only the task assigner or senior manager can change these details."))

        # Validation: Task deadline cannot be set to a date earlier than its assigned date
        if 'date_deadline' in vals and vals['date_deadline']:
            deadline_str = str(vals['date_deadline'])[:10]
            new_deadline = fields.Date.from_string(deadline_str)
            for record in self:
                if record.date_assigned:
                    assigned_date = record.date_assigned.date()
                    if new_deadline < assigned_date:
                        raise UserError(_(
                            "Cannot reschedule task to %s. Target deadline cannot be earlier than the task assignment date (%s)."
                        ) % (new_deadline.strftime('%d-%m-%Y'), assigned_date.strftime('%d-%m-%Y')))

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

        # Auto-heal: If an existing task has is_recurring=True, ensure its future occurrences are pre-created
        if 'is_recurring' in vals or 'recurrence_period' in vals or 'date_deadline' in vals or 'recurrence_end_date' in vals:
            for rec in self:
                if rec.is_recurring and rec.date_deadline:
                    rec._generate_future_recurring_occurrences()

        return res

    def _generate_future_recurring_occurrences(self):
        """Generates future occurrences for this recurring task if they do not exist already."""
        self.ensure_one()
        if not self.is_recurring or not self.date_deadline or not self.recurrence_period:
            return

        target_deadline = fields.Date.from_string(str(self.date_deadline)[:10])
        today = fields.Date.today()
        target_day = target_deadline.day

        current_date = today
        try:
            current_date = current_date.replace(day=target_day)
        except ValueError:
            pass

        if current_date <= today:
            current_date = current_date + relativedelta(months=1)

        count = 0
        while current_date < target_deadline and count < 36:
            # Check if this occurrence already exists
            existing = self.sudo().search_count([
                ('name', '=', self.name),
                ('assigned_to_id', '=', self.assigned_to_id.id),
                ('date_deadline', '=', current_date),
            ])
            if not existing:
                self.sudo().create({
                    'name': self.name,
                    'assigned_to_id': self.assigned_to_id.id,
                    'assigned_by_id': self.assigned_by_id.id if self.assigned_by_id else self.env.user.id,
                    'date_assigned': fields.Datetime.now(),
                    'date_deadline': current_date,
                    'instructions': self.instructions or '',
                    'attachment_name': self.attachment_name or '',
                    'attachment_file': self.attachment_file or False,
                    'company_id': self.company_id.id if self.company_id else False,
                    'related_model': self.related_model or False,
                    'lead_id': self.lead_id.id if self.lead_id else False,
                    'order_id': self.order_id.id if self.order_id else False,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                    'equipment_id': self.equipment_id.id if self.equipment_id else False,
                    'ticket_id': self.ticket_id.id if self.ticket_id else False,
                    'amc_id': self.amc_id.id if self.amc_id else False,
                    'is_recurring': False,
                    'recurrence_period': False,
                    'recurrence_end_date': False,
                    'is_unlocked': True,
                    'state': 'pending',
                })
            current_date = current_date + relativedelta(months=1)
            count += 1

    @api.model
    def action_auto_generate_all_recurring(self):
        """Finds all recurring tasks that don't have future occurrences yet and creates them."""
        recurring_tasks = self.sudo().search([
            ('is_recurring', '=', True),
            ('date_deadline', '!=', False),
            ('recurrence_period', '!=', False),
        ])
        for task in recurring_tasks:
            task._generate_future_recurring_occurrences()
        return True

    def action_finish_entire_series(self):
        """Marks this task as Done and completes the whole series by removing remaining future pending tasks."""
        self.ensure_one()
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system') or current_user.has_group('base.group_erp_manager') or current_user.id in (1, 2)
        if not is_admin and not self.can_edit_manager_fields:
            raise UserError(_("Only the task assigner, senior manager, or admin can finish the recurring series early."))

        # 1. Mark current task as Done
        self.sudo().write({'state': 'done', 'is_recurring': False})

        # 2. Remove all future pending tasks for this series
        domain = [
            ('assigned_to_id', '=', self.assigned_to_id.id),
            ('name', '=', self.name),
            ('state', '=', 'pending'),
            ('id', '!=', self.id),
        ]
        if self.date_deadline:
            domain.append(('date_deadline', '>=', self.date_deadline))

        future_tasks = self.sudo().search(domain)
        count = len(future_tasks)
        if future_tasks:
            future_tasks.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Series Finished Early'),
                'message': _('Current task marked as Done and %d future pending task(s) removed.') % count,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_cancel_future_series(self):
        """Cancels/deletes all remaining pending future tasks in this recurring series."""
        self.ensure_one()
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system') or current_user.has_group('base.group_erp_manager') or current_user.id in (1, 2)
        if not is_admin and not self.can_edit_manager_fields:
            raise UserError(_("Only the task assigner, senior manager, or admin can cancel future recurring tasks."))

        # Find all future pending tasks matching this series
        domain = [
            ('assigned_to_id', '=', self.assigned_to_id.id),
            ('name', '=', self.name),
            ('state', '=', 'pending'),
            ('id', '!=', self.id),
        ]
        if self.date_deadline:
            domain.append(('date_deadline', '>=', self.date_deadline))

        future_tasks = self.sudo().search(domain)
        count = len(future_tasks)
        if future_tasks:
            future_tasks.unlink()

        # Stop recurrence on current task as well
        self.write({'is_recurring': False})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recurring Series Stopped'),
                'message': _('Successfully removed %d remaining future task(s) from the calendar.') % count,
                'type': 'success',
                'sticky': False,
            }
        }

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

    def action_open_full_detail_form(self):
        """Opens the full detailed task form view from the calendar quick popup."""
        self.ensure_one()
        form_view_id = self.env.ref('custom_crm_extended.view_crm_task_management_form', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': self.name or 'Task Details',
            'res_model': 'crm.task.management',
            'res_id': self.id,
            'views': [(form_view_id.id if form_view_id else False, 'form')],
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


class CrmTaskAttachment(models.Model):
    _name = 'crm.task.attachment'
    _description = 'Task Attachment'

    task_id = fields.Many2one('crm.task.management', string='Task', ondelete='cascade', required=True)
    name = fields.Char(string='File Name', required=True)
    file = fields.Binary(string='File', attachment=True, required=True)

    def action_preview_file(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/crm.task.attachment/{self.id}/file/{self.name}?download=false',
            'target': 'new',
        }

    def action_download_file(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/crm.task.attachment/{self.id}/file/{self.name}?download=true',
            'target': 'self',
        }



