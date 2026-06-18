# -*- coding: utf-8 -*-
from odoo import api, fields, models

class SaleOrderLineImage(models.Model):
    _name = "sale.order.line.image"
    _description = "Sale Order Line Image"

    order_line_id = fields.Many2one("sale.order.line", string="Order Line", ondelete="cascade")
    name = fields.Char(string="Image Name")
    image = fields.Binary(string="Image", required=True)
    sequence = fields.Integer(string="Sequence", default=10)


class SaleLineMediaWizard(models.TransientModel):
    _name = "sale.line.media.wizard"
    _description = "Add Images / Technical Specs to Order Lines"

    order_id = fields.Many2one("sale.order", string="Quotation", required=True)
    mode = fields.Selection([("image", "Images"), ("specs", "Technical Specs")], default="image")
    line_ids = fields.One2many("sale.line.media.wizard.line", "wizard_id", string="Lines")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order_id = self.env.context.get("default_order_id")
        mode = self.env.context.get("default_mode", "image")
        if order_id:
            order = self.env["sale.order"].browse(order_id)
            lines = []
            for line in order.order_line.filtered(lambda l: not l.display_type):
                lines.append((0, 0, {
                    "order_line_id": line.id,
                    "product_name": line.x_product_name or line.product_id.name or "",
                    "x_technical_specs": line.x_technical_specs or "",
                }))
            res.update({"order_id": order_id, "mode": mode, "line_ids": lines})
        return res

    def action_save(self):
        for wline in self.line_ids:
            wline.order_line_id.write({"x_technical_specs": wline.x_technical_specs})
            for img in wline.image_ids:
                existing = self.env["sale.order.line.image"].search([
                    ("order_line_id", "=", wline.order_line_id.id),
                    ("name", "=", img.name),
                ])
                if not existing:
                    self.env["sale.order.line.image"].create({
                        "order_line_id": wline.order_line_id.id,
                        "name": img.name or "Image",
                        "image": img.image,
                    })
        return {"type": "ir.actions.act_window_close"}


class SaleLineMediaWizardLine(models.TransientModel):
    _name = "sale.line.media.wizard.line"
    _description = "Sale Line Media Wizard Line"

    wizard_id = fields.Many2one("sale.line.media.wizard", string="Wizard")
    order_line_id = fields.Many2one("sale.order.line", string="Order Line")
    product_name = fields.Char(string="Product", readonly=True)
    image_ids = fields.One2many("sale.line.media.wizard.image", "wizard_line_id", string="Images")
    x_technical_specs = fields.Text(string="Technical Specifications")


class SaleLineMediaWizardImage(models.TransientModel):
    _name = "sale.line.media.wizard.image"
    _description = "Sale Line Media Wizard Image"

    wizard_line_id = fields.Many2one("sale.line.media.wizard.line", string="Wizard Line")
    name = fields.Char(string="Image Name")
    image = fields.Binary(string="Image", required=True)
