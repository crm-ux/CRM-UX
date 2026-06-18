# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re

class CrmLeadWizard(models.TransientModel):
    _name = "crm.lead.wizard"
    _description = "Lead Creation Wizard"

    step = fields.Integer(default=1)
    created_by_id = fields.Many2one("res.users", string="Created By",
        default=lambda self: self.env.user, readonly=True)

    # Step 1
    company_id = fields.Many2one("res.company", string="Our Company",
        default=lambda self: self.env.company, domain="[(1, '=', 1)]")
    name = fields.Char(string="Lead Name")
    partner_name = fields.Char(string="Company Name")
    @api.model
    def _get_company_field_options(self):
        allowed_ids = [2, 10]  # Admin and Dhruvil
        if self.env.uid in allowed_ids:
            return {'quick_create': True, 'no_open': False}
        return {'quick_create': False, 'no_create': True, 'no_open': False}

    partner_company_id = fields.Many2one(
        'res.partner',
        string='Company Name',
        domain=[('is_company', '=', True)],
        context={'default_is_company': True, 'restrict_company_create': True},
    )
    can_create_company = fields.Boolean(
        compute='_compute_can_create_company',
        default=False
    )

    @api.depends_context('uid')
    def _compute_can_create_company(self):
        allowed_ids = [2, 10]  # Admin and Dhruvil
        for rec in self:
            rec.can_create_company = self.env.uid in allowed_ids
    x_customer_type = fields.Selection([
        ("new_new", "New Customer - New Product"),
        ("new_existing", "New Customer - Existing Product"),
        ("existing_new", "Existing Customer - New Product"),
        ("existing_existing", "Existing Customer - Existing Product"),
    ], string="Customer Type", default="new_new")
    partner_id = fields.Many2one("res.partner", string="Existing Customer",
        domain=[("customer_rank", ">", 0)])
    x_requirement_date = fields.Date(string="Date of Requirement")
    source_id = fields.Many2one("utm.source", string="Lead Source")
    user_id = fields.Many2one("res.users", string="Lead Owner",
        default=lambda self: self.env.user, domain=[("share", "=", False)])
    x_lead_priority = fields.Selection([
        ("high", "High"), ("medium", "Medium"), ("low", "Low"),
    ], string="Lead Priority", default="medium")

    # Step 2
    contact_name = fields.Char(string="Contact Person")
    function = fields.Char(string="Job Title")
    contact_picker_id = fields.Many2one(
        'res.partner', string='Select Contact',
        domain="[('parent_id', '=', partner_company_id), ('is_company', '=', False)]",
        help="Company has multiple contacts. Pick one to auto-fill name/job title."
    )
    has_multiple_contacts = fields.Boolean(string='Has Multiple Contacts', default=False)
    email_from = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    x_mobile = fields.Char(string="Mobile")
    city = fields.Char(string="City")
    state_id = fields.Many2one("res.country.state", string="State")
    zip = fields.Char(string="ZIP")

    # Step 3
    x_product_category_ids = fields.Many2many("product.category",
        string="Product Categories")
    x_purchase_timeline = fields.Selection([
        ("immediate", "Immediate (0-1 Month)"),
        ("short", "Short Term (1-3 Months)"),
        ("medium", "Medium Term (3-6 Months)"),
        ("long", "Long Term (6+ Months)"),
    ], string="Purchase Timeline")

    # Step 4
    expected_revenue = fields.Float(string="Expected Revenue")
    probability = fields.Float(string="Probability %", default=10)
    date_deadline = fields.Date(string="Expected Closing")

    # Step 5
    x_assign_to_id = fields.Many2one("res.users", string="Assign To",
        domain=[("share", "=", False)])
    description = fields.Text(string="Notes")

    # Admin check
    is_admin = fields.Boolean(
        compute='_compute_is_admin',
        default=lambda self: self.env.user.has_group('base.group_erp_manager')
    )

    @api.depends_context('uid')
    def _compute_is_admin(self):
        is_admin = self.env.user.has_group('base.group_erp_manager')
        for rec in self:
            rec.is_admin = is_admin

    # Validation flags - show red borders
    e1_name = fields.Boolean(default=False)       # step1: name missing
    e2_contact = fields.Boolean(default=lambda self: self.env.context.get('default_e2_contact', False))    # step2: no contact method

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    @api.onchange('phone')
    def _onchange_phone_digits_only(self):
        if self.phone:
            digits = re.sub(r'\D', '', self.phone)[:10]
            if digits != self.phone:
                self.phone = digits

    @api.onchange('x_mobile')
    def _onchange_mobile_digits_only(self):
        if self.x_mobile:
            digits = re.sub(r'\D', '', self.x_mobile)[:10]
            if digits != self.x_mobile:
                self.x_mobile = digits

    @api.onchange('partner_company_id')
    def _onchange_partner_company_id(self):
        if self.partner_company_id:
            allowed_ids = [2, 10]  # Admin and Dhruvil
            if self.env.uid not in allowed_ids:
                # Check if this partner was just created (not in original domain)
                partner = self.partner_company_id
                existing = self.env['res.partner'].search([
                    ('is_company', '=', True),
                    ('id', '=', partner.id),
                    ('create_uid', '!=', self.env.uid),
                ], limit=1)
                # If partner was created by current user just now
                from datetime import datetime, timedelta
                if partner.create_uid.id == self.env.uid:
                    created_at = partner.create_date
                    if created_at and (datetime.now() - created_at.replace(tzinfo=None)).seconds < 30:
                        partner.sudo().unlink()
                        self.partner_company_id = False
                        self.partner_name = False
                        return {'warning': {
                            'title': 'Not Allowed',
                            'message': 'Only Admin and Dhruvil Shah can create new companies.'
                        }}
            self.partner_name = self.partner_company_id.name
            # Auto-fill Contact Person & Job Title only when company has exactly ONE contact.
            # If multiple contacts exist, leave fields blank so the user picks/types the right one
            # instead of silently grabbing a random contact.
            children = self.env['res.partner'].search([
                ('parent_id', '=', self.partner_company_id.id),
                ('is_company', '=', False),
            ], order='id asc')
            if len(children) == 1:
                child = children[0]
                self.contact_name = child.name or ""
                self.function = child.function or ""
                if not self.email_from:
                    self.email_from = child.email or ""
                if not self.phone:
                    self.phone = child.phone or ""
                self.contact_picker_id = False
                self.has_multiple_contacts = False
            elif len(children) > 1:
                self.contact_name = False
                self.function = False
                self.contact_picker_id = False
                self.has_multiple_contacts = True
            else:
                self.contact_name = False
                self.function = False
                self.contact_picker_id = False
                self.has_multiple_contacts = False

    @api.onchange('contact_picker_id')
    def _onchange_contact_picker_id(self):
        if self.contact_picker_id:
            child = self.contact_picker_id
            self.contact_name = child.name or ""
            self.function = child.function or ""
            if not self.email_from:
                self.email_from = child.email or ""
            if not self.phone:
                self.phone = child.phone or ""
            # Check if newly created by unauthorized user
            allowed_ids = [2, 10]  # Admin and Dhruvil
            if self.env.uid not in allowed_ids:
                # Check if this is a new record (just created)
                # Check if the record is completely new and unsaved
                if not self.partner_company_id.id:
                    self.partner_company_id = False
                    self.partner_name = False
                    return {'warning': {
                        'title': 'Not Allowed',
                        'message': 'You are not allowed to create new companies. Please select an existing one.'
                    }}

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            p = self.partner_id
            self.partner_name = p.parent_id.name if p.parent_id else p.name
            self.contact_name = p.name if p.parent_id else ""
            self.function = p.function or ""
            self.email_from = p.email or ""
            self.phone = p.phone or ""
            self.city = p.city or ""
            self.state_id = p.state_id
            self.zip = p.zip or ""

    def _reopen(self, extra_context=None):
        ctx = dict(self.env.context)
        if extra_context:
            ctx.update(extra_context)
        return {
            "type": "ir.actions.act_window",
            "name": "Lead Creation",
            "res_model": "crm.lead.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }

    def action_next(self):
        # Validate current step
        if self.step == 1:
            self.e1_name = False
        elif self.step == 2:
            if not self.email_from and not self.phone and not self.x_mobile:
                self.e2_contact = True
                return self._reopen()
            self.e2_contact = False
            # Validate phone format (10 digits)
            if self.phone:
                digits = re.sub(r'\D', '', self.phone)
                if len(digits) != 10:
                    raise ValidationError(_("Phone number must be exactly 10 digits."))
            # Validate mobile format (10 digits)
            if self.x_mobile:
                digits = re.sub(r'\D', '', self.x_mobile)
                if len(digits) != 10:
                    raise ValidationError(_("Mobile number must be exactly 10 digits."))
            # Validate email format
            if self.email_from:
                if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', self.email_from):
                    raise ValidationError(_("Please enter a valid email address."))
        self.step += 1
        return self._reopen()

    def action_back(self):
        self.step -= 1
        return self._reopen()

    def action_goto_1(self):
        self.step = 1
        return self._reopen()

    def action_goto_2(self):
        if self.step > 2:
            self.step = 2
            return self._reopen()
        return self.action_next() if self.step == 1 else self._reopen()

    def action_goto_3(self):
        self.step = 3
        return self._reopen()
        self.step = 3
        return self._reopen()

    def action_goto_4(self):
        self.step = 4
        return self._reopen()

    def action_goto_5(self):
        self.step = 5
        return self._reopen()

    def action_save_lead(self):
        if not self.partner_name and not self.partner_company_id:
            raise ValidationError(_("Please enter a Company Name."))

        # Resolve the right partner_id to avoid Odoo creating duplicate companies later.
        # Priority: 1) contact picked from "Select Contact" dropdown
        #           2) existing company chosen in Step 1 (partner_company_id)
        #           3) existing customer explicitly chosen (partner_id)
        resolved_partner_id = False
        if self.contact_picker_id:
            resolved_partner_id = self.contact_picker_id.id
        elif self.partner_id:
            resolved_partner_id = self.partner_id.id
        elif self.partner_company_id:
            resolved_partner_id = self.partner_company_id.id

        vals = {
            "name": self.name or self.partner_name or "New Lead",
            "company_id": self.company_id.id,
            "x_customer_type": self.x_customer_type,
            "x_requirement_date": self.x_requirement_date,
            "user_id": self.user_id.id if self.user_id else False,
            "source_id": self.source_id.id if self.source_id else False,
            "partner_id": resolved_partner_id,
            "partner_name": self.partner_company_id.name if self.partner_company_id else self.partner_name,
            "contact_name": self.contact_name,
            "function": self.function,
            "email_from": self.email_from,
            "phone": self.phone,
            "x_mobile": self.x_mobile,
            "city": self.city,
            "state_id": self.state_id.id if self.state_id else False,
            "zip": self.zip,
            "x_product_category_ids": [(6, 0, self.x_product_category_ids.ids)],
            "x_purchase_timeline": self.x_purchase_timeline,
            "expected_revenue": self.expected_revenue,
            "probability": self.probability,
            "date_deadline": self.date_deadline,
            "x_assign_to_id": self.x_assign_to_id.id if self.x_assign_to_id else False,
            "user_id": self.x_assign_to_id.id if self.x_assign_to_id else (self.user_id.id if self.user_id else False),
            "x_original_owner_id": self.user_id.id if self.user_id else False,
            "description": self.description,
            "type": "opportunity",
            "x_created_by_id": self.created_by_id.id if self.created_by_id else False,
            "x_lead_priority": self.x_lead_priority or "medium",
        }
        lead = self.env["crm.lead"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "res_id": lead.id,
            "view_mode": "form",
            "target": "current",
        }
