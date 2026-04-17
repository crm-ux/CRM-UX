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
        priority        – Priority  (0/1/2 = Normal/High/Very High)
        currency_id     – Currency
        stage_id        – Stage
        tag_ids         – Tags
        expected_revenue– Expected Revenue
        description     – Notes / Internal Notes
    """
    _inherit = 'crm.lead'

    # ------------------------------------------------------------------
    # 1. ASSIGNMENT & OWNERSHIP
    # ------------------------------------------------------------------
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
                self.priority = '2'  # Very High
            elif any(kw in src_name for kw in ['social', 'email', 'campaign']):
                self.priority = '1'  # High
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
        self.write({
            'x_is_refused': False,
            'x_assign_to_id': False,
            'x_refused_by_id': False,
            'x_refuse_reason': False,
            'x_refuse_date': False,
        })
        self.message_post(body=_('Lead has been reset after refusal and returned to owner.'))
