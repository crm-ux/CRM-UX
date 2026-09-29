# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CrmProductStock(models.Model):
    _name = 'crm.product.stock'
    _description = 'Product Stock Registry'
    _order = 'last_updated_date desc, id desc'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        ondelete='cascade',
        index=True
    )
    safety_stock = fields.Float(
        string='Safety Stock',
        default=0.0,
        help='Minimum safety threshold. If quantity falls at or below this level, an alert signal will appear.'
    )
    quantity = fields.Float(
        string='Quantity',
        default=0.0,
        required=True
    )
    is_low_stock = fields.Boolean(
        string='Is Low Stock',
        compute='_compute_stock_alert',
        store=True
    )
    stock_alert_tooltip = fields.Char(
        string='Stock Alert Tooltip',
        compute='_compute_stock_alert',
        store=True
    )
    last_updated_date = fields.Datetime(
        string='Last Updated',
        default=fields.Datetime.now,
        readonly=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Updated By',
        default=lambda self: self.env.user,
        readonly=True
    )

    _sql_constraints = [
        ('product_unique', 'unique(product_id)', 'This product already exists in the stock registry! Please update its quantity instead.')
    ]

    @api.depends('quantity', 'safety_stock')
    def _compute_stock_alert(self):
        for rec in self:
            if rec.safety_stock > 0 and rec.quantity <= rec.safety_stock:
                rec.is_low_stock = True
                rec.stock_alert_tooltip = f"⚠️ Low Stock Alert: Current quantity ({rec.quantity:g}) is at or below safety stock ({rec.safety_stock:g})! Restocking recommended."
            else:
                rec.is_low_stock = False
                rec.stock_alert_tooltip = f"Healthy Stock: Current quantity ({rec.quantity:g}) is above safety stock ({rec.safety_stock:g})."

    def write(self, vals):
        if 'quantity' in vals or 'safety_stock' in vals:
            vals['last_updated_date'] = fields.Datetime.now()
            vals['user_id'] = self.env.user.id
        return super().write(vals)

    def action_update_stock_wizard(self):
        """Opens wizard to update stock for this specific record."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Update Stock',
            'res_model': 'crm.product.stock.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_id': self.product_id.id,
                'default_safety_stock': self.safety_stock,
                'default_quantity': self.quantity,
                'default_stock_id': self.id,
            }
        }


class CrmProductStockWizard(models.TransientModel):
    _name = 'crm.product.stock.wizard'
    _description = 'Update Product Stock Wizard'

    stock_id = fields.Many2one('crm.product.stock', string='Stock Record')
    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True
    )
    safety_stock = fields.Float(
        string='Safety Stock',
        default=0.0
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=0.0
    )

    def action_save_stock(self):
        self.ensure_one()
        Stock = self.env['crm.product.stock']
        existing = self.stock_id or Stock.search([('product_id', '=', self.product_id.id)], limit=1)
        vals = {
            'safety_stock': self.safety_stock,
            'quantity': self.quantity,
            'last_updated_date': fields.Datetime.now(),
            'user_id': self.env.user.id,
        }
        if existing:
            existing.write(vals)
        else:
            vals['product_id'] = self.product_id.id
            Stock.create(vals)
        return {'type': 'ir.actions.act_window_close'}
