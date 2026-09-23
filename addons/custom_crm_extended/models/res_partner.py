from odoo import fields, models, api, _
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_site_name = fields.Char(string='Site Name')
    x_building = fields.Char(string='Building')
    x_floor = fields.Char(string='Floor')
    x_department = fields.Char(string='Department')
    x_room_number = fields.Char(string='Room Number')

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        if not user.has_group('base.group_system'):
            if not getattr(user, 'perm_customer_create', True):
                raise UserError(_("Access Denied: You do not have permission to create Customer / Contact records."))
        return super(ResPartner, self).create(vals_list)

    def write(self, vals):
        user = self.env.user
        # Do not block background employee sync or self user profile updates
        if not user.has_group('base.group_system') and not self.env.context.get('skip_sync'):
            if not getattr(user, 'perm_customer_write', True):
                raise UserError(_("Access Denied: You do not have permission to update Customer / Contact records."))
        return super(ResPartner, self).write(vals)

    def unlink(self):
        for rec in self:
            user = self.env.user
            # Allow super admin or if user has delete customer permission
            if not user.has_group('base.group_system'):
                if not getattr(user, 'perm_customer_unlink', False):
                    raise UserError(_("Access Denied: You do not have permission to delete Customer / Contact records."))
        return super(ResPartner, self).unlink()
