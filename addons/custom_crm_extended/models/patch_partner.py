from odoo import models, api, fields

class ResPartnerPatch(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        to_update = records.filtered(lambda r: r.is_company and not r.customer_rank)
        if to_update:
            to_update.write({'customer_rank': 1})
        return records

    @api.depends_context('partner_display_name_hide_company')
    def _compute_display_name(self):
        hide_company = self.env.context.get('partner_display_name_hide_company')
        if not hide_company:
            return super()._compute_display_name()
        for partner in self:
            partner.display_name = partner.name or ''

class ResUsersNotificationPatch(models.Model):
    _inherit = 'res.users'
    x_signature_card = fields.Binary(string='Quotation Signature Card')
    notification_type = fields.Selection(
        selection_add=[],
        selection=[
            ('email', 'By Email'),
            ('inbox', 'In System'),
        ]
    )
