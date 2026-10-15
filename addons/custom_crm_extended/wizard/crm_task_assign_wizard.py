# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class CrmTaskAssignWizard(models.TransientModel):
    _name = 'crm.task.assign.wizard'
    _description = 'Assign Work Wizard'

    assigned_to_id = fields.Many2one('res.users', string='Assign To', required=True)
    name = fields.Char(string='Task Title', required=True)
    date_deadline = fields.Date(string='Deadline / Target Date')
    instructions = fields.Text(string='Work Details / Instructions')
    attachment_name = fields.Char(string='Attachment Name')
    attachment_file = fields.Binary(string='Attachment', attachment=True)

    # Company (Optional)
    company_id = fields.Many2one('res.company', string='Company')

    # Entity Linking (Optional)
    related_model = fields.Selection([
        ('crm.lead', 'Lead / Opportunity'),
        ('sale.order', 'Quotation / Sale Order'),
        ('res.partner', 'Customer / Contact'),
        ('equipment.master', 'Equipment Master'),
        ('service.ticket', 'Service Ticket'),
        ('amc.contract', 'AMC Contract'),
    ], string='Related Entity')

    lead_id = fields.Many2one('crm.lead', string='Linked Lead')
    order_id = fields.Many2one('sale.order', string='Linked Quotation')
    partner_id = fields.Many2one('res.partner', string='Linked Customer')
    equipment_id = fields.Many2one('equipment.master', string='Linked Equipment')
    ticket_id = fields.Many2one('service.ticket', string='Linked Service Ticket')
    amc_id = fields.Many2one('amc.contract', string='Linked AMC Contract')

    # Recurrence (Optional)
    is_recurring = fields.Boolean(string='Recurring Task', default=False)
    recurrence_period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], string='Repeat Every', default='monthly')
    recurrence_end_date = fields.Date(string='Repeat Until')

    @api.onchange('related_model')
    def _onchange_related_model(self):
        self.lead_id = False
        self.order_id = False
        self.partner_id = False
        self.equipment_id = False
        self.ticket_id = False
        self.amc_id = False

    def action_assign_work(self):
        self.ensure_one()

        # Check sequential delivery: if employee already has active pending task, queue this one (is_unlocked = False)
        active_tasks_count = self.env['crm.task.management'].search_count([
            ('assigned_to_id', '=', self.assigned_to_id.id),
            ('state', 'in', ['pending', 'in_progress']),
            ('is_unlocked', '=', True),
        ])
        is_unlocked = (active_tasks_count == 0)

        # 1. Create the persistent task management record
        task_rec = self.env['crm.task.management'].create({
            'name': self.name.strip(),
            'assigned_to_id': self.assigned_to_id.id,
            'assigned_by_id': self.env.user.id,
            'date_assigned': fields.Datetime.now(),
            'date_deadline': self.date_deadline,
            'instructions': self.instructions.strip() if self.instructions else '',
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
            'is_recurring': self.is_recurring,
            'recurrence_period': self.recurrence_period if self.is_recurring else False,
            'recurrence_end_date': self.recurrence_end_date if self.is_recurring else False,
            'is_unlocked': is_unlocked,
            'state': 'pending',
        })

        # 2. Notification message to assigned user with Direct Clickable Link
        sender = self.env.user
        target_partner = self.assigned_to_id.partner_id
        if target_partner:
            # Direct mail message with clickable task link
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
            task_link = f"{base_url}/web#id={task_rec.id}&model=crm.task.management&view_type=form"

            attachment_ids = []
            if self.attachment_name and self.attachment_file:
                try:
                    att = self.env['ir.attachment'].sudo().create({
                        'name': self.attachment_name,
                        'datas': self.attachment_file,
                        'res_model': 'crm.task.management',
                        'res_id': task_rec.id,
                        'type': 'binary',
                    })
                    if att:
                        attachment_ids.append(att.id)
                except Exception:
                    pass

            body_text = f"<b>New Task Assigned:</b> <a href='{task_link}' style='font-weight:bold; color:#0b3d91;'>{self.name.strip()}</a>"
            if self.instructions:
                body_text += f"<br/>{self.instructions}"
            if task_rec.related_record_display:
                body_text += f"<br/><b>Related:</b> {task_rec.related_record_display}"
            if self.attachment_name:
                body_text += f"<br/><small style='color:#0b3d91;'>📎 Attached: {self.attachment_name}</small>"
            body_text += f"<br/><p><a href='{task_link}' class='btn btn-sm btn-primary' style='display:inline-block; padding:4px 10px; background:#0b3d91; color:#ffffff; border-radius:4px; text-decoration:none;'>Open Task Details</a></p>"

            msg_vals = {
                'subject': f"Task: {self.name.strip()}",
                'body': body_text,
                'model': 'crm.task.management',
                'res_id': task_rec.id,
                'message_type': 'comment',
                'author_id': sender.partner_id.id if sender.partner_id else False,
                'partner_ids': [(6, 0, [target_partner.id])],
            }
            if attachment_ids:
                msg_vals['attachment_ids'] = [(6, 0, attachment_ids)]
            self.env['mail.message'].sudo().create(msg_vals)

        return {'type': 'ir.actions.act_window_close'}

