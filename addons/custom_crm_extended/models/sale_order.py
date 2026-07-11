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
            terms = self.env['sale.terms.condition'].search([], order='sequence, id')
            if terms:
                items = ''.join('<li>%s</li>' % (t.content or '') for t in terms)
                res['note'] = '<ol>%s</ol>' % items
            else:
                res['note'] = ''
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
    x_discount_label = fields.Char(
        string='Overall Discount Label',
        compute='_compute_discount_totals',
        store=True,
    )

    # ------------------------------------------------------------------
    # 4. PO DETAILS  (filled at PO stage, after quote is accepted)
    # ------------------------------------------------------------------
    x_invoice_number = fields.Char(string='Invoice No', tracking=True, copy=False)
    x_invoice_date = fields.Date(string='Invoice Date', tracking=True, copy=False)
    x_sales_order_number = fields.Char(string='Sales Order No', tracking=True, copy=False)
    x_uw_po_number = fields.Char(string='UW Purchase Order', tracking=True, copy=False)

    x_contact_person = fields.Char(
        string='Contact Person',
        help='Auto-filled from linked CRM lead contact name',
    )
    x_contact_person_id = fields.Many2one(
        'res.partner',
        string='Contact Person',
        domain="[('parent_id', '=', partner_id), ('is_company', '=', False)]",
        help='Select contact person from customer contacts',
        context={'show_address': False, 'no_display_parent': True},
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
    x_draft_signature_photo = fields.Binary(string='Draft Signature Photo')
    x_draft_best_offer = fields.Char(string='Draft Best Offer For')
    x_draft_image_ids = fields.Many2many(
        'ir.attachment', 'sale_order_draft_image_rel',
        'order_id', 'attachment_id',
        string='Draft Quote Images'
    )
    x_draft_term_ids = fields.Many2many(
        'sale.terms.condition', 'sale_order_draft_term_rel',
        'order_id', 'term_id',
        string='Draft Selected Terms'
    )
    x_draft_gst_included = fields.Boolean(string='Draft GST Included', default=True)
    x_draft_valid_until = fields.Date(string='Draft Valid Until')
    x_draft_quote_name = fields.Char(string='Draft Quotation No')
    x_draft_contact_person = fields.Char(string='Draft Contact Person')
    x_draft_contact_function = fields.Char(string='Draft Contact Function')
    x_draft_subject = fields.Char(string='Draft Subject')
    x_draft_quote_date = fields.Date(string='Draft Quote Date')
    x_draft_buyer_name = fields.Char(string='Draft Buyer Name')

    # ------------------------------------------------------------------
    # 7. QUOTE STATUS STAGE (beyond default state)
    # ------------------------------------------------------------------
    x_quote_type = fields.Selection([
        ('lead', 'Lead Quote'),
        ('direct', 'Direct Quote'),
    ], string='Quote Type', compute='_compute_quote_type', store=True)

    @api.depends('opportunity_id')
    def _compute_quote_type(self):
        for rec in self:
            rec.x_quote_type = 'lead' if rec.opportunity_id else 'direct'

    x_quote_stage = fields.Selection(
        selection=[
            ('draft',          'New'),
            ('sent',           'Sent'),
            ('negotiation',    'Negotiation'),
            ('order_expected', 'Order Expected'),
            ('po_received',    'PO Received'),
            ('won',            'Won'),
            ('lost',           'Lost'),
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
                 'order_line.price_unit', 'order_line.product_uom_qty',
                 'order_line.tax_ids', 'x_gst_included')
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
            # Net after all discounts (before tax)
            net_after_discount = max(0.0, subtotal_after_line_disc - total_disc)
            # Recompute tax on the DISCOUNTED net, not on the raw pre-discount subtotal,
            # so this matches the PDF/DOCX quotation logic exactly.
            tax_rates = set()
            for line in order.order_line.filtered(lambda l: not l.display_type):
                for tax in line.tax_ids:
                    tax_rates.add(tax.amount)
            total_tax_rate = sum(tax_rates)
            tax_on_net = net_after_discount * total_tax_rate / 100.0 if (order.x_gst_included and tax_rates) else 0.0
            # Net total = discounted subtotal + tax computed on that discounted amount
            order.x_net_total = net_after_discount + tax_on_net
            order.x_discount_label = 'Overall Discount (%s%%)' % (int(order.x_flat_discount_pct) if order.x_flat_discount_pct == int(order.x_flat_discount_pct) else order.x_flat_discount_pct)
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
        all_terms = self.env['sale.terms.condition'].search([], order='sequence, id')
        # Load saved terms from order note, or use all terms for new quote
        saved_terms = self.env['sale.terms.condition'].search([], order='sequence, id')
        if self.note:
            # Try to match saved terms
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(self.note, 'html.parser')
            saved_contents = [li.get_text().strip() for li in soup.find_all('li')]
            if saved_contents:
                matched = self.env['sale.terms.condition'].search([
                    ('content', 'in', saved_contents)
                ], order='sequence, id')
                if matched:
                    saved_terms = matched

        # Use draft fields if saved, else use order defaults
        has_draft = bool(self.x_draft_term_ids or self.x_draft_quote_name or self.x_draft_best_offer or self.x_draft_tech_specs)
        wizard_vals = {
            'order_id': self.id,
            'selected_term_ids': [(6, 0, self.x_draft_term_ids.ids)] if self.x_draft_term_ids else [(6, 0, saved_terms.ids)],
            'seller_name': self.company_id.name or '',
            'buyer_name': self.x_draft_buyer_name or self.partner_id.name or '',
            'contact_person': self.x_draft_contact_person or self.x_contact_person_id.name or self.x_contact_person or '',
            'contact_function': self.x_draft_contact_function or self.x_contact_person_id.function or '',
            'quote_name': self.x_draft_quote_name or self.name or '',
            'quote_date': self.x_draft_quote_date or (self.date_order.date() if self.date_order else fields.Date.today()),
            'valid_until': self.x_draft_valid_until or self.validity_date,
            'subject': self.x_draft_subject or 'Quotation for Products / Services',
            'x_gst_included': self.x_draft_gst_included if has_draft else self.x_gst_included,
            'best_offer_for': self.x_draft_best_offer or '',
            'technical_specs_html': self.x_draft_tech_specs or False,
            'signature_photo': self.x_draft_signature_photo or (self.user_id.x_signature_card if self.user_id else False),
        }
        if self.x_draft_image_ids:
            wizard_vals['quote_image_ids'] = [(6, 0, self.x_draft_image_ids.ids)]
        wizard = self.env['sale.quote.preview.wizard'].with_context(
            default_order_id=self.id
        ).sudo().create(wizard_vals)
        wizard._rebuild_document_html()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Editable Quotation Preview',
            'res_model': 'sale.quote.preview.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
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



    @api.depends_context('lang')
    @api.depends('order_line.price_subtotal', 'currency_id', 'company_id', 'payment_term_id')
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for order in self:
            if order.tax_totals and order.tax_totals.get('subtotals'):
                for subtotal in order.tax_totals['subtotals']:
                    if subtotal.get('name') == 'Untaxed Amount':
                        subtotal['name'] = 'Total Amount'
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

    def action_quotation_send(self):
        """Override default send action to mark stage as Sent immediately."""
        self.ensure_one()
        # Auto-set stage to Sent regardless of email result
        if self.x_quote_stage in ('draft', 'new', 'draft'):
            self.x_quote_stage = 'sent'
            if self.opportunity_id:
                self.opportunity_id.action_move_to_sent_sync()
        try:
            result = super().action_quotation_send()
        except Exception:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    def action_move_to_negotiation_from_sent(self):
        """Move quote from Sent to Negotiation stage."""
        self.ensure_one()
        self.x_quote_stage = 'negotiation'
        self.message_post(body=_('Quote moved to <b>Negotiation</b>.'))
        if self.opportunity_id:
            self.opportunity_id.action_move_to_negotiation_sync()

    def action_move_to_negotiation(self):
        """Move quote stage to Negotiation. Admin can move any quote, user only their own. Unlocks the quote, clears PO so it must be re-entered."""
        self.ensure_one()
        if self.env.user.id != 2 and self.user_id.id != self.env.user.id:
            raise UserError(_('You can only move your own quotes to Negotiation.'))
        self.x_quote_stage = 'negotiation'
        self.x_final_quote_locked = False
        self.x_po_number = False
        self.x_po_date = False
        self.message_post(body=_('Quote moved back to <b>Negotiation</b>, unlocked, and PO number cleared.'))
        if self.opportunity_id:
            self.opportunity_id.action_move_to_negotiation_sync()

    def action_admin_move_back(self):
        self.ensure_one()
        stage_order = ['draft', 'sent', 'negotiation', 'order_expected', 'won']
        current = self.x_quote_stage
        if current in stage_order:
            idx = stage_order.index(current)
            if idx > 0:
                prev_stage = stage_order[idx - 1]
                self.x_quote_stage = prev_stage
                self.x_final_quote_locked = False
                self.message_post(body=_('Quote moved back to <b>%s</b> by admin.') % prev_stage.title())
                if self.opportunity_id:
                    sync_map = {
                        'draft': 30, 'sent': 35, 'negotiation': 40,
                        'order_expected': 50, 'won': 90
                    }
                    seq = sync_map.get(prev_stage)
                    if seq:
                        stage = self.opportunity_id._get_stage_by_sequence(seq)
                        if stage:
                            self.opportunity_id.with_context(bypass_stage_lock=True).write({'stage_id': stage.id})

    def action_move_to_order_expected(self):
        self.ensure_one()
        if self.env.user.id != 2 and self.user_id.id != self.env.user.id:
            raise UserError(_('You can only move your own quotes.'))
        self.x_quote_stage = 'order_expected'
        self.message_post(body=_('Quote moved to <b>Order Expected</b>.'))
        if self.opportunity_id:
            self.opportunity_id.action_move_to_order_expected_sync()

    def action_mark_won(self):
        """Mark quote as Won - opens PO entry popup if PO number missing, else confirms directly."""
        self.ensure_one()
        if not self.x_po_number:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Enter Purchase Order'),
                'res_model': 'sale.order',
                'res_id': self.id,
                'view_mode': 'form',
                'view_id': self.env.ref('custom_crm_extended.view_sale_order_won_po_form').id,
                'target': 'new',
            }
        return self._confirm_won()

    def action_confirm_won(self):
        """Called from the PO popup form - validates PO number then confirms Won."""
        self.ensure_one()
        if not self.x_po_number:
            raise UserError(_('Please enter the PO Number before marking this quote as Won.'))
        self._confirm_won()
        return {'type': 'ir.actions.act_window_close'}

    def _confirm_won(self):
        """Internal: apply Won stage, lock quote, sync lead."""
        self.ensure_one()
        self.x_final_quote_locked = True
        self.x_quote_stage = 'won'
        self.x_lost_reason = False
        self.message_post(
            body=_('Quote marked as <b>Won</b>. PO: <b>%s</b>') % (self.x_po_number or '')
        )
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
    x_product_name = fields.Char(
        string='Product Name',
        compute='_compute_x_product_name',
        store=True,
        readonly=False,
    )

    @api.depends('product_id')
    def _compute_x_product_name(self):
        for line in self:
            if line.product_id:
                line.x_product_name = line.product_id.product_tmpl_id.with_context(lang='en_US').name or ''
            elif not line.x_product_name:
                line.x_product_name = ''
    x_product_name_m2o = fields.Many2one(
        'product.product',
        string='Product Name',
        store=True,
        ondelete='set null',
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
        self.x_product_name = product.product_tmpl_id.with_context(lang='en_US').name or product.with_context(lang='en_US').name or ''
        self.x_hsn_code = product.l10n_in_hsn_code or ''
        self.x_make = product.x_make or product.product_tmpl_id.x_make or ''
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
                    vals['x_make'] = product.x_make or product.product_tmpl_id.x_make or ''
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

    @api.onchange('product_id')
    def _onchange_product_internal_note(self):
        """Sync product name m2o and internal notes when product_id changes."""
        if self.product_id:
            self.x_product_name_m2o = self.product_id
            # Auto-fill internal notes
            if self.product_id.description:
                import re
                clean_note = re.sub(r'<[^>]+>', '', str(self.product_id.description)).strip()
                if clean_note:
                    self.x_notes = clean_note
            # Keep line taxes consistent with the order's own GST toggle,
            # regardless of the product's own default tax configuration.
            if self.order_id and not self.order_id.x_gst_included:
                self.tax_ids = [(5, 0, 0)]


class SaleOrderSettings(models.Model):
    _inherit = 'sale.order'

    def action_go_dashboard(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/odoo/action-435',
            'target': 'self',
        }

    def action_open_settings(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/odoo/settings',
            'target': 'self',
        }


class ResPartnerContactName(models.Model):
    _inherit = 'res.partner'

    def _get_name(self):
        if self.env.context.get('no_display_parent'):
            return self.name or ''
        return super()._get_name()

    def name_get(self):
        if self.env.context.get('no_display_parent'):
            return [(p.id, p.name or '') for p in self]
        return super().name_get()




class DashboardStats(models.Model):
    _inherit = 'crm.lead'

    @api.model
    def get_dashboard_stats(self, user_id, is_admin):
        """Return all dashboard stats in a single DB round-trip."""
        uid = user_id
        cr = self.env.cr

        # Lead stage counts
        lead_domain = [('active', '=', True)]
        if not is_admin:
            lead_domain.append(('user_id', '=', uid))
        leads = self.env['crm.lead'].read_group(
            lead_domain, ['x_stage_sequence'], ['x_stage_sequence'])
        lead_counts = {r['x_stage_sequence']: r['x_stage_sequence_count'] for r in leads}

        # Quote stage counts
        quote_domain = [('state', '!=', 'cancel')]
        if not is_admin:
            quote_domain.append(('user_id', '=', uid))
        quotes = self.env['sale.order'].read_group(
            quote_domain, ['x_quote_stage'], ['x_quote_stage'])
        quote_counts = {r['x_quote_stage']: r['x_quote_stage_count'] for r in quotes}

        # Revenue
        won_orders = self.env['sale.order'].search([('x_quote_stage', '=', 'won')])
        won_revenue = sum(won_orders.mapped('amount_total'))

        pending_orders = self.env['sale.order'].search([
            ('x_quote_stage', 'not in', ['won', 'lost']),
            ('state', '!=', 'cancel')
        ])
        quote_revenue = sum(pending_orders.mapped('amount_total'))

        from datetime import date
        today = date.today().strftime('%Y-%m-%d')
        today_orders = self.env['sale.order'].search([
            ('x_quote_stage', '=', 'won'),
            ('date_order', '>=', today + ' 00:00:00')
        ])
        today_revenue = sum(today_orders.mapped('amount_total'))

        # Other counts
        customers = self.env['res.partner'].search_count([('customer_rank', '>', 0)])
        products = self.env['product.template'].search_count([('sale_ok', '=', True)])
        users = self.env['res.users'].search_count([('active', '=', True), ('share', '=', False)])
        exhibition = self.env['exhibition.contact'].search_count([])

        return {
            'lead_counts': lead_counts,
            'quote_counts': quote_counts,
            'won_revenue': won_revenue,
            'quote_revenue': quote_revenue,
            'today_revenue': today_revenue,
            'customers': customers,
            'products': products,
            'users': users,
            'exhibition': exhibition,
        }
