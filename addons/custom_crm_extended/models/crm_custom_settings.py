# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class CrmCustomSettings(models.Model):
    _name = 'crm.custom.settings'
    _description = 'CRM Custom Settings'


    name = fields.Char(string="Name", default="CRM Settings")
    # Expense Configuration Fields
    new_expense_type_name = fields.Char(string="New Expense Type")
    expense_type_ids = fields.Many2many(
        'service.ticket.expense.type',
        string="Expense Types",
        compute='_compute_expense_type_ids',
        readonly=False
    )

    def _compute_expense_type_ids(self):
        all_types = self.env['service.ticket.expense.type'].search([])
        for rec in self:
            rec.expense_type_ids = all_types

    def action_add_expense_type(self):
        self.ensure_one()
        if self.new_expense_type_name:
            name = self.new_expense_type_name.strip()
            if name:
                self.env['service.ticket.expense.type'].create({
                    'name': name,
                    'active': True,
                })
            self.new_expense_type_name = False
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    equipment_sequence_type = fields.Selection([
        ('equipment_id', 'Equipment ID'),
        ('serial_number', 'Equipment Serial Number'),
    ], string='Name', compute='_compute_equipment_sequence_type', inverse='_inverse_equipment_sequence_type', store=True, readonly=False)

    # Equipment Category linkage for Category-wise Equipment IDs
    equipment_category_id = fields.Many2one(
        'product.category', 
        string="Category", 
        ondelete='set null', 
        help="Assign this Equipment ID sequence to a specific category. Leave blank for default."
    )

    # Link Serial Number to Equipment ID
    linked_equipment_id_seq_id = fields.Many2one(
        'ir.sequence',
        string="Linked Equipment ID Series",
        domain="[('code', '=', 'crm.equipment.id')]",
        ondelete='set null',
        help="Select which Equipment ID series this Serial Number series belongs to."
    )

    @api.depends('name', 'prefix', 'equipment_category_id')
    def _compute_display_name(self):
        for rec in self:
            if rec.code in ('crm.equipment.id', 'crm.equipment.serial'):
                prefix_info = f" [Prefix: {rec.prefix}]" if rec.prefix else ""
                cat_info = f" ({rec.equipment_category_id.name})" if rec.equipment_category_id else ""
                rec.display_name = f"{rec.name or 'Sequence'}{prefix_info}{cat_info}"
            else:
                super(IrSequence, rec)._compute_display_name()

    @api.depends('code')
    def _compute_equipment_sequence_type(self):
        for rec in self:
            if rec.code == 'crm.equipment.id':
                rec.equipment_sequence_type = 'equipment_id'
            elif rec.code == 'crm.equipment.serial':
                rec.equipment_sequence_type = 'serial_number'
            else:
                rec.equipment_sequence_type = False

    def _inverse_equipment_sequence_type(self):
        for rec in self:
            if rec.equipment_sequence_type == 'equipment_id':
                rec.code = 'crm.equipment.id'
            elif rec.equipment_sequence_type == 'serial_number':
                rec.code = 'crm.equipment.serial'

    @api.onchange('equipment_sequence_type')
    def _onchange_equipment_sequence_type(self):
        if self.equipment_sequence_type == 'equipment_id':
            self.code = 'crm.equipment.id'
            self.name = 'Equipment ID'
        elif self.equipment_sequence_type == 'serial_number':
            self.code = 'crm.equipment.serial'
            self.name = 'Equipment Serial Number'
            self.equipment_category_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Force company_id = False for All Companies
            if vals.get('code') in ('crm.equipment.id', 'crm.equipment.serial', 'service.ticket'):
                vals['company_id'] = False

            if vals.get('equipment_sequence_type') == 'equipment_id':
                vals['code'] = 'crm.equipment.id'
                vals['name'] = 'Equipment ID'
            elif vals.get('equipment_sequence_type') == 'serial_number':
                vals['code'] = 'crm.equipment.serial'
                vals['name'] = 'Equipment Serial Number'
                vals['equipment_category_id'] = False
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            code = vals.get('code', record.code)
            if code in ('crm.equipment.id', 'crm.equipment.serial', 'service.ticket'):
                if 'company_id' in vals and vals['company_id']:
                    vals['company_id'] = False
        return super().write(vals)
