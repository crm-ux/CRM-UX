# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import csv
import io


class CrmLeadProductLine(models.Model):
    _name = 'crm.lead.product.line'
    _description = 'CRM Lead - Product Interest Line'
    _order = 'sequence, id'

    lead_id = fields.Many2one('crm.lead', string='Lead / Opportunity', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='Sequence', default=10)

    # Category — computed from product, read-only display only
    x_category_id = fields.Many2one('product.category', string='Category', store=True)
    x_sub_category_id = fields.Many2one('product.category', string='Sub Category', store=True)

    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict', store=True)
    x_product_name_m2o = fields.Many2one('product.product', string='Product Name', store=True)
    x_product_template_id = fields.Many2one('product.template', string='Product Name', store=True)
    x_product_code = fields.Char(string='Product ID', index=True, store=True)
    x_product_name = fields.Char(string='Product Name Text', store=True)
    x_make = fields.Char(string='Make / Brand', store=True)
    x_default_price = fields.Float(string='Master Price', digits='Product Price', store=True)
    x_qty = fields.Float(string='Qty', default=1.0)
    x_discount = fields.Float(string='Discount %')
    x_amount = fields.Float(string='Amount', compute='_compute_amount', store=True)
    x_uom_id = fields.Many2one('uom.uom', string='UoM', store=True)
    x_unit_price = fields.Float(string='Unit Price', digits='Product Price', store=True)
    x_notes = fields.Char(string='Notes')
    x_is_manual = fields.Boolean(string='Manual Entry', default=False)
    x_mismatch_info = fields.Char(string='Mismatch Info', readonly=True)
    x_hsn_code = fields.Char(string='HSN/SAC Code', store=True)
    x_tax_ids = fields.Many2many('account.tax', 'crm_lead_product_line_account_tax_rel',
        'crm_lead_product_line_id', 'account_tax_id', string='Taxes', store=True)
    x_allowed_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_allowed_products',
        string='Allowed Products'
    )



    @api.depends('x_qty', 'x_unit_price', 'x_discount')
    def _compute_amount(self):
        for rec in self:
            price = rec.x_unit_price or 0.0
            qty = rec.x_qty or 0.0
            discount = rec.x_discount or 0.0

            rec.x_amount = (qty * price) * (1 - (discount / 100.0))

    @api.depends('x_category_id', 'x_sub_category_id')
    def _compute_allowed_products(self):
        Product = self.env['product.product']

        for rec in self:
            domain = [('sale_ok', '=', True)]

            if rec.x_sub_category_id:
                domain.append(
                    ('categ_id', 'child_of', rec.x_sub_category_id.id)
                )

            elif rec.x_category_id:
                domain.append(
                    ('categ_id', 'child_of', rec.x_category_id.id)
                )

            rec.x_allowed_product_ids = Product.search(domain)

    def _fill_product_fields(self, p):
        self.x_product_name_m2o = p
        self.x_product_template_id = p.product_tmpl_id
        self.product_id = p
        self.x_product_code = p.default_code or ""
        self.x_product_name = p.name or ""
        self.x_default_price = p.list_price or 0.0
        self.x_unit_price = p.list_price or 0.0
        self.x_uom_id = p.uom_id
        self.x_make = p.x_make or ""
        self.x_is_manual = False
        self.x_hsn_code = p.l10n_in_hsn_code or ""
        self.x_tax_ids = p.taxes_id

        if p.categ_id:
            if p.categ_id.parent_id:
                self.x_category_id = p.categ_id.parent_id
                self.x_sub_category_id = p.categ_id
            else:
                self.x_category_id = p.categ_id
                self.x_sub_category_id = False

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self._fill_product_fields(self.product_id)

    @api.onchange("x_product_name_m2o")
    def _onchange_product_name_m2o(self):
        if self.x_product_name_m2o:
            self._fill_product_fields(self.x_product_name_m2o)

    @api.onchange("x_product_template_id")
    def _onchange_product_template_id(self):
        if self.x_product_template_id:
            product = self.x_product_template_id.product_variant_id
            if product:
                self._fill_product_fields(product)


    @api.onchange('x_product_code')
    def _onchange_product_code(self):
        if self.x_product_code:
            p = self.env['product.product'].search([
                ('default_code', '=', self.x_product_code)
            ], limit=1)

            if p:
                self._fill_product_fields(p)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            pid = vals.get('product_id') or vals.get('x_product_name_m2o')
            if pid:
                product = self.env['product.product'].browse(pid)
                vals.setdefault('product_id', product.id)
                vals.setdefault('x_product_name_m2o', product.id)
                vals.setdefault('x_product_template_id', product.product_tmpl_id.id)
                vals.setdefault('x_product_code', product.default_code or '')
                vals.setdefault('x_product_name', product.name or '')
                if not vals.get('x_hsn_code'):
                    vals['x_hsn_code'] = product.l10n_in_hsn_code or ''
                if not vals.get('x_make'):
                    vals['x_make'] = product.x_make or ''
                if not vals.get('x_unit_price'):
                    vals['x_unit_price'] = product.list_price or 0.0
                if not vals.get('x_default_price'):
                    vals['x_default_price'] = product.list_price or 0.0
                if not vals.get('x_uom_id'):
                    vals['x_uom_id'] = product.uom_id.id
                if not vals.get('x_tax_ids'):
                    vals['x_tax_ids'] = [(6, 0, product.taxes_id.ids)]
                if product.categ_id:
                    if product.categ_id.parent_id and not vals.get('x_category_id'):
                        vals['x_category_id'] = product.categ_id.parent_id.id
                        vals.setdefault('x_sub_category_id', product.categ_id.id)
                    elif not vals.get('x_category_id'):
                        vals['x_category_id'] = product.categ_id.id
        records = super().create(vals_list)
        # Auto-move lead to Qualified when first product line added
        for rec in records:
            lead = self.env['crm.lead'].search([('x_product_line_ids', 'in', [rec.id])], limit=1)
            if lead and lead.stage_id and lead.stage_id.sequence < 10:
                qualified_stage = lead._get_stage_by_sequence(10)
                if qualified_stage:
                    lead.sudo().write({'stage_id': qualified_stage.id})
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'product_id' in vals or 'x_product_name_m2o' in vals or 'x_product_template_id' in vals:
            for rec in self:
                product = rec.product_id or rec.x_product_name_m2o or rec.x_product_template_id.product_variant_id
                if product:
                    super(type(rec), rec).write({
                        'product_id': product.id,
                        'x_product_name_m2o': product.id,
                        'x_product_template_id': product.product_tmpl_id.id,
                        'x_product_code': product.default_code or '',
                        'x_product_name': product.name or '',
                    })
        return res

    @api.onchange('x_category_id')
    def _onchange_category_id(self):
        if not self.product_id:
            self.x_sub_category_id = False
            self.x_product_name_m2o = False
            self.x_product_code = False
            self.x_product_name = False
            self.x_make = False
            self.x_default_price = 0.0
            self.x_unit_price = 0.0

    @api.onchange('x_sub_category_id')
    def _onchange_sub_category_id(self):
        if not self.product_id:
            self.x_product_name_m2o = False
            self.x_product_code = False
            self.x_product_name = False
            self.x_make = False
            self.x_default_price = 0.0
            self.x_unit_price = 0.0


