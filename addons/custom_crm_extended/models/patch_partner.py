from odoo import models, api

class ResPartnerPatch(models.Model):
    _inherit = 'res.partner'

    def name_get(self):
        if self.env.context.get('partner_display_name_hide_company'):
            result = []
            for partner in self:
                result.append((partner.id, partner.name or ''))
            return result
        return super().name_get()


class ResUsersNotificationPatch(models.Model):
    _inherit = 'res.users'

    notification_type = fields.Selection(
        selection_add=[],
        selection=[
            ('email', 'By Email'),
            ('inbox', 'In System'),
        ]
    )
