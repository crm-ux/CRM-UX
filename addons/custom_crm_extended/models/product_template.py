from odoo import models, fields, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_make = fields.Char(string='Make / Brand')

    def unlink(self):
        for rec in self:
            user = self.env.user
            if not user.has_group('base.group_system'):
                if not getattr(user, 'perm_product_unlink', False):
                    raise UserError(_("Access Denied: You do not have permission to delete Product Catalog records."))
        return super(ProductTemplate, self).unlink()