class ProductCategoryDisplay(models.Model):
    _inherit = 'product.category'

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name


class CrmLeadCsvImportWizard(models.TransientModel):
    _name = 'crm.lead.csv.import.wizard'
    _description = 'Import Product Lines from CSV'

    lead_id = fields.Many2one('crm.lead', string='Lead / Opportunity', required=True, ondelete='cascade')
    csv_file = fields.Binary(string='CSV File', required=True)
    csv_filename = fields.Char(string='Filename')
    preview_html = fields.Html(string='Preview', readonly=True)
    result_matched = fields.Integer(string='Matched', readonly=True)
    result_manual = fields.Integer(string='Manual (no match)', readonly=True)
    result_imported = fields.Integer(string='Total Imported', readonly=True)

    @api.onchange('csv_file')
    def _onchange_csv_file(self):
        if not self.csv_file:
            return
        rows, errors = self._parse_csv()
        if errors:
            return {'warning': {'title': _('CSV Parse Error'), 'message': '\n'.join(errors)}}
        html = '<table class="table table-sm table-bordered" style="font-size:12px">'
        html += '<thead><tr><th>Code</th><th>Name</th><th>Make</th><th>Qty</th><th>Price</th><th>Status</th></tr></thead><tbody>'
        for row in rows[:10]:
            product = self._find_product(row.get('product_code', ''), row.get('product_name', ''))
            status = '<span style="color:green">Match</span>' if product else '<span style="color:orange">Manual</span>'
            html += f'<tr><td>{row.get("product_code","")}</td><td>{row.get("product_name","")}</td>'
            html += f'<td>{row.get("make","")}</td><td>{row.get("qty","1")}</td>'
            html += f'<td>{row.get("unit_price","")}</td><td>{status}</td></tr>'
        if len(rows) > 10:
            html += f'<tr><td colspan="6" style="text-align:center;color:#888">... and {len(rows)-10} more rows</td></tr>'
        html += '</tbody></table>'
        self.preview_html = html

    def _parse_csv(self):
        try:
            raw = base64.b64decode(self.csv_file).decode('utf-8-sig')
        except Exception as e:
            return [], [f'Could not decode file: {e}']
        reader = csv.DictReader(io.StringIO(raw))
        if not reader.fieldnames:
            return [], ['Empty or invalid CSV file.']
        missing = {'product_code', 'product_name'} - {f.strip().lower() for f in reader.fieldnames}
        if missing:
            return [], [f'Missing required columns: {", ".join(missing)}']
        return [{k.strip().lower(): v.strip() for k, v in row.items()} for row in reader], []

    def _find_product(self, code, name):
        if code:
            p = self.env['product.product'].search(
                [('default_code', '=', code), ('sale_ok', '=', True)], limit=1)
            if p:
                return p
        if name:
            p = self.env['product.product'].search(
                [('name', 'ilike', name), ('sale_ok', '=', True)], limit=1)
            if p:
                return p
        return None

    def action_import(self):
        self.ensure_one()
        rows, errors = self._parse_csv()
        if errors:
            raise UserError('\n'.join(errors))
        if not rows:
            raise UserError(_('No data rows found in the CSV.'))
        matched = manual = 0
        lines_vals = []
        for row in rows:
            code = row.get('product_code', '')
            name = row.get('product_name', '')
            make = row.get('make', '')
            notes = row.get('notes', '')
            try:
                qty = float(row.get('qty', '1') or '1')
            except ValueError:
                qty = 1.0
            try:
                price = float(row.get('unit_price', '0') or '0')
            except ValueError:
                price = 0.0
            product = self._find_product(code, name)
            if product:
                matched += 1
                categ = product.categ_id
                if categ and categ.parent_id and categ.parent_id.name != 'All':
                    cat_id = categ.parent_id.id
                    sub_cat_id = categ.id
                else:
                    cat_id = categ.id if categ else False
                    sub_cat_id = False
                lines_vals.append({
                    'lead_id': self.lead_id.id,
                    'product_id': product.id,
                    'x_product_code': product.default_code or code,
                    'x_product_name': product.name,
                    'x_category_id': cat_id,
                    'x_sub_category_id': sub_cat_id,
                    'x_default_price': product.list_price,
                    'x_make': make or product.description_sale or '',
                    'x_qty': qty,
                    'x_unit_price': price or product.list_price,
                    'x_uom_id': product.uom_id.id,
                    'x_notes': notes,
                    'x_is_manual': False,
                })
            else:
                manual += 1
                lines_vals.append({
                    'lead_id': self.lead_id.id,
                    'x_product_code': code,
                    'x_product_name': name,
                    'x_make': make,
                    'x_qty': qty,
                    'x_unit_price': price,
                    'x_notes': notes,
                    'x_is_manual': True,
                    'x_mismatch_info': f'No match: code="{code}" name="{name}"',
                })
        self.env['crm.lead.product.line'].create(lines_vals)
        self.result_matched = matched
        self.result_manual = manual
        self.result_imported = len(lines_vals)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Complete'),
                'message': _('%d lines imported: %d matched, %d manual.') % (
                    len(lines_vals), matched, manual),
                'type': 'success' if manual == 0 else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.depends_context('show_code_only', 'show_name_only')
    def _compute_display_name(self):
        show_code_only = self.env.context.get("show_code_only")
        show_name_only = self.env.context.get("show_name_only")
        for rec in self:
            if show_code_only:
                rec.display_name = rec.default_code or rec.product_tmpl_id.name
            elif show_name_only:
                rec.display_name = rec.product_tmpl_id.name
            else:
                rec.display_name = rec.product_tmpl_id.name


    def name_get(self):
        result = []

        show_code_only = self.env.context.get('show_code_only')
        show_name_only = self.env.context.get('show_name_only')

        for rec in self:
            if show_code_only:
                name = rec.default_code or rec.name
            elif show_name_only:
                name = rec.name
            else:
                if rec.default_code:
                    name = f'[{rec.default_code}] {rec.name}'
                else:
                    name = rec.name

            result.append((rec.id, name))

        return result
