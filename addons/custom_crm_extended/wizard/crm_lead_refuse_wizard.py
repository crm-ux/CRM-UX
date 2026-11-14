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
        lead = self.lead_id.sudo()
        if not self.refuse_reason or not self.refuse_reason.strip():
            raise UserError(_('Please provide a reason for refusal.'))

        creator = lead.create_uid or getattr(lead, 'x_created_by_id', False) or getattr(lead, 'x_original_owner_id', False) or lead.user_id

        lead.write({
            'x_is_refused': True,
            'x_refused_by_id': self.env.user.id,
            'x_refuse_reason': self.refuse_reason,
            'x_refuse_date': fields.Datetime.now(),
            'user_id': creator.id,
            'x_assign_to_id': False,
        })

        # Post a message visible to the team
        lead.message_post(
            body=_(
                '<b>Lead assignment refused</b> by <b>%(user)s</b>.<br/>'
                '<b>Reason:</b> %(reason)s<br/>'
                'Lead has been returned to creator: <b>%(creator)s</b>.',
                user=self.env.user.name,
                reason=self.refuse_reason,
                creator=creator.name or '—',
            ),
            subtype_xmlid='mail.mt_note',
        )

        # Send notifications to creator (and owner if different)
        target_users = (lead.create_uid | creator) - self.env.user
        for target_user in target_users:
            if target_user.partner_id:
                # 1. Live Toast Popup via bus
                try:
                    self.env['bus.bus']._sendone(
                        target_user.partner_id,
                        'simple_notification',
                        {
                            'type': 'warning',
                            'title': _('Lead Assignment Refused'),
                            'message': _('Lead "%s" was refused by %s. Reason: %s') % (
                                lead.name, self.env.user.name, self.refuse_reason
                            ),
                            'sticky': True,
                        }
                    )
                except Exception:
                    pass

                try:
                    self.env['bus.bus']._sendone(
                        target_user.partner_id,
                        'crm_notification',
                        {
                            'title': 'Lead Assignment Refused',
                            'message': f'Lead "{lead.name}" was refused by {self.env.user.name}. Reason: {self.refuse_reason}',
                            'model': 'crm.lead',
                            'res_id': lead.id,
                        }
                    )
                except Exception:
                    pass

            # 2. CRM Notification record
            try:
                self.env['crm.notification'].create_notification(
                    user=target_user,
                    title=f'Lead Refused: {lead.name}',
                    summary=f'Assignment refused by {self.env.user.name}.\nReason: {self.refuse_reason}',
                    category='lead',
                    sender=self.env.user,
                    res_model='crm.lead',
                    res_id=lead.id,
                    record_ref_name=lead.name,
                )
            except Exception:
                pass

        seq = lead.x_stage_sequence or 0
        stage_labels = {
            0: "New Lead",
            5: "Contacted",
            7: "Tech. Discussion",
            10: "Qualified",
            20: "Opportunity",
            30: "Quotes",
            35: "Sent",
            40: "Negotiation",
            50: "Order Expected",
            90: "Won"
        }
        stage_name = stage_labels.get(seq, "Pipeline Leads")
        lead_domain = [('active', '=', True), ('x_stage_sequence', '=', seq)]
        if seq != 90:
            lead_domain.append(('x_stage_sequence', '!=', 90))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Assignment Refused'),
                'message': _('Lead assignment was refused. Creator (%s) has been notified.') % (creator.name or ''),
                'type': 'warning',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': stage_name,
                    'res_model': 'crm.lead',
                    'view_mode': 'list,form',
                    'views': [[False, 'list'], [False, 'form']],
                    'domain': lead_domain,
                    'context': {
                        'search_default_assigned_to_me': 0,
                        'search_default_my_leads': 0,
                        'is_quote_stage': seq >= 30,
                    },
                    'target': 'current',
                },
            }
        }
