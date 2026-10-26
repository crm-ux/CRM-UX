from odoo import models, api, fields

class ResPartnerPatch(models.Model):
    _inherit = 'res.partner'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Default new records on Customers form to Company
        if 'company_type' in fields_list and not self.env.context.get('default_parent_id'):
            res['company_type'] = 'company'
            res['is_company'] = True
        return res

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
    x_default_sale_tax_id = fields.Many2one(
        'account.tax',
        string='Default Sales Tax',
        domain="[('type_tax_use', '=', 'sale'), '|', ('company_id', '=', False), ('company_id', '=', id)]",
        help="Default Sales Tax pre-filled when creating new products."
    )
    crm_authorized_expense_manager_ids = fields.Many2many(
        'res.users',
        'res_company_expense_managers_rel',
        'company_id',
        'user_id',
        string="Authorized Expense Managers"
    )

    def write(self, vals):
        if 'x_default_sale_tax_id' in vals and hasattr(self, 'account_sale_tax_id'):
            vals['account_sale_tax_id'] = vals['x_default_sale_tax_id']
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'x_default_sale_tax_id' in vals and hasattr(self, 'account_sale_tax_id'):
                vals['account_sale_tax_id'] = vals['x_default_sale_tax_id']
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
