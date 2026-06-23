# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    """
    Extends sale.order (Quotation / Sales Order).

    Existing fields we USE (no redeclaration):
        name            - Quotation Reference
        partner_id      - Customer
        opportunity_id  - Linked CRM Lead/Opportunity  [from sale_crm]
        order_line      - Order Lines (sale.order.line)
        amount_untaxed  - Subtotal (before tax)
        amount_tax      - Tax Total
        amount_total    - Grand Total
        validity_date   - Expiration Date
        note            - Terms & Conditions
        payment_term_id - Payment Terms
        user_id         - Salesperson
        team_id         - Sales Team
        state           - Draft/Sent/Sale/Cancel
        currency_id     - Currency
    """
    _inherit = 'sale.order'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'note' in fields_list and not res.get('note'):
            res['note'] = '''<ol>
<li>All prices quoted are in Indian Rupees (INR) and are valid for a period of 40 days from the date of quotation.</li>
<li>GST @ 18% shall be charged extra as applicable.</li>
<li>Prices: All prices quoted are in Indian Rupees (INR).</li>
<li>Incoterms: FOR (Free on Road) at the specified destination.</li>
<li>Payment Terms: 100% advance payment against Proforma Invoice.</li>
<li>Purchase Order should be issued in favor of Ultrawin Technologies.<br/>FOURTH FLOOR, 401, RUDRAM ICON, OPP SILVER OAK COLLEGE, OPP SHAYONA ARCADE, GOTA, GHATLODIA, AHMEDABAD - 382481<br/>GST Reg. No. - 24CTXPP6943F1Z0</li>
<li>Delivery shall be made within 8-10 weeks from the date of receipt of a technically and commercially clear, error-free Purchase Order.</li>
<li>Warranty: One (1) year from the date of invoice against manufacturing defects.</li>
<li>Cancellation of Order: Orders once accepted cannot be cancelled or modified without written consent from Ultrawin Technologies.</li>
<li>Jurisdiction: Any dispute arising out of this quotation, order, or supply shall be subject to the exclusive jurisdiction of the courts at Ahmedabad, Gujarat, India.</li>
<li>Acceptance of this quotation constitutes acceptance of all terms and conditions stated herein.</li>
</ol>
<p>Should you require any further information or clarification, please feel free to contact us.</p>
<p>We thank you for your enquiry and look forward to receiving your valued order.</p>
<p>Thanking You,<br/>Sincerely,<br/>Himanshu Patel<br/>Ultrawin Technologies</p>'''
        return res

    # ------------------------------------------------------------------
    # 1. GST TOGGLE  (With GST / Without GST)
    # ------------------------------------------------------------------
    x_gst_included = fields.Boolean(
        string='Include GST',
        default=False,
        tracking=True,
        help='Toggle to show or hide GST/tax columns on all order lines. '
             'When OFF, tax fields are hidden but not deleted.',
    )

    # ------------------------------------------------------------------
    # 2. QUOTE VERSION  (v1, v2, ... - for revision tracking)
    # ------------------------------------------------------------------
    x_quote_version = fields.Integer(
        string='Quote Version',
        default=1,
        readonly=True,
        copy=False,
        tracking=True,
    )

    x_quote_version_label = fields.Char(
        string='Version',
        compute='_compute_version_label',
        store=False,
    )

    # ------------------------------------------------------------------
    # 3. FLAT DISCOUNT on the whole order (header level)
    # ------------------------------------------------------------------
    x_flat_discount = fields.Float(
        string='Flat Discount (Amount)',
        default=0.0,
        digits='Product Price',
        tracking=True,
        help='Fixed amount discount applied on the grand total.',
    )

    x_flat_discount_pct = fields.Float(
        string='Overall Discount (%)',
        default=0.0,
        digits=(5, 2),
        tracking=True,
        help='Percentage discount applied on the subtotal (before GST). '
             'Applied after all line-level discounts.',
    )

    x_amount_after_discount = fields.Monetary(
        string='Discount Amount',
        compute='_compute_discount_totals',
        store=True,
        currency_field='currency_id',
    )
    x_original_amount = fields.Monetary(
        string='Original Amount',
        compute='_compute_discount_totals',
        store=True,
        currency_field='currency_id',
    )
    x_net_total = fields.Monetary(
        string='Net Total',
        compute='_compute_discount_totals',
        store=True,
        currency_field='currency_id',
    )

    # ------------------------------------------------------------------
    # 4. PO DETAILS  (filled at PO stage, after quote is accepted)
    # ------------------------------------------------------------------
    x_invoice_number = fields.Char(string='Invoice No', tracking=True, copy=False)
    x_invoice_date = fields.Date(string='Invoice Date', tracking=True, copy=False)
    x_sales_order_number = fields.Char(string='Sales Order No', tracking=True, copy=False)

    x_contact_person = fields.Char(
        string='Contact Person',
        help='Auto-filled from linked CRM lead contact name',
    )

    x_po_number = fields.Char(
        string='PO Number',
        tracking=True,
        copy=False,
    )

    x_po_date = fields.Date(
        string='PO Date',
        tracking=True,
        copy=False,
    )

    x_po_file = fields.Binary(
        string='PO Document',
        attachment=True,
        copy=False,
    )

    x_po_filename = fields.Char(string='PO Filename')

    x_final_quote_locked = fields.Boolean(
        string='Final Quote Locked',
        default=False,
        tracking=True,
        copy=False,
        help='When True, line prices and quantities are locked. Set after PO is received.',
    )

    # ------------------------------------------------------------------
    # 5. REMARKS / HANDOFF NOTES
    # ------------------------------------------------------------------
    x_internal_remarks = fields.Text(
        string='Internal Remarks',
        help='Internal notes visible only to the sales team.',
    )

    x_service_remarks = fields.Text(
        string='Remarks for Service Team',
        help='Handoff notes when assigning to Service or After Sales.',
        tracking=True,
    )

    # ------------------------------------------------------------------
    # 6. HANDOFF ASSIGNMENT
    # ------------------------------------------------------------------
    x_assigned_to_service = fields.Many2one(
        'res.users',
        string='Assign to Service',
        tracking=True,
        domain=[('share', '=', False)],
        copy=False,
    )

    x_assigned_to_aftersales = fields.Many2one(
        'res.users',
        string='Assign to After Sales',
        tracking=True,
        domain=[('share', '=', False)],
        copy=False,
    )

    x_handoff_date = fields.Date(
        string='Handoff Date',
        tracking=True,
        copy=False,
    )

    # Draft fields for quotation wizard
    x_draft_tech_specs = fields.Html(string='Draft Technical Specs')
    x_draft_best_offer = fields.Char(string='Draft Best Offer For')
    x_draft_image_ids = fields.Many2many(
        'ir.attachment', 'sale_order_draft_image_rel',
        'order_id', 'attachment_id',
        string='Draft Quote Images'
    )

    # ------------------------------------------------------------------
    # 7. QUOTE STATUS STAGE (beyond default state)
    # ------------------------------------------------------------------
    x_quote_stage = fields.Selection(
        selection=[
            ('draft',     'Draft'),
            ('prepared',  'Quote Prepared'),
            ('sent',      'Quote Sent'),
            ('po_received', 'PO Received'),
            ('won',       'Won'),
            ('lost',      'Lost'),
        ],
        string='Quote Stage',
        default='draft',
        tracking=True,
        copy=False,
    )

    x_lost_reason = fields.Selection(
        selection=[
            ('price', 'Price too high'),
            ('competitor', 'Lost to competitor'),
            ('no_budget', 'No budget'),
            ('no_response', 'No response from customer'),
            ('other', 'Other'),
        ],
        string='Lost Reason',
        tracking=True,
        copy=False,
    )

    # ==================================================================
    # COMPUTE
    # ==================================================================

    @api.depends('x_quote_version')
    def _compute_version_label(self):
        for order in self:
            order.x_quote_version_label = f'v{order.x_quote_version}'

    @api.depends('amount_untaxed', 'amount_total',
                 'x_flat_discount', 'x_flat_discount_pct',
                 'order_line.price_unit', 'order_line.product_uom_qty')
    def _compute_discount_totals(self):
        for order in self:
            # Step 1: subtotal after product line discounts
            subtotal_after_line_disc = order.amount_untaxed
            # Step 2: apply overall % discount on subtotal
            pct_disc = subtotal_after_line_disc * (order.x_flat_discount_pct / 100.0)
            # Step 3: apply flat amount discount
            flat_disc = order.x_flat_discount or 0.0
            # Total discount amount
            total_disc = pct_disc + flat_disc
            # Store values
            order.x_original_amount = subtotal_after_line_disc
            order.x_amount_after_discount = total_disc
            # Net total = subtotal - all discounts + tax
            order.x_net_total = max(0.0, subtotal_after_line_disc - total_disc) + order.amount_tax
    # ==================================================================
    # ACTIONS
    # ==================================================================

    def action_print_custom_pdf(self):
        self.ensure_one()
        wizard = self.env['sale.quote.preview.wizard'].with_context(
            default_order_id=self.id
        ).create({'order_id': self.id})
        wizard._rebuild_document_html()
        return self.env['ir.actions.report'].search([
            ('report_name','=','custom_crm_extended.report_sale_quote_preview_wizard')
        ], limit=1).report_action(wizard)

    def action_preview_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Editable Quotation Preview',
            'res_model': 'sale.quote.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
            },
        }


    def action_new_quote_version(self):
        """
        Increment version counter and reset to draft for revision.
        Called from a button on the form.
        """
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            raise UserError(
                _('You can only create a new version of a draft or sent quotation.')
            )
        self.x_quote_version += 1
        self.state = 'draft'
        self.message_post(
            body=_('New quote version created: <b>v%d</b>') % self.x_quote_version
        )

    def action_lock_final_quote(self):
        """Lock line prices after PO is received."""
        self.ensure_one()
        if not self.x_po_number:
            raise UserError(_('Please enter the PO Number before locking the final quote.'))
        self.x_final_quote_locked = True
        self.x_quote_stage = 'po_received'
        self.message_post(
            body=_('Final quote locked. PO: <b>%s</b>') % (self.x_po_number or '')
        )

    @api.onchange('x_gst_included')
    def _onchange_gst_included(self):
        """Clear taxes when GST OFF, restore default taxes when GST ON."""
        for line in self.order_line.filtered(lambda l: not l.display_type):
            if self.x_gst_included:
                if line.product_id:
                    taxes = line.product_id.taxes_id.filtered(
                        lambda t: t.company_id == self.company_id
                    )
                    line.update({'tax_ids': taxes})
            else:
                line.update({'tax_ids': [(5, 0, 0)]})

    def _apply_gst_to_lines(self):
        """Apply GST setting to all lines - called on save."""
        for line in self.order_line.filtered(lambda l: not l.display_type):
            if self.x_gst_included:
                if line.product_id and not line.tax_ids:
                    taxes = line.product_id.taxes_id.filtered(
                        lambda t: t.company_id == self.company_id
                    )
                    line.write({'tax_ids': [(6, 0, taxes.ids)]})
            else:
                line.write({'tax_ids': [(5, 0, 0)]})

    @api.onchange('x_flat_discount_pct')
    def _onchange_flat_discount_pct(self):
        """Trigger recompute of discount totals."""
        pass

    @api.onchange('order_line')
    def _onchange_order_line_clear_discount(self):
        """Clear overall discount when all lines are removed."""
        active_lines = self.order_line.filtered(lambda l: not l.display_type)
        if not active_lines:
            self.x_flat_discount_pct = 0.0
            self.x_flat_discount = 0.0



    def write(self, vals):
        result = super().write(vals)
        if 'x_gst_included' in vals:
            for line in self.order_line.filtered(lambda l: not l.display_type):
                if vals['x_gst_included']:
                    if line.product_id:
                        taxes = line.product_id.taxes_id.filtered(
                            lambda t: t.company_id == self.company_id
                        )
                        line.write({'tax_ids': [(6, 0, taxes.ids)]})
                else:
                    line.write({'tax_ids': [(5, 0, 0)]})

        return result

    def action_apply_overall_discount(self):
        """Apply overall discount % to all order lines and handle GST."""
        self.ensure_one()
        # Apply discount to all lines
        if self.x_flat_discount_pct:
            for line in self.order_line.filtered(lambda l: not l.display_type):
                line.discount = self.x_flat_discount_pct
        # Handle GST taxes
        for line in self.order_line.filtered(lambda l: not l.display_type):
            if self.x_gst_included:
                if line.product_id and not line.tax_ids:
                    line.tax_ids = line.product_id.taxes_id.filtered(
                        lambda t: t.company_id == self.company_id
                    )
            else:
                line.tax_ids = [(5, 0, 0)]
        self.message_post(
            body=_('Applied: Discount <b>%s%%</b>, GST <b>%s</b>') % (
                self.x_flat_discount_pct,
                'ON' if self.x_gst_included else 'OFF'
            )
        )

    def action_mark_won(self):
        """Mark quote as Won - requires PO number."""
        self.ensure_one()
        if not self.x_po_number:
            raise UserError(_('Please enter the PO Number before marking this quote as Won.'))
        self.x_final_quote_locked = True
        self.x_quote_stage = 'won'
        self.x_lost_reason = False
        self.message_post(
            body=_('Quote marked as <b>Won</b>. PO: <b>%s</b>') % (self.x_po_number or '')
        )
        # Sync linked lead stage to Won + copy PO info
        if self.opportunity_id:
            self.opportunity_id.action_move_to_won(
                po_number=self.x_po_number,
                po_date=self.x_po_date
            )

    def action_mark_lost(self):
        """Mark quote as Lost - requires a lost reason."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mark as Lost'),
            'res_model': 'sale.order',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('custom_crm_extended.view_sale_order_lost_reason_form').id,
            'target': 'new',
        }

    def action_confirm_lost(self):
        """Confirm marking as Lost after reason is selected."""
        self.ensure_one()
        if not self.x_lost_reason:
            raise UserError(_('Please select a Lost Reason.'))
        self.x_quote_stage = 'lost'
        self.message_post(
            body=_('Quote marked as <b>Lost</b>. Reason: %s') % (
                dict(self._fields['x_lost_reason'].selection).get(self.x_lost_reason, '')
            )
        )
        return {'type': 'ir.actions.act_window_close'}

    def action_handoff_to_service(self):
        """Mark as handed off to service team."""
        self.ensure_one()
        if not self.x_assigned_to_service:
            raise UserError(_('Please select a Service team member before handoff.'))
        self.x_handoff_date = fields.Date.today()
        self.message_post(
            body=_('Handed off to service: <b>%s</b>. Remarks: %s') % (
                self.x_assigned_to_service.name,
                self.x_service_remarks or '—'
            )
        )
        # Schedule an activity for the service person
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.x_assigned_to_service.id,
            note=_('New order handed off for service delivery. Order: %s') % self.name,
        )


