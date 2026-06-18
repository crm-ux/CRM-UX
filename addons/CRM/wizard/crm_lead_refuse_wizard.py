# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CrmLeadRefuseWizard(models.TransientModel):
    _name = 'crm.lead.refuse.wizard'
    _description = 'Refuse Lead / Opportunity Assignment'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead / Opportunity',
        required=True,
        ondelete='cascade',
    )

    refuse_reason = fields.Text(
        string='Reason for Refusal',
        required=True,
        help='Explain why you are refusing this lead assignment. This will be visible to the owner.',
    )

    def action_confirm_refuse(self):
        self.ensure_one()
        lead = self.lead_id
        if not self.refuse_reason or not self.refuse_reason.strip():
            raise UserError(_('Please provide a reason for refusal.'))

        lead.write({
            'x_is_refused': True,
            'x_refused_by_id': self.env.user.id,
            'x_refuse_reason': self.refuse_reason,
            'x_refuse_date': fields.Datetime.now(),
        })

        # Post a message visible to the team
        lead.message_post(
            body=_(
                '<b>Lead assignment refused</b> by <b>%(user)s</b>.<br/>'
                '<b>Reason:</b> %(reason)s<br/>'
                'Lead has been returned to the owner: <b>%(owner)s</b>.',
                user=self.env.user.name,
                reason=self.refuse_reason,
                owner=lead.user_id.name or '—',
            ),
            subtype_xmlid='mail.mt_note',
        )

        # Notify owner via Odoo activity
        if lead.user_id:
            lead.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=lead.user_id.id,
                note=_('Assignment refused by %s. Reason: %s') % (
                    self.env.user.name, self.refuse_reason
                ),
            )

        return {'type': 'ir.actions.act_window_close'}
