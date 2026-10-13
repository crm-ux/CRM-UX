# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleOrderDuplicateWizard(models.TransientModel):
    _name = 'sale.order.duplicate.wizard'
    _description = 'Duplicate Quotation & Lead Wizard'

    order_id = fields.Many2one('sale.order', string='Original Quotation', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    contact_person_id = fields.Many2one(
        'res.partner',
        string='Contact Person',
        domain="[('parent_id', '=', partner_id), ('is_company', '=', False)]",
    )
    user_id = fields.Many2one('res.users', string='Salesperson', default=lambda self: self.env.user)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order_id = self.env.context.get('default_order_id') or res.get('order_id')
        if order_id:
            order = self.env['sale.order'].browse(order_id)
            if order.exists():
                res['order_id'] = order.id
                if 'partner_id' in fields_list and not res.get('partner_id'):
                    res['partner_id'] = order.partner_id.id if order.partner_id else False
                if 'contact_person_id' in fields_list and not res.get('contact_person_id'):
                    res['contact_person_id'] = order.x_contact_person_id.id if order.x_contact_person_id else False
                if 'user_id' in fields_list and not res.get('user_id'):
                    res['user_id'] = order.user_id.id if order.user_id else self.env.uid
        return res

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            # Pick first contact or clear
            contact = self.env['res.partner'].search([
                ('parent_id', '=', self.partner_id.id),
                ('is_company', '=', False)
            ], limit=1)
            self.contact_person_id = contact.id if contact else False
        else:
            self.contact_person_id = False

    def action_duplicate(self):
        self.ensure_one()
        source_order = self.order_id

        # 1. Create a fresh Lead for this new Quotation
        lead_vals = {
            'name': f"{self.partner_id.name or 'New'} - Quotation",
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id or source_order.user_id.id or self.env.uid,
            'team_id': source_order.team_id.id if source_order.team_id else False,
            'type': 'opportunity',
        }
        if self.contact_person_id:
            lead_vals['contact_name'] = self.contact_person_id.name or ''
            lead_vals['email_from'] = getattr(self.contact_person_id, 'email', False) or ''
            lead_vals['phone'] = getattr(self.contact_person_id, 'phone', False) or getattr(self.contact_person_id, 'mobile', False) or ''

        new_lead = self.env['crm.lead'].create(lead_vals)

        # 2. Duplicate Quotation using standard copy with clean defaults
        new_order = source_order.copy(default={
            'partner_id': self.partner_id.id,
            'opportunity_id': new_lead.id,
            'user_id': self.user_id.id or source_order.user_id.id or self.env.uid,
            'x_contact_person_id': self.contact_person_id.id if self.contact_person_id else False,
            'x_quote_stage': 'draft',
            'state': 'draft',
            'date_order': fields.Datetime.now(),
            'validity_date': False,
            # Wipe PO and Invoice details
            'x_po_number': False,
            'x_po_date': False,
            'x_po_file': False,
            'x_uw_po_number': False,
            'x_sales_order_number': False,
            'x_final_quote_locked': False,
            'x_assigned_to_service': False,
            'x_assigned_to_aftersales': False,
            'x_handoff_date': False,
            'x_invoice_number': False,
            'x_invoice_date': False,
            'x_service_remarks': False,
            'x_lost_reason': False,
        })

        # 3. Return action to immediately open the new Quotation
        return {
            'name': _('Quotation'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': new_order.id,
            'target': 'current',
        }