class SaleOrderLine(models.Model):
    """
    Extends sale.order.line.

    Existing fields used:
        product_id          - Product
        product_uom_qty     - Quantity
        product_uom         - Unit of Measure
        price_unit          - Unit Price
        discount            - % Discount per line (requires sale.group_discount_per_so_line)
        tax_id              - Taxes (GST, etc.) Many2many
        price_subtotal      - Subtotal (computed, no tax)
        price_total         - Total (computed, with tax)
        name                - Description
    """
    _inherit = 'sale.order.line'

    x_category_id = fields.Many2one('product.category', string='Category')
    x_sub_category_id = fields.Many2one('product.category', string='Sub Category')
    x_product_code = fields.Char(string='Product ID')
    x_product_name = fields.Char(string='Product Name')
    x_product_name_m2o = fields.Many2one(
        'product.product',
        string='Product Name Search',
        store=False,
    )
    x_hsn_code = fields.Char(string='HSN/SAC')
    x_make = fields.Char(string='Make / Brand')
    x_default_price = fields.Float(string='Master Price', digits='Product Price')
    x_notes = fields.Char(string='Notes')
    x_technical_specs = fields.Text(string='Technical Specifications')
    x_product_image = fields.Binary(string='Product Image')
    x_product_image_name = fields.Char(string='Product Image Name')

    # Toggle to show/hide Cost/Profit/Margin columns (admin only)
    x_show_cost_profit = fields.Boolean(
        string='Show Cost / Profit',
        default=False,
        help='Toggle to show or hide Cost, Profit and Margin columns. Admin only.',
    )

    # Cost field - visible to admin only (groups restriction in view)
    x_cost = fields.Float(
        string='Cost',
        digits='Product Price',
        default=0.0,
        help='Internal cost price. Not shown in quotation PDF.',
    )

    x_profit = fields.Float(
        string='Profit',
        compute='_compute_profit',
        digits='Product Price',
        store=True,
        help='Selling price minus cost price.',
    )

    x_profit_pct = fields.Float(
        string='Margin %',
        compute='_compute_profit',
        digits=(5, 2),
        store=True,
        help='Profit as percentage of selling price.',
    )

    @api.depends('price_unit', 'x_cost', 'product_uom_qty', 'discount')
    def _compute_profit(self):
        for line in self:
            sell = line.price_unit * (1 - (line.discount or 0) / 100) * (line.product_uom_qty or 1)
            cost = (line.x_cost or 0) * (line.product_uom_qty or 1)
            line.x_profit = sell - cost
            line.x_profit_pct = (line.x_profit / sell * 100) if sell else 0.0

    # ------------------------------------------------------------------
    # Flat discount per line (in addition to % discount)
    # ------------------------------------------------------------------
    x_flat_discount_line = fields.Float(
        string='Flat Disc.',
        default=0.0,
        digits='Product Price',
        help='Fixed amount discount on this line.',
    )

    x_price_after_flat_disc = fields.Float(
        string='Net Unit Price',
        compute='_compute_net_price',
        store=True,
        digits='Product Price',
        help='Unit price after applying flat line discount.',
    )

    # ------------------------------------------------------------------
    # GST visibility helper  (read from parent order toggle)
    # ------------------------------------------------------------------
    x_show_gst = fields.Boolean(
        string='Show GST',
        related='order_id.x_gst_included',
        store=False,
    )


    @api.onchange('product_id')
    def _onchange_product_id_apply_discount(self):
        """Apply order-level discount when product is selected."""

        # Clear taxes if GST is OFF
        if self.product_id and not self.order_id.x_gst_included:
            self.tax_ids = [(5, 0, 0)]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for line in records:
            if not line.display_type:

                # Clear taxes if GST OFF
                if not line.order_id.x_gst_included:
                    line.write({'tax_ids': [(5, 0, 0)]})
        return records

    def _fill_custom_product_fields(self, product):
        categ = product.categ_id
        self.x_category_id = categ.parent_id if categ and categ.parent_id else categ
        self.x_sub_category_id = categ if categ and categ.parent_id else False
        self.x_product_code = product.default_code or ''
        self.x_product_name = product.with_context(lang='en_US').name or ''
        self.x_hsn_code = product.l10n_in_hsn_code or ''
        self.x_make = product.x_make or ''
        self.x_default_price = product.list_price or 0.0

    @api.onchange('product_id')
    def _onchange_custom_product_fields(self):
        if self.product_id:
            self._fill_custom_product_fields(self.product_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            product_id = vals.get('product_id')
            if product_id:
                product = self.env['product.product'].browse(product_id)
                categ = product.categ_id
                if not vals.get('x_category_id'):
                    vals['x_category_id'] = categ.parent_id.id if categ and categ.parent_id else categ.id if categ else False
                if not vals.get('x_sub_category_id'):
                    vals['x_sub_category_id'] = categ.id if categ and categ.parent_id else False
                if not vals.get('x_product_code'):
                    vals['x_product_code'] = product.default_code or ''
                if not vals.get('x_product_name'):
                    vals['x_product_name'] = product.with_context(lang='en_US').name or ''
                if not vals.get('x_hsn_code'):
                    vals['x_hsn_code'] = product.l10n_in_hsn_code or ''
                if not vals.get('x_make'):
                    vals['x_make'] = product.x_make or ''
                if not vals.get('x_default_price'):
                    vals['x_default_price'] = product.list_price or 0.0
        return super().create(vals_list)

    # ==================================================================
    # COMPUTE
    # ==================================================================

    @api.depends('price_unit', 'x_flat_discount_line', 'product_uom_qty')
    def _compute_net_price(self):
        for line in self:
            if line.product_uom_qty:
                per_unit_flat = line.x_flat_discount_line / line.product_uom_qty
            else:
                per_unit_flat = 0.0
            line.x_price_after_flat_disc = max(0.0, line.price_unit - per_unit_flat)

    # ==================================================================
    # OVERRIDE price_subtotal to factor in flat line discount
    # ==================================================================
    # NOTE: We do NOT override _compute_amount because Odoo's tax engine
    # uses price_unit * (1 - discount/100) internally. Instead, we use
    # x_flat_discount_line as a display/info field and the salesperson
    # adjusts price_unit manually if they want it reflected in totals,
    # OR the client confirms they want a computed override (Phase 2).
    # This keeps the module safe and non-breaking for the tax engine.


class SaleOrderLineExtended(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('x_product_name_m2o')
    def _onchange_product_name_m2o(self):
        if self.x_product_name_m2o:
            self.product_id = self.x_product_name_m2o
            self.x_product_name = self.x_product_name_m2o.with_context(lang='en_US').name

    @api.onchange('product_id')
    def _onchange_product_internal_note(self):
        """Sync product name m2o and internal notes when product_id changes."""
        if self.product_id:
            # Sync x_product_name_m2o with product_id
            self.x_product_name_m2o = self.product_id
            # Auto-fill internal notes
            if self.product_id.description:
                import re
                clean_note = re.sub(r'<[^>]+>', '', str(self.product_id.description)).strip()
                if clean_note:
                    self.x_notes = clean_note
