# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    """
    Extends the default crm.lead model.

    Existing fields we REUSE (no redeclaration needed):
        name            – Opportunity / Lead Title
        partner_name    – Company Name
        contact_name    – Contact Person
        email_from      – Email
        phone           – Phone
        mobile          – Mobile
        function        – Job Title  (maps to function/job position)
        city            – City
        state_id        – State
        country_id      – Country
        user_id         – Salesperson (we rename label to "Lead Owner")
        team_id         – Sales Team
        source_id       – Lead Source  (utm.source)
        priority        – Priority  (0/1/2 = Low/Medium/High)
        currency_id     – Currency
        stage_id        – Stage
        tag_ids         – Tags
        expected_revenue– Expected Revenue
        description     – Notes / Internal Notes
    """
    _inherit = 'crm.lead'

    priority = fields.Selection(
        selection=[
            ('0', 'Low'),
            ('1', 'Medium'),
            ('2', 'High'),
        ],
        string='Priority',
        default='0',
        index=True,
    )

    # ------------------------------------------------------------------
    # 1. ASSIGNMENT & OWNERSHIP
    # ------------------------------------------------------------------
    x_original_owner_id = fields.Many2one('res.users', string='Original Owner', store=True)
    x_assign_to_id = fields.Many2one(
        'res.users',
        string='Assign To',
        tracking=True,
        help='Assign this lead to a team member. Only Team Leaders and Admins can change this field.',
        domain="[('share', '=', False)]",
        copy=False,
    )

    x_refused_by_id = fields.Many2one(
        'res.users',
        string='Refused By',
        readonly=True,
        copy=False,
        help='User who refused this assignment.',
    )

    x_refuse_reason = fields.Text(
        string='Refusal Reason',
        readonly=True,
        copy=False,
    )

    x_refuse_date = fields.Datetime(
        string='Refused On',
        readonly=True,
        copy=False,
    )

    x_is_refused = fields.Boolean(
        string='Refused',
        default=False,
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # 2. CUSTOMER CLASSIFICATION
    # ------------------------------------------------------------------
    x_customer_type = fields.Selection(
        selection=[
            ('existing_existing', 'Existing Customer – Existing Product'),
            ('existing_new',      'Existing Customer – New Product'),
            ('new_existing',      'New Customer – Existing Product'),
            ('new_new',           'New Customer – New Product'),
        ],
        string='Customer Type',
        tracking=True,
        help='Classify the type of customer and opportunity.',
    )

    # ------------------------------------------------------------------
    # 3. PURCHASE TIMELINE
    # ------------------------------------------------------------------
    x_purchase_timeline = fields.Selection(
        selection=[
            ('immediate',   'Immediate (0–1 Month)'),
            ('short',       'Short Term (1–3 Months)'),
            ('medium',      'Medium Term (3–6 Months)'),
            ('long',        'Long Term (6–12 Months)'),
            ('future',      'Future (12+ Months)'),
        ],
        string='Purchase Timeline',
        tracking=True,
    )

    # ------------------------------------------------------------------
    # 4. PRODUCT CATEGORIES  (multi-select – Many2many to product.category)
    # ------------------------------------------------------------------
    x_product_category_ids = fields.Many2many(
        'product.category',
        'crm_lead_product_category_rel',
        'lead_id',
        'category_id',
        string='Product Categories',
        help='Select one or more product categories this opportunity covers.',
    )

    # ------------------------------------------------------------------
    # 5. COMPUTED DISPLAY / HELPER FIELDS
    # ------------------------------------------------------------------
    x_lead_age_days = fields.Integer(
        string='Lead Age (Days)',
        compute='_compute_lead_age',
        store=False,
        help='Number of days since lead was created.',
    )

    x_is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_lead_age',
        store=False,
        help='True if lead is older than 30 days without activity.',
    )

    # ------------------------------------------------------------------
    # 6. ROLE-BASED FIELD CONTROL
    # ------------------------------------------------------------------
    x_assign_to_readonly = fields.Boolean(
        string='Assign To Read-only',
        compute='_compute_assign_to_readonly',
        store=False,
    )

    # ==================================================================
    # COMPUTE METHODS
    # ==================================================================

    @api.depends('create_date')
    def _compute_lead_age(self):
        today = fields.Date.today()
        for lead in self:
            if lead.create_date:
                delta = today - lead.create_date.date()
                lead.x_lead_age_days = delta.days
                lead.x_is_overdue = delta.days > 30
            else:
                lead.x_lead_age_days = 0
                lead.x_is_overdue = False

    def _compute_assign_to_readonly(self):
        """
        Normal sales reps cannot change x_assign_to_id.
        Team Leaders (CRM: manage) and Admins can.
        """
        is_manager = self.env.user.has_group('crm.group_crm_manager') or \
                     self.env.user.has_group('base.group_system')
        for lead in self:
            lead.x_assign_to_readonly = not is_manager

    # ==================================================================
    # ONCHANGE – auto-set priority based on lead source
    # ==================================================================

    @api.onchange('source_id')
    def _onchange_source_priority(self):
        """
        Auto-suggest priority based on lead source.
        High-value sources (referral, direct) → High priority.
        Adjust source names/IDs to match your actual data.
        """
        if self.source_id:
            src_name = (self.source_id.name or '').lower()
            if any(kw in src_name for kw in ['referral', 'direct', 'reference', 'partner']):
                self.priority = '2'  # High
            elif any(kw in src_name for kw in ['social', 'email', 'campaign']):
                self.priority = '1'  # Medium
            # else keep existing

    # ==================================================================
    # REFUSAL WORKFLOW
    # ==================================================================

    def action_refuse_lead(self):
        """
        Opens the refuse wizard. Called from the form button.
        The assigned user (x_assign_to_id) can refuse the lead,
        returning it to the original owner (user_id).
        """
        self.ensure_one()
        # Only the assigned person OR a manager can refuse
        is_manager = self.env.user.has_group('crm.group_crm_manager') or \
                     self.env.user.has_group('base.group_system')
        if not is_manager and self.x_assign_to_id != self.env.user:
            raise UserError(_('Only the assigned user or a manager can refuse this lead.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Refuse Lead / Opportunity'),
            'res_model': 'crm.lead.refuse.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lead_id': self.id},
        }

    def action_reset_from_refusal(self):
        """
        Owner can reset a refused lead back to active.
        """
        self.ensure_one()
        if self.user_id != self.env.user and \
           not self.env.user.has_group('crm.group_crm_manager') and \
           not self.env.user.has_group('base.group_system'):
            raise UserError(_('Only the lead owner or a manager can reset this lead.'))
        # Restore original owner
        original_owner = self.x_original_owner_id or self.user_id
        self.write({
            'x_is_refused': False,
            'x_assign_to_id': False,
            'x_refused_by_id': False,
            'x_refuse_reason': False,
            'x_refuse_date': False,
            'user_id': original_owner.id,
            'x_original_owner_id': False,
        })
        self.message_post(body=_('Lead reset after refusal. Returned to owner: %s') % original_owner.name)

    # ------------------------------------------------------------------
    # 7. PRODUCT INTEREST LINES  (One2many to crm.lead.product.line)
    # ------------------------------------------------------------------
    x_product_line_ids = fields.One2many(
        'crm.lead.product.line',
        'lead_id',
        string='Product Interest Lines',
        copy=True,
    )

    # ==================================================================
    # CSV IMPORT ACTION
    # ==================================================================

    def action_import_products_csv(self):
        """Opens the CSV import wizard for this lead."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Products from CSV'),
            'res_model': 'crm.lead.csv.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lead_id': self.id},
        }

    x_stage_sequence = fields.Integer(
        string='Stage Sequence',
        compute='_compute_stage_sequence',
        store=True
    )

    @api.depends('stage_id')
    def _compute_stage_sequence(self):
        for rec in self:
            rec.x_stage_sequence = rec.stage_id.sequence if rec.stage_id else 0

    @api.onchange('x_assign_to_id')
    def _onchange_assign_to_id(self):
        if self.x_assign_to_id:
            # Store original owner before changing user_id
            if not self.x_original_owner_id:
                self.x_original_owner_id = self.user_id
            self.user_id = self.x_assign_to_id

    # PO fields synced from won quotation
    x_po_number = fields.Char(string='PO Number', readonly=True, copy=False)
    x_po_date = fields.Date(string='PO Date', readonly=True, copy=False)

    def _get_stage_by_sequence(self, sequence):
        return self.env['crm.stage'].search([('sequence', '=', sequence)], limit=1)

    def action_move_to_contacted(self):
        stage = self._get_stage_by_sequence(5)
        if stage:
            self.stage_id = stage

    def action_move_to_technical_discussion(self):
        stage = self._get_stage_by_sequence(7)
        if stage:
            self.stage_id = stage

    def action_move_to_qualified(self):
        stage = self._get_stage_by_sequence(10)
        if stage:
            self.stage_id = stage

    def action_move_to_opportunity(self):
        stage = self._get_stage_by_sequence(20)
        if stage:
            self.stage_id = stage

    def action_move_to_quotes(self):
        stage = self._get_stage_by_sequence(30)
        if stage:
            self.with_context(bypass_stage_lock=True).write({'stage_id': stage.id})

    def action_move_to_negotiation(self):
        stage = self._get_stage_by_sequence(40)
        if stage:
            self.stage_id = stage

    def action_move_to_order_expected(self):
        stage = self._get_stage_by_sequence(50)
        if stage:
            self.stage_id = stage

    def action_open_won_po_wizard(self):
        """Open PO entry popup before marking lead as Won directly."""
        self.ensure_one()

        # Block Won if no quotation exists
        quotation = self.env['sale.order'].search([
            ('opportunity_id', '=', self.id),
        ], order='id desc', limit=1)

        if not quotation:
            raise UserError(_(
                'Cannot mark as Won without a quotation. \n'
                'Please create a quotation first using the "New Quotation" button.'
            ))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Mark Lead as Won',
            'res_model': 'crm.lead.won.po.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lead_id': self.id},
        }

    def action_move_to_won(self, po_number=False, po_date=False):
        """Called by sale.order when quote is marked Won - syncs lead stage + PO info."""
        stage = self._get_stage_by_sequence(90)
        if stage:
            self.with_context(bypass_stage_lock=True).stage_id = stage
        if po_number:
            self.x_po_number = po_number
        if po_date:
            self.x_po_date = po_date

    def action_move_to_negotiation_sync(self):
        """Called by sale.order when quote is moved to Negotiation - syncs lead stage."""
        stage = self._get_stage_by_sequence(40)
        if stage:
            self.with_context(bypass_stage_lock=True).stage_id = stage

    def action_move_to_sent_sync(self):
        """Called by sale.order when quote is sent - keeps lead in Quotes stage."""
        stage = self._get_stage_by_sequence(30)
        if stage and (not self.stage_id or self.stage_id.sequence < 30):
            self.with_context(bypass_stage_lock=True).stage_id = stage

    def write(self, vals):
        # Block moving stage BACKWARD once past Technical Discussion (sequence 7)
        # Admin (uid=2 or uid=11) can bypass all restrictions
        is_admin = self.env.user.id in (2, 11) or self.env.user.has_group('base.group_system')
        if 'stage_id' in vals and vals.get('stage_id') and not self.env.context.get('bypass_stage_lock') and not is_admin:
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            for rec in self:
                if rec.stage_id and rec.stage_id.sequence > 7 and new_stage.sequence < rec.stage_id.sequence:
                    raise UserError(_(
                        'You cannot move this lead back to an earlier stage once it has passed Technical Discussion.'
                    ))
            # Block manually setting Negotiation/Won stages - must go through the quote action buttons
            if new_stage.sequence in (40, 90):
                raise UserError(_(
                    'The "%s" stage can only be reached automatically when a quotation is Sent, '
                    'moved to Negotiation, or marked Won. Please use the quote buttons instead.'
                ) % new_stage.name)

        res = super().write(vals)

        # Auto-move to Technical Discussion when notes are saved (only if still before that stage)
        if 'description' in vals and vals.get('description'):
            for rec in self:
                if rec.stage_id and rec.stage_id.sequence <= 5:
                    tech_stage = rec._get_stage_by_sequence(7)
                    if tech_stage:
                        super(CrmLead, rec).write({'stage_id': tech_stage.id})
        return res

    def action_new_quotation(self):
        self.ensure_one()
        # Moving to Quotes stage signals quotation process has started
        if self.stage_id and self.stage_id.sequence < 30:
            self.action_move_to_quotes()
        # Check if quotation already exists for this lead
        existing_quote = self.env['sale.order'].search([
            ('opportunity_id', '=', self.id),
            ('state', 'in', ['draft', 'sent'])
        ], order='id desc', limit=1)
        if existing_quote:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Quotation',
                'res_model': 'sale.order',
                'res_id': existing_quote.id,
                'view_mode': 'form',
                'target': 'current',
            }
        # Build order lines from product interest lines
        order_lines = []
        for line in self.x_product_line_ids:
            if not line.product_id:
                continue
            order_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.x_product_name or line.product_id.name,
                'product_uom_qty': line.x_qty or 1.0,
                'price_unit': line.x_unit_price or line.x_default_price or line.product_id.list_price,
                'discount': line.x_discount or 0.0,
                'product_uom_id': line.x_uom_id.id if line.x_uom_id else line.product_id.uom_id.id,
                'tax_ids': [(6, 0, line.x_tax_ids.ids)] if line.x_tax_ids else [(6, 0, line.product_id.taxes_id.ids)],
                'x_category_id': line.x_category_id.id if line.x_category_id else False,
                'x_sub_category_id': line.x_sub_category_id.id if line.x_sub_category_id else False,
                'x_product_code': line.x_product_code or line.product_id.default_code or '',
                'x_product_name': line.x_product_name or line.product_id.name or '',
                'x_hsn_code': line.x_hsn_code or '',
                'x_make': line.x_make or '',
                'x_default_price': line.x_default_price or 0.0,
                'x_notes': line.x_notes or '',
            }))

        # Find or create partner from lead contact info
        # Always use company (parent) partner, not contact child
        if self.partner_id and self.partner_id.parent_id:
            partner_id = self.partner_id.parent_id.id
        else:
            partner_id = self.partner_id.id if self.partner_id else False
        customer_name = self.partner_name or self.contact_name or self.name
        if not partner_id and customer_name:
            partner = self.env['res.partner'].search(
                [('name', '=', customer_name)], limit=1)
            if not partner:
                partner = self.env['res.partner'].create({
                    'name': customer_name,
                    'email': self.email_from or '',
                    'phone': self.phone or self.x_mobile or '',
                    'city': self.city or '',
                    'state_id': self.state_id.id if self.state_id else False,
                    'zip': self.zip or '',
                    'is_company': bool(self.partner_name),
                })
            self.partner_id = partner.id
            partner_id = partner.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'New Quotation',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_opportunity_id': self.id,
                'default_partner_id': partner_id,
                'default_order_line': order_lines,
                'default_user_id': self.user_id.id,
                'default_company_id': self.company_id.id if self.company_id else self.env.company.id,
                'default_x_contact_person': self.contact_name or '',
            },
        }

    def get_formview_action(self, access_uid=None):
        if not self:
            return self.action_new_lead_wizard()
        return super().get_formview_action(access_uid=access_uid)

    @api.model
    def action_new_lead_wizard(self):
        """Open multi-step Lead Creation wizard (used by New buttons)."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lead Creation',
            'res_model': 'crm.lead.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context, default_step=1),
        }


class ResPartnerRestrict(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        allowed_ids = [2, 10]  # Admin and Dhruvil
        if self.env.uid not in allowed_ids and not self.env.su:
            for vals in vals_list:
                if vals.get('is_company'):
                    from odoo.exceptions import UserError
                    raise UserError('Only Admin and Dhruvil Shah can create new companies.')
        return super().create(vals_list)


    def action_move_to_order_expected_sync(self):
        """Called by sale.order when quote moves to Order Expected - syncs lead stage."""
        stage = self._get_stage_by_sequence(50)
        if stage:
            self.with_context(bypass_stage_lock=True).write({'stage_id': stage.id})
