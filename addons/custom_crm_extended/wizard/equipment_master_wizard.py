# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class EquipmentMasterWizard(models.TransientModel):
    _name = "equipment.master.wizard"
    _description = "Equipment Master Creation Wizard"

    step = fields.Integer(string="Step", default=1)

    # Step 1: Equipment Info
    equipment_id  = fields.Char(string="Equipment Category")
    name = fields.Char(string="Equipment Name")
    category_id = fields.Char(string='Equipment ID')
    manufacturer = fields.Char(string="Manufacturer")
    model_number = fields.Char(string="Model Number")
    serial_number = fields.Char(string="Serial Number")
    part_number = fields.Char(string="Part Number")
    child_part_no = fields.Char(string="Child Part No")
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

    # Navigation Actions
    def action_next(self):
        self.ensure_one()
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

    def action_goto_2(self):
        self.ensure_one()
        self.step = 2
        return self._reopen_self()

    def action_goto_3(self):
        self.ensure_one()
        self.step = 3
        return self._reopen_self()

    def action_goto_4(self):
        self.ensure_one()
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
        equipment = self.env["equipment.master"].create({
            "equipment_id ": self.equipment_id ,
            "name": self.name,
            "category_id": self.category_id,
            "manufacturer": self.manufacturer,
            "model_number": self.model_number,
            "serial_number": self.serial_number,
            "part_number": self.part_number,
            "child_part_no": self.child_part_no,
            "equipment_status": self.equipment_status,
            "criticality": self.criticality,
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
            "last_preventive_maintenance": self.last_preventive_maintenance,
            "next_preventive_maintenance": self.next_preventive_maintenance,
            "last_breakdown_date": self.last_breakdown_date,
            "calibration_due_date": self.calibration_due_date,
            "running_status": self.running_status,
            "firmware_version": self.firmware_version,
            "accessories": self.accessories,
            "remarks": self.remarks,
        })
        return {
            "type": "ir.actions.act_window",
            "name": equipment.name,
            "res_model": "equipment.master",
            "res_id": equipment.id,
            "view_mode": "form",
            "target": "current",
        }
