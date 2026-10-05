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
        if hide_company:
            for partner in self:
                partner.display_name = partner.name or ''
            return
        return super()._compute_display_name()

from lxml import etree
from odoo.exceptions import UserError

class ResCompanyDefaultCard(models.Model):
    _inherit = 'res.company'
    x_default_signature_card = fields.Binary(string='Default Quotation Signature Card')

    def _user_can_create_company(self):
        user = self.env.user
        if user._is_admin() or user.has_group('base.group_system'):
            return True
        if user.perm_company in ('create', 'none'):
            perm = user.perm_company
        elif user.crm_job_id and user.crm_job_id.perm_company:
            perm = user.crm_job_id.perm_company
        else:
            perm = 'none'
        return perm == 'create'

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options=options)
        if not self._user_can_create_company():
            for vtype in ['form', 'list', 'tree', 'kanban']:
                if vtype in res.get('views', {}):
                    arch_str = res['views'][vtype].get('arch')
                    if arch_str:
                        doc = etree.fromstring(arch_str)
                        doc.attrib['create'] = 'false'
                        res['views'][vtype]['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        if operation == 'create' and not self._user_can_create_company():
            if raise_exception:
                raise UserError("Access Denied: You do not have permission to create companies.")
            return False
        return super().check_access_rights(operation, raise_exception=raise_exception)

    @api.model_create_multi
    def create(self, vals_list):
        if not self._user_can_create_company():
            raise UserError("Access Denied: You do not have permission to create companies.")
        return super().create(vals_list)

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
