# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import csv
import io


class CrmLeadProductLine(models.Model):
    """
    One product interest line per lead.
    Links to the standard product.product (Sales module master).

    Fields used from product.product (no redeclaration needed):
        default_code  – Internal Reference / Product ID
        name          – Product Name
        categ_id      – Internal Category  (product.category)
        list_price    – Sales Price (default price)
        uom_id        – Unit of Measure

    We add:
        x_make        – Brand / Make (free text, not in product master)
        x_qty         – Quantity required
        x_unit_price  – Overridden price (defaults from list_price)
        x_is_manual   – True when product not found in master (manual entry)
        x_notes       – Line notes
    """
    _name = 'crm.lead.product.line'
    _description = 'CRM Lead – Product Interest Line'
    _order = 'sequence, id'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead / Opportunity',
        required=True,
        ondelete='cascade',
        index=True,
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    # ------------------------------------------------------------------
    # Product link  (from Sales master – product.product)
    # ------------------------------------------------------------------
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        ondelete='restrict',
        domain=[('sale_ok', '=', True)],
        help='Search by Internal Reference (Product ID) or Product Name.',
    )

    # Editable Product ID / Internal Reference field.
    # Populated via onchange from product_id, OR typed manually to trigger auto-lookup.
    # NOT using related= so it stays editable for manual lines.
    x_product_code = fields.Char(
        string='Product ID',
        index=True,
        help='Product Internal Reference. Type to auto-lookup product from master.',
    )

    x_product_name = fields.Char(
        string='Product Name',
        compute='_compute_from_product',
        store=True,
        readonly=False,   # editable override for manual lines
    )

    x_category_id = fields.Many2one(
        'product.category',
        string='Category',
        compute='_compute_from_product',
        store=True,
        readonly=False,   # editable override for manual lines
    )

    x_default_price = fields.Float(
        string='Master Price',
        compute='_compute_from_product',
        store=True,
        readonly=True,
        digits='Product Price',
        help='Auto-loaded from product master (Sales Price). Read-only.',
    )

    x_make = fields.Char(
        string='Make / Brand',
        help='Brand or manufacturer. Free text, not enforced from master.',
    )

    # ------------------------------------------------------------------
    # Qty + Unit price (editable by sales rep)
    # ------------------------------------------------------------------
    x_qty = fields.Float(
        string='Qty',
        default=1.0,
        digits='Product Unit of Measure',
    )

    x_uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
        compute='_compute_from_product',
        store=True,
        readonly=False,
    )

    x_unit_price = fields.Float(
        string='Unit Price',
        digits='Product Price',
        help='Editable. Defaults from master price when product is selected.',
    )

    x_notes = fields.Char(
        string='Notes',
        help='Short line note or requirement.',
    )

    # ------------------------------------------------------------------
    # Manual / mismatch flag
    # ------------------------------------------------------------------
    x_is_manual = fields.Boolean(
        string='Manual Entry',
        default=False,
        help='Set automatically when the product ID was not found in the master table. '
             'Manually entered lines are highlighted.',
    )

    x_mismatch_info = fields.Char(
        string='Mismatch Info',
        readonly=True,
        help='Populated during CSV import to describe what did not match.',
    )

    # ==================================================================
    # COMPUTE
    # ==================================================================

    @api.depends('product_id')
    def _compute_from_product(self):
        for line in self:
            if line.product_id:
                line.x_product_name = line.product_id.name
                line.x_category_id  = line.product_id.categ_id
                line.x_default_price = line.product_id.list_price
                line.x_uom_id       = line.product_id.uom_id
                # Only set unit price if not already manually overridden
                if not line.x_unit_price:
                    line.x_unit_price = line.product_id.list_price
            else:
                # Keep whatever was manually entered – don't wipe on clear
                if not line.x_is_manual:
                    line.x_product_name  = False
                    line.x_category_id   = False
                    line.x_default_price = 0.0
                    line.x_uom_id        = False

    # ==================================================================
    # ONCHANGE – when product is selected, auto-fill price
    # ==================================================================

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.x_product_code  = self.product_id.default_code or ''
            self.x_unit_price    = self.product_id.list_price
            self.x_uom_id        = self.product_id.uom_id
            self.x_is_manual     = False
            self.x_mismatch_info = False

    @api.onchange('x_product_code')
    def _onchange_product_code(self):
        """
        When user types a Product ID / Internal Reference,
        auto-search and fill the product_id field.
        """
        if self.x_product_code and not self.product_id:
            product = self.env['product.product'].search(
                [('default_code', '=', self.x_product_code),
                 ('sale_ok', '=', True)],
                limit=1
            )
            if product:
                self.product_id = product
                self.x_is_manual = False
            else:
                self.x_is_manual = True
                self.x_mismatch_info = f'No product found with ID: {self.x_product_code}'
                return {
                    'warning': {
                        'title': _('Product Not Found'),
                        'message': _(
                            'No product with Internal Reference "%s" found in master. '
                            'Line marked as manual entry.'
                        ) % self.x_product_code,
                    }
                }


