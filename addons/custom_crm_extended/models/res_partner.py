from lxml import etree
from odoo import fields, models, api, _
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_site_name = fields.Char(string='Site Name')
    x_building = fields.Char(string='Building')
    x_floor = fields.Char(string='Floor')
    x_department = fields.Char(string='Department')
    x_room_number = fields.Char(string='Room Number')

    @api.model
    def get_views(self, views, options=None):
        res = super(ResPartner, self).get_views(views, options=options)
        user = self.env.user
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
            can_create = getattr(user, 'perm_customer_create', True)
            can_write = getattr(user, 'perm_customer_write', True)
            can_delete = getattr(user, 'perm_customer_unlink', False)

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
            if operation == 'create' and not getattr(user, 'perm_customer_create', True):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to create Customer / Contact records."))
                return False
            if operation == 'write' and not getattr(user, 'perm_customer_write', True) and not self.env.context.get('skip_sync'):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to update Customer / Contact records."))
                return False
            if operation == 'unlink' and not getattr(user, 'perm_customer_unlink', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to delete Customer / Contact records."))
                return False
        return super(ResPartner, self).check_access_rights(operation, raise_exception=raise_exception)

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
            if not getattr(user, 'perm_customer_create', True):
                raise UserError(_("Access Denied: You do not have permission to create Customer / Contact records."))
        return super(ResPartner, self).create(vals_list)

    def write(self, vals):
        user = self.env.user
        # Do not block background sync, superusers, or the user updating their own partner record on login (e.g. tz, login_date)
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11) and not self.env.context.get('skip_sync'):
            # Allow user to update their own partner record
            other_partners = self.filtered(lambda p: p.id != user.partner_id.id)
            if other_partners and not getattr(user, 'perm_customer_write', True):
                raise UserError(_("Access Denied: You do not have permission to update Customer / Contact records."))
        return super(ResPartner, self).write(vals)

    def unlink(self):
        for rec in self:
            user = self.env.user
            # Allow super admin or if user has delete customer permission
            if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
                if not getattr(user, 'perm_customer_unlink', False):
                    raise UserError(_("Access Denied: You do not have permission to delete Customer / Contact records."))
        return super(ResPartner, self).unlink()
