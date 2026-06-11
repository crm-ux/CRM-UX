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

    def _get_stage_by_sequence(self, sequence):
        return self.env['crm.stage'].search([('sequence', '=', sequence)], limit=1)

    def action_move_to_qualified(self):
        stage = self._get_stage_by_sequence(1)
        if stage:
            self.stage_id = stage

    def action_move_to_opportunity(self):
        stage = self._get_stage_by_sequence(2)
        if stage:
            self.stage_id = stage

    def action_move_to_quotes(self):
        stage = self._get_stage_by_sequence(3)
        if stage:
            self.stage_id = stage

    def action_new_quotation(self):
        self.ensure_one()
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

