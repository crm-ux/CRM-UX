# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CrmLeadWonPoWizard(models.TransientModel):
    _name = 'crm.lead.won.po.wizard'
    _description = 'Enter PO Details to Mark Lead as Won'

    lead_id = fields.Many2one('crm.lead', string='Lead / Opportunity', required=True, ondelete='cascade')
    po_number = fields.Char(string='PO Number', required=True)
    po_date = fields.Date(string='PO Date', default=fields.Date.context_today, required=True)

    def action_confirm_won(self):
        self.ensure_one()
        if not self.po_number or not self.po_number.strip():
            raise UserError(_('Please enter a valid PO Number.'))

        lead = self.lead_id

        # Sync PO to linked quotation if exists
        quotation = self.env['sale.order'].sudo().search([
            ('opportunity_id', '=', lead.id),
            ('state', 'in', ['draft', 'sent'])
        ], order='id desc', limit=1)

        if quotation:
            if not quotation.order_line or (quotation.amount_total or 0.0) <= 0:
                raise UserError(_(
                    "Cannot mark as Won: The linked quotation '%s' has total amount of ₹0.00!\n\n"
                    "Please add at least one product with a valid price in the quotation first."
                ) % quotation.name)
            quotation.sudo().write({
                'x_po_number': self.po_number,
                'x_po_date': self.po_date,
                'x_final_quote_locked': True,
                'x_quote_stage': 'won',
            })
            quotation.sudo().message_post(
                body=_('Quote marked as <b>Won</b> via Lead. PO: <b>%s</b>') % (self.po_number or '')
            )

        # Mark lead as Won
        lead.action_move_to_won(po_number=self.po_number, po_date=self.po_date)
        lead.message_post(
            body=_('Lead marked as <b>Won</b>. PO: <b>%s</b>') % (self.po_number or '')
        )

        return {'type': 'ir.actions.act_window_close'}