class CrmLeadCsvImportWizard(models.TransientModel):
    """
    Wizard to bulk-import product interest lines from a CSV file.

    Expected CSV columns (header row required):
        product_code, product_name, make, qty, unit_price, notes

    Matching logic:
        1. Try exact match on product.product.default_code
        2. If no match, try case-insensitive name match
        3. If still no match → create manual line with mismatch info
    """
    _name = 'crm.lead.csv.import.wizard'
    _description = 'Import Product Lines from CSV'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead / Opportunity',
        required=True,
        ondelete='cascade',
    )

    csv_file = fields.Binary(
        string='CSV File',
        required=True,
        help='Upload a CSV with columns: product_code, product_name, make, qty, unit_price, notes',
    )

    csv_filename = fields.Char(string='Filename')

    preview_html = fields.Html(
        string='Preview',
        readonly=True,
        help='Preview of the parsed rows before import.',
    )

    # Result summary
    result_matched   = fields.Integer(string='Matched', readonly=True)
    result_manual    = fields.Integer(string='Manual (no match)', readonly=True)
    result_imported  = fields.Integer(string='Total Imported', readonly=True)

    @api.onchange('csv_file')
    def _onchange_csv_file(self):
        if not self.csv_file:
            return
        rows, errors = self._parse_csv()
        if errors:
            return {'warning': {'title': _('CSV Parse Error'), 'message': '\n'.join(errors)}}
        # Build HTML preview (first 10 rows)
        html = '<table class="table table-sm table-bordered" style="font-size:12px">'
        html += '<thead><tr><th>Code</th><th>Name</th><th>Make</th><th>Qty</th><th>Price</th><th>Notes</th><th>Status</th></tr></thead><tbody>'
        for i, row in enumerate(rows[:10]):
            product = self._find_product(row.get('product_code', ''), row.get('product_name', ''))
            status = '<span style="color:green">Match</span>' if product else '<span style="color:orange">Manual</span>'
            html += f'<tr><td>{row.get("product_code","")}</td><td>{row.get("product_name","")}</td>'
            html += f'<td>{row.get("make","")}</td><td>{row.get("qty","1")}</td>'
            html += f'<td>{row.get("unit_price","")}</td><td>{row.get("notes","")}</td><td>{status}</td></tr>'
        if len(rows) > 10:
            html += f'<tr><td colspan="7" style="text-align:center;color:#888">... and {len(rows)-10} more rows</td></tr>'
        html += '</tbody></table>'
        self.preview_html = html

    def _parse_csv(self):
        """Decode and parse the uploaded CSV. Returns (rows_list, errors_list)."""
        try:
            raw = base64.b64decode(self.csv_file).decode('utf-8-sig')
        except Exception as e:
            return [], [f'Could not decode file: {e}']
        reader = csv.DictReader(io.StringIO(raw))
        required = {'product_code', 'product_name'}
        if not reader.fieldnames:
            return [], ['Empty or invalid CSV file.']
        missing = required - {f.strip().lower() for f in reader.fieldnames}
        if missing:
            return [], [f'Missing required columns: {", ".join(missing)}. Found: {reader.fieldnames}']
        rows = []
        for row in reader:
            # normalise keys to lowercase
            rows.append({k.strip().lower(): v.strip() for k, v in row.items()})
        return rows, []

    def _find_product(self, code, name):
        """Try to find a product by code first, then name."""
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
        """Parse CSV and create crm.lead.product.line records."""
        self.ensure_one()
        rows, errors = self._parse_csv()
        if errors:
            raise UserError('\n'.join(errors))
        if not rows:
            raise UserError(_('No data rows found in the CSV.'))

        matched = 0
        manual = 0
        lines_vals = []

        for row in rows:
            code       = row.get('product_code', '')
            name       = row.get('product_name', '')
            make       = row.get('make', '')
            notes      = row.get('notes', '')
            try:
                qty    = float(row.get('qty', '1') or '1')
            except ValueError:
                qty    = 1.0
            try:
                price  = float(row.get('unit_price', '0') or '0')
            except ValueError:
                price  = 0.0

            product = self._find_product(code, name)

            if product:
                matched += 1
                mismatch_info = False
                is_manual = False
                final_price = price if price else product.list_price
                categ_id = product.categ_id.id
                uom_id   = product.uom_id.id
                default_price = product.list_price
            else:
                manual += 1
                is_manual = True
                mismatch_info = f'No match: code="{code}" name="{name}"'
                final_price = price
                categ_id = False
                uom_id   = False
                default_price = 0.0

            lines_vals.append({
                'lead_id':         self.lead_id.id,
                'product_id':      product.id if product else False,
                'x_product_code':  code,
                'x_product_name':  name,
                'x_category_id':   categ_id,
                'x_default_price': default_price,
                'x_make':          make,
                'x_qty':           qty,
                'x_unit_price':    final_price,
                'x_uom_id':        uom_id,
                'x_notes':         notes,
                'x_is_manual':     is_manual,
                'x_mismatch_info': mismatch_info,
            })

        self.env['crm.lead.product.line'].create(lines_vals)

        self.result_matched  = matched
        self.result_manual   = manual
        self.result_imported = len(lines_vals)

        # Return a notification action instead of closing immediately
        # so user can see the import summary
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Complete'),
                'message': _(
                    '%d lines imported: %d matched from master, %d manual entries.'
                ) % (len(lines_vals), matched, manual),
                'type': 'success' if manual == 0 else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
