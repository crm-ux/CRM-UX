# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class CrmTaskAssignWizard(models.TransientModel):
    _name = 'crm.task.assign.wizard'
    _description = 'Assign Work Wizard'

    assigned_to_id = fields.Many2one('res.users', string='Assign To', required=True)
    name = fields.Char(string='Task Title', required=True)
    date_deadline = fields.Date(string='Deadline', default=fields.Date.today)
    instructions = fields.Text(string='Work Details / Instructions')
    attachment_name = fields.Char(string='Attachment Name')
    attachment_file = fields.Binary(string='Attachment', attachment=True)

    def action_assign_work(self):
        self.ensure_one()
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
            'state': 'pending',
        })

        # 2. Activity and notification to the assigned user
        sender = self.env.user
        target_partner = self.assigned_to_id.partner_id
        if target_partner:
            act_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
            if not act_type:
                act_type = self.env['mail.activity.type'].sudo().search([('res_model', 'in', ['res.partner', False])], limit=1)
            if not act_type:
                act_type = self.env['mail.activity.type'].sudo().search([], limit=1)

            if act_type:
                try:
                    self.env['mail.activity'].sudo().create({
                        'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'res.partner')], limit=1).id,
                        'res_id': target_partner.id,
                        'activity_type_id': act_type.id,
                        'summary': self.name.strip(),
                        'note': self.instructions or '',
                        'user_id': self.assigned_to_id.id,
                        'date_deadline': self.date_deadline or fields.Date.today(),
                    })
                except Exception:
                    pass

            # Direct mail message
            attachment_ids = []
            if self.attachment_name and self.attachment_file:
                try:
                    att = self.env['ir.attachment'].sudo().create({
                        'name': self.attachment_name,
                        'datas': self.attachment_file,
                        'res_model': 'res.partner',
                        'res_id': target_partner.id,
                        'type': 'binary',
                    })
                    if att:
                        attachment_ids.append(att.id)
                except Exception:
                    pass

            body_text = f"<b>New Task: {self.name.strip()}</b>"
            if self.instructions:
                body_text += f"<br/>{self.instructions}"
            if self.attachment_name:
                body_text += f"<br/><small style='color:#0b3d91;'>📎 Attached: {self.attachment_name}</small>"

            msg_vals = {
                'subject': self.name.strip(),
                'body': body_text,
                'model': 'res.partner',
                'res_id': target_partner.id,
                'message_type': 'comment',
                'author_id': sender.partner_id.id if sender.partner_id else False,
                'partner_ids': [(6, 0, [target_partner.id])],
            }
            if attachment_ids:
                msg_vals['attachment_ids'] = [(6, 0, attachment_ids)]
            self.env['mail.message'].sudo().create(msg_vals)

        return {'type': 'ir.actions.act_window_close'}
