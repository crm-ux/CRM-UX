from lxml import etree
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_make = fields.Char(string='Make / Brand')

    @api.model
    def get_views(self, views, options=None):
        res = super(ProductTemplate, self).get_views(views, options=options)
        user = self.env.user
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
            can_create = getattr(user, 'perm_product_create', True)
            can_write = getattr(user, 'perm_product_write', True)
            can_delete = getattr(user, 'perm_product_unlink', False)

            for vtype in ['form', 'list', 'tree', 'kanban']:
                if vtype in res.get('views', {}):
                    arch_str = res['views'][vtype].get('arch')
                    if arch_str:
                        doc = etree.fromstring(arch_str)
                        if not can_create:
                            doc.attrib['create'] = 'false'
                        if not can_write:
                            doc.attrib['edit'] = 'false'
                        if not can_delete:
                            doc.attrib['delete'] = 'false'
                        res['views'][vtype]['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        user = self.env.user
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
            if operation == 'create' and not getattr(user, 'perm_product_create', True):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to create Product records."))
                return False
            if operation == 'write' and not getattr(user, 'perm_product_write', True):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to update Product records."))
                return False
            if operation == 'unlink' and not getattr(user, 'perm_product_unlink', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to delete Product Catalog records."))
                return False
        return super(ProductTemplate, self).check_access_rights(operation, raise_exception=raise_exception)

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
            if not getattr(user, 'perm_product_create', True):
                raise UserError(_("Access Denied: You do not have permission to create Product records."))
        return super(ProductTemplate, self).create(vals_list)

    def write(self, vals):
        user = self.env.user
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
            if not getattr(user, 'perm_product_write', True):
                raise UserError(_("Access Denied: You do not have permission to update Product records."))
        return super(ProductTemplate, self).write(vals)

    def unlink(self):
        for rec in self:
            user = self.env.user
            if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
                if not getattr(user, 'perm_product_unlink', False):
                    raise UserError(_("Access Denied: You do not have permission to delete Product Catalog records."))
        return super(ProductTemplate, self).unlink()
