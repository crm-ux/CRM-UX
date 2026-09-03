# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class EquipmentMasterWizard(models.TransientModel):
    _name = "equipment.master.wizard"
    _description = "Equipment Master Creation Wizard"

    step = fields.Integer(string="Step", default=1)

    # Step 1: Equipment Info
    e1_id = fields.Boolean(default=False)
    equipment_id  = fields.Char(string="Equipment ID")
    name = fields.Many2one("product.template", string="Equipment Name")
    category_id = fields.Char(string='Equipment Category')
    manufacturer = fields.Char(string="Manufacturer")
    model_number = fields.Char(string="Model Number")
    serial_number = fields.Char(string="Serial Number")
    part_number = fields.Char(string="Part Number")
    child_part_no = fields.Char(string="Child Part No")
    invoice_number = fields.Char(string="Invoice No")
    invoice_date = fields.Date(string="Invoice Date")
    equipment_status = fields.Selection([
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("under_repair", "Under Repair"),
    ], string="Equipment Status", default="active")
    criticality = fields.Selection([
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ], string="Criticality", default="medium")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    # Step 2: Location & Contact    
    partner_id = fields.Many2one("res.partner", string="Customer Name")
    site_name = fields.Char(string="Site Name")
    building = fields.Char(string="Building")
    floor = fields.Char(string="Floor")
    department = fields.Char(string="Department")
    room_number = fields.Char(string="Room Number")
    address = fields.Text(string="Address")
    contact_person = fields.Char(string="Contact Person")
    contact_number = fields.Char(string="Contact Number")
    email = fields.Char(string="Email")

    # Step 3: Maintenance & Contract
    installation_date = fields.Date(string="Installation Date")
    warranty_start_date = fields.Date(string="Warranty Start Date")
    warranty_end_date = fields.Date(string="Warranty End Date")
    service_contract = fields.Selection([
        ("amc", "AMC"),
        ("cmc", "CMC"),
        ("warranty", "Warranty"),
        ("none", "None"),
    ], string="Service Contract", default="amc")
    last_preventive_maintenance = fields.Date(string="Last PM Date")
    next_preventive_maintenance = fields.Date(string="Next PM Date")
    last_breakdown_date = fields.Date(string="Last Breakdown Date")
    calibration_due_date = fields.Date(string="Calibration Due Date")
    running_status = fields.Selection([
        ("running", "Running"),
        ("stopped", "Stopped"),
    ], string="Current Running Status", default="running")

    # Step 4: Specs & Remarks
    firmware_version = fields.Char(string="Software/Firmware Version")
    accessories = fields.Text(string="Accessories")
    remarks = fields.Text(string="Remarks")

    @api.onchange('name')
    def _onchange_name(self):
        if self.name:
            self.category_id = self.name.categ_id.display_name if self.name.categ_id else ''
            self.manufacturer = getattr(self.name, 'x_make', '') or ''
        else:
            self.category_id = ''
            self.manufacturer = ''

    # Navigation Actions
    def action_next(self):
        self.ensure_one()
        if self.step == 1:
            if not self.equipment_id:
                raise ValidationError(_("Please enter Equipment ID before proceeding."))
            # Check unique Equipment ID
            dup_eq = self.env['equipment.master'].search([('equipment_id', '=', self.equipment_id.strip())], limit=1)
            if dup_eq:
                raise ValidationError(_("Equipment ID '%s' already exists! Please use a unique Equipment ID.") % self.equipment_id)
            # Check unique Serial Number
            if self.serial_number:
                dup_sn = self.env['equipment.master'].search([('serial_number', '=', self.serial_number.strip())], limit=1)
                if dup_sn:
                    raise ValidationError(_("Serial Number '%s' already exists! Each equipment must have a unique Serial Number.") % self.serial_number)

        if self.step < 4:
            self.step += 1
        return self._reopen_self()

    def action_back(self):
        self.ensure_one()
        if self.step > 1:
            self.step -= 1
        return self._reopen_self()

    def action_goto_1(self):
        self.ensure_one()
        self.step = 1
        return self._reopen_self()

    def _check_step_1_uniqueness(self):
        if not self.equipment_id:
            raise ValidationError(_("Please enter Equipment ID before proceeding."))
        dup_eq = self.env['equipment.master'].search([('equipment_id', '=', self.equipment_id.strip())], limit=1)
        if dup_eq:
            raise ValidationError(_("Equipment ID '%s' already exists! Please use a unique Equipment ID.") % self.equipment_id)
        if self.serial_number:
            dup_sn = self.env['equipment.master'].search([('serial_number', '=', self.serial_number.strip())], limit=1)
            if dup_sn:
                raise ValidationError(_("Serial Number '%s' already exists! Each equipment must have a unique Serial Number.") % self.serial_number)

    def action_goto_2(self):
        self.ensure_one()
        self._check_step_1_uniqueness()
        self.step = 2
        return self._reopen_self()

    def action_goto_3(self):
        self.ensure_one()
        self._check_step_1_uniqueness()
        self.step = 3
        return self._reopen_self()

    def action_goto_4(self):
        self.ensure_one()
        self._check_step_1_uniqueness()
        self.step = 4
        return self._reopen_self()

    def _reopen_self(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Equipment Master Creation"),
            "res_model": self._name,
            "res_id": self.id,
            "view_id": self.env.ref("custom_crm_extended.equipment_master_wizard_form").id,
            "view_mode": "form",
            "target": "new",
        }

    def action_save_equipment(self):
        self.ensure_one()
        if not self.equipment_id:
            raise ValidationError(_("Please enter Equipment ID before saving."))

        # Final uniqueness check
        dup_eq = self.env['equipment.master'].search([('equipment_id', '=', self.equipment_id.strip())], limit=1)
        if dup_eq:
            raise ValidationError(_("Equipment ID '%s' already exists! Please use a unique Equipment ID.") % self.equipment_id)
        if self.serial_number:
            dup_sn = self.env['equipment.master'].search([('serial_number', '=', self.serial_number.strip())], limit=1)
            if dup_sn:
                raise ValidationError(_("Serial Number '%s' already exists! Each equipment must have a unique Serial Number.") % self.serial_number)

        equipment = self.env["equipment.master"].create({
            "equipment_id": self.equipment_id,
            "name": self.name.id if self.name else False,
            "category_id": self.category_id,
            "manufacturer": self.manufacturer,
            "model_number": self.model_number,
            "serial_number": self.serial_number,
            "part_number": self.part_number,
            "child_part_no": self.child_part_no,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "equipment_status": self.equipment_status,
            "criticality": self.criticality,
            "company_id": self.company_id.id if self.company_id else False,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "site_name": self.site_name,
            "building": self.building,
            "floor": self.floor,
            "department": self.department,
            "room_number": self.room_number,
            "address": self.address,
            "contact_person": self.contact_person,
            "contact_number": self.contact_number,
            "email": self.email,
            "installation_date": self.installation_date,
            "warranty_start_date": self.warranty_start_date,
            "warranty_end_date": self.warranty_end_date,
            "service_contract": self.service_contract,
            "firmware_version": self.firmware_version,
            "accessories": self.accessories,
            "remarks": self.remarks,
        })

        # Increment settings counter for next equipment
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('crm.equipment_id_auto', 'True') == 'True':
            current_next = int(ICP.get_param('crm.equipment_id_next', 1))
            ICP.set_param('crm.equipment_id_next', str(current_next + 1))

        if ICP.get_param('crm.serial_number_auto', 'True') == 'True':
            current_next_sn = int(ICP.get_param('crm.serial_number_next', 1))
            ICP.set_param('crm.serial_number_next', str(current_next_sn + 1))

        return {
            "type": "ir.actions.act_window",
            "name": equipment.name,
            "res_model": "equipment.master",
            "res_id": equipment.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            p = self.partner_id
            
            # Fetch contact person, phone, email
            if p.is_company:
                primary_contact = p.child_ids.filtered(lambda c: c.type == 'contact')[:1]
                if primary_contact:
                    self.contact_person = primary_contact.name or ""
                    self.contact_number = primary_contact.phone or primary_contact.mobile or p.phone or p.mobile or ""
                    self.email = primary_contact.email or p.email or ""
                else:
                    self.contact_person = p.name or ""
                    self.contact_number = p.phone or p.mobile or ""
                    self.email = p.email or ""
            else:
                self.contact_person = p.name or ""
                self.contact_number = p.phone or p.mobile or ""
                self.email = p.email or ""

            # Format address
            addr_parts = [p.street, p.street2, p.city, p.state_id.name if p.state_id else False, p.country_id.name if p.country_id else False, p.zip]
            self.address = ", ".join([str(a) for a in addr_parts if a])

            # Auto-fill location fields
            self.site_name = getattr(p, 'x_site_name', False) or ""
            self.building = getattr(p, 'x_building', False) or ""
            self.floor = getattr(p, 'x_floor', False) or ""
            self.department = getattr(p, 'x_department', False) or p.function or ""
            self.room_number = getattr(p, 'x_room_number', False) or ""


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ICP = self.env['ir.config_parameter'].sudo()
        Equipment = self.env['equipment.master'].sudo()

        # 1. Collision-Free Equipment ID
        if ICP.get_param('crm.equipment_id_auto', 'True') == 'True':
            prefix = ICP.get_param('crm.equipment_id_prefix', 'EQ-')
            pad = int(ICP.get_param('crm.equipment_id_padding', 4))
            next_num = int(ICP.get_param('crm.equipment_id_next', 1))
            suffix = ICP.get_param('crm.equipment_id_suffix', '')

            gen_id = f"{prefix}{str(next_num).zfill(pad)}{suffix}"
            while Equipment.search_count([('equipment_id', '=', gen_id)]) > 0:
                next_num += 1
                gen_id = f"{prefix}{str(next_num).zfill(pad)}{suffix}"

            res['equipment_id'] = gen_id

        # 2. Collision-Free Serial Number
        if ICP.get_param('crm.serial_number_auto', 'True') == 'True':
            prefix = ICP.get_param('crm.serial_number_prefix', 'SN-')
            pad = int(ICP.get_param('crm.serial_number_padding', 4))
            next_num = int(ICP.get_param('crm.serial_number_next', 1))
            suffix = ICP.get_param('crm.serial_number_suffix', '')

            gen_sn = f"{prefix}{str(next_num).zfill(pad)}{suffix}"
            while Equipment.search_count([('serial_number', '=', gen_sn)]) > 0:
                next_num += 1
                gen_sn = f"{prefix}{str(next_num).zfill(pad)}{suffix}"

            res['serial_number'] = gen_sn

        return res
