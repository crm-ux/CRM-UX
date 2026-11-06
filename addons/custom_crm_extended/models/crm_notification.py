# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class CrmNotification(models.Model):
    _name = 'crm.notification'
    _description = 'User Notification Master'
    _order = 'date desc, id desc'

    name = fields.Char(string='Notification Title', required=True, index=True)
    user_id = fields.Many2one(
        'res.users',
        string='Recipient (User)',
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete='cascade',
    )
    sender_id = fields.Many2one(
        'res.users',
        string='Sent By',
        default=lambda self: self.env.user,
        index=True,
    )
    date = fields.Datetime(string='Date & Time', default=fields.Datetime.now, index=True)
    category = fields.Selection([
        ('voucher', 'Expense Voucher'),
        ('ticket', 'Service Ticket'),
        ('lead', 'CRM Lead'),
        ('task', 'Task Management'),
        ('general', 'General'),
    ], string='Category', default='general', required=True, index=True)

    summary = fields.Text(string='Details / Message')
    state = fields.Selection([
        ('unread', 'Unread'),
        ('read', 'Read'),
    ], string='Status', default='unread', required=True, index=True)

    res_model = fields.Char(string='Target Model')
    res_id = fields.Integer(string='Target Record ID')
    record_ref_name = fields.Char(string='Target Record', compute='_compute_record_ref_name', store=True, readonly=False)

    @api.depends('res_model', 'res_id')
    def _compute_record_ref_name(self):
        for rec in self:
            if rec.res_model and rec.res_id and not rec.record_ref_name:
                try:
                    target = self.env[rec.res_model].sudo().browse(rec.res_id)
                    if target.exists():
                        rec.record_ref_name = target.display_name or str(rec.res_id)
                    else:
                        rec.record_ref_name = f"{rec.res_model} #{rec.res_id}"
                except Exception:
                    rec.record_ref_name = f"{rec.res_model} #{rec.res_id}"

    def action_mark_as_read(self):
        for rec in self:
            rec.state = 'read'

    def action_mark_as_unread(self):
        for rec in self:
            rec.state = 'unread'

    def action_open_target_record(self):
        self.ensure_one()
        self.state = 'read'
        if not self.res_model or not self.res_id:
            raise UserError(_("No target record linked to this notification."))

        target = self.env[self.res_model].sudo().browse(self.res_id)
        if not target.exists():
            raise UserError(_("The linked record (%s #%s) no longer exists.") % (self.res_model, self.res_id))

        return {
            'name': self.record_ref_name or self.name,
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def action_mark_all_read(self):
        """Mark all unread notifications of current user as read."""
        unread = self.search([('user_id', '=', self.env.user.id), ('state', '=', 'unread')])
        unread.write({'state': 'read'})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notifications Updated'),
                'message': _('All your notifications have been marked as read.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    @api.model
    def create_notification(self, user, title, summary, category='general', sender=None, res_model=None, res_id=None, record_ref_name=None):
        """Helper to create notification master record for a user."""
        if not user:
            return False
        sender_user = sender or self.env.user
        val = {
            'name': title or 'New Notification',
            'user_id': user.id if hasattr(user, 'id') else user,
            'sender_id': sender_user.id if hasattr(sender_user, 'id') else sender_user,
            'category': category,
            'summary': summary or '',
            'state': 'unread',
            'res_model': res_model or False,
            'res_id': res_id or 0,
            'record_ref_name': record_ref_name or False,
        }
        return self.sudo().create(val)

