from odoo import models, api, fields

class ResPartnerPatch(models.Model):
    _inherit = 'res.partner'

    @api.depends_context('partner_display_name_hide_company')
    def _compute_display_name(self):
        hide_company = self.env.context.get('partner_display_name_hide_company')
        if not hide_company:
            return super()._compute_display_name()
        for partner in self:
            partner.display_name = partner.name or ''

class ResUsersNotificationPatch(models.Model):
    _inherit = 'res.users'
    notification_type = fields.Selection(
        selection_add=[],
        selection=[
            ('email', 'By Email'),
            ('inbox', 'In System'),
        ]
    )
