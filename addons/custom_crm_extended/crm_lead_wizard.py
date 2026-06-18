# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class CrmLeadWizard(models.TransientModel):
    _name = "crm.lead.wizard"
    _description = "Lead Creation Wizard"

    step = fields.Integer(default=1)
    created_by_id = fields.Many2one("res.users", string="Created By",
        default=lambda self: self.env.user, readonly=True)

    # Step 1
    company_id = fields.Many2one("res.company", string="Our Company",
        default=lambda self: self.env.company)
    name = fields.Char(string="Lead Name")
    partner_name = fields.Char(string="Company Name")
    partner_company_id = fields.Many2one(
        'res.partner',
        string='Company Name',
        domain=[('is_company', '=', True)],
        context={'default_is_company': True},
    )
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

    # Validation flags - show red borders
    e1_name = fields.Boolean(default=False)       # step1: name missing
    e2_contact = fields.Boolean(default=False)    # step2: no contact method

    @api.onchange('partner_company_id')
    def _onchange_partner_company_id(self):
        if self.partner_company_id:
            self.partner_name = self.partner_company_id.name

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

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Lead Creation",
            "res_model": "crm.lead.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def action_next(self):
        # Validate current step
        if self.step == 1:
            self.e1_name = False
        elif self.step == 2:
            if not self.email_from and not self.phone and not self.x_mobile:
                self.e2_contact = True
                raise ValidationError(_("Please provide at least one: Email, Phone or Mobile."))
            self.e2_contact = False
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
        if not self.name and not self.partner_name:
            raise ValidationError(_("Please enter a Lead Name or Company Name."))
        vals = {
            "name": self.name or self.partner_name or "New Lead",
            "company_id": self.company_id.id,
            "x_customer_type": self.x_customer_type,
            "x_requirement_date": self.x_requirement_date,
            "user_id": self.user_id.id if self.user_id else False,
            "source_id": self.source_id.id if self.source_id else False,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "partner_name": self.partner_id.name if self.partner_id else self.partner_name,
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
