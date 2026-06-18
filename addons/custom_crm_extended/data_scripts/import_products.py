# -*- coding: utf-8 -*-
import csv

CSV_PATH = '/home/crm/product_import_clean.csv'

existing_cats = {
    'Freezers': 26,
    'Oven': 27,
    'Water Bath': 9,
    'Services': 10,
}

Category = env['product.category'].sudo()

for new_cat_name in ['Bio Safety Cabinets', 'Water Purification System']:
    existing = Category.search([('name', '=', new_cat_name)], limit=1)
    if existing:
        existing_cats[new_cat_name] = existing.id
        print('Found existing category:', new_cat_name, '->', existing.id)
    else:
        new_cat = Category.create({'name': new_cat_name})
        existing_cats[new_cat_name] = new_cat.id
        print('Created category:', new_cat_name, '->', new_cat.id)

TAX_18_GST_ID = 26
UOM_UNITS_ID = 1

Product = env['product.template'].sudo()

created = 0
skipped = 0
errors = 0

with open(CSV_PATH, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ref_no = (row.get('ref_no') or '').strip()
        name = (row.get('name') or '').strip()
        category = (row.get('category') or '').strip()
        hsn_code = (row.get('hsn_code') or '').strip()
        try:
            rate = float(row.get('rate') or 0)
        except ValueError:
            rate = 0.0

        if not name:
            continue

        if ref_no:
            existing = Product.search([('default_code', '=', ref_no)], limit=1)
            if existing:
                skipped += 1
                continue

        categ_id = existing_cats.get(category)
        if not categ_id:
            print('WARNING: unknown category "%s" for product %s - skipping' % (category, ref_no))
            errors += 1
            continue

        is_service = (category == 'Services')

        vals = {
            'name': name,
            'default_code': ref_no or False,
            'categ_id': categ_id,
            'list_price': rate,
            'l10n_in_hsn_code': hsn_code or False,
            'uom_id': UOM_UNITS_ID,
            'sale_ok': True,
            'purchase_ok': True,
            'taxes_id': [(6, 0, [TAX_18_GST_ID])],
            'type': 'service' if is_service else 'consu',
        }

        try:
            Product.create(vals)
            created += 1
        except Exception as e:
            print('ERROR creating product %s (%s): %s' % (ref_no, name, e))
            errors += 1

env.cr.commit()
print('---')
print('Created:', created)
print('Skipped (already exists):', skipped)
print('Errors:', errors)
