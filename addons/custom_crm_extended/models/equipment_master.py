from lxml import etree
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class EquipmentCategory(models.Model):
    _name = 'equipment.category'
    _description = 'Equipment Category'

    name = fields.Char(string='Category Name', required=True)

class EquipmentMaster(models.Model):
    _name = 'equipment.master'
    _description = 'Equipment Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _sql_constraints = [
        ('equipment_id_uniq', 'unique(equipment_id)', 'The Equipment ID must be unique! This ID is already assigned to another equipment.'),
        ('serial_number_uniq', 'unique(serial_number)', 'The Serial Number must be unique! This Serial Number already exists in the system.'),
    ]

    # Step 1: Equipment Info
    equipment_id  = fields.Char(string='Equipment ID', required=True, tracking=True, readonly=True)
    name = fields.Many2one('product.template', string='Model Name', tracking=True)
    category_id = fields.Char(string='Equipment', tracking=True)
    manufacturer = fields.Char(string='Manufacturer', tracking=True)
    model_number = fields.Char(string='Equipment Owner', tracking=True)
    serial_number = fields.Char(string='Serial Number', tracking=True)
    part_number = fields.Char(string='Part Number', tracking=True)
    child_part_no = fields.Char(string='Child Part No', tracking=True)
    invoice_number = fields.Char(string='Invoice No', tracking=True)
    invoice_date = fields.Date(string='Invoice Date', tracking=True)
    equipment_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('under_repair', 'Under Repair'),
    ], string='Equipment Status', default='active', tracking=True)
    criticality = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], string='Criticality', default='medium', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, tracking=True)
    user_id = fields.Many2one('res.users', string='Assigned Responsible', default=lambda self: self.env.user, tracking=True)

    # Step 2: Location & Contact
    partner_id = fields.Many2one('res.partner', string='Customer Name', tracking=True)
    site_name = fields.Char(string='Site Name', tracking=True)
    building = fields.Char(string='Building', tracking=True)
    floor = fields.Char(string='Floor', tracking=True)
    department = fields.Char(string='Department', tracking=True)
    room_number = fields.Char(string='Room Number', tracking=True)
    address = fields.Text(string='Address')
    contact_person = fields.Char(string='Contact Person', tracking=True)
    contact_number = fields.Char(string='Contact Number', tracking=True)
    email = fields.Char(string='Email', tracking=True)

    # Step 3: Maintenance & Contract
    installation_date = fields.Date(string='Installation Date')
    warranty_start_date = fields.Date(string='Warranty Start Date')
    warranty_end_date = fields.Date(string='Warranty End Date')
    service_contract = fields.Selection([
        ('amc', 'AMC'),
        ('cmc', 'CMC'),
        ('warranty', 'Warranty'),
        ('none', 'None'),
    ], string='Service Contract', default='amc', tracking=True)
    last_preventive_maintenance = fields.Date(string='Last PM Date')
    next_preventive_maintenance = fields.Date(string='Next PM Date')
    last_breakdown_date = fields.Date(string='Last Breakdown Date')
    calibration_due_date = fields.Date(string='Calibration Due Date')
    running_status = fields.Selection([
        ('running', 'Running'),
        ('stopped', 'Stopped'),
    ], string='Current Running Status', default='running', tracking=True)

    # Step 4: Specs & Remarks
    firmware_version = fields.Char(string='Software/Firmware Version')
    accessories = fields.Text(string='Accessories')
    remarks = fields.Text(string='Remarks')

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            p = self.partner_id
            contact_name = ""
            contact_phone = ""
            contact_email = ""

            def get_phone(partner):
                if not partner:
                    return ""
                return getattr(partner, 'mobile', False) or getattr(partner, 'phone', False) or ""

            if p.is_company:
                primary_contact = p.child_ids.filtered(lambda c: c.type == 'contact')[:1]
                if primary_contact:
                    c = primary_contact[0]
                    contact_name = c.name or p.name or ""
                    contact_phone = get_phone(c) or get_phone(p)
                    contact_email = c.email or p.email or ""
                else:
                    contact_name = p.name or ""
                    contact_phone = get_phone(p)
                    contact_email = p.email or ""
            else:
                contact_name = p.name or ""
                contact_phone = get_phone(p) or get_phone(p.parent_id)
                contact_email = p.email or (p.parent_id.email if p.parent_id else False) or ""

            self.contact_person = contact_name
            self.contact_number = contact_phone
            self.email = contact_email

            # Format Address (Restored!)
            addr_parts = [p.street, p.street2, p.city, p.state_id.name if p.state_id else False, p.country_id.name if p.country_id else False, p.zip]
            self.address = ", ".join([str(a) for a in addr_parts if a])

            # Auto-fill location fields
            self.site_name = getattr(p, 'x_site_name', False) or (getattr(p.parent_id, 'x_site_name', False) if p.parent_id else "") or ""
            self.building = getattr(p, 'x_building', False) or ""
            self.floor = getattr(p, 'x_floor', False) or ""
            self.department = getattr(p, 'x_department', False) or p.function or ""
            self.room_number = getattr(p, 'x_room_number', False) or ""

    @api.depends('name', 'serial_number', 'equipment_id')
    def _compute_display_name(self):
        for rec in self:
            eq_name = rec.name.display_name if rec.name else (rec.equipment_id or '')
            if rec.serial_number:
                sn = str(rec.serial_number).strip()
                last6 = sn[-6:] if len(sn) >= 6 else sn
                rec.display_name = f"{eq_name} ...{last6}"
            else:
                rec.display_name = eq_name

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        domain = list(domain or [])
        if name:
            domain += ['|', '|', ('name.name', operator, name), ('serial_number', operator, name), ('equipment_id', operator, name)]
        records = self.search(domain, limit=limit)
        return [(r.id, r.display_name) for r in records]

    @api.constrains('equipment_id')
    def _check_unique_equipment_id(self):
        for rec in self:
            if rec.equipment_id:
                duplicate = self.search([
                    ('equipment_id', '=', rec.equipment_id.strip()),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("Equipment ID '%s' already exists! Please use a unique Equipment ID.") % rec.equipment_id)

    @api.constrains('serial_number')
    def _check_unique_serial_number(self):
        for rec in self:
            if rec.serial_number and rec.serial_number.strip():
                duplicate = self.search([
                    ('serial_number', '=', rec.serial_number.strip()),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("Serial Number '%s' already exists! Each equipment must have a unique Serial Number.") % rec.serial_number)

    @api.onchange('name')
    def _onchange_name(self):
        if self.name:
            self.category_id = self.name.categ_id.display_name if self.name.categ_id else ''
            self.manufacturer = getattr(self.name, 'x_make', '') or ''
            self.part_number = getattr(self.name, 'default_code', '') or ''
        else:
            self.category_id = ''
            self.manufacturer = ''
            self.part_number = ''

    def action_create_service_ticket(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Service Ticket'),
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_name': f"Service Ticket - {self.name.name if self.name else ''}",
                'default_partner_id': self.partner_id.id if self.partner_id else False,
            }
        }

    @api.model
    def _user_can(self, perm_name, default=False):
        user = self.env.user
        if user.has_group('base.group_system') or user.id in (2, 10, 11):
            return True
        if user.crm_job_id and hasattr(user.crm_job_id, perm_name):
            return bool(getattr(user.crm_job_id, perm_name))
        val = getattr(user, perm_name, None)
        return bool(val if val is not None else default)

    @api.model
    def get_views(self, views, options=None):
        res = super(EquipmentMaster, self).get_views(views, options=options)
        user = self.env.user
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
            can_create = self._user_can('perm_equipment_create', True)
            can_write = self._user_can('perm_equipment_write', True)
            can_delete = self._user_can('perm_equipment_unlink', False)

            for vtype in ['form', 'list', 'tree', 'kanban']:
                if vtype in res.get('views', {}):
                    arch_str = res['views'][vtype].get('arch')
                    if arch_str:
                        doc = etree.fromstring(arch_str)
                        if not can_create:
                            doc.attrib['create'] = 'false'
                        if not can_write:
                            doc.attrib['edit'] = 'false'
                        if not can_delete:
                            doc.attrib['delete'] = 'false'
                        res['views'][vtype]['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        user = self.env.user
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
            if operation == 'create' and not self._user_can('perm_equipment_create', True):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to create Equipment Master records."))
                return False
            if operation == 'write' and not self._user_can('perm_equipment_write', True):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to update Equipment Master records."))
                return False
            if operation == 'unlink' and not self._user_can('perm_equipment_unlink', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to delete Equipment Master records."))
                return False
        return super(EquipmentMaster, self).check_access_rights(operation, raise_exception=raise_exception)

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
            if not self._user_can('perm_equipment_create', True):
                raise UserError(_("Access Denied: You do not have permission to create Equipment Master records."))
        return super(EquipmentMaster, self).create(vals_list)

    def write(self, vals):
        user = self.env.user
        if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
            if not self._user_can('perm_equipment_write', True):
                raise UserError(_("Access Denied: You do not have permission to update Equipment Master records."))
        return super(EquipmentMaster, self).write(vals)

    def unlink(self):
        for rec in self:
            user = self.env.user
            if not user.has_group('base.group_system') and user.id not in (2, 10, 11):
                if not self._user_can('perm_equipment_unlink', False):
                    raise UserError(_("Access Denied: You do not have permission to delete Equipment Master records."))
        return super(EquipmentMaster, self).unlink()